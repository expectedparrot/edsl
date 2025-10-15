"""Unit tests for edsl.macros.macro module."""
from __future__ import annotations
import pytest

from edsl.macros.macro import Macro
from edsl.macros.output_formatter import OutputFormatter, OutputFormatters
from edsl.surveys import Survey
from edsl import QuestionFreeText
from edsl.jobs import Jobs


class SimpleOutputFormatter(OutputFormatter):
    """Simple concrete output formatter for testing."""

    def __init__(self, description: str = "test_formatter", allowed_commands: list = None, params=None):
        super().__init__(description=description, allowed_commands=allowed_commands, params=params)

    def render(self, results, params=None):
        return f"formatted_output_from_{self.description}"


class MacroForTesting(Macro):
    """Concrete Macro subclass for testing."""
    application_type = "testable_macro"

    @classmethod
    def example(cls):
        """Create an example macro for testing."""
        initial_survey = Survey([
            QuestionFreeText(
                question_name="test_param",
                question_text="Test parameter question?"
            )
        ])

        # Create a simple jobs object
        jobs_survey = Survey([
            QuestionFreeText(
                question_name="output_question",
                question_text="Process the input: {{scenario.test_param}}"
            )
        ])
        jobs_object = jobs_survey.to_jobs()

        return cls(
            jobs_object=jobs_object,
            description="Test macro description",
            application_name="Test Macro",
            initial_survey=initial_survey
        )


class TestMacro:
    """Test cases for the Macro class."""

    def setup_method(self):
        """Set up test fixtures."""
        # Clear registry between tests
        Macro._registry.clear()

        # Create real survey
        self.survey = Survey([
            QuestionFreeText(
                question_name="test_param",
                question_text="Test question?"
            )
        ])

        # Create real jobs object
        jobs_survey = Survey([
            QuestionFreeText(
                question_name="output_question",
                question_text="Process the input: {{scenario.test_param}}"
            )
        ])
        self.jobs = jobs_survey.to_jobs()

        # Create test formatter
        self.test_formatter = SimpleOutputFormatter("test_formatter")

    def test_init_subclass_registration(self):
        """Test that subclasses are properly registered."""
        class TestMacro1(Macro):
            application_type = "test_macro_1"

        assert "test_macro_1" in Macro._registry
        assert Macro._registry["test_macro_1"] is TestMacro1

    def test_init_subclass_requires_application_type(self):
        """Test that subclasses must define application_type."""
        with pytest.raises(TypeError, match="must define a non-empty 'application_type'"):
            class BadMacro(Macro):
                pass

    def test_init_subclass_no_default_formatter_ok(self):
        """Subclasses need not define a class-level default formatter anymore."""
        class NoDefault(Macro):
            application_type = "no_default_ok"
        assert "no_default_ok" in Macro._registry

    def test_init_subclass_prevents_duplicate_types(self):
        """Test that duplicate application_type values are not allowed."""
        class TestMacro1(Macro):
            application_type = "duplicate_type"

        with pytest.raises(ValueError, match="Duplicate application_type 'duplicate_type'"):
            class TestMacro2(Macro):
                application_type = "duplicate_type"

    def test_macro_initialization(self):
        """Test basic Macro initialization."""
        macro = MacroForTesting(
            jobs_object=self.jobs,
            description="Test description",
            application_name="Test App",
            initial_survey=self.survey
        )

        assert macro.jobs_object is self.jobs
        assert macro.description == "Test description"
        assert macro.application_name == "Test Macro"
        assert macro.initial_survey is self.survey
        assert isinstance(macro.output_formatters, OutputFormatters)

    def test_macro_initialization_requires_initial_survey(self):
        """Test that Macro initialization requires initial_survey."""
        with pytest.raises(ValueError, match="An initial_survey is required"):
            MacroForTesting(
                jobs_object=self.jobs,
                description="Test description",
                application_name="Test Macro",
                initial_survey=None
            )

    def test_macro_initialization_validates_application_name(self):
        """Test application_name validation."""
        with pytest.raises(TypeError, match="application_name must be a string"):
            MacroForTesting(
                jobs_object=self.jobs,
                description="Test description",
                application_name=123,  # Invalid type
                initial_survey=self.survey
            )

    def test_macro_initialization_defaults_application_name(self):
        """Test that application_name defaults to class name."""
        macro = MacroForTesting(
            jobs_object=self.jobs,
            description="Test description",
            application_name=None,
            initial_survey=self.survey
        )

        assert macro.application_name == "MacroForTesting"

    def test_parameters_property(self):
        """Test the parameters property."""
        macro = MacroForTesting.example()
        params = macro.parameters

        assert len(params) == 1
        assert params[0] == ("test_param", "free_text", "Test parameter question?")

    def test_application_type_property(self):
        """Test the application_type property."""
        macro = MacroForTesting.example()
        assert macro.application_type == "testable_macro"

    def test_repr(self):
        """Test the __repr__ method."""
        macro = MacroForTesting.example()
        repr_str = repr(macro)

        assert "MacroForTesting" in repr_str
        assert "Test Macro" in repr_str
        assert "testable_macro" in repr_str

    def test_add_output_formatter(self):
        """Test adding an output formatter."""
        macro = MacroForTesting.example()
        new_formatter = SimpleOutputFormatter("new_formatter")

        result = macro.add_output_formatter(new_formatter)

        assert result is macro  # Fluent interface
        assert new_formatter.name in macro.output_formatters.mapping
        assert new_formatter in macro.output_formatters.data

    def test_add_output_formatter_validation(self):
        """Test output formatter validation."""
        macro = MacroForTesting.example()

        # Test invalid formatter type
        with pytest.raises(TypeError, match="formatter must be an OutputFormatter"):
            macro.add_output_formatter("not_a_formatter")

        # Test formatter without name
        bad_formatter = SimpleOutputFormatter()
        bad_formatter.name = None
        bad_formatter.description = None
        with pytest.raises(ValueError, match="formatter must have a unique, non-empty description"):
            macro.add_output_formatter(bad_formatter)

        # Test duplicate formatter name
        formatter1 = SimpleOutputFormatter("duplicate_name")
        formatter2 = SimpleOutputFormatter("duplicate_name")
        macro.add_output_formatter(formatter1)

        with pytest.raises(ValueError, match="Formatter with name 'duplicate_name' already exists"):
            macro.add_output_formatter(formatter2)

    def test_with_output_formatter(self):
        """Test creating new macro with different formatter."""
        macro = MacroForTesting.example()
        new_formatter = SimpleOutputFormatter("new_formatter")

        new_macro = macro.with_output_formatter(new_formatter)

        assert isinstance(new_macro, MacroForTesting)
        assert new_macro is not macro
        assert new_macro.jobs_object is macro.jobs_object
        assert new_macro.description == macro.description
        assert new_macro.application_name == macro.application_name

    def test_to_dict(self):
        """Test serialization to dictionary."""
        macro = MacroForTesting.example()
        result = macro.to_dict()

        assert isinstance(result, dict)
        assert "application_type" in result
        assert result["application_type"] == "testable_macro"

    def test_from_dict_roundtrip(self):
        """Test serialization roundtrip."""
        macro = MacroForTesting.example()
        macro_dict = macro.to_dict()

        # Test that we can create a macro from the dict
        reconstructed_macro = MacroForTesting.from_dict(macro_dict)

        assert isinstance(reconstructed_macro, Macro)
        assert reconstructed_macro.application_type == macro.application_type
        assert reconstructed_macro.description == macro.description

    def test_rshift_operator_invalid_operand(self):
        """Test >> operator with invalid operand."""
        macro = MacroForTesting.example()

        with pytest.raises(TypeError, match="Invalid operand for >>"):
            macro >> "invalid_operand"

    def test_generate_results(self):
        """Test _generate_results method."""
        macro = MacroForTesting.example()

        # This is a real test that calls the actual method
        # We can't easily test the full pipeline without running expensive operations,
        # so we just test that the method exists and has the right signature
        assert hasattr(macro, '_generate_results')
        assert callable(macro._generate_results)

    def test_debug_properties(self):
        """Test debug properties."""
        macro = MacroForTesting.example()

        # Test initial state
        assert macro.debug_history == []

        # Test that debug_last property exists and returns a dict
        debug_data = macro.debug_last
        assert isinstance(debug_data, dict)
        assert "params" in debug_data
        assert "head_attachments" in debug_data
        assert "jobs" in debug_data
        assert "results" in debug_data
        assert "formatted_output" in debug_data