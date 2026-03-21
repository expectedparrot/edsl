"""PostgreSQL implementation of :class:`MetadataIndex`.

Requires ``psycopg2`` (install with ``pip install edsl[gcp]``).
"""

from __future__ import annotations

import secrets
from datetime import datetime, timezone
from typing import Optional


class PostgreSQLMetadataIndex:
    """MetadataIndex backed by PostgreSQL.

    Uses a ``psycopg2.pool.ThreadedConnectionPool`` for thread safety.
    Creates the schema (4 tables: objects, commits, users, tokens) on
    first instantiation via ``CREATE TABLE IF NOT EXISTS``.

    Parameters:
        dsn: PostgreSQL connection string (e.g.
             ``"postgresql://user:pass@host:5432/dbname"``).
        minconn: Minimum pool connections (default 1).
        maxconn: Maximum pool connections (default 10).
    """

    def __init__(self, dsn: str, minconn: int = 1, maxconn: int = 10) -> None:
        import psycopg2.pool

        self._pool = psycopg2.pool.ThreadedConnectionPool(minconn, maxconn, dsn)
        self._ensure_schema()

    def _get_conn(self):
        return self._pool.getconn()

    def _put_conn(self, conn):
        self._pool.putconn(conn)

    def _execute(self, sql, params=(), *, fetch=False, fetchone=False):
        """Execute a query with automatic connection management."""
        conn = self._get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                if fetchone:
                    row = cur.fetchone()
                    if row is None:
                        return None
                    cols = [desc[0] for desc in cur.description]
                    return dict(zip(cols, row))
                if fetch:
                    cols = [desc[0] for desc in cur.description]
                    return [dict(zip(cols, r)) for r in cur.fetchall()]
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            self._put_conn(conn)

    def _ensure_schema(self) -> None:
        conn = self._get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute("""
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
                """)
            conn.commit()
        finally:
            self._put_conn(conn)

    # ------------------------------------------------------------------
    # Object metadata
    # ------------------------------------------------------------------

    def put(self, uuid: str, meta: dict, owner: Optional[str] = None) -> None:
        self._execute(
            """INSERT INTO objects (uuid, type, description, created, last_modified, owner,
                                   title, alias, visibility)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
               ON CONFLICT (uuid) DO UPDATE SET
                   description = COALESCE(EXCLUDED.description, objects.description),
                   last_modified = EXCLUDED.last_modified,
                   title = COALESCE(EXCLUDED.title, objects.title),
                   alias = COALESCE(EXCLUDED.alias, objects.alias),
                   visibility = COALESCE(EXCLUDED.visibility, objects.visibility)""",
            (
                uuid,
                meta.get("type", ""),
                meta.get("description", ""),
                meta.get("created", ""),
                meta.get("last_modified", ""),
                owner,
                meta.get("title"),
                meta.get("alias"),
                meta.get("visibility", "private"),
            ),
        )

    def get(self, uuid: str) -> Optional[dict]:
        return self._execute(
            "SELECT * FROM objects WHERE uuid = %s", (uuid,), fetchone=True
        )

    def resolve_prefix(self, prefix: str) -> list[str]:
        """Return all UUIDs matching the given prefix."""
        rows = self._execute(
            "SELECT uuid FROM objects WHERE uuid LIKE %s",
            (prefix + "%",),
            fetch=True,
        )
        return [r["uuid"] for r in rows]

    def resolve_alias(self, alias: str) -> Optional[str]:
        """Look up a UUID by alias (any owner). Returns None if not found."""
        row = self._execute(
            "SELECT uuid FROM objects WHERE alias = %s LIMIT 1",
            (alias,),
            fetchone=True,
        )
        return row["uuid"] if row else None

    def delete(self, uuid: str) -> None:
        self._execute("DELETE FROM objects WHERE uuid = %s", (uuid,))

    def list_all(self, owner: Optional[str] = None) -> list[dict]:
        if owner:
            return self._execute(
                "SELECT * FROM objects WHERE owner = %s ORDER BY last_modified DESC",
                (owner,),
                fetch=True,
            )
        return self._execute(
            "SELECT * FROM objects ORDER BY last_modified DESC", fetch=True
        )

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
            clauses.append("type = %s")
            params.append(type_name)
        if query:
            clauses.append("(description LIKE %s OR title LIKE %s)")
            params.extend([f"%{query}%", f"%{query}%"])
        if owner:
            clauses.append("owner = %s")
            params.append(owner)
        if visibility:
            clauses.append("visibility = %s")
            params.append(visibility)
        if alias:
            clauses.append("alias = %s")
            params.append(alias)
        where = " AND ".join(clauses) if clauses else "1=1"
        return self._execute(
            f"SELECT * FROM objects WHERE {where} ORDER BY last_modified DESC",
            params,
            fetch=True,
        )

    def get_by_alias(self, owner: str, alias: str) -> Optional[dict]:
        return self._execute(
            "SELECT * FROM objects WHERE owner = %s AND alias = %s",
            (owner, alias),
            fetchone=True,
        )

    def update_metadata(self, uuid: str, **kwargs) -> None:
        allowed = {"title", "alias", "visibility", "description"}
        updates = {k: v for k, v in kwargs.items() if k in allowed and v is not None}
        if not updates:
            return
        now = datetime.now(timezone.utc).isoformat()
        updates["last_modified"] = now
        set_clause = ", ".join(f"{k} = %s" for k in updates)
        params = list(updates.values()) + [uuid]
        self._execute(f"UPDATE objects SET {set_clause} WHERE uuid = %s", params)

    # ------------------------------------------------------------------
    # Ownership
    # ------------------------------------------------------------------

    def get_owner(self, uuid: str) -> Optional[str]:
        row = self._execute(
            "SELECT owner FROM objects WHERE uuid = %s", (uuid,), fetchone=True
        )
        return row["owner"] if row else None

    def set_owner(self, uuid: str, username: str) -> None:
        self._execute(
            "UPDATE objects SET owner = %s WHERE uuid = %s AND owner IS NULL",
            (username, uuid),
        )

    # ------------------------------------------------------------------
    # Commit history
    # ------------------------------------------------------------------

    def put_commit(self, uuid: str, commit_hash: str, commit_data: dict) -> None:
        self._execute(
            """INSERT INTO commits (hash, uuid, parent, tree, timestamp, message, branch)
               VALUES (%s, %s, %s, %s, %s, %s, %s)
               ON CONFLICT (uuid, hash) DO NOTHING""",
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

    def log(self, uuid: str, branch: Optional[str] = None, limit: int = 0) -> list[dict]:
        if branch:
            sql = """SELECT hash, parent, tree, timestamp, message, branch
                     FROM commits WHERE uuid = %s AND branch = %s
                     ORDER BY timestamp DESC"""
            params: list = [uuid, branch]
        else:
            sql = """SELECT hash, parent, tree, timestamp, message, branch
                     FROM commits WHERE uuid = %s
                     ORDER BY timestamp DESC"""
            params = [uuid]
        if limit:
            sql += " LIMIT %s"
            params.append(limit)
        return self._execute(sql, params, fetch=True)

    # ------------------------------------------------------------------
    # User management
    # ------------------------------------------------------------------

    def create_user(self, username: str) -> dict:
        now = datetime.now(timezone.utc).isoformat()
        self._execute(
            "INSERT INTO users (username, created) VALUES (%s, %s)",
            (username, now),
        )
        return {"username": username, "created": now}

    def get_user(self, username: str) -> Optional[dict]:
        return self._execute(
            "SELECT * FROM users WHERE username = %s", (username,), fetchone=True
        )

    def list_users(self) -> list[dict]:
        return self._execute("SELECT * FROM users ORDER BY created", fetch=True)

    # ------------------------------------------------------------------
    # Token management
    # ------------------------------------------------------------------

    def create_token(self, username: str, token: Optional[str] = None) -> str:
        token = token or secrets.token_urlsafe(32)
        now = datetime.now(timezone.utc).isoformat()
        self._execute(
            """INSERT INTO tokens (token, username, created) VALUES (%s, %s, %s)
               ON CONFLICT (token) DO NOTHING""",
            (token, username, now),
        )
        return token

    def validate_token(self, token: str) -> Optional[str]:
        row = self._execute(
            "SELECT username FROM tokens WHERE token = %s", (token,), fetchone=True
        )
        return row["username"] if row else None

    def revoke_token(self, token: str) -> None:
        self._execute("DELETE FROM tokens WHERE token = %s", (token,))

    def delete_all(self) -> None:
        """Delete all data from all tables."""
        # Order matters due to FK constraints
        for table in ("commits", "tokens", "objects", "users"):
            self._execute(f"DELETE FROM {table}")

    # ------------------------------------------------------------------

    def close(self) -> None:
        """Close the connection pool."""
        self._pool.closeall()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
