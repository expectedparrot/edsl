import pytest
from edsl.questions.exceptions import QuestionAnswerValidationError
from edsl.questions import QuestionDropdown
from edsl.questions.question_dropdown import QuestionDropdown


# Valid question configurations for testing
valid_question = {
    "question_text": "Which city would you like to visit?",
    "question_options": ["New York", "Paris", "Tokyo", "London", "Sydney", "Rome"],
    "question_name": "city_choice",
}

valid_question_with_details = {
    "question_text": "Which restaurant would you prefer?",
    "question_options": ["Mario's Pizza", "Sushi Zen", "Burger Palace"],
    "question_options_details": [
        "Authentic Italian pizza with wood-fired oven",
        "Traditional Japanese sushi with fresh fish",
        "American-style burgers with premium beef"
    ],
    "question_name": "restaurant_choice",
    "sample_indices": [0, 1, 2],
    "max_options_shown": 2,
}

large_question = {
    "question_text": "Choose your preferred programming language",
    "question_options": [
        "Python", "JavaScript", "Java", "C++", "C#", "Ruby", "Go", "Rust",
        "Swift", "Kotlin", "PHP", "TypeScript", "Scala", "Clojure", "Haskell",
        "Perl", "R", "MATLAB", "Julia", "Dart", "Objective-C", "Assembly",
        "COBOL", "Fortran", "Ada", "Lisp", "Prolog", "Erlang", "F#", "VB.NET"
    ],
    "question_name": "language_choice",
    "sample_indices": [0, 5, 10, 15, 20],
    "max_options_shown": 5,
}


def test_QuestionDropdown_construction():
    """Test QuestionDropdown construction with various configurations."""

    # Basic construction
    q = QuestionDropdown(**valid_question)
    assert isinstance(q, QuestionDropdown)
    assert q.question_text == valid_question["question_text"]
    assert q.question_options == valid_question["question_options"]
    assert q.question_name == valid_question["question_name"]

    # Default sample_indices should be first 10 options (or all if fewer than 10)
    assert q.sample_indices == [0, 1, 2, 3, 4, 5]
    assert q.max_options_shown == 5  # default

    # Construction with details
    q_with_details = QuestionDropdown(**valid_question_with_details)
    assert isinstance(q_with_details, QuestionDropdown)
    assert q_with_details.question_options_details == valid_question_with_details["question_options_details"]
    assert q_with_details.sample_indices == [0, 1, 2]
    assert q_with_details.max_options_shown == 2

    # Large question with custom sample indices
    q_large = QuestionDropdown(**large_question)
    assert q_large.sample_indices == [0, 5, 10, 15, 20]
    assert q_large.max_options_shown == 5


def test_QuestionDropdown_construction_errors():
    """Test QuestionDropdown construction error cases."""

    # Missing question_text
    invalid_question = valid_question.copy()
    invalid_question.pop("question_text")
    with pytest.raises(Exception):
        QuestionDropdown(**invalid_question)

    # Empty question_text
    invalid_question = valid_question.copy()
    invalid_question.update({"question_text": ""})
    with pytest.raises(Exception):
        QuestionDropdown(**invalid_question)

    # Missing question_options
    invalid_question = valid_question.copy()
    invalid_question.pop("question_options")
    with pytest.raises(Exception):
        QuestionDropdown(**invalid_question)

    # Empty question_options
    invalid_question = valid_question.copy()
    invalid_question.update({"question_options": []})
    with pytest.raises(Exception):
        QuestionDropdown(**invalid_question)

    # Mismatched question_options_details length
    invalid_question = valid_question.copy()
    invalid_question.update({
        "question_options_details": ["Detail 1", "Detail 2"]  # Only 2 details for 6 options
    })
    with pytest.raises(ValueError, match="question_options_details must have same length"):
        QuestionDropdown(**invalid_question)

    # Invalid sample_indices (negative)
    invalid_question = valid_question.copy()
    invalid_question.update({"sample_indices": [-1, 0, 1]})
    with pytest.raises(ValueError, match="Invalid sample indices"):
        QuestionDropdown(**invalid_question)

    # Invalid sample_indices (out of range)
    invalid_question = valid_question.copy()
    invalid_question.update({"sample_indices": [0, 1, 10]})  # Index 10 doesn't exist
    with pytest.raises(ValueError, match="Invalid sample indices"):
        QuestionDropdown(**invalid_question)


def test_QuestionDropdown_sample_options():
    """Test sample option selection functionality."""

    # Test default sample indices (first 10 or all if fewer)
    q = QuestionDropdown(**valid_question)
    sample_options = q._get_sample_options()
    assert sample_options == ["New York", "Paris", "Tokyo", "London", "Sydney", "Rome"]

    # Test custom sample indices
    q_custom = QuestionDropdown(**large_question)
    sample_options = q_custom._get_sample_options()
    expected = ["Python", "Ruby", "PHP", "Perl", "Objective-C"]
    assert sample_options == expected

    # Test with sample_indices=None (should default to first 10)
    q_none = QuestionDropdown(
        question_name="test",
        question_text="Test question",
        question_options=large_question["question_options"],
        sample_indices=None
    )
    expected_default = large_question["question_options"][:10]
    assert q_none._get_sample_options() == expected_default


def test_QuestionDropdown_bm25_search():
    """Test BM25 search functionality."""

    # Test basic search
    q = QuestionDropdown(**valid_question)

    # Test search with relevant keywords
    results = q.perform_bm25_search("big city urban", verbose=False)
    assert isinstance(results, list)
    assert len(results) <= q.max_options_shown
    assert all(result in [str(opt) for opt in q.question_options] for result in results)

    # Test empty search terms
    results_empty = q.perform_bm25_search("", verbose=False)
    assert len(results_empty) <= q.max_options_shown

    # Test with top_k = 1 (similar to former feeling_lucky mode)
    limited_question = valid_question_with_details.copy()
    limited_question["top_k"] = 1
    q_limited = QuestionDropdown(**limited_question)
    results_limited = q_limited.perform_bm25_search("pizza italian", verbose=False)
    assert len(results_limited) == 1  # Should return only one result

    # Test search with details
    q_with_details = QuestionDropdown(**valid_question_with_details)
    results_with_details = q_with_details.perform_bm25_search("authentic traditional", verbose=False)
    assert isinstance(results_with_details, list)


def test_QuestionDropdown_response_model():
    """Test response model creation."""

    q = QuestionDropdown(**valid_question)

    # Test without use_code
    response_model = q.create_response_model()
    assert response_model is not None

    # Test with use_code
    q_with_code = QuestionDropdown(use_code=True, **valid_question)
    response_model_code = q_with_code.create_response_model()
    assert response_model_code is not None


def test_QuestionDropdown_answer_translation():
    """Test answer code translation functionality."""

    q = QuestionDropdown(**valid_question)

    # Test without use_code
    answer = "Paris"
    translated = q._translate_answer_code_to_answer(answer, {})
    assert translated == answer

    # Test with use_code
    q_with_code = QuestionDropdown(use_code=True, **valid_question)
    answer_code = 1  # Should correspond to "Paris"
    translated_code = q_with_code._translate_answer_code_to_answer(answer_code, {})
    assert translated_code == "Paris"

    # Test invalid code
    with pytest.raises(Exception):
        q_with_code._translate_answer_code_to_answer(999, {})


def test_QuestionDropdown_simulation():
    """Test answer simulation functionality."""

    q = QuestionDropdown(**valid_question)

    # Test answer simulation
    simulated = q._simulate_answer()
    assert isinstance(simulated, dict)
    assert "answer" in simulated

    if q._include_comment:
        assert "comment" in simulated

    # Test with details
    q_with_details = QuestionDropdown(**valid_question_with_details)
    simulated_with_details = q_with_details._simulate_answer()
    assert isinstance(simulated_with_details, dict)
    assert "answer" in simulated_with_details


def test_QuestionDropdown_html_content():
    """Test HTML content generation."""

    q = QuestionDropdown(**valid_question)
    html_content = q.question_html_content
    assert isinstance(html_content, str)
    assert "dropdown-question" in html_content
    assert q.question_text in html_content
    assert str(len(q.question_options)) in html_content


def test_QuestionDropdown_example():
    """Test example method."""

    q = QuestionDropdown.example()
    assert isinstance(q, QuestionDropdown)
    assert q.question_name == "city_preference"
    assert len(q.question_options) > 10  # Should be a large list
    assert q.question_options_details is not None
    assert len(q.question_options_details) == len(q.question_options)

    # Test example with different parameters
    q_no_comment = QuestionDropdown.example(include_comment=False)
    assert q_no_comment._include_comment == False

    q_with_code = QuestionDropdown.example(use_code=True)
    assert q_with_code.use_code == True


def test_QuestionDropdown_validator():
    """Test response validator functionality."""

    q = QuestionDropdown(**valid_question)
    validator = q.response_validator

    # Test valid response
    valid_response = {"answer": "Paris", "comment": "Great city!"}
    fixed_response = validator.fix(valid_response)
    # The validator might return a list or string
    answer = fixed_response["answer"]
    if isinstance(answer, list):
        assert "Paris" in answer
    else:
        assert answer == "Paris"

    # Test response that needs fixing (case sensitivity)
    case_response = {"answer": "paris"}
    fixed_case = validator.fix(case_response)
    # Should either return original or fix to "Paris"
    assert isinstance(fixed_case, dict)


def test_QuestionDropdown_question_type():
    """Test question type and purpose."""

    q = QuestionDropdown(**valid_question)
    assert q.question_type == "dropdown"
    assert q.purpose == "When options are numerous and need to be searched"


def test_QuestionDropdown_serialization():
    """Test serialization and deserialization."""

    q = QuestionDropdown(**valid_question_with_details)

    # Test to_dict
    q_dict = q.to_dict()
    assert isinstance(q_dict, dict)
    assert q_dict["question_type"] == "dropdown"
    assert q_dict["question_text"] == q.question_text

    # Test from_dict
    q_restored = QuestionDropdown.from_dict(q_dict)
    assert isinstance(q_restored, QuestionDropdown)
    assert q_restored.question_text == q.question_text
    assert q_restored.question_options == q.question_options
    assert q_restored.sample_indices == q.sample_indices


def test_QuestionDropdown_clean_nan():
    """Test NaN cleaning functionality."""

    import math

    options_with_nan = ["Option1", float('nan'), "Option3"]
    q = QuestionDropdown(
        question_name="test_nan",
        question_text="Test NaN cleaning",
        question_options=options_with_nan
    )

    # NaN should be replaced with None
    assert q.question_options == ["Option1", None, "Option3"]


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])