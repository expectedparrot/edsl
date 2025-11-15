"""Support for analyzing comment fields as if they were questions.

Comments are free-text fields associated with each question response.
This module allows them to be analyzed using the same Report/analyze interface.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from edsl.results import Results


class CommentField:
    """Represents a comment field as a pseudo-question for analysis purposes.

    Comments are always free text, so this class mimics a free_text Question.
    """

    def __init__(self, field_name: str, question_name: str):
        """Initialize a CommentField.

        Args:
            field_name: The full comment field name (e.g., "how_feeling_comment")
            question_name: The associated question name (e.g., "how_feeling")
        """
        self.question_name = field_name
        self.question_type = "free_text"
        self.question_text = f"Comment for '{question_name}'"
        self._associated_question = question_name
        self._is_comment_field = True  # Marker for identifying comment fields

    def __repr__(self):
        return f"CommentField('{self.question_name}')"


def is_comment_field(field_name: str) -> bool:
    """Check if a field name refers to a comment field.

    Args:
        field_name: The field name to check (e.g., "how_feeling_comment" or "comment.how_feeling_comment")

    Returns:
        True if the field name is a comment field

    Examples:
        >>> is_comment_field("how_feeling_comment")
        True
        >>> is_comment_field("comment.how_feeling_comment")
        True
        >>> is_comment_field("how_feeling")
        False
    """
    if field_name.startswith("comment."):
        return True
    if field_name.endswith("_comment"):
        return True
    return False


def normalize_comment_field(field_name: str) -> str:
    """Normalize a comment field name to the short form.

    Args:
        field_name: The field name (e.g., "how_feeling_comment" or "comment.how_feeling_comment")

    Returns:
        The normalized field name (e.g., "how_feeling_comment")

    Examples:
        >>> normalize_comment_field("comment.how_feeling_comment")
        'how_feeling_comment'
        >>> normalize_comment_field("how_feeling_comment")
        'how_feeling_comment'
    """
    if field_name.startswith("comment."):
        return field_name[len("comment."):]
    return field_name


def extract_question_name_from_comment(comment_field: str) -> str:
    """Extract the base question name from a comment field name.

    Args:
        comment_field: The comment field name (e.g., "how_feeling_comment")

    Returns:
        The base question name (e.g., "how_feeling")

    Examples:
        >>> extract_question_name_from_comment("how_feeling_comment")
        'how_feeling'
        >>> extract_question_name_from_comment("comment.how_feeling_comment")
        'how_feeling'
    """
    normalized = normalize_comment_field(comment_field)
    if normalized.endswith("_comment"):
        return normalized[:-len("_comment")]
    return normalized


def get_available_comment_fields(results: "Results") -> list[str]:
    """Get all available comment field names from a Results object.

    Args:
        results: The Results object to inspect

    Returns:
        List of comment field names in short form (e.g., ["how_feeling_comment", ...])
    """
    comment_columns = [col for col in results.columns if col.startswith("comment.")]
    return [normalize_comment_field(col) for col in comment_columns]


def create_comment_field(field_name: str, results: "Results") -> CommentField:
    """Create a CommentField object for analysis.

    Args:
        field_name: The comment field name (e.g., "how_feeling_comment" or "comment.how_feeling_comment")
        results: The Results object containing the comments

    Returns:
        A CommentField object that can be used like a Question

    Raises:
        ValueError: If the field name is not a valid comment field
    """
    if not is_comment_field(field_name):
        raise ValueError(f"'{field_name}' is not a valid comment field name")

    normalized = normalize_comment_field(field_name)
    full_column_name = f"comment.{normalized}"

    # Verify the column exists
    if full_column_name not in results.columns:
        available = get_available_comment_fields(results)
        raise ValueError(
            f"Comment field '{field_name}' not found in results. "
            f"Available comment fields: {available}"
        )

    question_name = extract_question_name_from_comment(field_name)
    return CommentField(normalized, question_name)


def get_data_column_name(question_or_field) -> str:
    """Get the correct column name for accessing data from a question or comment field.

    Args:
        question_or_field: Either a Question object or a CommentField object

    Returns:
        The column prefix and name (e.g., "answer.how_feeling" or "comment.how_feeling_comment")

    Examples:
        >>> # For a regular question
        >>> get_data_column_name(question)  # Returns "answer.how_feeling"
        >>> # For a comment field
        >>> get_data_column_name(comment_field)  # Returns "comment.how_feeling_comment"
    """
    # Check if this is a comment field
    if hasattr(question_or_field, "_is_comment_field") and question_or_field._is_comment_field:
        return f"comment.{question_or_field.question_name}"
    else:
        return f"answer.{question_or_field.question_name}"
