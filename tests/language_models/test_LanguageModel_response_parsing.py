from edsl.language_models import LanguageModel


def test_integrer_list_examples():
    example_1 = """[1,2,3]

    These are my comments."""

    example_2 = """[1,2,3]"""

    example_3 = """

    [1,2,3]"""

    example_4 = """


    [1,2,3]

    These are my comments.

    """

    examples = [example_1, example_2, example_3, example_4]

    for generated_tokens in examples:
        m = LanguageModel.example(test_model=True, canned_response=generated_tokens)
        raw_model_response = m.execute_model_call("", "")
        model_response = m.parse_response(raw_model_response)
        # breakpoint()
        assert model_response.answer == [1, 2, 3]
        assert (
            model_response.comment == "These are my comments."
            or model_response.comment == None
        )


def test_str_list_examples():

    example_1 = """["hello", "world"]"""

    example_1 = """["hello", "world"]
    
    These are my comments."""

    example_3 = """
    ["hello", "world"]
    
    
    There are my comments.


    """

    examples = [example_1]

    for generated_tokens in examples:
        m = LanguageModel.example(test_model=True, canned_response=generated_tokens)
        raw_model_response = m.execute_model_call("", "")
        model_response = m.parse_response(raw_model_response)
        assert model_response.answer == ["hello", "world"]
        assert (
            model_response.comment == "These are my comments."
            or model_response.comment == None
        )


# ---------------------------------------------------------------------------
# Tests for COMMENT: delimiter parsing  (GitHub issue #2133)
# ---------------------------------------------------------------------------
from edsl.language_models.raw_response_handler import RawResponseHandler


class TestSplitAnswerAndComment:
    """Unit tests for RawResponseHandler._split_answer_and_comment."""

    def test_comment_delimiter_simple(self):
        """Basic COMMENT: on its own line."""
        text = "No\nCOMMENT: The policy does not apply here."
        answer, comment = RawResponseHandler._split_answer_and_comment(text)
        assert answer == "No"
        assert comment == "The policy does not apply here."

    def test_comment_delimiter_multiline_answer(self):
        """Answer spans multiple lines; COMMENT: follows."""
        text = "Line 1\nLine 2\nLine 3\nCOMMENT: This is the real comment."
        answer, comment = RawResponseHandler._split_answer_and_comment(text)
        assert answer == "Line 1\nLine 2\nLine 3"
        assert comment == "This is the real comment."

    def test_comment_delimiter_multiline_comment(self):
        """Multi-line comment after the COMMENT: delimiter."""
        text = "No\nCOMMENT: First line of comment.\nSecond line of comment."
        answer, comment = RawResponseHandler._split_answer_and_comment(text)
        assert answer == "No"
        assert comment == "First line of comment.\nSecond line of comment."

    def test_comment_delimiter_case_insensitive(self):
        """Delimiter is matched case-insensitively."""
        text = "Yes\ncomment: I agree with this."
        answer, comment = RawResponseHandler._split_answer_and_comment(text)
        assert answer == "Yes"
        assert comment == "I agree with this."

    def test_comment_delimiter_with_leading_whitespace(self):
        """COMMENT: may be preceded by whitespace on its line."""
        text = "42\n   COMMENT: The answer is 42."
        answer, comment = RawResponseHandler._split_answer_and_comment(text)
        assert answer == "42"
        assert comment == "The answer is 42."

    def test_answer_with_newlines_no_delimiter(self):
        """No COMMENT: present — splits on first newline, rest is comment."""
        text = "No\n\nThe explanation is here."
        answer, comment = RawResponseHandler._split_answer_and_comment(text)
        assert answer == "No"
        assert comment == "The explanation is here."

    def test_no_newline_no_comment(self):
        """Single-line answer with no newline at all."""
        text = "42"
        answer, comment = RawResponseHandler._split_answer_and_comment(text)
        assert answer == "42"
        assert comment is None

    def test_bug_scenario_answer_with_newlines_and_comment(self):
        """
        The original bug: answer contains newlines AND there is a comment.
        Without COMMENT: delimiter the comment would be clipped.
        With the delimiter, both parts are correctly extracted.
        """
        text = "No\n\nI have additional thoughts.\nCOMMENT: The policy does not apply because of reason X and reason Y."
        answer, comment = RawResponseHandler._split_answer_and_comment(text)
        assert answer == "No\n\nI have additional thoughts."
        assert comment == "The policy does not apply because of reason X and reason Y."

    def test_only_comment_delimiter_no_answer(self):
        """Edge case: string starts with COMMENT: and has no answer before it."""
        text = "COMMENT: everything is a comment"
        answer, comment = RawResponseHandler._split_answer_and_comment(text)
        # Should treat whole string as answer, no comment
        assert answer == text
        assert comment is None

    def test_list_answer_with_comment_delimiter(self):
        """List answer followed by a COMMENT: delimiter."""
        text = '[1, 2, 3]\nCOMMENT: These are my choices.'
        answer, comment = RawResponseHandler._split_answer_and_comment(text)
        assert answer == "[1, 2, 3]"
        assert comment == "These are my choices."


def test_parse_response_with_comment_delimiter():
    """Integration test: full parse_response flow with COMMENT: delimiter."""
    m = LanguageModel.example(
        test_model=True,
        canned_response="No\n\nExtra line in answer\nCOMMENT: The explanation here.",
    )
    raw_model_response = m.execute_model_call("", "")
    model_response = m.parse_response(raw_model_response)
    assert model_response.answer == "No\n\nExtra line in answer"
    assert model_response.comment == "The explanation here."


def test_parse_response_legacy_no_delimiter():
    """Integration test: legacy responses without COMMENT: still work."""
    m = LanguageModel.example(
        test_model=True,
        canned_response="[1,2,3]\n\nThese are my comments.",
    )
    raw_model_response = m.execute_model_call("", "")
    model_response = m.parse_response(raw_model_response)
    assert model_response.answer == [1, 2, 3]
    assert (
        model_response.comment == "These are my comments."
        or model_response.comment is None
    )
