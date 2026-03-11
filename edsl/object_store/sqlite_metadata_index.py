"""SQLite implementation of :class:`MetadataIndex`.

Uses only the Python standard library (``sqlite3``).
"""

from __future__ import annotations

import json
import secrets
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


class _ThreadSafeConnection:
    """Thin wrapper around a sqlite3 Connection that serializes all access."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn
        self._lock = threading.Lock()

    def execute(self, sql, params=()):
        with self._lock:
            return self._conn.execute(sql, params)

    def executescript(self, sql):
        with self._lock:
            return self._conn.executescript(sql)

    def commit(self):
        with self._lock:
            self._conn.commit()

    def close(self):
        with self._lock:
            self._conn.close()

    @property
    def row_factory(self):
        return self._conn.row_factory

    @row_factory.setter
    def row_factory(self, value):
        self._conn.row_factory = value


class SQLiteMetadataIndex:
    """MetadataIndex backed by a single SQLite database.

    The database is stored at *db_path* (e.g. ``~/.edsl_objects/index.db``).

    Examples:
        >>> import tempfile, os
        >>> db = os.path.join(tempfile.mkdtemp(), "index.db")
        >>> idx = SQLiteMetadataIndex(db)
        >>> idx.put("u1", {"type": "AgentList", "description": "test", "created": "t0", "last_modified": "t0"})
        >>> idx.get("u1")["type"]
        'AgentList'
        >>> len(idx.list_all())
        1
        >>> idx.put_commit("u1", "abc", {"parent": None, "tree": "t1", "timestamp": "t0", "message": "first", "branch": "main"})
        >>> len(idx.log("u1"))
        1
        >>> idx.delete("u1")
        >>> idx.list_all()
        []
        >>> idx.log("u1")
        []
    """

    def __init__(self, db_path: str | Path) -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        raw = sqlite3.connect(str(self._db_path), check_same_thread=False)
        raw.row_factory = sqlite3.Row
        self._conn = _ThreadSafeConnection(raw)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS objects (
                uuid          TEXT PRIMARY KEY,
                type          TEXT NOT NULL,
                description   TEXT DEFAULT '',
                created       TEXT NOT NULL,
                last_modified TEXT NOT NULL,
                owner         TEXT,
                title         TEXT DEFAULT '',
                alias         TEXT,
                visibility    TEXT DEFAULT 'private'
            );

            CREATE INDEX IF NOT EXISTS idx_objects_type
                ON objects(type);
            CREATE INDEX IF NOT EXISTS idx_objects_owner
                ON objects(owner);
            CREATE UNIQUE INDEX IF NOT EXISTS idx_objects_owner_alias
                ON objects(owner, alias) WHERE alias IS NOT NULL;

            CREATE TABLE IF NOT EXISTS commits (
                hash      TEXT NOT NULL,
                uuid      TEXT NOT NULL,
                parent    TEXT,
                tree      TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                message   TEXT DEFAULT '',
                branch    TEXT NOT NULL,
                PRIMARY KEY (uuid, hash),
                FOREIGN KEY (uuid) REFERENCES objects(uuid) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_commits_uuid
                ON commits(uuid);
            CREATE INDEX IF NOT EXISTS idx_commits_branch
                ON commits(uuid, branch);

            CREATE TABLE IF NOT EXISTS users (
                username  TEXT PRIMARY KEY,
                created   TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS tokens (
                token     TEXT PRIMARY KEY,
                username  TEXT NOT NULL,
                created   TEXT NOT NULL,
                FOREIGN KEY (username) REFERENCES users(username) ON DELETE CASCADE
            );
            """
        )
        self._conn.commit()

    # ------------------------------------------------------------------
    # Migration: import existing meta.json files on first access
    # ------------------------------------------------------------------

    def migrate_from_directory(self, store_root: Path) -> int:
        """One-time import of existing ``meta.json`` files into SQLite.

        Returns the number of objects imported.  Skips if the table is
        already populated.
        """
        count = self._conn.execute("SELECT COUNT(*) FROM objects").fetchone()[0]
        if count > 0:
            return 0

        imported = 0
        for meta_path in store_root.glob("*/meta.json"):
            try:
                meta = json.loads(meta_path.read_text())
                uuid = meta_path.parent.name
                self.put(
                    uuid,
                    {
                        "type": meta.get("type", ""),
                        "description": meta.get("description", ""),
                        "created": meta.get("created", ""),
                        "last_modified": meta.get("last_modified", ""),
                    },
                )
                imported += 1
            except Exception:
                continue
        return imported

    # ------------------------------------------------------------------
    # Object metadata
    # ------------------------------------------------------------------

    def put(self, uuid: str, meta: dict, owner: Optional[str] = None) -> None:
        self._conn.execute(
            """INSERT INTO objects (uuid, type, description, created, last_modified, owner,
                                   title, alias, visibility)
               VALUES (:uuid, :type, :description, :created, :last_modified, :owner,
                       :title, :alias, :visibility)
               ON CONFLICT(uuid) DO UPDATE SET
                   description = COALESCE(excluded.description, objects.description),
                   last_modified = excluded.last_modified,
                   title = COALESCE(excluded.title, objects.title),
                   alias = COALESCE(excluded.alias, objects.alias),
                   visibility = COALESCE(excluded.visibility, objects.visibility)""",
            {
                "uuid": uuid,
                "owner": owner,
                "type": meta.get("type", ""),
                "description": meta.get("description", ""),
                "created": meta.get("created", ""),
                "last_modified": meta.get("last_modified", ""),
                "title": meta.get("title"),
                "alias": meta.get("alias"),
                "visibility": meta.get("visibility", "private"),
            },
        )
        self._conn.commit()

    def get(self, uuid: str) -> Optional[dict]:
        row = self._conn.execute(
            "SELECT * FROM objects WHERE uuid = ?", (uuid,)
        ).fetchone()
        return dict(row) if row else None

    def delete(self, uuid: str) -> None:
        self._conn.execute("DELETE FROM objects WHERE uuid = ?", (uuid,))
        self._conn.commit()

    def list_all(self, owner: Optional[str] = None) -> list[dict]:
        if owner:
            rows = self._conn.execute(
                "SELECT * FROM objects WHERE owner = ? ORDER BY last_modified DESC",
                (owner,),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM objects ORDER BY last_modified DESC"
            ).fetchall()
        return [dict(r) for r in rows]

    def search(
        self,
        type_name: Optional[str] = None,
        query: Optional[str] = None,
        owner: Optional[str] = None,
        visibility: Optional[str] = None,
        alias: Optional[str] = None,
    ) -> list[dict]:
        clauses: list[str] = []
        params: list = []
        if type_name:
            clauses.append("type = ?")
            params.append(type_name)
        if query:
            clauses.append("(description LIKE ? OR title LIKE ?)")
            params.extend([f"%{query}%", f"%{query}%"])
        if owner:
            clauses.append("owner = ?")
            params.append(owner)
        if visibility:
            clauses.append("visibility = ?")
            params.append(visibility)
        if alias:
            clauses.append("alias = ?")
            params.append(alias)
        where = " AND ".join(clauses) if clauses else "1=1"
        rows = self._conn.execute(
            f"SELECT * FROM objects WHERE {where} ORDER BY last_modified DESC",
            params,
        ).fetchall()
        return [dict(r) for r in rows]

    def get_by_alias(self, owner: str, alias: str) -> Optional[dict]:
        """Look up an object by its owner/alias pair."""
        row = self._conn.execute(
            "SELECT * FROM objects WHERE owner = ? AND alias = ?",
            (owner, alias),
        ).fetchone()
        return dict(row) if row else None

    def update_metadata(self, uuid: str, **kwargs) -> None:
        """Update metadata fields (title, alias, visibility, description) without a commit."""
        allowed = {"title", "alias", "visibility", "description"}
        updates = {k: v for k, v in kwargs.items() if k in allowed and v is not None}
        if not updates:
            return
        now = datetime.now(timezone.utc).isoformat()
        updates["last_modified"] = now
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        params = list(updates.values()) + [uuid]
        self._conn.execute(
            f"UPDATE objects SET {set_clause} WHERE uuid = ?", params
        )
        self._conn.commit()

    # ------------------------------------------------------------------
    # Ownership
    # ------------------------------------------------------------------

    def get_owner(self, uuid: str) -> Optional[str]:
        row = self._conn.execute(
            "SELECT owner FROM objects WHERE uuid = ?", (uuid,)
        ).fetchone()
        return row["owner"] if row else None

    def set_owner(self, uuid: str, username: str) -> None:
        self._conn.execute(
            "UPDATE objects SET owner = ? WHERE uuid = ? AND owner IS NULL",
            (username, uuid),
        )
        self._conn.commit()

    # ------------------------------------------------------------------
    # Commit history
    # ------------------------------------------------------------------

    def put_commit(
        self,
        uuid: str,
        commit_hash: str,
        commit_data: dict,
    ) -> None:
        self._conn.execute(
            """INSERT OR IGNORE INTO commits
               (hash, uuid, parent, tree, timestamp, message, branch)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                commit_hash,
                uuid,
                commit_data.get("parent"),
                commit_data["tree"],
                commit_data["timestamp"],
                commit_data.get("message", ""),
                commit_data.get("branch", "main"),
            ),
        )
        self._conn.commit()

    def log(
        self,
        uuid: str,
        branch: Optional[str] = None,
        limit: int = 0,
    ) -> list[dict]:
        if branch:
            sql = """SELECT hash, parent, tree, timestamp, message, branch
                     FROM commits
                     WHERE uuid = ? AND branch = ?
                     ORDER BY timestamp DESC"""
            params: list = [uuid, branch]
        else:
            sql = """SELECT hash, parent, tree, timestamp, message, branch
                     FROM commits
                     WHERE uuid = ?
                     ORDER BY timestamp DESC"""
            params = [uuid]
        if limit:
            sql += " LIMIT ?"
            params.append(limit)
        rows = self._conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # User management
    # ------------------------------------------------------------------

    def create_user(self, username: str) -> dict:
        now = datetime.now(timezone.utc).isoformat()
        self._conn.execute(
            "INSERT INTO users (username, created) VALUES (?, ?)",
            (username, now),
        )
        self._conn.commit()
        return {"username": username, "created": now}

    def get_user(self, username: str) -> Optional[dict]:
        row = self._conn.execute(
            "SELECT * FROM users WHERE username = ?", (username,)
        ).fetchone()
        return dict(row) if row else None

    def list_users(self) -> list[dict]:
        rows = self._conn.execute(
            "SELECT * FROM users ORDER BY created"
        ).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Token management
    # ------------------------------------------------------------------

    def create_token(self, username: str, token: Optional[str] = None) -> str:
        token = token or secrets.token_urlsafe(32)
        now = datetime.now(timezone.utc).isoformat()
        self._conn.execute(
            "INSERT OR IGNORE INTO tokens (token, username, created) VALUES (?, ?, ?)",
            (token, username, now),
        )
        self._conn.commit()
        return token

    def validate_token(self, token: str) -> Optional[str]:
        row = self._conn.execute(
            "SELECT username FROM tokens WHERE token = ?", (token,)
        ).fetchone()
        return row["username"] if row else None

    def revoke_token(self, token: str) -> None:
        self._conn.execute("DELETE FROM tokens WHERE token = ?", (token,))
        self._conn.commit()

    # ------------------------------------------------------------------

    def close(self) -> None:
        """Close the database connection."""
        self._conn.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


if __name__ == "__main__":
    import doctest

    doctest.testmod()
