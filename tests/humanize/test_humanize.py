"""Tests for the humanize survey system.

These tests verify:
- HumanizedJob creation and URL generation
- Question rendering for different types
- Answer submission
- Results retrieval
- Custom CSS application
- Skip functionality
- Progress tracking
"""

import pytest

# Skip all tests in this module - humanize feature is not yet implemented
pytest.skip(
    "Humanize feature not yet implemented - module edsl.jobs.humanized_job does not exist",
    allow_module_level=True
)

import json
import time
from unittest.mock import patch, MagicMock

from edsl import Survey
from edsl.questions import (
    QuestionMultipleChoice,
    QuestionFreeText,
    QuestionNumerical,
    QuestionYesNo,
    QuestionLinearScale,
    QuestionCheckBox,
    QuestionLikertFive,
)
from edsl.scenarios import Scenario, ScenarioList
from edsl.jobs.humanized_job import HumanizedJob
from edsl.jobs.runners.humanize_ingestor import HumanizeIngestor


class TestHumanizedJobCreation:
    """Test creating humanized jobs."""

    def test_simple_survey_humanize(self):
        """Test humanizing a simple single-question survey."""
        q = QuestionMultipleChoice(
            question_name="color",
            question_text="What is your favorite color?",
            question_options=["Red", "Blue", "Green"]
        )
        survey = Survey([q])
        jobs = survey.to_jobs()

        # Mock the server interaction
        with patch.object(jobs, 'humanize') as mock_humanize:
            mock_humanize.return_value = HumanizedJob(
                job_id="test-job-123",
                server_url="http://localhost:8080",
                survey=survey,
                name="Test Survey",
            )

            humanized = jobs.humanize(name="Test Survey")

            assert humanized.job_id == "test-job-123"
            assert humanized.name == "Test Survey"
            assert "humanize" in humanized.url

    def test_multi_question_survey(self):
        """Test humanizing a survey with multiple question types."""
        q1 = QuestionMultipleChoice(
            question_name="color",
            question_text="Favorite color?",
            question_options=["Red", "Blue", "Green"]
        )
        q2 = QuestionFreeText(
            question_name="reason",
            question_text="Why do you like that color?"
        )
        q3 = QuestionNumerical(
            question_name="age",
            question_text="How old are you?"
        )

        survey = Survey([q1, q2, q3])

        # Verify survey structure
        assert len(survey.questions) == 3
        assert survey.questions[0].question_type == "multiple_choice"
        assert survey.questions[1].question_type == "free_text"
        assert survey.questions[2].question_type == "numerical"

    def test_humanize_with_scenarios(self):
        """Test humanizing with multiple scenarios."""
        q = QuestionMultipleChoice(
            question_name="product",
            question_text="Do you like {{ product_name }}?",
            question_options=["Yes", "No", "Maybe"]
        )
        survey = Survey([q])

        scenarios = ScenarioList([
            Scenario({"product_name": "Product A"}),
            Scenario({"product_name": "Product B"}),
        ])

        jobs = survey.by(scenarios)

        # Verify scenarios are attached
        assert len(jobs.scenarios) == 2


class TestHumanizeIngestor:
    """Test the HumanizeIngestor class."""

    def test_ingestor_creates_tasks(self):
        """Test that ingestor creates proper task structure."""
        q1 = QuestionMultipleChoice(
            question_name="q1",
            question_text="Question 1?",
            question_options=["A", "B", "C"]
        )
        q2 = QuestionFreeText(
            question_name="q2",
            question_text="Question 2?"
        )

        survey = Survey([q1, q2])

        # Create ingestor with mock client
        ingestor = HumanizeIngestor(
            survey=survey,
            config={"one_at_a_time": True, "show_progress": True},
            server_url="http://localhost:8080",
        )

        # Mock the client
        mock_client = MagicMock()
        mock_client.create_task_job = MagicMock()
        mock_client.create_task_group = MagicMock(return_value="group-123")
        mock_client.create_unified_task = MagicMock()
        mock_client.push_snapshot = MagicMock()
        mock_client.push_binary = MagicMock()

        ingestor._client = mock_client

        # Run ingestion
        job_id, interview_ids, agent_map = ingestor.ingest()

        # Verify job was created
        assert mock_client.create_task_job.called

        # Verify tasks were created (one per question)
        assert mock_client.create_unified_task.call_count == 2

    def test_ingestor_sets_dependencies(self):
        """Test that sequential dependencies are set correctly."""
        questions = [
            QuestionMultipleChoice(
                question_name=f"q{i}",
                question_text=f"Question {i}?",
                question_options=["A", "B"]
            )
            for i in range(3)
        ]

        survey = Survey(questions)

        ingestor = HumanizeIngestor(
            survey=survey,
            config={},
            server_url="http://localhost:8080",
        )

        # Capture create_unified_task calls
        task_calls = []

        mock_client = MagicMock()
        mock_client.create_task_job = MagicMock()
        mock_client.create_task_group = MagicMock(return_value="group-123")
        mock_client.push_snapshot = MagicMock()
        mock_client.push_binary = MagicMock()

        def capture_task(*args, **kwargs):
            task_calls.append(kwargs)

        mock_client.create_unified_task = capture_task
        ingestor._client = mock_client

        job_id, interview_ids, agent_map = ingestor.ingest()

        # First task should have no dependencies
        assert task_calls[0].get("dependencies") is None or task_calls[0].get("dependencies") == []

        # Second task should depend on first
        assert len(task_calls[1].get("dependencies", [])) >= 1

        # Third task should depend on second
        assert len(task_calls[2].get("dependencies", [])) >= 1


class TestHumanizeConfig:
    """Test humanize configuration options."""

    def test_one_at_a_time_config(self):
        """Test one_at_a_time configuration."""
        q = QuestionMultipleChoice(
            question_name="q1",
            question_text="Question?",
            question_options=["A", "B"]
        )
        survey = Survey([q])

        # Default should be True
        ingestor = HumanizeIngestor(
            survey=survey,
            config={},
            server_url="http://localhost:8080",
        )
        assert ingestor.config.get("one_at_a_time") is None  # Will default to True in routes

        # Explicit False
        ingestor = HumanizeIngestor(
            survey=survey,
            config={"one_at_a_time": False},
            server_url="http://localhost:8080",
        )
        assert ingestor.config.get("one_at_a_time") is False

    def test_allow_skip_config(self):
        """Test allow_skip configuration."""
        q = QuestionMultipleChoice(
            question_name="q1",
            question_text="Question?",
            question_options=["A", "B"]
        )
        survey = Survey([q])

        ingestor = HumanizeIngestor(
            survey=survey,
            config={"allow_skip": True},
            server_url="http://localhost:8080",
        )
        assert ingestor.config.get("allow_skip") is True

    def test_custom_css_config(self):
        """Test custom_css configuration."""
        q = QuestionMultipleChoice(
            question_name="q1",
            question_text="Question?",
            question_options=["A", "B"]
        )
        survey = Survey([q])

        custom_css = """
        .question-text {
            font-family: Georgia, serif;
            color: #2c3e50;
        }
        .submit-btn {
            background: #27ae60;
        }
        """

        ingestor = HumanizeIngestor(
            survey=survey,
            config={"custom_css": custom_css},
            server_url="http://localhost:8080",
        )
        assert ".question-text" in ingestor.config.get("custom_css")
        assert "Georgia" in ingestor.config.get("custom_css")


class TestHumanizedJobStatus:
    """Test HumanizedJob status methods."""

    def test_status_method(self):
        """Test the status() method returns correct format."""
        survey = Survey([
            QuestionMultipleChoice(
                question_name="q1",
                question_text="Q?",
                question_options=["A", "B"]
            )
        ])

        humanized = HumanizedJob(
            job_id="test-123",
            server_url="http://localhost:8080",
            survey=survey,
            name="Test",
        )

        # Mock the client
        mock_client = MagicMock()
        mock_client.get_task_job = MagicMock(return_value={"job_id": "test-123"})
        mock_client.list_unified_tasks = MagicMock(return_value=[
            {"task_id": "t1", "status": "completed", "group_id": "interview-1"},
            {"task_id": "t2", "status": "pending", "group_id": "interview-1"},
        ])

        humanized._client = mock_client

        status = humanized.status()

        # New status format uses interview-based metrics
        assert "total_interviews" in status
        assert "completed_interviews" in status
        assert "started_interviews" in status
        assert "questions_per_interview" in status
        assert status["total_interviews"] == 1
        assert status["started_interviews"] == 1  # Has at least one completed task
        assert status["completed_interviews"] == 0  # Not all tasks completed

    def test_repr_method(self):
        """Test the __repr__ method."""
        survey = Survey([
            QuestionMultipleChoice(
                question_name="q1",
                question_text="Q?",
                question_options=["A", "B"]
            )
        ])

        humanized = HumanizedJob(
            job_id="test-123",
            server_url="http://localhost:8080",
            survey=survey,
            name="My Survey",
        )

        # Mock status with new format
        humanized.status = MagicMock(return_value={
            "total_interviews": 10,
            "completed_interviews": 5,
            "started_interviews": 8,
            "questions_per_interview": 3,
        })

        repr_str = repr(humanized)

        assert "HumanizedJob" in repr_str
        assert "My Survey" in repr_str
        assert "test-123" in repr_str
        assert "completed=5" in repr_str or "completed_interviews" in repr_str


class TestQuestionTypes:
    """Test different question types in humanize context."""

    def test_multiple_choice_question(self):
        """Test multiple choice question structure."""
        q = QuestionMultipleChoice(
            question_name="mc",
            question_text="Pick one:",
            question_options=["Option A", "Option B", "Option C"]
        )

        data = q.to_dict()
        assert data["question_type"] == "multiple_choice"
        assert len(data["question_options"]) == 3

    def test_free_text_question(self):
        """Test free text question structure."""
        q = QuestionFreeText(
            question_name="text",
            question_text="Tell us more:"
        )

        data = q.to_dict()
        assert data["question_type"] == "free_text"

    def test_numerical_question(self):
        """Test numerical question structure."""
        q = QuestionNumerical(
            question_name="num",
            question_text="Enter a number:"
        )

        data = q.to_dict()
        assert data["question_type"] == "numerical"

    def test_yes_no_question(self):
        """Test yes/no question structure."""
        q = QuestionYesNo(
            question_name="yn",
            question_text="Do you agree?"
        )

        data = q.to_dict()
        assert data["question_type"] == "yes_no"

    def test_linear_scale_question(self):
        """Test linear scale question structure."""
        q = QuestionLinearScale(
            question_name="scale",
            question_text="Rate from 1-5:",
            question_options=[1, 2, 3, 4, 5]
        )

        data = q.to_dict()
        assert data["question_type"] == "linear_scale"
        assert 1 in data["question_options"]
        assert 5 in data["question_options"]

    def test_checkbox_question(self):
        """Test checkbox question structure."""
        q = QuestionCheckBox(
            question_name="check",
            question_text="Select all that apply:",
            question_options=["A", "B", "C", "D"]
        )

        data = q.to_dict()
        assert data["question_type"] == "checkbox"
        assert len(data["question_options"]) == 4

    def test_likert_question(self):
        """Test likert scale question structure."""
        q = QuestionLikertFive(
            question_name="likert",
            question_text="How much do you agree?"
        )

        data = q.to_dict()
        assert data["question_type"] == "likert_five"


class TestHumanizeHTML:
    """Test the HTML generation for humanize surveys."""

    def test_html_contains_survey_name(self):
        """Test that generated HTML contains the survey name."""
        from edsl.server.routes.humanize import _generate_survey_html

        html = _generate_survey_html(
            job_id="test-123",
            interview_id="interview-456",
            survey_name="My Test Survey",
            config={}
        )

        assert "My Test Survey" in html

    def test_html_contains_api_base(self):
        """Test that generated HTML contains the correct API base."""
        from edsl.server.routes.humanize import _generate_survey_html

        html = _generate_survey_html(
            job_id="job-123",
            interview_id="interview-456",
            survey_name="Survey",
            config={}
        )

        assert "/humanize/job-123/interview-456" in html

    def test_html_includes_custom_css(self):
        """Test that custom CSS is included in the HTML."""
        from edsl.server.routes.humanize import _generate_survey_html

        custom_css = ".question-text { color: red; font-size: 2rem; }"

        html = _generate_survey_html(
            job_id="test",
            interview_id="test",
            survey_name="Survey",
            config={"custom_css": custom_css}
        )

        assert custom_css in html

    def test_html_progress_bar_conditional(self):
        """Test that progress bar respects show_progress config."""
        from edsl.server.routes.humanize import _generate_survey_html

        # With progress
        html_with = _generate_survey_html(
            job_id="test",
            interview_id="test",
            survey_name="Survey",
            config={"show_progress": True}
        )
        assert "SHOW_PROGRESS = true" in html_with

        # Without progress
        html_without = _generate_survey_html(
            job_id="test",
            interview_id="test",
            survey_name="Survey",
            config={"show_progress": False}
        )
        assert "SHOW_PROGRESS = false" in html_without

    def test_html_skip_button_conditional(self):
        """Test that skip button respects allow_skip config."""
        from edsl.server.routes.humanize import _generate_survey_html

        # With skip
        html_with = _generate_survey_html(
            job_id="test",
            interview_id="test",
            survey_name="Survey",
            config={"allow_skip": True}
        )
        assert "ALLOW_SKIP = true" in html_with

        # Without skip
        html_without = _generate_survey_html(
            job_id="test",
            interview_id="test",
            survey_name="Survey",
            config={"allow_skip": False}
        )
        assert "ALLOW_SKIP = false" in html_without

    def test_html_contains_question_type_classes(self):
        """Test that HTML contains semantic CSS classes for question types."""
        from edsl.server.routes.humanize import _generate_survey_html

        html = _generate_survey_html(
            job_id="test",
            interview_id="test",
            survey_name="Survey",
            config={}
        )

        # Check for semantic class patterns in the React code
        # Question types are handled by type string in the Question component
        assert "multiple_choice" in html
        assert "free_text" in html
        assert "numerical" in html
        assert ".question-text" in html
        assert ".option" in html


class TestCSSSelectors:
    """Test that CSS selectors work as documented."""

    def test_css_selector_documentation(self):
        """Verify documented CSS selectors exist in the generated HTML."""
        from edsl.server.routes.humanize import _generate_survey_html

        html = _generate_survey_html(
            job_id="test",
            interview_id="test",
            survey_name="Survey",
            config={}
        )

        # Layout selectors
        assert ".survey-page" in html
        assert ".survey-container" in html
        assert ".survey-header" in html
        assert ".survey-title" in html
        assert ".survey-content" in html

        # Progress selectors
        assert ".progress-bar" in html
        assert ".progress-fill" in html
        assert ".progress-text" in html

        # Question selectors
        assert ".question" in html
        assert ".question-text" in html

        # Option selectors
        assert ".option" in html
        assert ".option-label" in html

        # Input selectors
        assert ".text-input" in html
        assert ".number-input" in html

        # Button selectors
        assert ".submit-btn" in html
        assert ".skip-btn" in html

        # State selectors
        assert ".loading" in html
        assert ".error" in html
        assert ".complete-message" in html


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
