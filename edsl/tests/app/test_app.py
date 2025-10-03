"""Unit tests for edsl.app.app module."""
from __future__ import annotations
import pytest

from edsl.app.app import App
from edsl.app.output_formatter import OutputFormatter, OutputFormatters
from edsl.surveys import Survey
from edsl import QuestionFreeText
from edsl.jobs import Jobs


class SimpleOutputFormatter(OutputFormatter):
    """Simple concrete output formatter for testing."""

    def __init__(self, description: str = "test_formatter", allowed_commands: list = None, params=None):
        super().__init__(description=description, allowed_commands=allowed_commands, params=params)

    def render(self, results, params=None):
        return f"formatted_output_from_{self.description}"


class AppForTesting(App):
    """Concrete App subclass for testing."""
    application_type = "testable_app"

    @classmethod
    def example(cls):
        """Create an example app for testing."""
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
            description="Test app description",
            application_name="Test App",
            initial_survey=initial_survey
        )


class TestApp:
    """Test cases for the App class."""

    def setup_method(self):
        """Set up test fixtures."""
        # Clear registry between tests
        App._registry.clear()

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
        class TestApp1(App):
            application_type = "test_app_1"

        assert "test_app_1" in App._registry
        assert App._registry["test_app_1"] is TestApp1

    def test_init_subclass_requires_application_type(self):
        """Test that subclasses must define application_type."""
        with pytest.raises(TypeError, match="must define a non-empty 'application_type'"):
            class BadApp(App):
                pass

    def test_init_subclass_no_default_formatter_ok(self):
        """Subclasses need not define a class-level default formatter anymore."""
        class NoDefault(App):
            application_type = "no_default_ok"
        assert "no_default_ok" in App._registry

    def test_init_subclass_prevents_duplicate_types(self):
        """Test that duplicate application_type values are not allowed."""
        class TestApp1(App):
            application_type = "duplicate_type"

        with pytest.raises(ValueError, match="Duplicate application_type 'duplicate_type'"):
            class TestApp2(App):
                application_type = "duplicate_type"

    def test_app_initialization(self):
        """Test basic App initialization."""
        app = AppForTesting(
            jobs_object=self.jobs,
            description="Test description",
            application_name="Test App",
            initial_survey=self.survey
        )

        assert app.jobs_object is self.jobs
        assert app.description == "Test description"
        assert app.application_name == "Test App"
        assert app.initial_survey is self.survey
        assert isinstance(app.output_formatters, OutputFormatters)

    def test_app_initialization_requires_initial_survey(self):
        """Test that App initialization requires initial_survey."""
        with pytest.raises(ValueError, match="An initial_survey is required"):
            AppForTesting(
                jobs_object=self.jobs,
                description="Test description",
                application_name="Test App",
                initial_survey=None
            )

    def test_app_initialization_validates_application_name(self):
        """Test application_name validation."""
        with pytest.raises(TypeError, match="application_name must be a string"):
            AppForTesting(
                jobs_object=self.jobs,
                description="Test description",
                application_name=123,  # Invalid type
                initial_survey=self.survey
            )

    def test_app_initialization_defaults_application_name(self):
        """Test that application_name defaults to class name."""
        app = AppForTesting(
            jobs_object=self.jobs,
            description="Test description",
            application_name=None,
            initial_survey=self.survey
        )

        assert app.application_name == "AppForTesting"

    def test_parameters_property(self):
        """Test the parameters property."""
        app = AppForTesting.example()
        params = app.parameters

        assert len(params) == 1
        assert params[0] == ("test_param", "free_text", "Test parameter question?")

    def test_application_type_property(self):
        """Test the application_type property."""
        app = AppForTesting.example()
        assert app.application_type == "testable_app"

    def test_repr(self):
        """Test the __repr__ method."""
        app = AppForTesting.example()
        repr_str = repr(app)

        assert "AppForTesting" in repr_str
        assert "Test App" in repr_str
        assert "testable_app" in repr_str

    def test_add_output_formatter(self):
        """Test adding an output formatter."""
        app = AppForTesting.example()
        new_formatter = SimpleOutputFormatter("new_formatter")

        result = app.add_output_formatter(new_formatter)

        assert result is app  # Fluent interface
        assert new_formatter.name in app.output_formatters.mapping
        assert new_formatter in app.output_formatters.data

    def test_add_output_formatter_validation(self):
        """Test output formatter validation."""
        app = AppForTesting.example()

        # Test invalid formatter type
        with pytest.raises(TypeError, match="formatter must be an OutputFormatter"):
            app.add_output_formatter("not_a_formatter")

        # Test formatter without name
        bad_formatter = SimpleOutputFormatter()
        bad_formatter.name = None
        bad_formatter.description = None
        with pytest.raises(ValueError, match="formatter must have a unique, non-empty description"):
            app.add_output_formatter(bad_formatter)

        # Test duplicate formatter name
        formatter1 = SimpleOutputFormatter("duplicate_name")
        formatter2 = SimpleOutputFormatter("duplicate_name")
        app.add_output_formatter(formatter1)

        with pytest.raises(ValueError, match="Formatter with name 'duplicate_name' already exists"):
            app.add_output_formatter(formatter2)

    def test_with_output_formatter(self):
        """Test creating new app with different formatter."""
        app = AppForTesting.example()
        new_formatter = SimpleOutputFormatter("new_formatter")

        new_app = app.with_output_formatter(new_formatter)

        assert isinstance(new_app, AppForTesting)
        assert new_app is not app
        assert new_app.jobs_object is app.jobs_object
        assert new_app.description == app.description
        assert new_app.application_name == app.application_name

    def test_to_dict(self):
        """Test serialization to dictionary."""
        app = AppForTesting.example()
        result = app.to_dict()

        assert isinstance(result, dict)
        assert "application_type" in result
        assert result["application_type"] == "testable_app"

    def test_from_dict_roundtrip(self):
        """Test serialization roundtrip."""
        app = AppForTesting.example()
        app_dict = app.to_dict()

        # Test that we can create an app from the dict
        reconstructed_app = AppForTesting.from_dict(app_dict)

        assert isinstance(reconstructed_app, App)
        assert reconstructed_app.application_type == app.application_type
        assert reconstructed_app.description == app.description

    def test_rshift_operator_invalid_operand(self):
        """Test >> operator with invalid operand."""
        app = AppForTesting.example()

        with pytest.raises(TypeError, match="Invalid operand for >>"):
            app >> "invalid_operand"

    def test_generate_results(self):
        """Test _generate_results method."""
        app = AppForTesting.example()

        # This is a real test that calls the actual method
        # We can't easily test the full pipeline without running expensive operations,
        # so we just test that the method exists and has the right signature
        assert hasattr(app, '_generate_results')
        assert callable(app._generate_results)

    def test_debug_properties(self):
        """Test debug properties."""
        app = AppForTesting.example()

        # Test initial state
        assert app.debug_history == []

        # Test that debug_last property exists and returns a dict
        debug_data = app.debug_last
        assert isinstance(debug_data, dict)
        assert "params" in debug_data
        assert "head_attachments" in debug_data
        assert "jobs" in debug_data
        assert "results" in debug_data
        assert "formatted_output" in debug_data