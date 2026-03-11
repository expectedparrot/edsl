"""HTTP implementation of :class:`StorageBackend`.

Talks to a remote CAS service (e.g. the ``cas_editor`` FastAPI backend)
using the transfer protocol endpoints.

Writes are buffered and flushed as a :class:`PushBundle` when a ref is
updated, matching git's model of "stage objects, then push."
"""

from __future__ import annotations

import json
import re
from typing import Iterator, Optional
from urllib.request import Request, urlopen
from urllib.error import HTTPError


# ---------------------------------------------------------------------------
# Key parsing utilities
# ---------------------------------------------------------------------------

# Patterns: "blobs/<hash>.json", "trees/<hash>.json", "commits/<hash>.json"
_CAS_KEY_RE = re.compile(r"^(blobs|trees|commits)/([0-9a-f]+)\.json$")
_REF_KEY_RE = re.compile(r"^refs/(.+)$")


def _parse_cas_key(key: str) -> tuple[str, str]:
    """Parse a CAS key like ``blobs/abc123.json`` into ``("blobs", "abc123")``.

    Raises :class:`KeyError` if the key doesn't match.
    """
    m = _CAS_KEY_RE.match(key)
    if not m:
        raise KeyError(f"Not a CAS object key: {key}")
    return m.group(1), m.group(2)


def _parse_ref_key(key: str) -> str:
    """Parse ``refs/<branch>`` and return the branch name."""
    m = _REF_KEY_RE.match(key)
    if not m:
        raise KeyError(f"Not a ref key: {key}")
    return m.group(1)


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
        if key == "current.jsonl":
            return f"{self._prefix}/content", lambda r: r["content"]

        # refs/<branch>
        try:
            branch = _parse_ref_key(key)
            return f"{self._prefix}/refs/{branch}", lambda r: r["commit"] + "\n"
        except KeyError:
            pass

        # blobs/trees/commits
        try:
            kind, hash_hex = _parse_cas_key(key)
        except KeyError:
            raise KeyError(f"Unmapped key: {key}")

        if kind == "blobs":
            return f"{self._prefix}/blobs/{hash_hex}", lambda r: r["content"]
        # trees and commits are stored as JSON objects
        return f"{self._prefix}/{kind}/{hash_hex}", lambda r: json.dumps(r, sort_keys=True)

    # ------------------------------------------------------------------
    # Write (buffered)
    # ------------------------------------------------------------------

    def write(self, key: str, content: str) -> None:
        """Buffer a write.  Ref/HEAD writes trigger a flush (push)."""
        # CAS object keys
        try:
            kind, hash_hex = _parse_cas_key(key)
            {"blobs": self._pending_blobs,
             "trees": self._pending_trees,
             "commits": self._pending_commits}[kind][hash_hex] = content
            return
        except KeyError:
            pass

        # Ref update — flush everything as a push bundle
        try:
            branch = _parse_ref_key(key)
            commit_hash = content.strip()
            self._flush(branch, commit_hash)
            return
        except KeyError:
            pass

        if key == "HEAD":
            self._put_json(
                f"{self._prefix}/head",
                {"branch": content.strip()},
            )
        elif key == "current.jsonl":
            pass  # snapshot — derived from the commit, no push needed
        else:
            raise KeyError(f"Unmapped write key: {key}")

    def _flush(
        self,
        branch: str,
        commit_hash: str,
        expected_tip: Optional[str] = None,
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
        if expected_tip is not None:
            bundle["update_ref"]["expected_tip"] = expected_tip
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
                headers=self._auth_headers(),
            )
            with urlopen(req, timeout=30) as resp:
                pass
        except HTTPError as e:
            if e.code != 404:
                raise

    # ------------------------------------------------------------------
    # Metadata
    # ------------------------------------------------------------------

    def get_metadata(self) -> dict:
        """Fetch object metadata from the remote service."""
        return self._get(f"{self._prefix}/meta")

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
