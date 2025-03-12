import pytest
from edsl.questions.exceptions import QuestionAnswerValidationError
from edsl.questions.answer_validator_mixin import AnswerValidatorMixin

class MockQuestion:
    """Base mock question class for testing"""

    def __init__(self):
        self.question_options = ["Option 1", "Option 2", "Option 3"]


class TestAnswerValidatorMixin:
    @pytest.fixture
    def validator(self):
        """Creates a basic validator instance for testing"""

        class TestValidator(AnswerValidatorMixin, MockQuestion):
            pass

        return TestValidator()

    def test_validate_answer_template_basic(self, validator):
        # Test valid cases
        valid_answers = [
            {"answer": 1},
            {"answer": {"a": 1}, "other_key": [1, 2, 3]},
            {"answer": [1, 2, 3]},
        ]
        for answer in valid_answers:
            validator._validate_answer_template_basic(answer)

        # Test invalid cases
        with pytest.raises(QuestionAnswerValidationError):
            validator._validate_answer_template_basic([1, 2, 3])  # Not a dict

        with pytest.raises(QuestionAnswerValidationError):
            validator._validate_answer_template_basic({"wrong_key": 1})  # No answer key

    def test_validate_answer_key_value(self, validator):
        answer = {"key1": "string", "key2": 123}

        # Test valid cases
        validator._validate_answer_key_value(answer, "key1", str)
        validator._validate_answer_key_value(answer, "key2", int)

        # Test invalid cases
        with pytest.raises(QuestionAnswerValidationError):
            validator._validate_answer_key_value(answer, "key1", int)

        with pytest.raises(QuestionAnswerValidationError):
            validator._validate_answer_key_value(answer, "key2", str)

    def test_validate_answer_key_value_numeric(self, validator):
        valid_answers = [
            {"value": 123},
            {"value": 123.45},
            {"value": "123"},
            {"value": "123.45"},
            {"value": "1,234"},
            {"value": "$123.45"},
        ]

        for answer in valid_answers:
            validator._validate_answer_key_value_numeric(answer, "value")

        invalid_answers = [
            {"value": "abc"},
            {"value": "12.34.56"},
            {"value": None},
            {"value": [1, 2, 3]},
        ]

        for answer in invalid_answers:
            with pytest.raises(QuestionAnswerValidationError):
                validator._validate_answer_key_value_numeric(answer, "value")

    def test_validate_answer_budget(self, validator):
        # Set up budget-specific attributes
        validator.budget_sum = 100

        # Test valid case
        valid_answer = {"answer": {0: 50, 1: 30, 2: 20}}
        validator._validate_answer_budget(valid_answer)

        # Test invalid cases
        invalid_answers = [
            {"answer": {0: 60, 1: 50}},  # Sum > budget_sum
            {"answer": {0: -10, 1: 110}},  # Negative values
            {"answer": {0: 50, 1: 50, 5: 0}},  # Invalid key
            {"answer": {0: 100}},  # Missing keys
        ]

        for answer in invalid_answers:
            with pytest.raises(QuestionAnswerValidationError):
                validator._validate_answer_budget(answer)

    def test_validate_answer_checkbox(self, validator):
        # Set up checkbox-specific attributes
        validator.min_selections = 1
        validator.max_selections = 2

        # Test valid cases
        valid_answers = [{"answer": [0]}, {"answer": [0, 1]}, {"answer": ["0", "1"]}]

        for answer in valid_answers:
            validator._validate_answer_checkbox(answer)

        # Test invalid cases
        invalid_answers = [
            {"answer": []},  # Too few selections
            {"answer": [0, 1, 2]},  # Too many selections
            {"answer": [5]},  # Invalid option
            {"answer": ["abc"]},  # Non-numeric string
        ]

        for answer in invalid_answers:
            with pytest.raises(QuestionAnswerValidationError):
                validator._validate_answer_checkbox(answer)

    def test_validate_answer_extract(self, validator):
        # Set up extract-specific attributes
        validator.answer_template = {"field1": None, "field2": None}

        # Test valid case
        valid_answer = {"answer": {"field1": "value1", "field2": "value2"}}
        validator._validate_answer_extract(valid_answer)

        # Test invalid cases
        invalid_answers = [
            {"answer": {"field1": "value1"}},  # Missing required field
            {
                "answer": {"field1": "value1", "field2": "value2", "field3": "value3"}
            },  # Extra field
        ]

        for answer in invalid_answers:
            with pytest.raises(QuestionAnswerValidationError):
                validator._validate_answer_extract(answer)

    def test_validate_answer_list(self, validator):
        # Set up list-specific attributes
        validator.allow_nonresponse = False
        validator.max_list_items = 3

        # Test valid cases
        valid_answers = [
            {"answer": ["item1"]},
            {"answer": ["item1", "item2"]},
            {"answer": ["item1", "item2", "item3"]},
        ]

        for answer in valid_answers:
            validator._validate_answer_list(answer)

        # Test invalid cases
        invalid_answers = [
            {"answer": []},  # Empty list when not allowed
            {"answer": ["item1", "item2", "item3", "item4"]},  # Too many items
            {"answer": ["item1", ""]},  # Contains empty string
        ]

        for answer in invalid_answers:
            with pytest.raises(QuestionAnswerValidationError):
                validator._validate_answer_list(answer)

    def test_validate_answer_numerical(self, validator):
        # Set up numerical-specific attributes
        validator.min_value = 0
        validator.max_value = 100

        # Test valid cases
        valid_answers = [
            {"answer": 50},
            {"answer": "50"},
            {"answer": 0},
            {"answer": 100},
        ]

        for answer in valid_answers:
            validator._validate_answer_numerical(answer)

        # Test invalid cases
        invalid_answers = [
            {"answer": -1},  # Below min
            {"answer": 101},  # Above max
            {"answer": "abc"},  # Non-numeric
        ]

        for answer in invalid_answers:
            with pytest.raises(QuestionAnswerValidationError):
                validator._validate_answer_numerical(answer)

    def test_validate_answer_multiple_choice(self, validator):
        # Test valid cases
        valid_answers = [{"answer": 0}, {"answer": "1"}, {"answer": 2}]

        for answer in valid_answers:
            validator._validate_answer_multiple_choice(answer)

        # Test invalid cases
        invalid_answers = [
            {"answer": -1},  # Negative index
            {"answer": 3},  # Index out of range
            {"answer": "abc"},  # Non-numeric string
            {"answer": None},  # None value
        ]

        for answer in invalid_answers:
            with pytest.raises(QuestionAnswerValidationError):
                validator._validate_answer_multiple_choice(answer)

    def test_validate_answer_rank(self, validator):
        # Set up rank-specific attributes
        validator.num_selections = 2

        # Test valid cases
        valid_answers = [{"answer": [0, 1]}, {"answer": [1, 0]}, {"answer": ["0", "1"]}]

        for answer in valid_answers:
            validator._validate_answer_rank(answer)

        # Test invalid cases
        invalid_answers = [
            {"answer": [0]},  # Too few selections
            {"answer": [0, 1, 2]},  # Too many selections
            {"answer": [3, 0]},  # Invalid option
            {"answer": ["abc", "def"]},  # Non-numeric strings
        ]

        for answer in invalid_answers:
            with pytest.raises(QuestionAnswerValidationError):
                validator._validate_answer_rank(answer)

    def test_validate_answer_matrix(self, validator):
        # Set up matrix-specific attributes
        validator.question_items = ["item1", "item2"]
        validator.question_options = ["opt1", "opt2", "opt3"]

        # Test valid case
        valid_answer = {"answer": {"item1": "opt1", "item2": "opt2"}}
        validator._validate_answer_matrix(valid_answer)

        # Test invalid cases
        invalid_answers = [
            {"answer": {"item1": "opt1"}},  # Missing item
            {
                "answer": {"item1": "opt1", "item2": "opt2", "item3": "opt3"}
            },  # Extra item
            {"answer": {"item1": "invalid", "item2": "opt1"}},  # Invalid option
            {"answer": ["item1", "item2"]},  # Wrong type (list instead of dict)
        ]

        for answer in invalid_answers:
            with pytest.raises(QuestionAnswerValidationError):
                validator._validate_answer_matrix(answer)
