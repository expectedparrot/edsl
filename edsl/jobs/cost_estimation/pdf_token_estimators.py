from __future__ import annotations


class OpenAIPDFEstimator:
    """Estimates token cost for PDFs sent to OpenAI models.

    OpenAI's Files API charges a fixed overhead per document plus a per-page rate
    that varies by model family. Rates are empirically derived:

        Fixed overhead:  230 tokens (model-independent)
        gpt-4o family:   80 tokens/page
        gpt-5.x family: 780 tokens/page

    Reasoning models (o1, o3, o4-mini) receive extracted text instead of rendered
    pages; tokens = len(extracted_text) / chars_per_token in that case.

    DEFAULT_PAGE_COUNT is used when page count cannot be determined (e.g. offloaded).
    Default per-page rate is gpt-5.x (conservative — more expensive family).
    """

    # Fixed overhead charged per document regardless of page count (~229 observed, rounded up)
    FIXED_OVERHEAD = 230

    # Empirically derived per-page rates, keyed by model name prefix.
    # Longest-prefix match; falls back to DEFAULT_TOKENS_PER_PAGE.
    TOKENS_PER_PAGE: dict[str, int] = {
        "gpt-5": 780,  # observed ~779, rounded up
        "gpt-4": 80,  # observed ~77, rounded up
    }
    DEFAULT_TOKENS_PER_PAGE = 780

    DEFAULT_PAGE_COUNT = 5
    REASONING_PREFIXES: tuple[str, ...] = ("o1", "o3", "o4-mini")

    def _is_reasoning(self, model_name: str | None) -> bool:
        if not model_name:
            return False
        return any(model_name.startswith(p) for p in self.REASONING_PREFIXES)

    def _tokens_per_page(self, model_name: str | None) -> int:
        if not model_name:
            return self.DEFAULT_TOKENS_PER_PAGE
        for prefix in sorted(self.TOKENS_PER_PAGE, key=len, reverse=True):
            if model_name.startswith(prefix):
                return self.TOKENS_PER_PAGE[prefix]
        return self.DEFAULT_TOKENS_PER_PAGE

    def estimate(
        self,
        model_name: str | None = None,
        num_pages: int | None = None,
        extracted_text: str | None = None,
        chars_per_token: int = 4,
    ) -> int:
        pages = num_pages if num_pages is not None else self.DEFAULT_PAGE_COUNT
        if self._is_reasoning(model_name) and extracted_text:
            return max(1, len(extracted_text) // chars_per_token)
        return self.FIXED_OVERHEAD + pages * self._tokens_per_page(model_name)

    def describe(
        self,
        model_name: str | None = None,
        num_pages: int | None = None,
        extracted_text: str | None = None,
        chars_per_token: int = 4,
    ) -> str:
        pages = num_pages if num_pages is not None else self.DEFAULT_PAGE_COUNT
        page_note = (
            ""
            if num_pages is not None
            else f" (page count unavailable; using default {self.DEFAULT_PAGE_COUNT})"
        )
        if self._is_reasoning(model_name) and extracted_text:
            return (
                f"OpenAI reasoning PDF: extracted text "
                f"({len(extracted_text)} chars / {chars_per_token} chars/token)"
            )
        tpp = self._tokens_per_page(model_name)
        return (
            f"OpenAI PDF via Files API: {self.FIXED_OVERHEAD} fixed + "
            f"{pages} pages x {tpp} tokens/page{page_note}"
        )


class AnthropicPDFEstimator:
    """Estimates token cost for PDFs sent to Anthropic models.

    Anthropic processes PDFs as document content blocks. Each page is rendered
    and charged at the vision formula rate (width x height / 750), capped at
    1,568 tokens/page for standard models. Empirically, most pages hit the cap.

    Empirically derived rates (all models consistent):
        Fixed overhead:  40 tokens (document preamble, rounded up from ~37)
        Per-page rate: 1,580 tokens/page (rounded up from ~1,574)

    DEFAULT_PAGE_COUNT is used when page count cannot be determined.
    """

    FIXED_OVERHEAD = 40
    TOKENS_PER_PAGE = 1580
    DEFAULT_PAGE_COUNT = 5

    def estimate(self, num_pages: int | None = None) -> int:
        pages = num_pages if num_pages is not None else self.DEFAULT_PAGE_COUNT
        return self.FIXED_OVERHEAD + pages * self.TOKENS_PER_PAGE

    def describe(self, num_pages: int | None = None) -> str:
        pages = num_pages if num_pages is not None else self.DEFAULT_PAGE_COUNT
        page_note = (
            ""
            if num_pages is not None
            else f" (page count unavailable; using default {self.DEFAULT_PAGE_COUNT})"
        )
        return (
            f"Anthropic PDF: {self.FIXED_OVERHEAD} fixed + "
            f"{pages} pages x {self.TOKENS_PER_PAGE} tokens/page{page_note}"
        )


class GooglePDFEstimator:
    """Estimates token cost for PDFs sent to Google Gemini models.

    Empirically derived (model-independent — all Gemini models consistent):
        No fixed overhead
        535 tokens/page (observed ~532, rounded up)

    DEFAULT_PAGE_COUNT is used when page count cannot be determined.
    """

    TOKENS_PER_PAGE = 535
    DEFAULT_PAGE_COUNT = 5

    def estimate(self, num_pages: int | None = None) -> int:
        pages = num_pages if num_pages is not None else self.DEFAULT_PAGE_COUNT
        return pages * self.TOKENS_PER_PAGE

    def describe(self, num_pages: int | None = None) -> str:
        pages = num_pages if num_pages is not None else self.DEFAULT_PAGE_COUNT
        page_note = (
            ""
            if num_pages is not None
            else f" (page count unavailable; using default {self.DEFAULT_PAGE_COUNT})"
        )
        return (
            f"Google PDF: {pages} pages x {self.TOKENS_PER_PAGE} tokens/page{page_note}"
        )
