"""
Agent status monitor for Agent V.

Scans the ``data/`` directory tree to determine the last-active
timestamps, file counts, and operational state of each agent in the
multi-agent crystal prediction system.
"""

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from agent_v.config import (
    DATA_DIR,
    PREDICTIONS_WATCH_DIR,
    REFINEMENTS_DIR,
    REPORTS_DIR,
    SYNTHETIC_DIR,
)

logger = logging.getLogger("AgentV.Monitors.AgentStatus")


# ---------------------------------------------------------------------------
# Watched directories per logical agent
# ---------------------------------------------------------------------------
_AGENT_DIRS: dict[str, list[Path]] = {
    "Agent CB (Crystal Builder)": [
        SYNTHETIC_DIR,
        DATA_DIR / "crystal_patterns",
    ],
    "Agent PB (Property Predictor)": [
        PREDICTIONS_WATCH_DIR / "agent_pb",
    ],
    "Agent XC (XRD Crystallographer)": [
        PREDICTIONS_WATCH_DIR / "agent_xc",
    ],
    "Convergence Loop": [
        REFINEMENTS_DIR,
        REPORTS_DIR,
    ],
}


def _newest_mtime_in(directory: Path) -> Optional[float]:
    """Return the newest file modification time under *directory*,
    or ``None`` if the directory is empty / missing."""
    if not directory.is_dir():
        return None
    newest: Optional[float] = None
    try:
        for entry in directory.iterdir():
            if entry.name.startswith("."):
                continue
            try:
                mt = entry.stat().st_mtime
            except OSError:
                continue
            if newest is None or mt > newest:
                newest = mt
            # Recurse one level into subdirectories
            if entry.is_dir():
                for child in entry.iterdir():
                    if child.name.startswith("."):
                        continue
                    try:
                        cmt = child.stat().st_mtime
                    except OSError:
                        continue
                    if newest is None or cmt > newest:
                        newest = cmt
    except PermissionError:
        pass
    return newest


def _count_files_in(directory: Path, extensions: Optional[set[str]] = None) -> int:
    """Count non-hidden files (optionally filtered by extension)."""
    if not directory.is_dir():
        return 0
    count = 0
    try:
        for entry in directory.rglob("*"):
            if entry.is_file() and not entry.name.startswith("."):
                if extensions is None or entry.suffix.lower() in extensions:
                    count += 1
    except PermissionError:
        pass
    return count


def _state_label(last_active_ts: Optional[float], stale_seconds: float = 300.0) -> str:
    """Derive a human-readable state from the last-active timestamp.

    - ``"active"``   — file changed within *stale_seconds* of now
    - ``"idle"``     — file exists but older than *stale_seconds*
    - ``"no data"``  — no files found
    """
    if last_active_ts is None:
        return "no data"
    age = datetime.now(timezone.utc).timestamp() - last_active_ts
    if age < stale_seconds:
        return "active"
    return "idle"


class AgentStatusMonitor:
    """Query the file-system to infer agent activity states."""

    def __init__(
        self,
        agent_dirs: Optional[dict[str, list[Path]]] = None,
        stale_seconds: float = 300.0,
    ) -> None:
        """
        Parameters
        ----------
        agent_dirs : dict or None
            Override the default directory mapping.
        stale_seconds : float
            Seconds after which an agent is considered ``"idle"``.
        """
        self._agent_dirs = agent_dirs or _AGENT_DIRS
        self._stale = stale_seconds

    # ------------------------------------------------------------------ #
    # get_agent_states
    # ------------------------------------------------------------------ #

    def get_agent_states(self) -> dict[str, dict[str, Any]]:
        """Scan data directories and return a status dict per agent.

        Returns
        -------
        dict[str, dict]
            Keyed by agent name.  Each value contains:

            - ``state``  : ``"active"`` | ``"idle"`` | ``"no data"``
            - ``last_active`` : ISO-8601 string or ``None``
            - ``seconds_ago`` : float or ``None``
            - ``file_count``  : int — total files across watched dirs
            - ``directories`` : list[str] — resolved paths watched
        """
        results: dict[str, dict[str, Any]] = {}

        now_ts = datetime.now(timezone.utc).timestamp()

        for agent_name, dirs in self._agent_dirs.items():
            newest_ts: Optional[float] = None
            total_files = 0
            resolved_dirs: list[str] = []

            for d in dirs:
                resolved_dirs.append(str(d))
                mt = _newest_mtime_in(d)
                if mt is not None and (newest_ts is None or mt > newest_ts):
                    newest_ts = mt
                total_files += _count_files_in(d)

            if newest_ts is not None:
                last_active_iso = datetime.fromtimestamp(
                    newest_ts, tz=timezone.utc
                ).isoformat()
                seconds_ago = round(now_ts - newest_ts, 1)
            else:
                last_active_iso = None
                seconds_ago = None

            results[agent_name] = {
                "state": _state_label(newest_ts, self._stale),
                "last_active": last_active_iso,
                "seconds_ago": seconds_ago,
                "file_count": total_files,
                "directories": resolved_dirs,
            }

        logger.debug("Agent states: %s", {k: v["state"] for k, v in results.items()})
        return results
