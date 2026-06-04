from __future__ import annotations


class OpenAIImageEstimator:
    """Estimates token cost for images sent to OpenAI models.

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
                f"OpenAI patch formula: 32px patches, x{multiplier} multiplier "
                f"(budget: {patch_budget} patches)"
            )
        tile_cfg = self._lookup(model_name, self.TILE_CONFIG)
        base, tile_cost = tile_cfg if tile_cfg else self.TILE_DEFAULT
        return (
            f"OpenAI tile formula: fit to 2048x2048 -> shortest side 768px -> "
            f"512px tiles ({tile_cost} tokens/tile + {base} base)"
        )


class GoogleImageEstimator:
    """Estimates token cost for images sent to Google Gemini models.

    - Both dimensions <= 384px -> 258 tokens (flat).
    - Larger images are tiled: crop_unit = floor(min(w, h) / 1.5),
      tiles = ceil(w / crop_unit) x ceil(h / crop_unit), cost = tiles x 258.

    Example: 960x540 -> crop_unit=360 -> 3x2=6 tiles -> 1,548 tokens.

    Reference: https://ai.google.dev/gemini-api/docs/image-understanding#technical-details-image
    """

    TOKENS_PER_TILE = 258
    SMALL_IMAGE_THRESHOLD = 384

    def estimate(self, width: int, height: int) -> int:
        import math

        if width <= self.SMALL_IMAGE_THRESHOLD and height <= self.SMALL_IMAGE_THRESHOLD:
            return self.TOKENS_PER_TILE
        crop_unit = math.floor(min(width, height) / 1.5)
        tiles = math.ceil(width / crop_unit) * math.ceil(height / crop_unit)
        return tiles * self.TOKENS_PER_TILE

    def describe(self) -> str:
        return (
            f"Google tile formula: images <= 384px -> {self.TOKENS_PER_TILE} tokens; "
            f"larger images tiled at crop_unit=floor(short_edge/1.5), {self.TOKENS_PER_TILE} tokens/tile"
        )


class AnthropicImageEstimator:
    """Estimates token cost for images sent to Anthropic models.

    Formula: tokens = round(width x height / 750), after scaling the long edge
    down to the model's limit if needed, capped at the model's token maximum.

    Two tiers:
    - Opus 4.7 / 4.8+: long edge <= 2576px, cap at 4784 tokens
    - All other models: long edge <= 1568px, cap at 1568 tokens

    Reference: https://platform.claude.com/docs/en/build-with-claude/vision
    """

    # Models with high-resolution support (long-prefix match)
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
                f"Anthropic high-res formula: width x height / 750, "
                f"long edge capped at {self.HIGH_RES_MAX_LONG_EDGE}px, "
                f"max {self.HIGH_RES_MAX_TOKENS} tokens"
            )
        return (
            f"Anthropic standard formula: width x height / 750, "
            f"long edge capped at {self.STANDARD_MAX_LONG_EDGE}px, "
            f"max {self.STANDARD_MAX_TOKENS} tokens"
        )
