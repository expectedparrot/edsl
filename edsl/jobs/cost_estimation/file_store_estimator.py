from __future__ import annotations
from typing import Callable, TYPE_CHECKING

from .cost_estimation_constants import EDSL_DEFAULT_CHARS_PER_TOKEN

if TYPE_CHECKING:
    from ...scenarios import FileStore


# ------------------------------------------------------------------
# Built-in MIME-type estimators


def _estimate_text_file(
    filestore: "FileStore",
    inference_service: str,
    chars_per_token: int = EDSL_DEFAULT_CHARS_PER_TOKEN,
) -> tuple[int, list[str]]:
    text = getattr(filestore, "extracted_text", None)
    if text:
        return max(1, len(text) // chars_per_token), []
    size = getattr(filestore, "size", 0) or 0
    return max(1, size // chars_per_token), []


def _estimate_image_openai(
    filestore: "FileStore", inference_service: str
) -> tuple[int, list[str]]:
    import math

    warnings = []
    try:
        width, height = filestore.get_image_dimensions()
        # Resize to fit 2048x2048, then tile at 512x512 (high-detail mode)
        scale = min(1.0, 2048 / max(width, height))
        w = int(width * scale)
        h = int(height * scale)
        tiles = math.ceil(w / 512) * math.ceil(h / 512)
        tokens = 170 * tiles + 85
        return tokens, warnings
    except ImportError:
        warnings.append(
            f"Image '{getattr(filestore, '_path', 'unknown')}': PIL not available — "
            f"using fixed estimate of 1000 tokens."
        )
        return 1000, warnings
    except Exception as e:
        warnings.append(
            f"Image '{getattr(filestore, '_path', 'unknown')}': could not get dimensions ({e}) — "
            f"using fixed estimate of 1000 tokens."
        )
        return 1000, warnings


def _estimate_image_google(
    filestore: "FileStore", inference_service: str
) -> tuple[int, list[str]]:
    return 258, []


def _estimate_image_default(
    filestore: "FileStore", inference_service: str
) -> tuple[int, list[str]]:
    warnings = [
        f"Image '{getattr(filestore, '_path', 'unknown')}': no provider-specific image estimator "
        f"for '{inference_service}' — using fixed estimate of 1000 tokens."
    ]
    return 1000, warnings


def _estimate_image(
    filestore: "FileStore", inference_service: str
) -> tuple[int, list[str]]:
    if inference_service in ("openai", "openai_v2", "anthropic"):
        return _estimate_image_openai(filestore, inference_service)
    elif inference_service == "google":
        return _estimate_image_google(filestore, inference_service)
    else:
        return _estimate_image_default(filestore, inference_service)


def _estimate_audio_video(
    filestore: "FileStore", inference_service: str
) -> tuple[int, list[str]]:
    warnings = [
        f"File '{getattr(filestore, '_path', 'unknown')}' (type: {filestore.mime_type}): "
        f"audio/video token estimation not supported — contributing 0 tokens. "
        f"Use token_overrides to set manually."
    ]
    return 0, warnings


def _estimate_offloaded(
    filestore: "FileStore",
    inference_service: str,
    chars_per_token: int = EDSL_DEFAULT_CHARS_PER_TOKEN,
) -> tuple[int, list[str]]:
    size = getattr(filestore, "size", 0) or 0
    tokens = max(0, size // chars_per_token)
    warnings = [
        f"File '{getattr(filestore, '_path', 'unknown')}' is offloaded — "
        f"estimating from file size ({size} bytes → {tokens} tokens)."
    ]
    return tokens, warnings


def _estimate_unknown(
    filestore: "FileStore", inference_service: str
) -> tuple[int, list[str]]:
    warnings = [
        f"File '{getattr(filestore, '_path', 'unknown')}' has unknown MIME type "
        f"'{filestore.mime_type}' — contributing 0 tokens."
    ]
    return 0, warnings


# ------------------------------------------------------------------
# FileStoreEstimator


class FileStoreEstimator:
    """Estimates input tokens contributed by a FileStore object.

    Dispatches by MIME type. Receives inference_service so that image estimators
    can apply the correct provider-specific formula.

    Args:
        overrides: dict mapping mime_type -> callable(filestore, inference_service) -> (int, list[str]).
                   Merged over built-in dispatch; only the types you specify are changed.
    """

    def __init__(
        self,
        overrides: dict[str, Callable] | None = None,
        chars_per_token: int = EDSL_DEFAULT_CHARS_PER_TOKEN,
    ):
        self._overrides = overrides or {}
        self.chars_per_token = chars_per_token

    @property
    def chars_per_token_overrides(self) -> dict[str, int]:
        return {
            mime: estimator.chars_per_token
            for mime, estimator in self._overrides.items()
            if hasattr(estimator, "chars_per_token")
            and estimator.chars_per_token != self.chars_per_token
        }

    def estimate(
        self, filestore: "FileStore", inference_service: str
    ) -> tuple[int, list[str]]:
        """Return (token_count, warnings) for the given FileStore."""
        mime = getattr(filestore, "mime_type", "") or ""

        # Check overrides first
        if mime in self._overrides:
            return self._overrides[mime](filestore, inference_service)

        # Offloaded content
        if getattr(filestore, "base64_string", None) == "offloaded":
            return _estimate_offloaded(
                filestore, inference_service, self.chars_per_token
            )

        # extracted_text covers text, PDF, Word, CSV, markdown, etc.
        extracted = getattr(filestore, "extracted_text", None)
        if extracted:
            return _estimate_text_file(
                filestore, inference_service, self.chars_per_token
            )

        # Images
        if mime.startswith("image/"):
            return _estimate_image(filestore, inference_service)

        # Audio / video
        if mime.startswith("audio/") or mime.startswith("video/"):
            return _estimate_audio_video(filestore, inference_service)

        # Binary files with no extracted text — fall back to size
        if getattr(filestore, "binary", False):
            size = getattr(filestore, "size", 0) or 0
            tokens = max(0, size // self.chars_per_token)
            warnings = [
                f"File '{getattr(filestore, '_path', 'unknown')}' (binary, {mime}): "
                f"estimating from file size → {tokens} tokens."
            ]
            return tokens, warnings

        return _estimate_unknown(filestore, inference_service)
