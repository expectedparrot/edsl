from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel

# Google reports roughly this many output tokens for a single generated image.
# Used as a fallback when the provider response omits usage metadata so that a
# generated image still carries a non-zero cost.
FALLBACK_OUTPUT_TOKENS_PER_IMAGE = 1290


class GeneratedImage(BaseModel):
    """A generated image plus provider metadata."""

    base64_string: str
    mime_type: str = "image/png"
    model: Optional[str] = None
    service_name: Optional[str] = None
    prompt: Optional[str] = None
    raw_response: Optional[dict[str, Any]] = None
    # Normalized provider token usage, using edsl's Google field names
    # (prompt_token_count / candidates_token_count / thoughts_token_count).
    usage: Optional[dict[str, Any]] = None

    def token_usage(self) -> dict[str, Optional[int]]:
        """Return input/output/thinking token counts for cost calculation.

        Reads the normalized ``usage`` metadata when present. When the provider
        omits usage, falls back to a per-image output-token estimate and a
        prompt-length-based input estimate so the image is still priced.
        """
        usage = self.usage or {}
        input_tokens = usage.get("prompt_token_count")
        output_tokens = usage.get("candidates_token_count")
        thinking_tokens = usage.get("thoughts_token_count")

        if not output_tokens:
            output_tokens = FALLBACK_OUTPUT_TOKENS_PER_IMAGE
        if not input_tokens:
            # Rough estimate: ~4 characters per token.
            input_tokens = max(1, len(self.prompt or "") // 4)

        return {
            "input_tokens": int(input_tokens),
            "output_tokens": int(output_tokens),
            "thinking_tokens": int(thinking_tokens) if thinking_tokens else None,
        }

    def cost(self):
        """Compute a ResponseCost for this image, priced against its own model.

        Attributes cost to the image service/model (e.g. google /
        gemini-3.1-flash-image) rather than the interview's default model.
        """
        from ..language_models.price_manager import PriceManager

        usage = self.token_usage()
        return PriceManager().calculate_cost(
            inference_service=self.service_name,
            model=self.model,
            usage=usage,
            input_token_name="input_tokens",
            output_token_name="output_tokens",
        )

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
