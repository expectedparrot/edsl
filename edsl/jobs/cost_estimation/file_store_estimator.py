from __future__ import annotations
from abc import ABC, abstractmethod
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
# Anthropic image estimator


class AnthropicImageEstimator:
    """Estimates token cost for images sent to Anthropic models.

    Formula: tokens = round(width x height / 750), after scaling the long edge
    down to the model's limit if needed, capped at the model's token maximum.

    Two tiers:
    - Opus 4.7 / 4.8+: long edge ≤ 2576px, cap at 4784 tokens
    - All other models: long edge ≤ 1568px, cap at 1568 tokens

    Reference: https://platform.claude.com/docs/en/build-with-claude/vision
    """

    # Models with high-resolution support (long-edge prefix match)
    HIGH_RES_PREFIXES: tuple[str, ...] = ("claude-opus-4-7", "claude-opus-4-8")
    HIGH_RES_MAX_LONG_EDGE = 2576
    HIGH_RES_MAX_TOKENS = 4784

    STANDARD_MAX_LONG_EDGE = 1568
    STANDARD_MAX_TOKENS = 1568

    def _is_high_res(self, model_name: str | None) -> bool:
        if not model_name:
            return False
        return any(model_name.startswith(p) for p in self.HIGH_RES_PREFIXES)

    def estimate(self, width: int, height: int, model_name: str | None = None) -> int:
        if self._is_high_res(model_name):
            max_long_edge, max_tokens = (
                self.HIGH_RES_MAX_LONG_EDGE,
                self.HIGH_RES_MAX_TOKENS,
            )
        else:
            max_long_edge, max_tokens = (
                self.STANDARD_MAX_LONG_EDGE,
                self.STANDARD_MAX_TOKENS,
            )

        long_edge = max(width, height)
        if long_edge > max_long_edge:
            scale = max_long_edge / long_edge
            width, height = int(width * scale), int(height * scale)

        return min(round(width * height / 750), max_tokens)

    def describe(self, model_name: str | None = None) -> str:
        if self._is_high_res(model_name):
            return (
                f"Anthropic high-res formula: width x height ÷ 750, "
                f"long edge capped at {self.HIGH_RES_MAX_LONG_EDGE}px, "
                f"max {self.HIGH_RES_MAX_TOKENS} tokens"
            )
        return (
            f"Anthropic standard formula: width x height ÷ 750, "
            f"long edge capped at {self.STANDARD_MAX_LONG_EDGE}px, "
            f"max {self.STANDARD_MAX_TOKENS} tokens"
        )


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
            return 258, []
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
            return "Google flat rate: 258 tokens per image"
        return "Fixed fallback: 1,000 tokens (no provider-specific formula)"


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
            f"Text/document files: character count ÷ {self.chars_per_token} chars/token (from extracted content). "
            "Images: tile/patch formula (OpenAI), width x height ÷ 750 (Anthropic), or flat rate (Google, 258 tokens/image). "
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

        if mime.startswith("audio/") or mime.startswith("video/"):
            return self._audio_video.estimate(filestore, inference_service, model_name)

        # extracted_text covers text, PDF, Word, CSV, markdown, etc.
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
