from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel


class GeneratedImage(BaseModel):
    """A generated image plus provider metadata."""

    base64_string: str
    mime_type: str = "image/png"
    model: Optional[str] = None
    service_name: Optional[str] = None
    prompt: Optional[str] = None
    raw_response: Optional[dict[str, Any]] = None

    @property
    def suffix(self) -> str:
        if self.mime_type == "image/jpeg":
            return "jpeg"
        if self.mime_type == "image/webp":
            return "webp"
        return "png"

    def to_filestore(self):
        from edsl.scenarios import FileStore

        return FileStore(
            path=None,
            suffix=self.suffix,
            mime_type=self.mime_type,
            binary=True,
            base64_string=self.base64_string,
            external_locations={},
            extracted_text="",
        )
