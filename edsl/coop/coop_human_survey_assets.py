"""The human survey asset library: images a survey's branding uses.

An asset is uploaded once and referenced by uuid from a humanize schema
(``survey.branding.logo.source``), so a schema never carries image bytes. See
``AssetImageSource`` in ``coop_humanize_schema.py`` for the reference shape.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import requests

from .exceptions import CoopValueError

# The server's limits, mirrored so an unusable file is rejected before it is sent.
# The server stays authoritative: it decodes the image, while these checks only
# read the name and the size on disk.
ASSET_MAX_BYTES = 2 * 1024 * 1024
ASSET_EXTENSIONS = ("png", "jpg", "jpeg", "webp", "gif")

ASSET_FORMATS_MESSAGE = (
    "Accepted formats: PNG, JPEG, WebP, and static GIF, at most 2 MB and 4096 "
    "pixels on each side."
)


def validate_asset_file(path: Path) -> None:
    """Check a file against the library's limits. Raises CoopValueError if unusable."""
    if not path.exists():
        raise CoopValueError(f"File not found: {path}")
    if path.suffix.lower().lstrip(".") not in ASSET_EXTENSIONS:
        raise CoopValueError(
            f"{path.name} is not a supported image file. {ASSET_FORMATS_MESSAGE}"
        )
    size_bytes = path.stat().st_size
    if size_bytes == 0:
        raise CoopValueError(f"{path.name} is empty.")
    if size_bytes > ASSET_MAX_BYTES:
        raise CoopValueError(
            f"{path.name} is {size_bytes / (1024 * 1024):.1f} MB, over the 2 MB limit."
        )


class HumanSurveyAsset(dict):
    """One asset's metadata, as the server returned it.

    A dict, so it prints and serializes like every other Coop result, with
    ``download`` added for the one thing the metadata can't give you: the image.
    """

    @property
    def uuid(self) -> str:
        return self["uuid"]

    @property
    def url(self) -> Optional[str]:
        """The signed download URL. Returned by ``get``, not by ``upload``."""
        return self.get("url")

    def download(self, path: Optional[str] = None) -> str:
        """Save the image, defaulting to its name in the library. Returns the path."""
        if not self.url:
            raise CoopValueError(
                "This asset has no download URL. Fetch it with "
                "Coop().get_human_survey_asset(uuid), which returns one."
            )
        # The signed URL carries its own credentials and points at storage rather
        # than the API, so the Coop API key must not be sent with it.
        response = requests.get(self.url, timeout=60)
        response.raise_for_status()
        destination = Path(path or self.get("name") or self.uuid)
        if destination.parent != Path(""):
            destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(response.content)
        return str(destination)
