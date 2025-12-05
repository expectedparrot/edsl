"""
Tests for the text_differ module.
"""

import pytest
from edsl.conjure.text_differ import (
    tokenize,
    find_varying_positions,
    extract_template,
    SlotInfo,
    TemplateResult,
)


class TestTokenize:
    """Tests for the tokenize function."""
    
    def test_simple_sentence(self):
        result = tokenize("Would you buy for $800?")
        assert result == ["Would", "you", "buy", "for", "$800?"]
    
    def test_empty_string(self):
        result = tokenize("")
        assert result == []  # split() on empty string returns empty list
    
    def test_single_word(self):
        result = tokenize("Hello")
        assert result == ["Hello"]
    
    def test_multiple_spaces(self):
        # split() handles multiple spaces
        result = tokenize("Hello   world")
        assert result == ["Hello", "world"]


class TestFindVaryingPositions:
    """Tests for the find_varying_positions function."""
    
    def test_single_varying_position(self):
        tokens = [
            ["Would", "you", "buy", "for", "$800"],
            ["Would", "you", "buy", "for", "$900"],
            ["Would", "you", "buy", "for", "$1000"],
        ]
        result = find_varying_positions(tokens)
        assert result == [4]
    
    def test_multiple_varying_positions(self):
        tokens = [
            ["Buy", "$800", "for", "1", "year"],
            ["Buy", "$900", "for", "2", "years"],
            ["Buy", "$1000", "for", "3", "years"],
        ]
        result = find_varying_positions(tokens)
        assert result == [1, 3, 4]  # $price, number, year/years
    
    def test_no_variation(self):
        tokens = [
            ["Hello", "world"],
            ["Hello", "world"],
            ["Hello", "world"],
        ]
        result = find_varying_positions(tokens)
        assert result == []
    
    def test_empty_list(self):
        result = find_varying_positions([])
        assert result == []
    
    def test_single_token_list(self):
        result = find_varying_positions([["Hello", "world"]])
        assert result == []


class TestExtractTemplate:
    """Tests for the main extract_template function."""
    
    def test_price_variation(self):
        """Basic test with price varying."""
        texts = [
            "Would you buy for $800 per year?",
            "Would you buy for $900 per year?",
            "Would you buy for $1000 per year?",
        ]
        result = extract_template(texts)
        
        assert result is not None
        assert "{{ scenario.x }}" in result.template
        assert len(result.slots) == 1
        assert result.slots[0].name == "x"
        assert set(result.slots[0].unique_values) == {"$800", "$900", "$1000"}
    
    def test_price_with_comma(self):
        """Test with comma-formatted prices like $1,200."""
        texts = [
            "Would you buy for $800 per year?",
            "Would you buy for $1,200 per year?",
        ]
        result = extract_template(texts)
        
        assert result is not None
        assert "{{ scenario.x }}" in result.template
        assert "$1,200" in result.slots[0].unique_values
    
    def test_multiple_slots(self):
        """Test with multiple varying parts."""
        texts = [
            "Buy product A for $100",
            "Buy product B for $200",
            "Buy product C for $300",
        ]
        result = extract_template(texts)
        
        assert result is not None
        assert len(result.slots) == 2
        # First slot should be product name (A, B, C)
        # Second slot should be price ($100, $200, $300)
        slot_names = {s.name for s in result.slots}
        assert slot_names == {"x", "y"}
    
    def test_no_variation_returns_none(self):
        """When all texts are identical, should return None."""
        texts = [
            "Same text here",
            "Same text here",
            "Same text here",
        ]
        result = extract_template(texts)
        assert result is None
    
    def test_single_text_returns_none(self):
        """Single text can't have variation."""
        texts = ["Only one text"]
        result = extract_template(texts)
        assert result is None
    
    def test_empty_list_returns_none(self):
        """Empty list should return None."""
        result = extract_template([])
        assert result is None
    
    def test_empty_strings_filtered(self):
        """Empty strings should be filtered out."""
        texts = [
            "",
            "Would you buy for $800?",
            "",
            "Would you buy for $900?",
        ]
        result = extract_template(texts)
        
        assert result is not None
        assert "{{ scenario.x }}" in result.template
    
    def test_whitespace_only_filtered(self):
        """Whitespace-only strings should be filtered out."""
        texts = [
            "   ",
            "Would you buy for $800?",
            "Would you buy for $900?",
        ]
        result = extract_template(texts)
        
        assert result is not None
    
    def test_non_numeric_variation(self):
        """Test with non-numeric varying parts."""
        texts = [
            "What color do you prefer: red?",
            "What color do you prefer: blue?",
            "What color do you prefer: green?",
        ]
        result = extract_template(texts)
        
        assert result is not None
        assert "{{ scenario.x }}" in result.template
        assert set(result.slots[0].unique_values) == {"red?", "blue?", "green?"}
    
    def test_values_per_row_preserves_duplicates(self):
        """values_per_row should have one entry per input text."""
        texts = [
            "Price: $800",
            "Price: $900",
            "Price: $800",  # Duplicate
            "Price: $1000",
        ]
        result = extract_template(texts)
        
        assert result is not None
        # values_per_row should have 4 entries (one per non-empty text)
        assert len(result.slots[0].values_per_row) == 4
        # unique_values should have 3 entries
        assert len(result.slots[0].unique_values) == 3
    
    def test_long_question_text(self):
        """Test with realistic long survey question."""
        base = """If you were offered cloud-based takeoff software that lets you:

measure lines, areas, and counts right in your browser
auto name and auto link documents
use basic automation takeoff assistance

Would you purchase it for {} per user per year (USD)?"""
        
        texts = [
            base.format("$800"),
            base.format("$900"),
            base.format("$1000"),
            base.format("$1,100"),
            base.format("$1,200"),
        ]
        result = extract_template(texts)
        
        assert result is not None
        assert "{{ scenario.x }}" in result.template
        assert len(result.slots) == 1
        # Check that all prices were captured
        prices = set(result.slots[0].unique_values)
        assert "$800" in prices
        assert "$1,200" in prices
    
    def test_template_structure_preserved(self):
        """Template should preserve the structure of the original text."""
        texts = [
            "Hello Alice, welcome!",
            "Hello Bob, welcome!",
            "Hello Charlie, welcome!",
        ]
        result = extract_template(texts)
        
        assert result is not None
        assert result.template == "Hello {{ scenario.x }} welcome!"
    
    def test_numeric_sorting(self):
        """unique_values should be sorted numerically when possible."""
        texts = [
            "Price: $1000",
            "Price: $800",
            "Price: $1,200",
            "Price: $900",
        ]
        result = extract_template(texts)
        
        assert result is not None
        # Should be sorted: $800, $900, $1000, $1,200
        values = result.slots[0].unique_values
        assert values[0] == "$800"
        assert values[-1] == "$1,200"


class TestEdgeCases:
    """Edge case tests."""
    
    def test_all_different_texts(self):
        """When texts are completely different."""
        texts = [
            "Apple banana cherry",
            "Dog elephant fox",
            "Guitar harmonica instrument",
        ]
        result = extract_template(texts)
        
        # Should find all positions as varying
        assert result is not None
        assert len(result.slots) == 3
    
    def test_different_length_texts(self):
        """Texts with different numbers of tokens."""
        texts = [
            "Short text",
            "A bit longer text here",
            "Medium length text",
        ]
        result = extract_template(texts)
        
        # Should handle gracefully, finding common varying positions
        assert result is not None
    
    def test_punctuation_attached(self):
        """Punctuation stays attached to tokens."""
        texts = [
            "Is it $100?",
            "Is it $200?",
        ]
        result = extract_template(texts)
        
        assert result is not None
        # The ? should be part of the token
        assert "$100?" in result.slots[0].unique_values or "$100" in result.slots[0].unique_values


class TestSlotInfo:
    """Tests for SlotInfo structure."""
    
    def test_slot_info_fields(self):
        """Verify SlotInfo has expected fields."""
        texts = [
            "Value: A",
            "Value: B",
        ]
        result = extract_template(texts)
        
        assert result is not None
        slot = result.slots[0]
        
        assert hasattr(slot, 'name')
        assert hasattr(slot, 'position')
        assert hasattr(slot, 'values_per_row')
        assert hasattr(slot, 'unique_values')
        
        assert isinstance(slot.name, str)
        assert isinstance(slot.position, int)
        assert isinstance(slot.values_per_row, list)
        assert isinstance(slot.unique_values, list)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

