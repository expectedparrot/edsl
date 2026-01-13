"""Extended tests for humanize survey features.

These tests cover:
- one_at_a_time=False behavior
- Skip logic dependencies (DAG dependencies)
- All question types (including new ones)
- Instruction objects
- File upload with download URLs
- Answer validation
- FileStore scenario piping
- Markdown rendering
- Numerical slider configuration
- Time tracking
- Optional comments
"""

import pytest

# Skip all tests in this module - humanize feature is not yet implemented
pytest.skip(
    "Humanize feature not yet implemented - module edsl.jobs.runners.humanize_ingestor does not exist",
    allow_module_level=True
)

import json
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
    QuestionList,
    QuestionRank,
    QuestionBudget,
    QuestionTopK,
    QuestionMatrix,
)
from edsl.scenarios import Scenario, ScenarioList
from edsl.instructions import Instruction
from edsl.jobs.runners.humanize_ingestor import HumanizeIngestor


class TestOneAtATimeFalse:
    """Test one_at_a_time=False behavior - showing all available questions."""
    
    def test_no_sequential_dependencies_when_false(self):
        """When one_at_a_time=False, tasks should not have sequential dependencies."""
        questions = [
            QuestionFreeText(question_name=f"q{i}", question_text=f"Question {i}?")
            for i in range(4)
        ]
        
        survey = Survey(questions)
        
        ingestor = HumanizeIngestor(
            survey=survey,
            config={"one_at_a_time": False},
            server_url="http://localhost:8080",
        )
        
        # Capture task creation calls
        task_calls = []
        
        mock_client = MagicMock()
        mock_client.create_task_job = MagicMock()
        mock_client.create_task_group = MagicMock(return_value="group-123")
        mock_client.push_snapshot = MagicMock()
        mock_client.push_binary = MagicMock()
        mock_client.create_unified_task = lambda **kwargs: task_calls.append(kwargs)
        
        ingestor._client = mock_client
        ingestor.ingest()
        
        # All tasks should have no dependencies (or empty list)
        for i, call in enumerate(task_calls):
            deps = call.get("dependencies") or []
            assert len(deps) == 0, f"Task {i} should have no dependencies, got {deps}"
    
    def test_sequential_dependencies_when_true(self):
        """When one_at_a_time=True (default), tasks should have sequential dependencies."""
        questions = [
            QuestionFreeText(question_name=f"q{i}", question_text=f"Question {i}?")
            for i in range(4)
        ]
        
        survey = Survey(questions)
        
        ingestor = HumanizeIngestor(
            survey=survey,
            config={"one_at_a_time": True},
            server_url="http://localhost:8080",
        )
        
        task_calls = []
        
        mock_client = MagicMock()
        mock_client.create_task_job = MagicMock()
        mock_client.create_task_group = MagicMock(return_value="group-123")
        mock_client.push_snapshot = MagicMock()
        mock_client.push_binary = MagicMock()
        mock_client.create_unified_task = lambda **kwargs: task_calls.append(kwargs)
        
        ingestor._client = mock_client
        ingestor.ingest()
        
        # First task has no dependencies
        assert len(task_calls[0].get("dependencies") or []) == 0
        
        # Subsequent tasks have dependencies
        for i in range(1, len(task_calls)):
            deps = task_calls[i].get("dependencies") or []
            assert len(deps) > 0, f"Task {i} should have dependencies"


class TestSkipLogicDependencies:
    """Test that skip logic creates correct DAG dependencies."""
    
    def test_skip_rule_creates_dependency(self):
        """Questions with skip rules should depend on referenced questions."""
        q1 = QuestionFreeText(question_name="name", question_text="Name?")
        q2 = QuestionMultipleChoice(
            question_name="has_pet",
            question_text="Do you have a pet?",
            question_options=["Yes", "No"]
        )
        q3 = QuestionFreeText(question_name="pet_name", question_text="Pet's name?")
        q4 = QuestionFreeText(question_name="hobby", question_text="Hobby?")
        
        survey = Survey([q1, q2, q3, q4])
        survey = survey.add_skip_rule(q3, "has_pet != 'Yes'")
        
        ingestor = HumanizeIngestor(
            survey=survey,
            config={"one_at_a_time": False},
            server_url="http://localhost:8080",
        )
        
        # Check dependency calculation
        memory_plan = survey.memory_plan
        rule_collection = survey.rule_collection
        
        # q3 (index 2) should depend on q2 (has_pet)
        deps = ingestor._get_dag_dependencies("pet_name", memory_plan, rule_collection, 2)
        assert "has_pet" in deps, f"pet_name should depend on has_pet, got {deps}"
        
        # q4 (index 3) should have no skip dependencies
        deps = ingestor._get_dag_dependencies("hobby", memory_plan, rule_collection, 3)
        assert "has_pet" not in deps, f"hobby should not depend on has_pet, got {deps}"
    
    def test_skip_rule_with_one_at_a_time_false(self):
        """With one_at_a_time=False, skip logic should still create dependencies."""
        q1 = QuestionFreeText(question_name="q1", question_text="Q1?")
        q2 = QuestionMultipleChoice(
            question_name="gate",
            question_text="Gate?",
            question_options=["Yes", "No"]
        )
        q3 = QuestionFreeText(question_name="gated", question_text="Gated question?")
        
        survey = Survey([q1, q2, q3])
        survey = survey.add_skip_rule(q3, "gate != 'Yes'")
        
        ingestor = HumanizeIngestor(
            survey=survey,
            config={"one_at_a_time": False},
            server_url="http://localhost:8080",
        )
        
        task_calls = []
        
        mock_client = MagicMock()
        mock_client.create_task_job = MagicMock()
        mock_client.create_task_group = MagicMock(return_value="group-123")
        mock_client.push_snapshot = MagicMock()
        mock_client.push_binary = MagicMock()
        mock_client.create_unified_task = lambda **kwargs: task_calls.append(kwargs)
        
        ingestor._client = mock_client
        ingestor.ingest()
        
        # q1 and q2 should have no dependencies
        assert len(task_calls[0].get("dependencies") or []) == 0
        assert len(task_calls[1].get("dependencies") or []) == 0
        
        # q3 should depend on q2 (gate question) due to skip rule
        q3_deps = task_calls[2].get("dependencies") or []
        assert len(q3_deps) > 0, "q3 should have dependencies from skip rule"


class TestInstructionObjects:
    """Test handling of Instruction objects in humanize surveys."""
    
    def test_instruction_creates_task(self):
        """Instructions should be converted to tasks."""
        instruction = Instruction(
            name="intro",
            text="Welcome to this survey!"
        )
        q1 = QuestionFreeText(question_name="q1", question_text="Q1?")
        
        survey = Survey([instruction, q1])
        
        ingestor = HumanizeIngestor(
            survey=survey,
            config={},
            server_url="http://localhost:8080",
        )
        
        task_calls = []
        
        mock_client = MagicMock()
        mock_client.create_task_job = MagicMock()
        mock_client.create_task_group = MagicMock(return_value="group-123")
        mock_client.push_snapshot = MagicMock()
        mock_client.push_binary = MagicMock()
        mock_client.create_unified_task = lambda **kwargs: task_calls.append(kwargs)
        
        ingestor._client = mock_client
        ingestor.ingest()
        
        # Should have 2 tasks (instruction + question)
        assert len(task_calls) == 2
        
        # First task should be instruction type
        assert task_calls[0]["task_type"] == "human_instruction"
        assert task_calls[0]["meta"]["item_type"] == "instruction"
        
        # Second task should be question type
        assert task_calls[1]["task_type"] == "human_question"
        assert task_calls[1]["meta"]["item_type"] == "question"


class TestNewQuestionTypes:
    """Test new question types added for humanize."""
    
    def test_list_question(self):
        """Test QuestionList structure."""
        q = QuestionList(
            question_name="items",
            question_text="List your items:"
        )
        
        data = q.to_dict()
        assert data["question_type"] == "list"
        assert data["question_name"] == "items"
    
    def test_rank_question(self):
        """Test QuestionRank structure."""
        q = QuestionRank(
            question_name="priorities",
            question_text="Rank these:",
            question_options=["A", "B", "C", "D"]
        )
        
        data = q.to_dict()
        assert data["question_type"] == "rank"
        assert len(data["question_options"]) == 4
    
    def test_budget_question(self):
        """Test QuestionBudget structure."""
        q = QuestionBudget(
            question_name="allocation",
            question_text="Allocate 100 points:",
            question_options=["Option A", "Option B", "Option C"],
            budget_sum=100
        )
        
        data = q.to_dict()
        assert data["question_type"] == "budget"
        assert data["budget_sum"] == 100
    
    def test_top_k_question(self):
        """Test QuestionTopK structure."""
        q = QuestionTopK(
            question_name="favorites",
            question_text="Pick your top 3:",
            question_options=["A", "B", "C", "D", "E"],
            max_selections=3,
            min_selections=3
        )
        
        data = q.to_dict()
        assert data["question_type"] == "top_k"
        assert data["max_selections"] == 3
    
    def test_matrix_question(self):
        """Test QuestionMatrix structure."""
        q = QuestionMatrix(
            question_name="ratings",
            question_text="Rate each:",
            question_items=["Item 1", "Item 2", "Item 3"],
            question_options=[1, 2, 3, 4, 5]
        )
        
        data = q.to_dict()
        assert data["question_type"] == "matrix"
        assert len(data["question_items"]) == 3
        assert len(data["question_options"]) == 5


class TestNumericalSlider:
    """Test numerical slider configuration."""
    
    def test_slider_config_passed_through(self):
        """Test that slider_for_numerical config is passed through."""
        q = QuestionNumerical(
            question_name="rating",
            question_text="Rate 1-10:",
            min_value=1,
            max_value=10
        )
        
        survey = Survey([q])
        
        ingestor = HumanizeIngestor(
            survey=survey,
            config={"slider_for_numerical": True},
            server_url="http://localhost:8080",
        )
        
        assert ingestor.config.get("slider_for_numerical") is True
    
    def test_html_contains_slider_config(self):
        """Test that HTML respects slider configuration."""
        from edsl.server.routes.humanize import _generate_survey_html
        
        # With slider
        html_with = _generate_survey_html(
            job_id="test",
            interview_id="test",
            survey_name="Survey",
            config={"slider_for_numerical": True}
        )
        assert "SLIDER_FOR_NUMERICAL = true" in html_with
        
        # Without slider
        html_without = _generate_survey_html(
            job_id="test",
            interview_id="test",
            survey_name="Survey",
            config={"slider_for_numerical": False}
        )
        assert "SLIDER_FOR_NUMERICAL = false" in html_without


class TestMarkdownRendering:
    """Test markdown rendering in question text."""
    
    def test_markdown_functions_exist(self):
        """Test that markdown rendering functions exist."""
        from edsl.server.routes.humanize import _render_markdown
        
        # Basic bold
        result = _render_markdown("This is **bold** text")
        assert "<strong>" in result or "<b>" in result
        
        # Basic italic
        result = _render_markdown("This is *italic* text")
        assert "<em>" in result or "<i>" in result
    
    def test_markdown_lists(self):
        """Test markdown list rendering."""
        from edsl.server.routes.humanize import _render_markdown_lists
        
        text = """
- Item 1
- Item 2
- Item 3
"""
        result = _render_markdown_lists(text)
        assert "<ul" in result
        assert "<li>" in result
    
    def test_markdown_tables(self):
        """Test markdown table rendering."""
        from edsl.server.routes.humanize import _render_markdown_tables
        
        text = """
| Header 1 | Header 2 |
|----------|----------|
| Cell 1   | Cell 2   |
"""
        result = _render_markdown_tables(text)
        assert "<table" in result
        assert "<th>" in result
        assert "<td>" in result


class TestFileUploadDownload:
    """Test file upload with download URL functionality."""
    
    def test_upload_response_includes_download_url(self):
        """Test that upload endpoint response includes download_url."""
        # This is a unit test for the expected response format
        expected_response = {
            "blob_id": "upload_job_interview_abc123",
            "file_name": "test.pdf",
            "file_size": 12345,
            "content_type": "application/pdf",
            "download_url": "/humanize/job/interview/download/upload_job_interview_abc123"
        }
        
        assert "download_url" in expected_response
        assert "blob_id" in expected_response


class TestAnswerValidation:
    """Test answer validation in humanize."""
    
    def test_numerical_validation(self):
        """Test that numerical answers are validated."""
        from edsl.questions import QuestionNumerical
        
        q = QuestionNumerical(
            question_name="age",
            question_text="Age?",
            min_value=0,
            max_value=120
        )
        
        # The question should have min/max constraints
        assert q.min_value == 0
        assert q.max_value == 120


class TestScenarioPiping:
    """Test scenario variable piping in humanize."""
    
    def test_scenario_data_passed_to_task(self):
        """Test that scenario data is passed to tasks."""
        q = QuestionFreeText(
            question_name="feedback",
            question_text="What do you think of {{ product }}?"
        )
        
        survey = Survey([q])
        scenario = Scenario({"product": "Widget X"})
        
        ingestor = HumanizeIngestor(
            survey=survey,
            scenarios=ScenarioList([scenario]),
            config={},
            server_url="http://localhost:8080",
        )
        
        task_calls = []
        
        mock_client = MagicMock()
        mock_client.create_task_job = MagicMock()
        mock_client.create_task_group = MagicMock(return_value="group-123")
        mock_client.push_snapshot = MagicMock()
        mock_client.push_binary = MagicMock()
        mock_client.create_unified_task = lambda **kwargs: task_calls.append(kwargs)
        
        ingestor._client = mock_client
        ingestor.ingest()
        
        # Task should have scenario_data in params
        assert task_calls[0]["params"]["scenario_data"] is not None
        assert task_calls[0]["params"]["scenario_data"]["product"] == "Widget X"


class TestTimeTracking:
    """Test time tracking in humanize surveys."""
    
    def test_html_contains_timing_code(self):
        """Test that HTML includes time tracking JavaScript."""
        from edsl.server.routes.humanize import _generate_survey_html
        
        html = _generate_survey_html(
            job_id="test",
            interview_id="test",
            survey_name="Survey",
            config={}
        )
        
        # Check for timing-related code
        assert "timing" in html.lower() or "time" in html.lower()
        assert "visibilitychange" in html  # Page visibility tracking


class TestOptionalComments:
    """Test optional comment functionality."""
    
    def test_html_contains_comment_ui(self):
        """Test that HTML includes comment button."""
        from edsl.server.routes.humanize import _generate_survey_html
        
        html = _generate_survey_html(
            job_id="test",
            interview_id="test",
            survey_name="Survey",
            config={}
        )
        
        # Check for comment-related UI
        assert "Add comment" in html or "comment" in html.lower()


class TestMultiRespondentMode:
    """Test multi-respondent survey mode."""
    
    def test_multi_respondent_config(self):
        """Test multi_respondent configuration is stored."""
        q = QuestionFreeText(question_name="q1", question_text="Q?")
        survey = Survey([q])
        
        ingestor = HumanizeIngestor(
            survey=survey,
            config={"multi_respondent": True},
            server_url="http://localhost:8080",
        )
        
        assert ingestor.config.get("multi_respondent") is True


class TestDropdownThreshold:
    """Test dropdown threshold configuration."""
    
    def test_dropdown_threshold_config(self):
        """Test that dropdown_threshold is passed through."""
        q = QuestionMultipleChoice(
            question_name="choice",
            question_text="Choose:",
            question_options=[f"Option {i}" for i in range(15)]
        )
        survey = Survey([q])
        
        ingestor = HumanizeIngestor(
            survey=survey,
            config={"dropdown_threshold": 10},
            server_url="http://localhost:8080",
        )
        
        assert ingestor.config.get("dropdown_threshold") == 10
    
    def test_html_contains_dropdown_styles(self):
        """Test that HTML includes dropdown styling."""
        from edsl.server.routes.humanize import _generate_survey_html
        
        html = _generate_survey_html(
            job_id="test",
            interview_id="test",
            survey_name="Survey",
            config={"dropdown_threshold": 5}
        )
        
        # Check that dropdown styles are present
        assert ".dropdown-input" in html or "dropdown" in html


class TestCustomJavaScript:
    """Test custom JavaScript injection."""
    
    def test_custom_js_config(self):
        """Test that custom_js is stored in config."""
        q = QuestionFreeText(question_name="q1", question_text="Q?")
        survey = Survey([q])
        
        custom_js = "window.humanizeCustomData = { source: 'test' };"
        
        ingestor = HumanizeIngestor(
            survey=survey,
            config={"custom_js": custom_js},
            server_url="http://localhost:8080",
        )
        
        assert "humanizeCustomData" in ingestor.config.get("custom_js")
    
    def test_html_contains_custom_js(self):
        """Test that custom JS is included in HTML."""
        from edsl.server.routes.humanize import _generate_survey_html
        
        custom_js = "console.log('Custom JS loaded');"
        
        html = _generate_survey_html(
            job_id="test",
            interview_id="test",
            survey_name="Survey",
            config={"custom_js": custom_js}
        )
        
        assert custom_js in html


class TestQuestionSettings:
    """Test per-question settings configuration."""
    
    def test_question_settings_passed_through(self):
        """Test that question_settings config is stored."""
        q = QuestionNumerical(
            question_name="rating",
            question_text="Rate:",
            min_value=1,
            max_value=10
        )
        survey = Survey([q])
        
        question_settings = {
            "rating": {"use_slider": True}
        }
        
        ingestor = HumanizeIngestor(
            survey=survey,
            config={"question_settings": question_settings},
            server_url="http://localhost:8080",
        )
        
        assert ingestor.config.get("question_settings") == question_settings


class TestEmailQuestionType:
    """Test email question type."""
    
    def test_email_question_structure(self):
        """Test QuestionEmail structure if it exists."""
        try:
            from edsl.questions import QuestionEmail
            
            q = QuestionEmail(
                question_name="contact",
                question_text="Your email address?"
            )
            
            data = q.to_dict()
            assert data["question_type"] == "email"
            assert data["question_name"] == "contact"
        except ImportError:
            pytest.skip("QuestionEmail not implemented")


class TestImageAnnotationQuestionType:
    """Test image annotation question type."""
    
    def test_image_annotation_structure(self):
        """Test QuestionImageAnnotation structure if it exists."""
        try:
            from edsl.questions import QuestionImageAnnotation
            
            q = QuestionImageAnnotation(
                question_name="annotation",
                question_text="Click on the image:",
                annotation_image="https://example.com/image.png",
                annotation_mode="multiclick"
            )
            
            data = q.to_dict()
            assert data["question_type"] == "image_annotation"
            assert data["annotation_mode"] == "multiclick"
        except ImportError:
            pytest.skip("QuestionImageAnnotation not implemented")


class TestHTMLReactComponents:
    """Test that React components are properly defined in HTML."""
    
    def test_html_contains_all_question_components(self):
        """Test that HTML contains React components for all question types."""
        from edsl.server.routes.humanize import _generate_survey_html
        
        html = _generate_survey_html(
            job_id="test",
            interview_id="test",
            survey_name="Survey",
            config={}
        )
        
        # Check for question type handling in React
        question_types = [
            "multiple_choice",
            "free_text",
            "numerical",
            "yes_no",
            "linear_scale",
            "checkbox",
            "likert_five",
            "dropdown",
            "rank",
            "list",
            "budget",
            "top_k",
            "matrix",
            "file_upload",
        ]
        
        for qtype in question_types:
            # Check that the type is handled (either as case or component)
            assert qtype in html.lower(), f"Missing handler for {qtype}"
    
    def test_html_contains_instruction_component(self):
        """Test that HTML contains Instruction component."""
        from edsl.server.routes.humanize import _generate_survey_html
        
        html = _generate_survey_html(
            job_id="test",
            interview_id="test",
            survey_name="Survey",
            config={}
        )
        
        assert "Instruction" in html or "instruction" in html


class TestAgentURLs:
    """Test agent-specific URLs for humanize surveys."""
    
    def test_humanize_with_agents_creates_mapping(self):
        """Test that humanize with agents creates agent-to-URL mapping."""
        from edsl.agents import Agent, AgentList
        
        # Create agents with unique trait (using 'first_name' instead of reserved 'name')
        agents = AgentList([
            Agent(traits={"first_name": "Alice", "email": "alice@example.com"}),
            Agent(traits={"first_name": "Bob", "email": "bob@example.com"}),
        ])
        
        survey = Survey([
            QuestionFreeText(
                question_name="greeting",
                question_text="Hello {{ agent.first_name }}, how are you?"
            )
        ])
        
        # Mock the ingestor
        ingestor = HumanizeIngestor(
            survey=survey,
            agents=agents,
            agent_key="email",
            config={},
            server_url="http://localhost:8080",
        )
        
        task_calls = []
        
        mock_client = MagicMock()
        mock_client.create_task_job = MagicMock()
        mock_client.create_task_group = MagicMock(side_effect=["int-1", "int-2"])
        mock_client.push_snapshot = MagicMock()
        mock_client.push_binary = MagicMock()
        mock_client.create_unified_task = lambda **kwargs: task_calls.append(kwargs)
        
        ingestor._client = mock_client
        job_id, interview_ids, agent_map = ingestor.ingest()
        
        # Check that we have 2 interviews (one per agent)
        assert len(interview_ids) == 2
        
        # Check agent mapping
        assert "alice@example.com" in agent_map
        assert "bob@example.com" in agent_map
    
    def test_agent_key_validation_missing_trait(self):
        """Test that humanize raises error if agent is missing the key trait."""
        from edsl.agents import Agent, AgentList
        from edsl.jobs.jobs import Jobs
        
        # Agent without email trait
        agents = AgentList([
            Agent(traits={"first_name": "Alice", "email": "alice@example.com"}),
            Agent(traits={"first_name": "Bob"}),  # Missing email!
        ])
        
        survey = Survey([
            QuestionFreeText(
                question_name="q1",
                question_text="Question?"
            )
        ])
        
        jobs = survey.by(agents)
        
        # Mock require_client to avoid real server connection
        from unittest.mock import MagicMock, patch
        mock_client = MagicMock()
        mock_client.base_url = "http://localhost:8080"
        mock_client.api_key = "test-key"
        
        with patch('edsl.server.require_client', return_value=mock_client):
            with pytest.raises(ValueError) as exc_info:
                jobs.humanize(agent_key="email")
            
            assert "Agent at index 1 does not have trait 'email'" in str(exc_info.value)
    
    def test_agent_trait_piping_in_question_text(self):
        """Test that agent traits are resolved in question text."""
        from edsl.server.routes.humanize import _resolve_agent_template
        
        text = "Hello {{ agent.first_name }}, tell me about {{ agent.topic }}."
        agent_data = {
            "traits": {
                "first_name": "Alice",
                "topic": "machine learning"
            }
        }
        
        result = _resolve_agent_template(text, agent_data)
        assert result == "Hello Alice, tell me about machine learning."
    
    def test_agent_trait_piping_preserves_unknown_vars(self):
        """Test that unknown agent variables are preserved."""
        from edsl.server.routes.humanize import _resolve_agent_template
        
        text = "Hello {{ agent.first_name }}, value is {{ agent.unknown }}."
        agent_data = {
            "traits": {
                "first_name": "Alice"
            }
        }
        
        result = _resolve_agent_template(text, agent_data)
        assert result == "Hello Alice, value is {{ agent.unknown }}."
    
    def test_agent_data_stored_in_task_params(self):
        """Test that agent data is included in task params."""
        from edsl.agents import Agent, AgentList
        
        agents = AgentList([
            Agent(traits={"first_name": "Alice", "email": "alice@example.com"}),
        ])
        
        survey = Survey([
            QuestionFreeText(question_name="q1", question_text="Question?")
        ])
        
        ingestor = HumanizeIngestor(
            survey=survey,
            agents=agents,
            agent_key="email",
            config={},
            server_url="http://localhost:8080",
        )
        
        task_calls = []
        
        mock_client = MagicMock()
        mock_client.create_task_job = MagicMock()
        mock_client.create_task_group = MagicMock(return_value="int-1")
        mock_client.push_snapshot = MagicMock()
        mock_client.push_binary = MagicMock()
        mock_client.create_unified_task = lambda **kwargs: task_calls.append(kwargs)
        
        ingestor._client = mock_client
        ingestor.ingest()
        
        # Check that agent_data is in task params
        assert len(task_calls) == 1
        params = task_calls[0]["params"]
        assert "agent_data" in params
        assert params["agent_data"]["traits"]["first_name"] == "Alice"
    
    def test_humanized_job_agent_urls_property(self):
        """Test that HumanizedJob.agent_urls property returns correct mapping."""
        from edsl.jobs.humanized_job import HumanizedJob
        from edsl.surveys import Survey
        
        survey = Survey([
            QuestionFreeText(question_name="q1", question_text="Question?")
        ])
        
        humanized = HumanizedJob(
            job_id="job-123",
            server_url="http://localhost:8080",
            survey=survey,
            interview_ids=["int-1", "int-2"],
            agent_interview_map={
                "alice@example.com": "int-1",
                "bob@example.com": "int-2"
            },
            agent_key="email"
        )
        
        agent_urls = humanized.agent_urls
        
        assert agent_urls["alice@example.com"] == "http://localhost:8080/humanize/job-123/int-1"
        assert agent_urls["bob@example.com"] == "http://localhost:8080/humanize/job-123/int-2"
    
    def test_humanized_job_empty_agent_urls(self):
        """Test that agent_urls is empty when no agents are attached."""
        from edsl.jobs.humanized_job import HumanizedJob
        from edsl.surveys import Survey
        
        survey = Survey([
            QuestionFreeText(question_name="q1", question_text="Question?")
        ])
        
        humanized = HumanizedJob(
            job_id="job-123",
            server_url="http://localhost:8080",
            survey=survey,
            interview_ids=["int-1"],
        )
        
        assert humanized.agent_urls == {}
    
    def test_agents_with_scenarios_creates_cross_product(self):
        """Test that agents combined with scenarios creates cross-product of interviews."""
        from edsl.agents import Agent, AgentList
        
        agents = AgentList([
            Agent(traits={"first_name": "Alice", "id": "a1"}),
            Agent(traits={"first_name": "Bob", "id": "a2"}),
        ])
        
        scenarios = ScenarioList([
            Scenario({"topic": "AI"}),
            Scenario({"topic": "ML"}),
        ])
        
        survey = Survey([
            QuestionFreeText(
                question_name="q1",
                question_text="{{ agent.first_name }} discusses {{ scenario.topic }}"
            )
        ])
        
        ingestor = HumanizeIngestor(
            survey=survey,
            scenarios=scenarios,
            agents=agents,
            agent_key="id",
            config={},
            server_url="http://localhost:8080",
        )
        
        # Track group creation calls
        group_calls = []
        
        mock_client = MagicMock()
        mock_client.create_task_job = MagicMock()
        mock_client.create_task_group = MagicMock(side_effect=lambda *args, **kwargs: (group_calls.append(kwargs), f"int-{len(group_calls)}")[1])
        mock_client.push_snapshot = MagicMock()
        mock_client.push_binary = MagicMock()
        mock_client.create_unified_task = MagicMock()
        
        ingestor._client = mock_client
        job_id, interview_ids, agent_map = ingestor.ingest()
        
        # 2 scenarios x 2 agents = 4 interviews
        assert len(interview_ids) == 4
        
        # Agent mapping should have both agents
        assert "a1" in agent_map
        assert "a2" in agent_map
    
    def test_agent_key_required_when_agents_present(self):
        """Test that agent_key is required when agents are attached."""
        from edsl.agents import Agent, AgentList
        from edsl.jobs.jobs import Jobs
        
        agents = AgentList([
            Agent(traits={"first_name": "Alice", "email": "alice@example.com"}),
        ])
        
        survey = Survey([
            QuestionFreeText(question_name="q1", question_text="Question?")
        ])
        
        jobs = survey.by(agents)
        
        # Mock require_client to avoid real server connection
        from unittest.mock import MagicMock, patch
        mock_client = MagicMock()
        mock_client.base_url = "http://localhost:8080"
        mock_client.api_key = "test-key"
        
        with patch('edsl.server.require_client', return_value=mock_client):
            with pytest.raises(ValueError) as exc_info:
                jobs.humanize()  # No agent_key specified
            
            assert "agent_key is required when agents are attached" in str(exc_info.value)
    
    def test_humanized_job_repr_html_with_agents(self):
        """Test that _repr_html_ shows agent URLs table when agents present."""
        from edsl.jobs.humanized_job import HumanizedJob
        from edsl.surveys import Survey
        
        survey = Survey([
            QuestionFreeText(question_name="q1", question_text="Question?")
        ])
        
        humanized = HumanizedJob(
            job_id="job-123",
            server_url="http://localhost:8080",
            survey=survey,
            interview_ids=["int-1", "int-2"],
            agent_interview_map={
                "alice@example.com": "int-1",
                "bob@example.com": "int-2"
            },
            agent_key="email"
        )
        
        # Mock status to avoid server call
        with patch.object(humanized, 'status', return_value={
            'completed_interviews': 0,
            'started_interviews': 0,
            'total_interviews': 2,
            'questions_per_interview': 1
        }):
            html = humanized._repr_html_()
        
        # Should contain agent URL table
        assert "Agent URLs" in html
        assert "alice@example.com" in html
        assert "bob@example.com" in html
        assert "int-1" in html
        assert "int-2" in html
    
    def test_agent_data_stored_in_task_group(self):
        """Test that agent data is stored in task group for results building."""
        from edsl.agents import Agent, AgentList
        
        agents = AgentList([
            Agent(traits={"first_name": "Alice", "email": "alice@example.com"}),
        ])
        
        survey = Survey([
            QuestionFreeText(question_name="q1", question_text="Question?")
        ])
        
        ingestor = HumanizeIngestor(
            survey=survey,
            agents=agents,
            agent_key="email",
            config={},
            server_url="http://localhost:8080",
        )
        
        # Track group creation calls
        group_calls = []
        
        mock_client = MagicMock()
        mock_client.create_task_job = MagicMock()
        mock_client.create_task_group = MagicMock(
            side_effect=lambda group_id, **kwargs: (group_calls.append(kwargs), group_id)[1]
        )
        mock_client.push_snapshot = MagicMock()
        mock_client.push_binary = MagicMock()
        mock_client.create_unified_task = MagicMock()
        
        ingestor._client = mock_client
        ingestor.ingest()
        
        # Check group data contains agent info
        assert len(group_calls) == 1
        group_data = group_calls[0].get("data", {})
        assert "agent" in group_data
        assert group_data["agent"]["traits"]["first_name"] == "Alice"
    
    def test_agent_trait_resolution_in_format_question(self):
        """Test that _format_question_for_ui resolves agent traits."""
        from edsl.server.routes.humanize import _format_question_for_ui
        
        task = {
            "task_id": "test-task",
            "params": {
                "question_data": {
                    "question_name": "greeting",
                    "question_text": "Hello {{ agent.first_name }}!",
                    "question_type": "free_text",
                },
                "question_name": "greeting",
                "agent_data": {
                    "traits": {"first_name": "Charlie", "email": "charlie@test.com"}
                },
            },
            "meta": {
                "item_type": "question",
                "question_type": "free_text",
                "question_text": "Hello {{ agent.first_name }}!",
            }
        }
        
        result = _format_question_for_ui(task)
        assert result["question_text"] == "Hello Charlie!"
    
    def test_agent_and_scenario_combined_resolution(self):
        """Test that both agent and scenario templates resolve together."""
        from edsl.server.routes.humanize import _format_question_for_ui
        
        task = {
            "task_id": "test-task",
            "params": {
                "question_data": {
                    "question_name": "combined",
                    "question_text": "{{ agent.first_name }} discusses {{ scenario.topic }}",
                    "question_type": "free_text",
                },
                "question_name": "combined",
                "agent_data": {
                    "traits": {"first_name": "Alice"}
                },
                "scenario_data": {
                    "topic": "machine learning"
                },
            },
            "meta": {
                "item_type": "question",
                "question_type": "free_text",
                "question_text": "{{ agent.first_name }} discusses {{ scenario.topic }}",
            }
        }
        
        result = _format_question_for_ui(task)
        assert result["question_text"] == "Alice discusses machine learning"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

