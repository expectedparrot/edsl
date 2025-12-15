"""
Text cleanup processor for structural fixes only.
"""

import re
from typing import Dict, Any, Optional
from edsl.questions import Question
from .base_processor import BaseProcessor, ProcessingResult


class TextCleanupProcessor(BaseProcessor):
    """Processor that cleans up question text for structural issues only."""

    async def process(
        self, question: Question, context: Optional[Dict[str, Any]] = None
    ) -> ProcessingResult:
        """
        Process question text and options for structural cleanup.

        Args:
            question: Question to process
            context: Optional context data

        Returns:
            ProcessingResult with cleaned text and options if needed
        """
        original_text = question.question_text
        cleaned_text = self._clean_text(original_text)

        # Also clean question options if they exist
        original_options = None
        cleaned_options = None
        options_changed = False

        if hasattr(question, "question_options") and question.question_options:
            original_options = list(question.question_options)
            cleaned_options = [
                self._clean_text(str(option)) for option in original_options
            ]
            options_changed = cleaned_options != [str(opt) for opt in original_options]

        text_changed = cleaned_text != original_text

        if text_changed or options_changed:
            changes = []
            if text_changed:
                self.log("Cleaned question text")
                changes.append(
                    {
                        "type": "text_cleaned",
                        "original": original_text,
                        "new": cleaned_text,
                    }
                )

            if options_changed:
                self.log("Cleaned question options")
                changes.append(
                    {
                        "type": "options_cleaned",
                        "original": original_options,
                        "new": cleaned_options,
                    }
                )

            # Create new question with cleaned text and/or options
            question_dict = question.to_dict()
            if text_changed:
                question_dict["question_text"] = cleaned_text
            if options_changed:
                question_dict["question_options"] = cleaned_options

            try:
                question_class = type(question)
                improved_question = question_class.from_dict(question_dict)
                return ProcessingResult(
                    question=improved_question,
                    changed=True,
                    changes=changes,
                    confidence=0.9,
                    reasoning="Fixed structural text and/or option encoding issues",
                )
            except Exception as e:
                self.log(f"Failed to create question with cleaned text/options: {e}")

        return ProcessingResult(
            question=question,
            changed=False,
            changes=[],
            confidence=1.0,
            reasoning="Text and options don't need structural cleanup",
        )

    def _clean_text(self, text: str) -> str:
        """
        Clean text for structural issues only.

        IMPORTANT: This should ONLY fix technical/structural problems,
        NOT grammar, spelling, or style issues.

        Args:
            text: Original text

        Returns:
            Cleaned text
        """
        if not text:
            return text

        cleaned = text

        # Remove common CSV export artifacts
        cleaned = self._remove_csv_artifacts(cleaned)

        # Fix truncation issues
        cleaned = self._fix_truncation(cleaned)

        # Clean up whitespace
        cleaned = self._normalize_whitespace(cleaned)

        # Remove duplicate instructions
        cleaned = self._remove_duplicate_instructions(cleaned)

        return cleaned

    def _remove_csv_artifacts(self, text: str) -> str:
        """Remove common CSV export artifacts."""
        # Remove HTML entities that got exported literally
        text = re.sub(r"&nbsp;", " ", text)
        text = re.sub(r"&amp;", "&", text)
        text = re.sub(r"&lt;", "<", text)
        text = re.sub(r"&gt;", ">", text)
        text = re.sub(r"&quot;", '"', text)

        # Remove CSV escaping artifacts
        text = re.sub(r'""', '"', text)  # Double quotes from CSV escaping

        # Remove encoding issues
        text = re.sub(r"â€™", "'", text)  # Smart quote encoding issue
        text = re.sub(r"â€œ", '"', text)  # Left double quote
        text = re.sub(r"â€\x9d", '"', text)  # Right double quote

        return text

    def _fix_truncation(self, text: str) -> str:
        """Fix obvious truncation issues."""
        # If text ends abruptly mid-sentence or with truncation indicators
        if text.endswith("...") or text.endswith("â€¦"):
            # This is truncated, but we can't recover the missing text
            # Just clean up the ending
            text = re.sub(r"(â€¦|\.\.\.)$", "", text).strip()

        # Fix common truncation patterns in Qualtrics exports
        # e.g., "Please select one." often gets exported as "Please select one"
        if re.search(r"\w$", text) and not text.endswith((".", "?", "!")):
            # Ends with a word character but no punctuation
            # Check if it looks like it should have punctuation
            if any(
                phrase in text.lower()
                for phrase in ["please select", "choose one", "pick one", "indicate"]
            ):
                text += "."

        return text

    def _normalize_whitespace(self, text: str) -> str:
        """Normalize whitespace without changing meaning."""
        # Replace multiple spaces with single space
        text = re.sub(r" +", " ", text)

        # Replace various whitespace characters with regular spaces
        text = re.sub(r"[\t\n\r\f\v]+", " ", text)

        # Remove leading/trailing whitespace
        text = text.strip()

        return text

    def _remove_duplicate_instructions(self, text: str) -> str:
        """Remove duplicate instruction patterns."""
        # Common duplications from Qualtrics exports
        duplications = [
            (r"(Please select one\.?)\s*Please select one\.?", r"\1"),
            (r"(Choose one\.?)\s*Choose one\.?", r"\1"),
            (r"(Select all that apply\.?)\s*Select all that apply\.?", r"\1"),
        ]

        for pattern, replacement in duplications:
            text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

        return text
