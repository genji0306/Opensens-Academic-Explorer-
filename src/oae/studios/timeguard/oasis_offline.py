"""Deterministic no-key OASIS-style Reddit simulation for Timeguard.

This path writes a SQLite database shaped like the OASIS Reddit schema so the
existing OASIS adapter and review flow can operate without a live model key.
It is intentionally deterministic and frontier-constrained.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sqlite3
from typing import Any

from src.oae.studios.timeguard.schemas import OasisOfflineSimulationReport


def run_oasis_frontier_offline(
    *,
    manifest_path: str | Path,
    output_dir: str | Path | None = None,
    cycles: int = 2,
) -> tuple[OasisOfflineSimulationReport, dict[str, str] | None]:
    manifest = _load_manifest(manifest_path)
    profiles = json.loads(Path(manifest["profiles_path"]).read_text(encoding="utf-8"))
    target_dir = (
        Path(output_dir).resolve()
        if output_dir is not None
        else Path(manifest_path).resolve().parent / "oasis_frontier_offline_run"
    )
    target_dir.mkdir(parents=True, exist_ok=True)
    db_path = target_dir / "oasis_frontier_simulation.db"
    report_path = target_dir / "oasis_offline_simulation_report.md"

    result = _write_simulation_db(
        db_path=db_path,
        manifest=manifest,
        profiles=profiles,
        cycles=max(1, cycles),
    )
    report = OasisOfflineSimulationReport(
        generated_at=datetime.now(timezone.utc).isoformat(),
        manifest_path=str(Path(manifest_path).resolve()),
        db_path=str(db_path),
        profile_count=len(profiles),
        post_count=result["post_count"],
        comment_count=result["comment_count"],
        trace_count=result["trace_count"],
        warnings=(
            "This is a deterministic no-key simulation. Treat it as synthetic idea generation, not as mathematical evidence.",
        ),
        evidence_refs=(
            str(Path(manifest_path).resolve()),
            str(db_path),
        ),
    )
    report_path.write_text(_render_report(report, manifest), encoding="utf-8")
    outputs = {
        "db": str(db_path),
        "report": str(report_path),
    }
    return report, outputs


def _load_manifest(path: str | Path) -> dict[str, Any]:
    manifest_path = Path(path).resolve()
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    required = ("profiles_path", "seed_posts", "seed_packs")
    missing = [key for key in required if key not in payload]
    if missing:
        raise ValueError(
            f"OASIS frontier manifest is missing required fields: {', '.join(missing)}"
        )
    return payload


def _write_simulation_db(
    *,
    db_path: Path,
    manifest: dict[str, Any],
    profiles: list[dict[str, Any]],
    cycles: int,
) -> dict[str, int]:
    if db_path.exists():
        db_path.unlink()
    conn = sqlite3.connect(str(db_path))
    try:
        conn.executescript(_schema_sql())
        post_count = 0
        comment_count = 0
        trace_count = 0
        base_time = datetime.now(timezone.utc).replace(microsecond=0)

        for index, profile in enumerate(profiles, start=1):
            conn.execute(
                """
                INSERT INTO user (
                    user_id, agent_id, user_name, name, bio, created_at,
                    num_followings, num_followers
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    index,
                    index,
                    profile["username"],
                    profile["realname"],
                    profile["bio"],
                    (base_time + timedelta(minutes=index)).isoformat(),
                    0,
                    max(1, len(profiles) - index),
                ),
            )

        seed_posts = tuple(manifest.get("seed_posts", ()))
        seed_packs = tuple(manifest.get("seed_packs", ()))
        current_frontier = tuple(manifest.get("current_frontier", ()))
        taboo_routes = tuple(manifest.get("taboo_routes", ()))
        closed_routes = tuple(manifest.get("closed_routes", ()))
        current_work = tuple(manifest.get("current_work_packages", ()))

        generated_post_ids: list[int] = []
        for index, seed in enumerate(seed_posts, start=1):
            user_id = ((index - 1) % max(1, len(profiles))) + 1
            cursor = conn.execute(
                """
                INSERT INTO post (
                    user_id, original_post_id, content, quote_content, created_at,
                    num_likes, num_dislikes, num_shares, num_reports
                ) VALUES (?, NULL, ?, NULL, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    _normalize(seed),
                    (base_time + timedelta(minutes=10 + index)).isoformat(),
                    2 + index,
                    0,
                    1,
                    0,
                ),
            )
            generated_post_ids.append(int(cursor.lastrowid))
            post_count += 1

        for index, profile in enumerate(profiles, start=1):
            pack = seed_packs[(index - 1) % max(1, len(seed_packs))] if seed_packs else {}
            route_family = str(pack.get("route_family") or "meta_research")
            proof_object = str(pack.get("proof_object") or "Need a concrete proof object.")
            focus = str(
                profile.get("seed_focus")
                or (
                    current_frontier[(index - 1) % len(current_frontier)]
                    if current_frontier
                    else "frontier audit"
                )
            )
            taboo = taboo_routes[(index - 1) % max(1, len(taboo_routes))] if taboo_routes else "Avoid replaying closed routes."
            closed = closed_routes[(index - 1) % max(1, len(closed_routes))] if closed_routes else "The current map already closed multiple dead branches."
            work_item = current_work[(index - 1) % max(1, len(current_work))] if current_work else "frontier audit"
            content = _normalize(
                f"{profile['username']} as {profile.get('debate_role', 'participant')} proposes a {route_family} branch. "
                f"Focus: {focus}. Current work anchor: {work_item}. "
                f"Proof object: {proof_object} "
                f"This is not another replay because the campaign already established: {closed} "
                f"Constraint: {taboo}"
            )
            cursor = conn.execute(
                """
                INSERT INTO post (
                    user_id, original_post_id, content, quote_content, created_at,
                    num_likes, num_dislikes, num_shares, num_reports
                ) VALUES (?, NULL, ?, NULL, ?, ?, ?, ?, ?)
                """,
                (
                    index,
                    content,
                    (base_time + timedelta(minutes=30 + index)).isoformat(),
                    3 + (index % 5),
                    0,
                    index % 3,
                    0,
                ),
            )
            generated_post_ids.append(int(cursor.lastrowid))
            post_count += 1

        for cycle in range(cycles):
            for index, profile in enumerate(profiles, start=1):
                target_post_id = generated_post_ids[(index + cycle) % len(generated_post_ids)]
                pack = seed_packs[(index + cycle) % max(1, len(seed_packs))] if seed_packs else {}
                taboo = taboo_routes[(index + cycle) % max(1, len(taboo_routes))] if taboo_routes else "Avoid replaying closed routes."
                frontier = current_frontier[(index + cycle) % max(1, len(current_frontier))] if current_frontier else "frontier audit"
                content = _normalize(
                    f"{profile['username']} comments from the {profile.get('debate_role', 'participant')} role: "
                    f"keep the frontier on {frontier}. "
                    f"Pack under review: {pack.get('name', 'none')}. "
                    f"Do not regress into {taboo}. "
                    f"The next useful artifact must be exclusion-grade rather than another finite-data or equivalence-wall replay."
                )
                conn.execute(
                    """
                    INSERT INTO comment (
                        post_id, user_id, content, created_at, num_likes, num_dislikes
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        target_post_id,
                        index,
                        content,
                        (base_time + timedelta(hours=1, minutes=cycle * len(profiles) + index)).isoformat(),
                        1 + ((index + cycle) % 4),
                        0,
                    ),
                )
                comment_count += 1

        for index, profile in enumerate(profiles, start=1):
            pack = seed_packs[(index - 1) % max(1, len(seed_packs))] if seed_packs else {}
            frontier = current_frontier[(index - 1) % max(1, len(current_frontier))] if current_frontier else "frontier audit"
            payload = {
                "summary": _normalize(
                    f"{profile['username']} synthesizes the current RH frontier as {frontier}. "
                    f"Preferred route family: {pack.get('route_family', 'meta_research')}. "
                    f"Proof object: {pack.get('proof_object', 'none')}."
                ),
                "reason": _normalize(
                    f"Reject closed routes and keep only what remains after the current map. "
                    f"Focus on {profile.get('seed_focus', frontier)}."
                ),
                "prompt": _normalize(
                    f"What has been done, what remains, what to avoid. "
                    f"Work package anchor: {current_work[(index - 1) % max(1, len(current_work))] if current_work else 'frontier audit'}."
                ),
            }
            conn.execute(
                """
                INSERT INTO trace (user_id, created_at, action, info)
                VALUES (?, ?, ?, ?)
                """,
                (
                    index,
                    (base_time + timedelta(hours=2, minutes=index)).isoformat(),
                    "frontier_reflection",
                    json.dumps(payload),
                ),
            )
            trace_count += 1

        conn.commit()
        return {
            "post_count": post_count,
            "comment_count": comment_count,
            "trace_count": trace_count,
        }
    finally:
        conn.close()


def _schema_sql() -> str:
    return """
    CREATE TABLE user (
        user_id INTEGER PRIMARY KEY AUTOINCREMENT,
        agent_id INTEGER,
        user_name TEXT,
        name TEXT,
        bio TEXT,
        created_at DATETIME,
        num_followings INTEGER DEFAULT 0,
        num_followers INTEGER DEFAULT 0
    );
    CREATE TABLE post (
        post_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        original_post_id INTEGER,
        content TEXT DEFAULT '',
        quote_content TEXT,
        created_at DATETIME,
        num_likes INTEGER DEFAULT 0,
        num_dislikes INTEGER DEFAULT 0,
        num_shares INTEGER DEFAULT 0,
        num_reports INTEGER DEFAULT 0,
        FOREIGN KEY(user_id) REFERENCES user(user_id),
        FOREIGN KEY(original_post_id) REFERENCES post(post_id)
    );
    CREATE TABLE comment (
        comment_id INTEGER PRIMARY KEY AUTOINCREMENT,
        post_id INTEGER,
        user_id INTEGER,
        content TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        num_likes INTEGER DEFAULT 0,
        num_dislikes INTEGER DEFAULT 0,
        FOREIGN KEY(post_id) REFERENCES post(post_id),
        FOREIGN KEY(user_id) REFERENCES user(user_id)
    );
    CREATE TABLE trace (
        user_id INTEGER,
        created_at DATETIME,
        action TEXT,
        info TEXT,
        PRIMARY KEY(user_id, created_at, action, info),
        FOREIGN KEY(user_id) REFERENCES user(user_id)
    );
    """


def _render_report(report: OasisOfflineSimulationReport, manifest: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# OASIS Offline Simulation",
            "",
            f"Generated: {report.generated_at}",
            f"Manifest: {report.manifest_path}",
            f"Database: {report.db_path}",
            "",
            "## Summary",
            "",
            f"- Profiles: {report.profile_count}",
            f"- Posts: {report.post_count}",
            f"- Comments: {report.comment_count}",
            f"- Traces: {report.trace_count}",
            f"- Topic: {manifest.get('simulation_topic', 'n/a')}",
            "",
            "## Warnings",
            "",
            *[f"- {item}" for item in report.warnings],
            "",
        ]
    )


def _normalize(value: str) -> str:
    return " ".join(str(value).split())
