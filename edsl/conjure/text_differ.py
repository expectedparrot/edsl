"""
Module for finding varying parts in a list of similar texts.

Uses tokenization to compare texts and find positions where they differ,
without relying on regex patterns.
"""

from dataclasses import dataclass
from typing import List
import re


@dataclass
class SlotInfo:
    """Information about a slot (varying part) in templated text."""

    name: str  # Variable name: "x", "y", "z", etc.
    position: int  # Token position where the slot occurs
    values_per_row: List[str]  # Value for each row
    unique_values: List[str]  # Unique values found


@dataclass
class TemplateResult:
    """Result of extracting a template from varying texts."""

    template: str  # Text with {{ scenario.x }} placeholders
    slots: List[SlotInfo]  # Information about each slot


def tokenize(text: str) -> List[str]:
    """
    Split text into tokens, preserving whitespace structure.

    Tokens are split on whitespace boundaries, keeping punctuation attached.
    """
    # Split on whitespace but keep the structure
    return text.split()


def find_varying_positions(token_lists: List[List[str]]) -> List[int]:
    """
    Find token positions where texts differ.

    Args:
        token_lists: List of tokenized texts (each is a list of tokens)

    Returns:
        List of positions (indices) where tokens vary across texts
    """
    if not token_lists or len(token_lists) < 2:
        return []

    # Find the minimum length (in case texts have different token counts)
    min_len = min(len(tokens) for tokens in token_lists)

    varying_positions = []

    for pos in range(min_len):
        # Get all tokens at this position
        tokens_at_pos = [tokens[pos] for tokens in token_lists if pos < len(tokens)]

        # Check if they're all the same
        unique_tokens = set(tokens_at_pos)
        if len(unique_tokens) > 1:
            varying_positions.append(pos)

    return varying_positions


def extract_template(texts: List[str]) -> TemplateResult | None:
    """
    Extract a template from a list of similar texts by finding varying parts.

    Args:
        texts: List of similar texts that differ in certain positions

    Returns:
        TemplateResult with template string and slot information,
        or None if no varying parts found

    Example:
        Input: [
            "Would you buy for $800 per year?",
            "Would you buy for $900 per year?",
            "Would you buy for $1000 per year?"
        ]
        Output: TemplateResult(
            template="Would you buy for {{ scenario.x }} per year?",
            slots=[SlotInfo(name="x", values_per_row=["$800", "$900", "$1000"], ...)]
        )
    """
    if not texts or len(texts) < 2:
        return None

    # Filter out empty strings
    non_empty = [t for t in texts if t and t.strip()]
    if len(non_empty) < 2:
        return None

    # Get unique texts to analyze
    unique_texts = list(set(non_empty))
    if len(unique_texts) < 2:
        return None  # All texts are identical

    # Tokenize all unique texts
    unique_token_lists = [tokenize(t) for t in unique_texts]

    # Find positions where tokens vary
    varying_positions = find_varying_positions(unique_token_lists)

    if not varying_positions:
        return None

    # Now extract values for ALL texts (not just unique) at varying positions
    all_token_lists = [tokenize(t) for t in non_empty]

    # Generate variable names
    var_names = iter("xyzabcdefghijklmnopqrstuvw")
    slots = []

    for pos in varying_positions:
        var_name = next(var_names)

        # Extract value at this position for each row
        values_per_row = []
        for tokens in all_token_lists:
            if pos < len(tokens):
                values_per_row.append(tokens[pos])
            else:
                values_per_row.append("")

        # Get unique values, try to sort them sensibly
        unique_values = sorted(set(v for v in values_per_row if v), key=_sort_key)

        slots.append(
            SlotInfo(
                name=var_name,
                position=pos,
                values_per_row=values_per_row,
                unique_values=unique_values,
            )
        )

    # Build template from first unique text, replacing varying tokens
    template_tokens = list(unique_token_lists[0])  # Copy
    for slot in slots:
        if slot.position < len(template_tokens):
            template_tokens[slot.position] = f"{{{{ scenario.{slot.name} }}}}"

    template = " ".join(template_tokens)

    return TemplateResult(template=template, slots=slots)


def _sort_key(value: str):
    """
    Sort key that handles numeric values sensibly.

    Extracts numeric part from strings like "$800", "1,200", "50%" for sorting.
    """
    # Remove common prefixes/suffixes and extract number
    cleaned = re.sub(r"[^\d.]", "", value.replace(",", ""))
    try:
        return float(cleaned) if cleaned else 0
    except ValueError:
        return value  # Fall back to string sorting


def merge_adjacent_slots(result: TemplateResult) -> TemplateResult:
    """
    Merge adjacent slots that might be part of the same value.

    For example, if "$800" was tokenized as ["$800"] but "$1,200" as ["$1,200"],
    they'd be at the same position. But if a value like "10 percent" spans
    two tokens, this would merge them.

    (Currently a placeholder for future enhancement)
    """
    # For now, just return as-is
    # Could be enhanced to detect patterns like "10 percent" vs "20 percent"
    return result
