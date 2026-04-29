"""Incremental CAS writer for streaming JSONL rows.

Builds a CAS object progressively — each append creates a new commit
whose tree contains all rows written so far.  Every intermediate commit
is a valid, loadable JSONL object.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Optional

from .storage_backend import StorageBackend


class StreamingCASWriter:
    """Incrementally build a CAS object by appending JSONL rows.

    Each append writes one blob and creates a new commit whose tree
    is [preamble blobs...] + [result blobs so far...].  Every commit
    is a valid, loadable JSONL object.

    Row content is cached in memory so that ``current.jsonl`` can be
    rebuilt by appending rather than re-reading every blob from disk.

    Examples:
        >>> import tempfile
        >>> from edsl.object_store.fs_backend import FileSystemBackend
        >>> backend = FileSystemBackend(tempfile.mkdtemp())
        >>> w = StreamingCASWriter(backend)
        >>> w.write_preamble(['{"__header__": true}', '{"n_survey_lines": 0}'])
        >>> w.n_results
        0
        >>> w.tip is not None
        True
        >>> w.append_result('{"answer": "hello"}')
        >>> w.n_results
        1
        >>> w.append_results_batch(['{"answer": "a"}', '{"answer": "b"}'])
        >>> w.n_results
        3
    """

    def __init__(self, backend: StorageBackend, branch: str = "main"):
        self._backend = backend
        self._branch = branch
        self._preamble_hashes: list[str] = []
        self._result_hashes: list[str] = []
        self._tip: Optional[str] = None
        # In-memory cache: hash -> row content (avoids re-reading blobs)
        self._row_cache: dict[str, str] = {}

    def write_preamble(self, rows: list[str], message: str = "Job started"):
        """Write header + manifest + survey rows as blobs, create initial commit."""
        for row in rows:
            h = self._write_blob(row)
            self._preamble_hashes.append(h)
        self._commit(message)

    def append_result(self, result_json_row: str, message: str = ""):
        """Append one Result row and create a new commit."""
        h = self._write_blob(result_json_row)
        self._result_hashes.append(h)
        self._commit(message or f"Result {len(self._result_hashes)}")

    def append_results_batch(self, rows: list[str], message: str = ""):
        """Append multiple Result rows in a single commit."""
        for row in rows:
            h = self._write_blob(row)
            self._result_hashes.append(h)
        if self._result_hashes or self._preamble_hashes:
            self._commit(message or f"Batch: {len(rows)} results")

    @property
    def n_results(self) -> int:
        return len(self._result_hashes)

    @property
    def tip(self) -> Optional[str]:
        return self._tip

    # ------------------------------------------------------------------
    # internals
    # ------------------------------------------------------------------

    @staticmethod
    def _hash(content: str) -> str:
        return hashlib.sha256(content.encode()).hexdigest()

    def _write_blob(self, content: str) -> str:
        h = self._hash(content)
        self._row_cache[h] = content
        key = f"blobs/{h}.json"
        if not self._backend.exists(key):
            self._backend.write(key, content)
        return h

    def _commit(self, message: str):
        """Build tree, create commit, advance ref."""
        b = self._backend

        # Tree
        all_hashes = self._preamble_hashes + self._result_hashes
        tree_obj = {"blobs": all_hashes}
        tree_content = json.dumps(tree_obj, sort_keys=True)
        tree_hash = self._hash(tree_content)
        tree_key = f"trees/{tree_hash}.json"
        if not b.exists(tree_key):
            b.write(tree_key, tree_content)

        # Commit
        timestamp = datetime.now(timezone.utc).isoformat()
        commit_obj = {
            "tree": tree_hash,
            "parent": self._tip,
            "timestamp": timestamp,
            "message": message,
        }
        commit_content = json.dumps(commit_obj, sort_keys=True)
        commit_hash = self._hash(commit_content)
        b.write(f"commits/{commit_hash}.json", commit_content)

        # Update ref + HEAD
        b.write(f"refs/{self._branch}", commit_hash + "\n")
        b.write("HEAD", self._branch + "\n")

        # Update current.jsonl from in-memory cache (no blob re-reads)
        parts = [self._row_cache[h] for h in all_hashes]
        b.write("current.jsonl", "\n".join(parts) + "\n")

        self._tip = commit_hash


if __name__ == "__main__":
    import doctest

    doctest.testmod()
