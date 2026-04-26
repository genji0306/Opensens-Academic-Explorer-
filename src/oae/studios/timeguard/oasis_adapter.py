"""Adapters for CAMEL-AI OASIS SQLite simulation outputs.

The adapter treats OASIS content as synthetic idea-harvest only. It converts
posts, comments, and trace payloads into frontier claims for Timeguard's
duplicate-route filter, but never upgrades them to mathematical evidence.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path
import sqlite3
from typing import Any


def load_oasis_claim_rows(db_paths: tuple[str | Path, ...]) -> tuple[dict[str, str], ...]:
    rows: list[dict[str, str]] = []
    for locator in db_paths:
        db_path = Path(locator).resolve()
        if not db_path.exists():
            continue
        rows.extend(_load_single_db(db_path))
    return tuple(rows)


def _load_single_db(db_path: Path) -> list[dict[str, str]]:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        tables = _table_names(conn)
        users = _user_map(conn) if "user" in tables else {}
        rows: list[dict[str, str]] = []
        if "post" in tables:
            rows.extend(_post_rows(conn, db_path, users))
        if "comment" in tables:
            rows.extend(_comment_rows(conn, db_path, users))
        if "trace" in tables:
            rows.extend(_trace_rows(conn, db_path, users))
        return rows
    finally:
        conn.close()


def _table_names(conn: sqlite3.Connection) -> set[str]:
    cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    return {str(row[0]) for row in cursor.fetchall()}


def _user_map(conn: sqlite3.Connection) -> dict[int, str]:
    cursor = conn.execute("SELECT user_id, COALESCE(user_name, name, '') AS label FROM user")
    return {
        int(row["user_id"]): str(row["label"] or f"user-{row['user_id']}")
        for row in cursor.fetchall()
    }


def _post_rows(conn: sqlite3.Connection, db_path: Path, users: dict[int, str]) -> list[dict[str, str]]:
    cursor = conn.execute(
        """
        SELECT post_id, user_id, content, quote_content, created_at,
               num_likes, num_dislikes, num_shares
        FROM post
        ORDER BY created_at, post_id
        """
    )
    rows: list[dict[str, str]] = []
    for row in cursor.fetchall():
        content = " ".join(
            part.strip()
            for part in (str(row["content"] or ""), str(row["quote_content"] or ""))
            if part and part.strip()
        )
        if len(content) < 24:
            continue
        user_label = users.get(int(row["user_id"] or 0), f"user-{row['user_id']}")
        meta = (
            f"likes={int(row['num_likes'] or 0)}, "
            f"dislikes={int(row['num_dislikes'] or 0)}, "
            f"shares={int(row['num_shares'] or 0)}"
        )
        rows.append(
            {
                "source_locator": f"{db_path}#post:{row['post_id']}",
                "source_title": f"OASIS Reddit post {row['post_id']} by {user_label}",
                "source_kind": "oasis_reddit_post",
                "claim_text": f"{content} [{meta}]",
            }
        )
    return rows


def _comment_rows(conn: sqlite3.Connection, db_path: Path, users: dict[int, str]) -> list[dict[str, str]]:
    cursor = conn.execute(
        """
        SELECT comment_id, post_id, user_id, content, created_at,
               num_likes, num_dislikes
        FROM comment
        ORDER BY created_at, comment_id
        """
    )
    rows: list[dict[str, str]] = []
    for row in cursor.fetchall():
        content = str(row["content"] or "").strip()
        if len(content) < 24:
            continue
        user_label = users.get(int(row["user_id"] or 0), f"user-{row['user_id']}")
        meta = f"post_id={row['post_id']}, likes={int(row['num_likes'] or 0)}, dislikes={int(row['num_dislikes'] or 0)}"
        rows.append(
            {
                "source_locator": f"{db_path}#comment:{row['comment_id']}",
                "source_title": f"OASIS Reddit comment {row['comment_id']} by {user_label}",
                "source_kind": "oasis_reddit_comment",
                "claim_text": f"{content} [{meta}]",
            }
        )
    return rows


def _trace_rows(conn: sqlite3.Connection, db_path: Path, users: dict[int, str]) -> list[dict[str, str]]:
    cursor = conn.execute(
        """
        SELECT user_id, created_at, action, info
        FROM trace
        ORDER BY created_at
        """
    )
    rows: list[dict[str, str]] = []
    for row in cursor.fetchall():
        action = str(row["action"] or "").strip()
        payload = _parse_trace_info(str(row["info"] or ""))
        claim_text = _trace_claim_text(action, payload)
        if len(claim_text) < 24:
            continue
        user_label = users.get(int(row["user_id"] or 0), f"user-{row['user_id']}")
        rows.append(
            {
                "source_locator": f"{db_path}#trace:{row['created_at']}:{action}",
                "source_title": f"OASIS trace {action} by {user_label}",
                "source_kind": "oasis_trace",
                "claim_text": claim_text,
            }
        )
    return rows


def _parse_trace_info(value: str) -> Any:
    text = value.strip()
    if not text:
        return {}
    for loader in (json.loads, ast.literal_eval):
        try:
            return loader(text)
        except Exception:
            continue
    return {"raw": text}


def _trace_claim_text(action: str, payload: Any) -> str:
    if isinstance(payload, dict):
        for key in ("content", "query", "keyword", "reason", "summary", "prompt", "message", "raw"):
            value = str(payload.get(key) or "").strip()
            if len(value) >= 24:
                return f"{value} [trace action={action}]"
        flattened = "; ".join(
            f"{key}={value}" for key, value in payload.items()
            if isinstance(value, (str, int, float)) and str(value).strip()
        )
        if len(flattened) >= 24:
            return f"{flattened} [trace action={action}]"
    if isinstance(payload, list):
        flattened = " ".join(str(item).strip() for item in payload if str(item).strip())
        if len(flattened) >= 24:
            return f"{flattened} [trace action={action}]"
    if isinstance(payload, str):
        text = payload.strip()
        if len(text) >= 24:
            return f"{text} [trace action={action}]"
    return ""
