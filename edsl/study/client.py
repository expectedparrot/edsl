"""HTTP client for the Study meta-server."""

import os
from urllib.parse import urlparse, urlunparse

import requests

from edsl.study.exceptions import StudyAuthError, StudyServerError

_DEFAULT_SERVER_URL = "https://study.expectedparrot.com"


def _resolve_server_url(server_url: str | None) -> str:
    """Return a normalized server URL, falling back to config or the built-in default."""
    if server_url is not None:
        return server_url.rstrip("/")
    try:
        from edsl.config import CONFIG
        return CONFIG.get("EDSL_STUDY_SERVER_URL")
    except Exception:
        return _DEFAULT_SERVER_URL


def _get_api_key() -> str:
    """Retrieve the Expected Parrot API key from the environment."""
    key = os.environ.get("EXPECTED_PARROT_API_KEY")
    if not key:
        try:
            from edsl.coop.ep_key_handling import ExpectedParrotKeyHandler
            key = ExpectedParrotKeyHandler().get_ep_api_key()
        except Exception:
            pass
    if not key:
        raise StudyAuthError(
            "No API key found. Set EXPECTED_PARROT_API_KEY or run edsl.login()."
        )
    # Strip surrounding quotes if present (from .env files)
    return key.strip("'\"")


def authed_remote_url(gitlab_url: str, token: str) -> str:
    """Inject ``oauth2:{token}@`` into a GitLab URL."""
    parsed = urlparse(gitlab_url)
    authed = parsed._replace(
        netloc=f"oauth2:{token}@{parsed.hostname}"
        + (f":{parsed.port}" if parsed.port else "")
    )
    return urlunparse(authed)


class StudyClient:
    """Thin HTTP wrapper for the study meta-server.

    All methods raise ``StudyServerError`` on transport failures and return
    parsed JSON (or raise on HTTP error status).
    """

    def __init__(self, server_url: str | None = None):
        self.server_url = _resolve_server_url(server_url)

    @property
    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {_get_api_key()}"}

    def _request(self, method: str, endpoint: str, **kwargs) -> requests.Response:
        kwargs.setdefault("headers", self._headers)
        kwargs.setdefault("timeout", 30)
        try:
            return requests.request(method, f"{self.server_url}{endpoint}", **kwargs)
        except requests.RequestException as exc:
            raise StudyServerError(f"Failed to contact server: {exc}")

    def push_request(self, body: dict) -> dict:
        resp = self._request("POST", "/push-req", json=body)
        if resp.status_code == 409:
            raise StudyServerError("Alias already taken.")
        if resp.status_code == 403:
            raise StudyServerError("Not authorized to push to this study.")
        if not resp.ok:
            raise StudyServerError(
                f"Push request failed ({resp.status_code}): {resp.text}"
            )
        return resp.json()

    def pull_request(self, uuid: str) -> dict:
        resp = self._request("POST", "/pull-event", json={"uuid": uuid})
        if not resp.ok:
            raise StudyServerError(
                f"Pull request failed ({resp.status_code}): {resp.text}"
            )
        return resp.json()

    def clone_request(self, *, uuid: str | None = None, alias: str | None = None) -> dict:
        body = {}
        if uuid is not None:
            body["uuid"] = uuid
        if alias is not None:
            body["alias"] = alias
        resp = self._request("POST", "/clone-req", json=body, timeout=60)
        if resp.status_code == 404:
            error = resp.json().get("error", "not_found")
            raise StudyServerError(f"Study not found or not yet pushed: {error}")
        if resp.status_code == 403:
            raise StudyServerError("Not authorized to access this study.")
        if not resp.ok:
            raise StudyServerError(
                f"Clone request failed ({resp.status_code}): {resp.text}"
            )
        return resp.json()

    def update_metadata(self, uuid: str, body: dict) -> None:
        resp = self._request("PATCH", f"/repos/{uuid}", json=body)
        if not resp.ok:
            raise StudyServerError(
                f"Metadata update failed ({resp.status_code}): {resp.text}"
            )

    def list_repos(self) -> list[dict]:
        resp = self._request("GET", "/repos")
        if not resp.ok:
            raise StudyServerError(
                f"List request failed ({resp.status_code}): {resp.text}"
            )
        return resp.json().get("repos", [])
