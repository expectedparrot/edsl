"""Versioned review comments for Survey git packages."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


COMMENTS_PATH = "metadata/comments.json"


class SurveyComments:
    """Manage review comment threads in a bound Survey git package."""

    def __init__(self, git_accessor: Any) -> None:
        self._git = git_accessor

    def list(self, status: str | None = None) -> list[dict[str, Any]]:
        comments = self._read()
        threads = list(comments.get("threads") or [])
        if status is not None:
            threads = [thread for thread in threads if thread.get("status") == status]
        return threads

    def add(
        self,
        *,
        body: str,
        target: dict[str, Any] | None = None,
        question_name: str | None = None,
        path: str | None = None,
        author: str | dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        comments = self._read()
        now = _now()
        target = target or self._question_target(question_name, path)
        message = _message(body=body, author=author, created_at=now)
        thread = {
            "id": _id(),
            "target": target,
            "status": "open",
            "created_at": now,
            "updated_at": now,
            "resolved_at": None,
            "author": _author(author),
            "messages": [message],
        }
        comments.setdefault("threads", []).append(thread)
        self._write(comments)
        commit = self._git._commit_package_changes(
            f"Add comment on {_target_label(target)}"
        )
        return {"status": "ok", "thread": thread, "commit": commit}

    def reply(
        self,
        thread_id: str,
        *,
        body: str,
        author: str | dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        comments = self._read()
        thread = _find_thread(comments, thread_id)
        now = _now()
        thread.setdefault("messages", []).append(
            _message(body=body, author=author, created_at=now)
        )
        thread["updated_at"] = now
        self._write(comments)
        commit = self._git._commit_package_changes(f"Reply to comment {thread_id}")
        return {"status": "ok", "thread": thread, "commit": commit}

    def resolve(self, thread_id: str) -> dict[str, Any]:
        comments = self._read()
        thread = _find_thread(comments, thread_id)
        now = _now()
        thread["status"] = "resolved"
        thread["updated_at"] = now
        thread["resolved_at"] = now
        self._write(comments)
        commit = self._git._commit_package_changes(f"Resolve comment {thread_id}")
        return {"status": "ok", "thread": thread, "commit": commit}

    def reopen(self, thread_id: str) -> dict[str, Any]:
        comments = self._read()
        thread = _find_thread(comments, thread_id)
        now = _now()
        thread["status"] = "open"
        thread["updated_at"] = now
        thread["resolved_at"] = None
        self._write(comments)
        commit = self._git._commit_package_changes(f"Reopen comment {thread_id}")
        return {"status": "ok", "thread": thread, "commit": commit}

    def _read(self) -> dict[str, Any]:
        path = self._comments_path()
        if not path.exists():
            return {"version": 1, "threads": []}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            data = {}
        return {"version": data.get("version", 1), "threads": data.get("threads") or []}

    def _write(self, comments: dict[str, Any]) -> None:
        path = self._comments_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(comments, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    def _comments_path(self) -> Path:
        return self._git._bound_worktree_path() / COMMENTS_PATH

    def _question_target(
        self, question_name: str | None, path: str | None
    ) -> dict[str, Any]:
        if not question_name:
            return {"kind": "survey", "path": path}
        question_id = None
        survey = self._git._instance
        question_names = list(getattr(survey, "question_names", []) or [])
        if question_name in question_names:
            index = question_names.index(question_name)
            question_ids = self._question_ids()
            if index < len(question_ids):
                question_id = question_ids[index]
        return {
            "kind": "question",
            "question_id": question_id,
            "question_name": question_name,
            "path": path,
        }

    def _question_ids(self) -> list[str]:
        question_ids = list(getattr(self._git, "question_ids", []) or [])
        if question_ids:
            return question_ids
        manifest_path = self._git._bound_worktree_path() / "manifest.json"
        if not manifest_path.exists():
            return []
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return []
        return list(manifest.get("question_order") or [])


def read_comments_at_ref(path: Path, ref: str, *, error_cls) -> dict[str, Any]:
    from edsl.base import git_package as gitpkg

    try:
        data = gitpkg.read_json_at_ref(path, COMMENTS_PATH, ref, error_cls=error_cls)
    except Exception:
        return {"version": 1, "threads": []}
    return {"version": data.get("version", 1), "threads": data.get("threads") or []}


def _message(
    *, body: str, author: str | dict[str, Any] | None, created_at: str
) -> dict[str, Any]:
    return {
        "id": _id(),
        "created_at": created_at,
        "author": _author(author),
        "body": body,
    }


def _author(author: str | dict[str, Any] | None) -> dict[str, Any]:
    if isinstance(author, dict):
        return {"id": author.get("id"), "name": author.get("name") or "unknown"}
    return {"id": None, "name": author or "unknown"}


def _find_thread(comments: dict[str, Any], thread_id: str) -> dict[str, Any]:
    for thread in comments.get("threads") or []:
        if thread.get("id") == thread_id:
            return thread
    raise ValueError(f"No comment thread found: {thread_id}")


def _target_label(target: dict[str, Any]) -> str:
    if target.get("question_name"):
        if target.get("path"):
            return f"{target['question_name']} {target['path']}"
        return str(target["question_name"])
    return str(target.get("kind") or "survey")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _id() -> str:
    return str(uuid.uuid4())
