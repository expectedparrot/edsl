from __future__ import annotations
import base64
from abc import ABC, abstractmethod
from typing import Callable, TYPE_CHECKING

from .cost_estimation_constants import EDSL_DEFAULT_CHARS_PER_TOKEN
from .image_token_estimators import (
    AnthropicImageEstimator,
    GoogleImageEstimator,
    OpenAIImageEstimator,
)
from .pdf_token_estimators import (
    AnthropicPDFEstimator,
    GooglePDFEstimator,
    OpenAIPDFEstimator,
)

if TYPE_CHECKING:
    from ...scenarios import FileStore


# ------------------------------------------------------------------
# Per-type estimators


class FileTypeEstimator(ABC):
    """Base class for per-MIME-type token estimators."""

    def estimate(
        self,
        filestore: "FileStore",
        inference_service: str,
        model_name: str | None = None,
    ) -> tuple[int, list[str]]:
        if getattr(filestore, "base64_string", None) == "offloaded":
            return self.estimate_offloaded(filestore, inference_service, model_name)
        return self.estimate_inline(filestore, inference_service, model_name)

    @abstractmethod
    def estimate_inline(
        self,
        filestore: "FileStore",
        inference_service: str,
        model_name: str | None = None,
    ) -> tuple[int, list[str]]: ...

    def estimate_offloaded(
        self,
        filestore: "FileStore",
        inference_service: str,
        model_name: str | None = None,
    ) -> tuple[int, list[str]]:
        path = getattr(filestore, "_path", "unknown")
        size = getattr(filestore, "size", 0) or 0
        tokens = max(0, size // EDSL_DEFAULT_CHARS_PER_TOKEN)
        return tokens, [
            f"File '{path}' is offloaded — estimating from file size ({size} bytes → {tokens} tokens)."
        ]


class TextEstimator(FileTypeEstimator):
    def __init__(self, chars_per_token: int = EDSL_DEFAULT_CHARS_PER_TOKEN):
        self.chars_per_token = chars_per_token

    def estimate_inline(self, filestore, inference_service, model_name=None):
        text = getattr(filestore, "extracted_text", None)
        if text:
            return max(1, len(text) // self.chars_per_token), []
        size = getattr(filestore, "size", 0) or 0
        return max(1, size // self.chars_per_token), []

    def describe(self) -> str:
        return f"Character count ÷ {self.chars_per_token} chars/token (from extracted text or file size)"


class ImageEstimator(FileTypeEstimator):
    def __init__(self, restore_offloaded: bool = True):
        self.restore_offloaded = restore_offloaded
        self._dimensions_cache: dict[str, tuple[int, int]] = {}

    def _cache_key(self, filestore: "FileStore") -> str | None:
        ext = getattr(filestore, "external_locations", {}) or {}
        uuid = (ext.get("gcs") or {}).get("file_uuid")
        return str(uuid) if uuid else getattr(filestore, "_path", None)

    def _tokens_from_dimensions(
        self, width: int, height: int, inference_service: str, model_name: str | None
    ) -> tuple[int, list[str]]:
        if inference_service in ("openai", "openai_v2"):
            return OpenAIImageEstimator().estimate(width, height, model_name), []
        elif inference_service == "anthropic":
            return AnthropicImageEstimator().estimate(width, height, model_name), []
        elif inference_service == "google":
            return GoogleImageEstimator().estimate(width, height), []
        return 1000, [
            f"No provider-specific image formula for '{inference_service}' — using 1,000 tokens."
        ]

    def estimate_inline(self, filestore, inference_service, model_name=None):
        path = getattr(filestore, "_path", "unknown")
        try:
            width, height = filestore.get_image_dimensions()
        except ImportError:
            return 1000, [
                f"Image '{path}': PIL not available — using fixed estimate of 1,000 tokens."
            ]
        except Exception as e:
            return 1000, [
                f"Image '{path}': could not get dimensions ({e}) — using fixed estimate of 1,000 tokens."
            ]
        return self._tokens_from_dimensions(
            width, height, inference_service, model_name
        )

    def estimate_offloaded(self, filestore, inference_service, model_name=None):
        path = getattr(filestore, "_path", "unknown")
        key = self._cache_key(filestore)

        if key and key in self._dimensions_cache:
            width, height = self._dimensions_cache[key]
        elif not self.restore_offloaded:
            return 1000, [
                f"Image '{path}' is offloaded — restore disabled, using 1,000 tokens."
            ]
        else:
            try:
                width, height = filestore.get_image_dimensions()
                print(f"Restored offloaded image '{path}' from GCS ({width}×{height})")
                if key:
                    self._dimensions_cache[key] = (width, height)
            except Exception as e:
                return 1000, [
                    f"Image '{path}' is offloaded — GCS restore failed ({e}), using 1,000 tokens."
                ]

        return self._tokens_from_dimensions(
            width, height, inference_service, model_name
        )

    def describe(self, inference_service: str, model_name: str | None = None) -> str:
        if inference_service in ("openai", "openai_v2"):
            return OpenAIImageEstimator().describe(model_name)
        elif inference_service == "anthropic":
            return AnthropicImageEstimator().describe(model_name)
        elif inference_service == "google":
            return GoogleImageEstimator().describe()
        return "Fixed fallback: 1,000 tokens (no provider-specific formula)"


class PdfEstimator(FileTypeEstimator):
    def __init__(
        self,
        restore_offloaded: bool = True,
        chars_per_token: int = EDSL_DEFAULT_CHARS_PER_TOKEN,
    ):
        self.restore_offloaded = restore_offloaded
        self.chars_per_token = chars_per_token
        self._page_count_cache: dict[str, int] = {}

    def _cache_key(self, filestore: "FileStore") -> str | None:
        ext = getattr(filestore, "external_locations", {}) or {}
        uuid = (ext.get("gcs") or {}).get("file_uuid")
        return str(uuid) if uuid else getattr(filestore, "_path", None)

    def _get_page_count(self, filestore: "FileStore") -> int | None:
        try:
            from ...scenarios.handlers.pdf_file_store import count_pdf_pages_from_bytes

            return count_pdf_pages_from_bytes(base64.b64decode(filestore.base64_string))
        except Exception:
            return None

    def _tokens_from_pages(
        self,
        filestore: "FileStore",
        inference_service: str,
        model_name: str | None,
        num_pages: int | None,
    ) -> tuple[int, list[str]]:
        extracted = getattr(filestore, "extracted_text", None)
        if inference_service in ("openai", "openai_v2"):
            tokens = OpenAIPDFEstimator().estimate(
                model_name=model_name,
                num_pages=num_pages,
                extracted_text=extracted,
                chars_per_token=self.chars_per_token,
            )
            return tokens, []
        if inference_service == "anthropic":
            return (
                AnthropicPDFEstimator().estimate(
                    num_pages=num_pages, extracted_text=extracted
                ),
                [],
            )
        if inference_service == "google":
            return GooglePDFEstimator().estimate(num_pages=num_pages), []
        # Other services: extracted text or size-based fallback
        if extracted:
            return max(1, len(extracted) // self.chars_per_token), []
        size = getattr(filestore, "size", 0) or 0
        return max(0, size // self.chars_per_token), []

    def estimate_inline(self, filestore, inference_service, model_name=None):
        key = self._cache_key(filestore)
        if key and key in self._page_count_cache:
            num_pages = self._page_count_cache[key]
        else:
            num_pages = self._get_page_count(filestore)
            if key and num_pages is not None:
                self._page_count_cache[key] = num_pages
        return self._tokens_from_pages(
            filestore, inference_service, model_name, num_pages
        )

    def estimate_offloaded(self, filestore, inference_service, model_name=None):
        path = getattr(filestore, "_path", "unknown")
        key = self._cache_key(filestore)

        if key and key in self._page_count_cache:
            return self._tokens_from_pages(
                filestore, inference_service, model_name, self._page_count_cache[key]
            )

        if not self.restore_offloaded:
            tokens, warnings = self._tokens_from_pages(
                filestore, inference_service, model_name, None
            )
            return tokens, warnings + [
                f"PDF '{path}' is offloaded — restore disabled, "
                f"using default {OpenAIPDFEstimator.DEFAULT_PAGE_COUNT} pages."
            ]

        try:
            _ = filestore.path  # triggers _restore_from_gcs
            if getattr(filestore, "base64_string", None) != "offloaded":
                num_pages = self._get_page_count(filestore)
                if key and num_pages is not None:
                    self._page_count_cache[key] = num_pages
                print(f"Restored offloaded PDF '{path}' from GCS ({num_pages} pages)")
                return self._tokens_from_pages(
                    filestore, inference_service, model_name, num_pages
                )
        except Exception:
            pass

        tokens, warnings = self._tokens_from_pages(
            filestore, inference_service, model_name, None
        )
        return tokens, warnings + [
            f"PDF '{path}' is offloaded — GCS restore failed, "
            f"using default {OpenAIPDFEstimator.DEFAULT_PAGE_COUNT} pages."
        ]

    def describe(
        self,
        inference_service: str,
        model_name: str | None = None,
        num_pages: int | None = None,
        extracted_text: str | None = None,
    ) -> str:
        if inference_service in ("openai", "openai_v2"):
            return OpenAIPDFEstimator().describe(
                model_name=model_name,
                num_pages=num_pages,
                extracted_text=extracted_text,
            )
        if inference_service == "anthropic":
            return AnthropicPDFEstimator().describe(
                num_pages=num_pages, extracted_text=extracted_text
            )
        if inference_service == "google":
            return GooglePDFEstimator().describe(num_pages=num_pages)
        return f"Character count / {self.chars_per_token} chars/token (from extracted text or file size)"


class AudioVideoEstimator(FileTypeEstimator):
    def estimate_inline(self, filestore, inference_service, model_name=None):
        return self._warn(filestore)

    def estimate_offloaded(self, filestore, inference_service, model_name=None):
        return self._warn(filestore)

    @staticmethod
    def _warn(filestore) -> tuple[int, list[str]]:
        path = getattr(filestore, "_path", "unknown")
        mime = getattr(filestore, "mime_type", "unknown")
        return 0, [
            f"File '{path}' (type: {mime}): audio/video token estimation not supported — "
            f"contributing 0 tokens. Use token_overrides to set manually."
        ]


# ------------------------------------------------------------------
# FileStoreEstimator


class FileStoreEstimator:
    """Estimates input tokens contributed by a FileStore object.

    Dispatches by MIME type. Receives inference_service and model_name so that
    image estimators can apply the correct provider- and model-specific formula.

    Args:
        overrides: dict mapping mime_type -> callable(filestore, inference_service) -> (int, list[str]).
                   Merged over built-in dispatch; only the types you specify are changed.
        restore_offloaded_files: if True, offloaded images are restored from GCS to get
                   real dimensions. Set False to skip network calls and use a 1,000-token fallback.
    """

    def __init__(
        self,
        overrides: dict[str, Callable] | None = None,
        chars_per_token: int = EDSL_DEFAULT_CHARS_PER_TOKEN,
        restore_offloaded_files: bool = True,
    ):
        self._overrides = overrides or {}
        self.chars_per_token = chars_per_token
        self._text = TextEstimator(chars_per_token)
        self._image = ImageEstimator(restore_offloaded=restore_offloaded_files)
        self._pdf = PdfEstimator(
            restore_offloaded=restore_offloaded_files,
            chars_per_token=chars_per_token,
        )
        self._audio_video = AudioVideoEstimator()

    @property
    def chars_per_token_overrides(self) -> dict[str, int]:
        return {
            mime: estimator.chars_per_token
            for mime, estimator in self._overrides.items()
            if hasattr(estimator, "chars_per_token")
            and estimator.chars_per_token != self.chars_per_token
        }

    def describe(self) -> str:
        return (
            f"Text/document files: character count / {self.chars_per_token} chars/token (from extracted content). "
            "PDFs (OpenAI): pages x image formula (Files API) or extracted text (reasoning models). "
            "Images: tile/patch formula (OpenAI), width x height / 750 (Anthropic), or crop-unit tile formula (Google). "
            "Audio/video: not estimated — 0 tokens (see warnings)."
        )

    def describe_for(
        self,
        mime_type: str,
        inference_service: str,
        model_name: str | None = None,
    ) -> str:
        if mime_type in self._overrides:
            return "Custom estimator (override)"
        if mime_type.startswith("image/"):
            return self._image.describe(inference_service, model_name)
        if mime_type == "application/pdf":
            return self._pdf.describe(inference_service, model_name)
        if mime_type.startswith("audio/") or mime_type.startswith("video/"):
            return "Not estimated — 0 tokens (use token_overrides to set manually)"
        return self._text.describe()

    def describe_for_file(
        self,
        filestore: "FileStore",
        inference_service: str,
        model_name: str | None = None,
    ) -> str:
        """Description of how this specific file was estimated (cache-aware)."""
        mime = getattr(filestore, "mime_type", "") or ""

        if mime == "application/pdf":
            key = self._pdf._cache_key(filestore)
            num_pages = self._pdf._page_count_cache.get(key) if key else None
            extracted = getattr(filestore, "extracted_text", None)
            return self._pdf.describe(
                inference_service,
                model_name,
                num_pages=num_pages,
                extracted_text=extracted,
            )

        key = self._image._cache_key(filestore)

        if key and key in self._image._dimensions_cache:
            return self.describe_for(mime, inference_service, model_name)

        if getattr(filestore, "base64_string", None) == "offloaded":
            if mime.startswith("image/"):
                if self._image.restore_offloaded:
                    return (
                        "fixed estimate: 1,000 tokens (offloaded — GCS restore failed)"
                    )
                return "fixed estimate: 1,000 tokens (offloaded — restore disabled)"
            return "estimated from file size (offloaded)"

        return self.describe_for(mime, inference_service, model_name)

    def estimate(
        self,
        filestore: "FileStore",
        inference_service: str,
        model_name: str | None = None,
    ) -> tuple[int, list[str]]:
        """Return (token_count, warnings) for the given FileStore."""
        mime = getattr(filestore, "mime_type", "") or ""

        if mime in self._overrides:
            return self._overrides[mime](filestore, inference_service)

        if mime.startswith("image/"):
            return self._image.estimate(filestore, inference_service, model_name)

        if mime == "application/pdf":
            return self._pdf.estimate(filestore, inference_service, model_name)

        if mime.startswith("audio/") or mime.startswith("video/"):
            return self._audio_video.estimate(filestore, inference_service, model_name)

        # extracted_text covers Word, CSV, markdown, etc. (non-PDF docs with text)
        extracted = getattr(filestore, "extracted_text", None)
        if extracted:
            return self._text.estimate(filestore, inference_service, model_name)

        # Binary files with no extracted text — fall back to size
        if getattr(filestore, "binary", False):
            size = getattr(filestore, "size", 0) or 0
            tokens = max(0, size // self.chars_per_token)
            return tokens, [
                f"File '{getattr(filestore, '_path', 'unknown')}' (binary, {mime}): "
                f"estimating from file size → {tokens} tokens."
            ]

        # Offloaded non-image, non-audio/video with no extracted text
        if getattr(filestore, "base64_string", None) == "offloaded":
            return self._text.estimate_offloaded(
                filestore, inference_service, model_name
            )

        return 0, [
            f"File '{getattr(filestore, '_path', 'unknown')}' has unknown MIME type "
            f"'{mime}' — contributing 0 tokens."
        ]
