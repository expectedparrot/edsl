from __future__ import annotations
from typing import Callable, TYPE_CHECKING

from .cost_estimation_constants import EDSL_DEFAULT_CHARS_PER_TOKEN

if TYPE_CHECKING:
    from ...scenarios import FileStore


# ------------------------------------------------------------------
# OpenAI image estimator


class OpenAIImageEstimator:
    """Estimates token cost for images sent to OpenAI or Anthropic models.

    Dispatches between patch-based (gpt-4.1-mini/nano, gpt-5-mini/nano, o4-mini)
    and tile-based (gpt-4o, gpt-4.1, o1, o3, …) tokenization based on model name.
    Falls back to GPT-4o defaults (85 base + 170/tile) when the model is unknown.

    Reference: https://developers.openai.com/api/docs/guides/images-vision#calculating-costs
    """

    # Tile-based config: model_prefix -> (base_tokens, tile_tokens)
    # Fit to 2048×2048 → scale shortest side to 768px → count 512px tiles
    TILE_CONFIG: dict[str, tuple[int, int]] = {
        "gpt-5-chat-latest": (70, 140),
        "gpt-5": (70, 140),
        "gpt-4.5": (85, 170),
        "gpt-4.1": (85, 170),
        "gpt-4o-mini": (2833, 5667),
        "gpt-4o": (85, 170),
        "o1": (75, 150),
        "o3": (75, 150),
        "computer-use-preview": (65, 129),
    }

    # Patch-based config: model_prefix -> (multiplier, patch_budget)
    # Cover with 32px patches → shrink to fit budget → apply multiplier
    PATCH_CONFIG: dict[str, tuple[float, int]] = {
        "gpt-5.4-mini": (1.62, 1536),
        "gpt-5.4-nano": (2.46, 1536),
        "gpt-5-mini": (1.62, 1536),
        "gpt-5-nano": (2.46, 1536),
        "gpt-4.1-mini": (1.62, 1536),
        "gpt-4.1-nano": (2.46, 1536),
        "o4-mini": (1.72, 1536),
    }

    TILE_DEFAULT: tuple[int, int] = (85, 170)  # GPT-4o fallback

    @classmethod
    def _lookup(cls, model_name: str | None, config: dict) -> tuple | None:
        """Longest-prefix match. Returns None if no match."""
        if not model_name:
            return None
        if model_name in config:
            return config[model_name]
        for key in sorted(config, key=len, reverse=True):
            if model_name.startswith(key):
                return config[key]
        return None

    @staticmethod
    def _tile_tokens(width: int, height: int, base: int, tile_cost: int) -> int:
        import math

        scale = min(1.0, 2048 / max(width, height))
        w, h = int(width * scale), int(height * scale)
        scale2 = 768 / min(w, h)
        w, h = int(w * scale2), int(h * scale2)
        tiles = math.ceil(w / 512) * math.ceil(h / 512)
        return base + tile_cost * tiles

    @staticmethod
    def _patch_tokens(
        width: int, height: int, multiplier: float, patch_budget: int
    ) -> int:
        import math

        original = math.ceil(width / 32) * math.ceil(height / 32)
        if original <= patch_budget:
            resized = original
        else:
            shrink = math.sqrt((32**2 * patch_budget) / (width * height))
            adjusted = shrink * min(
                math.floor(width * shrink / 32) / (width * shrink / 32),
                math.floor(height * shrink / 32) / (height * shrink / 32),
            )
            rw, rh = int(width * adjusted), int(height * adjusted)
            resized = min(patch_budget, math.ceil(rw / 32) * math.ceil(rh / 32))
        return round(resized * multiplier)

    def estimate(self, width: int, height: int, model_name: str | None = None) -> int:
        patch_cfg = self._lookup(model_name, self.PATCH_CONFIG)
        if patch_cfg:
            multiplier, patch_budget = patch_cfg
            return self._patch_tokens(width, height, multiplier, patch_budget)
        tile_cfg = self._lookup(model_name, self.TILE_CONFIG)
        base, tile_cost = tile_cfg if tile_cfg else self.TILE_DEFAULT
        return self._tile_tokens(width, height, base, tile_cost)

    def describe(self, model_name: str | None = None) -> str:
        patch_cfg = self._lookup(model_name, self.PATCH_CONFIG)
        if patch_cfg:
            multiplier, patch_budget = patch_cfg
            return (
                f"OpenAI patch formula: 32px patches, ×{multiplier} multiplier "
                f"(budget: {patch_budget} patches)"
            )
        tile_cfg = self._lookup(model_name, self.TILE_CONFIG)
        base, tile_cost = tile_cfg if tile_cfg else self.TILE_DEFAULT
        return (
            f"OpenAI tile formula: fit to 2048×2048 → shortest side 768px → "
            f"512px tiles ({tile_cost} tokens/tile + {base} base)"
        )


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
    filestore: "FileStore",
    inference_service: str,
    model_name: str | None = None,
) -> tuple[int, list[str]]:
    warnings = []
    try:
        width, height = filestore.get_image_dimensions()
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
    return OpenAIImageEstimator().estimate(width, height, model_name), warnings


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
    filestore: "FileStore",
    inference_service: str,
    model_name: str | None = None,
) -> tuple[int, list[str]]:
    if inference_service in ("openai", "openai_v2", "anthropic"):
        return _estimate_image_openai(filestore, inference_service, model_name)
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
    path = getattr(filestore, "_path", "unknown")
    size = getattr(filestore, "size", 0) or 0
    tokens = max(0, size // chars_per_token)
    return tokens, [
        f"File '{path}' is offloaded — estimating from file size ({size} bytes → {tokens} tokens)."
    ]


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
        self.restore_offloaded_files = restore_offloaded_files
        self._file_metadata: dict[str, dict] = {}

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
            f"Text/document files: character count ÷ {self.chars_per_token} chars/token (from extracted content). "
            "Images: model-specific tile or patch formula (OpenAI/Anthropic) or flat rate (Google, 258 tokens/image). "
            "Audio/video: not estimated — 0 tokens (see warnings)."
        )

    def _file_cache_key(self, filestore: "FileStore") -> str | None:
        ext = getattr(filestore, "external_locations", {}) or {}
        gcs = ext.get("gcs", {}) or {}
        uuid = gcs.get("file_uuid")
        if uuid:
            return str(uuid)
        return getattr(filestore, "_path", None)

    def _estimate_offloaded_image(
        self,
        filestore: "FileStore",
        inference_service: str,
        model_name: str | None = None,
    ) -> tuple[int, list[str]]:
        path = getattr(filestore, "_path", "unknown")
        key = self._file_cache_key(filestore)

        if key and key in self._file_metadata:
            meta = self._file_metadata[key]
            width, height = meta["width"], meta["height"]
        elif not self.restore_offloaded_files:
            return 1000, [
                f"Image '{path}' is offloaded — restore_offloaded_files=False, "
                f"using fixed estimate of 1,000 tokens."
            ]
        else:
            try:
                width, height = filestore.get_image_dimensions()
                print(f"Restored offloaded image '{path}' from GCS ({width}×{height})")
                if key is not None:
                    self._file_metadata[key] = {
                        "type": "image",
                        "width": width,
                        "height": height,
                    }
            except Exception as e:
                return 1000, [
                    f"Image '{path}' is offloaded — could not restore from GCS ({e}), "
                    f"using fixed estimate of 1,000 tokens."
                ]

        if inference_service in ("openai", "openai_v2", "anthropic"):
            return OpenAIImageEstimator().estimate(width, height, model_name), []
        elif inference_service == "google":
            return 258, []
        else:
            return 1000, [
                f"Image '{path}': no provider-specific formula for '{inference_service}' — "
                f"using fixed estimate of 1,000 tokens."
            ]

    def describe_for(
        self,
        mime_type: str,
        inference_service: str,
        model_name: str | None = None,
    ) -> str:
        if mime_type in self._overrides:
            return "Custom estimator (override)"
        if mime_type.startswith("image/"):
            if inference_service in ("openai", "openai_v2", "anthropic"):
                return OpenAIImageEstimator().describe(model_name)
            elif inference_service == "google":
                return "Google flat rate: 258 tokens per image"
            else:
                return "Fixed fallback: 1,000 tokens (no provider-specific formula)"
        if mime_type.startswith("audio/") or mime_type.startswith("video/"):
            return "Not estimated — 0 tokens (use token_overrides to set manually)"
        return f"Character count ÷ {self.chars_per_token} chars/token (from extracted text or file size)"

    def describe_for_file(
        self,
        filestore: "FileStore",
        inference_service: str,
        model_name: str | None = None,
    ) -> str:
        """Description of how this specific file was estimated (cache-aware)."""
        mime = getattr(filestore, "mime_type", "") or ""
        key = self._file_cache_key(filestore)

        if key and key in self._file_metadata:
            return self.describe_for(mime, inference_service, model_name)

        if getattr(filestore, "base64_string", None) == "offloaded":
            if mime.startswith("image/"):
                if self.restore_offloaded_files:
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

        # Check overrides first
        if mime in self._overrides:
            return self._overrides[mime](filestore, inference_service)

        # Offloaded content
        if getattr(filestore, "base64_string", None) == "offloaded":
            if mime.startswith("image/"):
                return self._estimate_offloaded_image(
                    filestore, inference_service, model_name
                )
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
            return _estimate_image(filestore, inference_service, model_name)

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
