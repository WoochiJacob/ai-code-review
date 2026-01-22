import os
import sqlite3
from datetime import datetime
from typing import Optional, Tuple

DB_PATH = os.path.join("data", "reviewer.db")


def get_conn() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


def init_db() -> None:
    with get_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS processed_pr (
                repo TEXT NOT NULL,
                pr_number INTEGER NOT NULL,
                head_sha TEXT NOT NULL,
                processed_at TEXT NOT NULL,
                PRIMARY KEY (repo, pr_number, head_sha)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS ai_comment (
                repo TEXT NOT NULL,
                pr_number INTEGER NOT NULL,
                comment_id INTEGER NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (repo, pr_number)
            )
            """
        )


def already_processed(repo: str, pr_number: int, head_sha: str) -> bool:
    with get_conn() as conn:
        cur = conn.execute(
            "SELECT 1 FROM processed_pr WHERE repo=? AND pr_number=? AND head_sha=? LIMIT 1",
            (repo, pr_number, head_sha),
        )
        return cur.fetchone() is not None


def mark_processed(repo: str, pr_number: int, head_sha: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO processed_pr(repo, pr_number, head_sha, processed_at) VALUES(?,?,?,?)",
            (repo, pr_number, head_sha, datetime.utcnow().isoformat()),
        )


def get_saved_comment_id(repo: str, pr_number: int) -> Optional[int]:
    with get_conn() as conn:
        cur = conn.execute(
            "SELECT comment_id FROM ai_comment WHERE repo=? AND pr_number=?",
            (repo, pr_number),
        )
        row = cur.fetchone()
        return int(row[0]) if row else None


def save_comment_id(repo: str, pr_number: int, comment_id: int) -> None:
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO ai_comment(repo, pr_number, comment_id, updated_at)
            VALUES(?,?,?,?)
            ON CONFLICT(repo, pr_number)
            DO UPDATE SET comment_id=excluded.comment_id, updated_at=excluded.updated_at
            """,
            (repo, pr_number, comment_id, datetime.utcnow().isoformat()),
        )
