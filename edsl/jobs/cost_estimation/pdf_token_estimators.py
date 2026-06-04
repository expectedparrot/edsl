from __future__ import annotations


class OpenAIPDFEstimator:
    """Estimates token cost for PDFs sent to OpenAI models.

    Two model families behave differently:

    gpt-4.x — additive: page visual rendering + text tokenization are separate charges.
        tokens = FIXED_OVERHEAD + pages x 80 + len(text) / 4.0

    gpt-5.x — the high per-page rate already accounts for text rendering; text
        tokenization only wins when content is very dense. Uses max(page, text).
        tokens = max(FIXED_OVERHEAD + pages x 850, FIXED_OVERHEAD + len(text) / 2.8)

    Reasoning models (o1, o3, o4-mini) receive extracted text only;
    tokens = len(extracted_text) / chars_per_token.

    All rates are empirically derived. DEFAULT_PAGE_COUNT used when page count is
    unavailable. Defaults are gpt-5.x rates (conservative — more expensive family).
    """

    FIXED_OVERHEAD = 230

    TOKENS_PER_PAGE: dict[str, int] = {
        "gpt-5": 850,  # observed ~831 on text-heavy; rounded up for safety
        "gpt-4": 80,  # observed ~77, rounded up
    }
    DEFAULT_TOKENS_PER_PAGE = 850

    # gpt-4 uses additive (page visual + text are separate charges).
    # gpt-5 uses max (high page rate already covers text rendering).
    ADDITIVE_PREFIXES: tuple[str, ...] = ("gpt-4",)

    TEXT_CHARS_PER_TOKEN: dict[str, float] = {
        "gpt-5": 2.8,  # observed ~2.89; rounded down to overestimate
        "gpt-4": 4.0,  # standard GPT-4 tokenizer
    }
    DEFAULT_TEXT_CHARS_PER_TOKEN = 2.8

    DEFAULT_PAGE_COUNT = 5
    REASONING_PREFIXES: tuple[str, ...] = ("o1", "o3", "o4-mini")

    def _is_reasoning(self, model_name: str | None) -> bool:
        if not model_name:
            return False
        return any(model_name.startswith(p) for p in self.REASONING_PREFIXES)

    def _is_additive(self, model_name: str | None) -> bool:
        if not model_name:
            return False
        return any(model_name.startswith(p) for p in self.ADDITIVE_PREFIXES)

    def _tokens_per_page(self, model_name: str | None) -> int:
        if not model_name:
            return self.DEFAULT_TOKENS_PER_PAGE
        for prefix in sorted(self.TOKENS_PER_PAGE, key=len, reverse=True):
            if model_name.startswith(prefix):
                return self.TOKENS_PER_PAGE[prefix]
        return self.DEFAULT_TOKENS_PER_PAGE

    def _text_chars_per_token(self, model_name: str | None) -> float:
        if not model_name:
            return self.DEFAULT_TEXT_CHARS_PER_TOKEN
        for prefix in sorted(self.TEXT_CHARS_PER_TOKEN, key=len, reverse=True):
            if model_name.startswith(prefix):
                return self.TEXT_CHARS_PER_TOKEN[prefix]
        return self.DEFAULT_TEXT_CHARS_PER_TOKEN

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
        tpp = self._tokens_per_page(model_name)
        page_component = pages * tpp
        if extracted_text:
            cpt = self._text_chars_per_token(model_name)
            text_component = int(len(extracted_text) / cpt)
            if self._is_additive(model_name):
                return self.FIXED_OVERHEAD + page_component + text_component
            return max(
                self.FIXED_OVERHEAD + page_component,
                self.FIXED_OVERHEAD + text_component,
            )
        return self.FIXED_OVERHEAD + page_component

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
        page_component = pages * tpp
        if extracted_text:
            cpt = self._text_chars_per_token(model_name)
            text_component = int(len(extracted_text) / cpt)
            if self._is_additive(model_name):
                total = self.FIXED_OVERHEAD + page_component + text_component
                return (
                    f"OpenAI PDF: {self.FIXED_OVERHEAD} fixed + {pages} pages x {tpp}/page + "
                    f"{len(extracted_text)} chars ÷ {cpt} = {total} tokens{page_note}"
                )
            if text_component > page_component:
                text_total = self.FIXED_OVERHEAD + text_component
                return (
                    f"OpenAI PDF: extracted text ({len(extracted_text)} chars ÷ {cpt} "
                    f"+ {self.FIXED_OVERHEAD} overhead = {text_total} tokens)"
                )
        return (
            f"OpenAI PDF via Files API: {self.FIXED_OVERHEAD} fixed + "
            f"{pages} pages x {tpp} tokens/page{page_note}"
        )


class AnthropicPDFEstimator:
    """Estimates token cost for PDFs sent to Anthropic models.

    Anthropic charges for both page visual rendering AND text tokenization additively:
        tokens = FIXED_OVERHEAD + pages x TOKENS_PER_PAGE + len(text) / TEXT_CHARS_PER_TOKEN

    Empirically derived rates (all models consistent):
        Fixed overhead:  40 tokens
        Per-page rate:  1,580 tokens/page
        Text rate:      2.7 chars/token (conservative — cross-validated on two PDFs;
                        overestimates both opus and sonnet by 1-8%)

    DEFAULT_PAGE_COUNT is used when page count cannot be determined.
    """

    FIXED_OVERHEAD = 40
    TOKENS_PER_PAGE = 1580
    DEFAULT_PAGE_COUNT = 5
    # Empirically ~2.7-3.1 chars/token across PDFs; use 2.7 to slightly overestimate.
    TEXT_CHARS_PER_TOKEN = 2.7

    def estimate(
        self, num_pages: int | None = None, extracted_text: str | None = None
    ) -> int:
        pages = num_pages if num_pages is not None else self.DEFAULT_PAGE_COUNT
        page_component = pages * self.TOKENS_PER_PAGE
        if extracted_text:
            text_component = int(len(extracted_text) / self.TEXT_CHARS_PER_TOKEN)
            return self.FIXED_OVERHEAD + page_component + text_component
        return self.FIXED_OVERHEAD + page_component

    def describe(
        self, num_pages: int | None = None, extracted_text: str | None = None
    ) -> str:
        pages = num_pages if num_pages is not None else self.DEFAULT_PAGE_COUNT
        page_note = (
            ""
            if num_pages is not None
            else f" (page count unavailable; using default {self.DEFAULT_PAGE_COUNT})"
        )
        if extracted_text:
            text_component = int(len(extracted_text) / self.TEXT_CHARS_PER_TOKEN)
            total = self.FIXED_OVERHEAD + pages * self.TOKENS_PER_PAGE + text_component
            return (
                f"Anthropic PDF: {self.FIXED_OVERHEAD} fixed + {pages} pages x {self.TOKENS_PER_PAGE}/page + "
                f"{len(extracted_text)} chars ÷ {self.TEXT_CHARS_PER_TOKEN} = {total} tokens{page_note}"
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
