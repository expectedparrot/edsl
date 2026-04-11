"""HTTP client for GitLab-backed studies via the Coop API."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional
from urllib.parse import urlparse, urlunparse

from edsl.coop.utils import VisibilityType

if TYPE_CHECKING:
    from edsl.coop import Coop
    from edsl.coop.coop_regular_objects import CoopRegularObjects
    from edsl.study.study import Study


def _resolve_server_url(server_url: str | None) -> str:
    """Return the Coop frontend base URL (trailing slash stripped).

    Passed to :class:`~edsl.coop.Coop` so ``api_url`` matches other Coop
    traffic. If omitted, uses ``EXPECTED_PARROT_URL`` from config.
    """
    if server_url is not None:
        return server_url.rstrip("/")
    try:
        from edsl.config import CONFIG

        return str(CONFIG.EXPECTED_PARROT_URL).rstrip("/")
    except Exception:
        return "https://www.expectedparrot.com"


def authed_remote_url(gitlab_url: str, token: str) -> str:
    """Inject ``oauth2:{token}@`` into a GitLab URL."""
    parsed = urlparse(gitlab_url)
    authed = parsed._replace(
        netloc=f"oauth2:{token}@{parsed.hostname}"
        + (f":{parsed.port}" if parsed.port else "")
    )
    return urlunparse(authed)


class StudyClient:
    """Thin adapter over :class:`~edsl.coop.Coop` GitLab study endpoints.

    Uses the same ``api_url`` and API key as Coop. Study Coop methods call
    :meth:`~edsl.coop.Coop._resolve_server_response` on the raw response, so
    failures surface as :class:`~edsl.coop.exceptions.CoopServerResponseError`
    (and transport errors from ``requests``).
    """

    def __init__(self, server_url: str | None = None, coop: Optional["Coop"] = None):
        from edsl.coop import Coop

        self._coop = (
            coop if coop is not None else Coop(url=_resolve_server_url(server_url))
        )

    def push_request(
        self,
        *,
        value: "Study",
        uuid: Optional[str] = None,
        alias: Optional[str] = None,
        description: Optional[str] = None,
        visibility: VisibilityType = "private",
    ) -> dict:
        """Create or refresh a study on the server and return token payload.

        Uses :meth:`~edsl.coop.Coop.push_study` for the first upload and
        :meth:`~edsl.coop.Coop.patch_study` when ``uuid`` is set. GitLab write
        credentials come from ``POST /api/v0/gitlab/study-write-token``.
        """
        request_data = {
            "description": description,
            "alias": alias,
            "visibility": visibility,
        }
        if uuid is not None:
            return self._coop.patch_study(url_or_uuid=uuid, value=value, **request_data)
        return self._coop.push_study(object=value, **request_data)

    def pull_request(self, uuid: str) -> dict:
        """Mint a read token for pulling an existing study repo.

        Wraps :meth:`~edsl.coop.Coop.pull_study`.
        """
        return self._coop.pull_study(uuid)

    def clone_request(
        self, *, uuid: Optional[str] = None, alias: Optional[str] = None
    ) -> dict:
        """Obtain clone credentials by repository UUID or alias.

        Wraps :meth:`~edsl.coop.Coop.clone_study`.
        """
        return self._coop.clone_study(uuid=uuid, alias=alias)

    def update_metadata(
        self,
        uuid: str,
        *,
        alias: Optional[str] = None,
        title: Optional[str] = None,
        description: Optional[str] = None,
        visibility: Optional[VisibilityType] = None,
    ) -> None:
        """Patch server-side metadata for a study you own.

        Wraps :meth:`~edsl.coop.Coop.update_study_metadata`. ``None`` values
        are omitted from the request payload by the Coop client.
        """
        self._coop.update_study_metadata(
            uuid,
            alias=alias,
            title=title,
            description=description,
            visibility=visibility,
        )

    def list_repos(self) -> "CoopRegularObjects":
        """List study objects for the current user via :meth:`~edsl.coop.Coop.list`."""
        return self._coop.list(object_type="study")
