"""HTTP implementation of :class:`StorageBackend`.

Talks to a remote CAS service (e.g. the ``cas_editor`` FastAPI backend)
using the transfer protocol endpoints.

Writes are buffered and flushed as a :class:`PushBundle` when a ref is
updated, matching git's model of "stage objects, then push."
"""

from __future__ import annotations

import hashlib
import json
from typing import Iterator, Optional
from urllib.request import Request, urlopen
from urllib.error import HTTPError


class HttpBackend:
    """StorageBackend that proxies to a remote CAS service over HTTP.

    The *base_url* should point to the API root (e.g. ``http://localhost:8000``).
    The *uuid* identifies which object's CAS repository to access.

    Examples:
        Assumes a CAS service is running at ``base_url`` with an object
        at ``uuid``.  See :mod:`cas_editor.backend.main` for the server.

        >>> # HttpBackend("http://localhost:8000", "some-uuid")
    """

    def __init__(self, base_url: str, uuid: str, token: Optional[str] = None) -> None:
        self.base_url = base_url.rstrip("/")
        self.uuid = uuid
        self.token = token
        self._prefix = f"{self.base_url}/api/objects/{uuid}"

        # Write buffer — flushed on ref update
        self._pending_blobs: dict[str, str] = {}
        self._pending_trees: dict[str, str] = {}
        self._pending_commits: dict[str, str] = {}
        self._pending_meta: Optional[dict] = None

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def read(self, key: str) -> str:
        """Read a CAS key from the remote service."""
        url, extract = self._read_url(key)
        try:
            resp = self._get(url)
        except HTTPError as e:
            if e.code == 404:
                raise KeyError(key)
            raise
        return extract(resp)

    def _read_url(self, key: str):
        """Map a StorageBackend key to an HTTP URL and a response extractor."""
        if key == "HEAD":
            return f"{self._prefix}/head", lambda r: r["branch"] + "\n"
        if key.startswith("refs/"):
            branch = key[5:]
            return f"{self._prefix}/refs/{branch}", lambda r: r["commit"] + "\n"
        if key.startswith("commits/") and key.endswith(".json"):
            h = key[8:-5]
            return f"{self._prefix}/commits/{h}", lambda r: json.dumps(r, sort_keys=True)
        if key.startswith("trees/") and key.endswith(".json"):
            h = key[6:-5]
            return f"{self._prefix}/trees/{h}", lambda r: json.dumps(r, sort_keys=True)
        if key.startswith("blobs/") and key.endswith(".json"):
            h = key[6:-5]
            return f"{self._prefix}/blobs/{h}", lambda r: r["content"]
        if key == "current.jsonl":
            return f"{self._prefix}/content", lambda r: r["content"]
        raise KeyError(f"Unmapped key: {key}")

    # ------------------------------------------------------------------
    # Write (buffered)
    # ------------------------------------------------------------------

    def write(self, key: str, content: str) -> None:
        """Buffer a write.  Ref/HEAD writes trigger a flush (push)."""
        if key.startswith("blobs/") and key.endswith(".json"):
            h = key[6:-5]
            self._pending_blobs[h] = content
        elif key.startswith("trees/") and key.endswith(".json"):
            h = key[6:-5]
            self._pending_trees[h] = content
        elif key.startswith("commits/") and key.endswith(".json"):
            h = key[8:-5]
            self._pending_commits[h] = content
        elif key.startswith("refs/"):
            # Ref update — flush everything as a push bundle
            branch = key[5:]
            commit_hash = content.strip()
            self._flush(branch, commit_hash)
        elif key == "HEAD":
            # HEAD update — just set it on the server
            self._put_json(
                f"{self._prefix}/head",
                {"branch": content.strip()},
            )
        elif key == "current.jsonl":
            # Snapshot — no need to push, it's derived from the commit
            pass
        else:
            raise KeyError(f"Unmapped write key: {key}")

    def _flush(
        self,
        branch: str,
        commit_hash: str,
        expected_parent: Optional[str] = None,
    ) -> dict:
        """Push buffered objects and update a ref."""
        bundle: dict = {
            "blobs": self._pending_blobs,
            "trees": self._pending_trees,
            "commits": self._pending_commits,
            "update_ref": {
                "branch": branch,
                "commit": commit_hash,
            },
        }
        if expected_parent is not None:
            bundle["update_ref"]["expected_parent"] = expected_parent
        if self._pending_meta is not None:
            bundle["meta"] = self._pending_meta

        result = self._post_json(f"{self._prefix}/push", bundle)

        # Clear buffers
        self._pending_blobs.clear()
        self._pending_trees.clear()
        self._pending_commits.clear()
        self._pending_meta = None

        return result

    # ------------------------------------------------------------------
    # Exists
    # ------------------------------------------------------------------

    def exists(self, key: str) -> bool:
        try:
            self.read(key)
            return True
        except KeyError:
            return False

    # ------------------------------------------------------------------
    # Delete
    # ------------------------------------------------------------------

    def delete(self, key: str) -> None:
        # Individual key deletion not supported in the transfer protocol.
        # For CAS, objects are immutable, so deletion is rare.
        pass

    def delete_tree(self, prefix: str) -> None:
        """Delete the entire object from the remote."""
        try:
            req = Request(
                f"{self._prefix}",
                method="DELETE",
            )
            urlopen(req)
        except HTTPError:
            pass

    # ------------------------------------------------------------------
    # List
    # ------------------------------------------------------------------

    def list_prefix(self, prefix: str) -> Iterator[str]:
        if prefix == "refs/" or prefix == "refs":
            try:
                refs = self._get(f"{self._prefix}/refs")
            except HTTPError:
                return
            for branch_name in refs:
                yield f"refs/{branch_name}"
        else:
            # Other prefixes not supported via HTTP
            return

    # ------------------------------------------------------------------
    # HTTP helpers (stdlib only — no requests dependency)
    # ------------------------------------------------------------------

    def _auth_headers(self) -> dict[str, str]:
        """Return headers with Authorization if a token is set."""
        h: dict[str, str] = {"Accept": "application/json"}
        if self.token:
            h["Authorization"] = f"Bearer {self.token}"
        return h

    def _get(self, url: str):
        """GET a URL and return parsed JSON."""
        req = Request(url, headers=self._auth_headers())
        with urlopen(req) as resp:
            return json.loads(resp.read().decode())

    def _post_json(self, url: str, data: dict) -> dict:
        """POST JSON and return parsed response."""
        body = json.dumps(data).encode()
        headers = {**self._auth_headers(), "Content-Type": "application/json"}
        req = Request(url, data=body, headers=headers, method="POST")
        with urlopen(req) as resp:
            return json.loads(resp.read().decode())

    def _put_json(self, url: str, data: dict) -> dict:
        """PUT JSON and return parsed response."""
        body = json.dumps(data).encode()
        headers = {**self._auth_headers(), "Content-Type": "application/json"}
        req = Request(url, data=body, headers=headers, method="PUT")
        with urlopen(req) as resp:
            return json.loads(resp.read().decode())
