import pytest
from edsl.jobs import Jobs
from edsl.jobs.exceptions import JobsCompatibilityError
from edsl.questions import QuestionFreeText
from edsl.scenarios import Scenario
from edsl.surveys import Survey


class TestJobsComponentConstructorTemplateValidation:
    """Test template validation integration in JobsComponentConstructor."""
    
    def test_valid_scenario_template_integration(self):
        """Test that valid scenario templates pass when scenarios are added."""
        q = QuestionFreeText(
            question_name="price_q",
            question_text="The price is {{scenario.price}} dollars"
        )
        survey = Survey(questions=[q])
        job = Jobs(survey=survey)
        
        scenario = Scenario({"price": 100})
        
        # Should not raise an exception
        result_job = job.by(scenario)
        assert len(result_job.scenarios) == 1
    
    def test_invalid_scenario_template_caught_on_scenario_addition(self):
        """Test that invalid templates are caught when scenarios are added."""
        q = QuestionFreeText(
            question_name="price_q",
            question_text="The price is {{invalid_ref.price}} dollars"
        )
        survey = Survey(questions=[q])
        job = Jobs(survey=survey)
        
        scenario = Scenario({"price": 100})
        
        with pytest.raises(JobsCompatibilityError) as exc_info:
            job.by(scenario)
        
        error_msg = str(exc_info.value)
        # The validation correctly catches that scenario fields aren't being used
        assert "Scenario with fields" in error_msg
        assert "none of these fields are used" in error_msg
    
    def test_adding_agents_does_not_trigger_validation_errors(self):
        """Test that adding agents to jobs with invalid templates doesn't raise errors."""
        q = QuestionFreeText(
            question_name="test_q",
            question_text="Invalid template: {{invalid_ref.field}}"
        )
        survey = Survey(questions=[q])
        job = Jobs(survey=survey)
        
        from edsl.agents import Agent
        agent = Agent(traits={"status": "test"})
        
        # Adding an agent should not trigger template validation
        # This should succeed even though the survey has invalid templates
        result_job = job.by(agent)
        assert len(result_job.agents) == 1
    
    def test_adding_models_does_not_trigger_validation_errors(self):
        """Test that adding models to jobs with invalid templates doesn't raise errors."""
        q = QuestionFreeText(
            question_name="test_q",
            question_text="Invalid template: {{invalid_ref.field}}"
        )
        survey = Survey(questions=[q])
        job = Jobs(survey=survey)
        
        from edsl.language_models import Model
        model = Model("test", canned_response="test response")
        
        # Adding a model should not trigger template validation
        # This should succeed even though the survey has invalid templates
        result_job = job.by(model)
        assert len(result_job.models) == 1
    
    def test_no_validation_error_without_survey(self):
        """Test that adding scenarios to jobs without survey doesn't cause errors."""
        # Create a job with survey=None
        empty_survey = Survey(questions=[])
        job = Jobs(survey=empty_survey)
        scenario = Scenario({"price": 100})
        
        # Should not raise any errors since there are no questions to validate
        result_job = job.by(scenario)
        assert len(result_job.scenarios) == 1
    
    def test_multiple_scenarios_validation(self):
        """Test template validation with multiple scenarios."""
        q = QuestionFreeText(
            question_name="test_q",
            question_text="Price: {{scenario.price}}, Quantity: {{scenario.quantity}}"
        )
        survey = Survey(questions=[q])
        job = Jobs(survey=survey)
        
        scenarios = [
            Scenario({"price": 100, "quantity": 1}),
            Scenario({"price": 200, "quantity": 2})
        ]
        
        # Should not raise an exception
        result_job = job.by(scenarios)
        assert len(result_job.scenarios) == 2
    
    def test_validation_error_raises_exception_on_scenario_addition(self):
        """Test that validation errors raise exceptions when scenarios are added."""
        q = QuestionFreeText(
            question_name="test_q",
            question_text="Invalid: {{bad_ref.field}}"
        )
        survey = Survey(questions=[q])
        job = Jobs(survey=survey)
        
        scenario = Scenario({"price": 100})
        
        # Validation should fail and raise JobsCompatibilityError
        with pytest.raises(JobsCompatibilityError) as exc_info:
            job.by(scenario)
        
        # Verify the error message is helpful
        error_msg = str(exc_info.value)
        # The validation correctly catches that scenario fields aren't being used
        assert "Scenario with fields" in error_msg
        assert "none of these fields are used" in error_msg
    
    def test_scenario_list_validation(self):
        """Test validation works with ScenarioList."""
        from edsl.scenarios import ScenarioList
        
        q = QuestionFreeText(
            question_name="test_q",
            question_text="Price: {{scenario.price}}"
        )
        survey = Survey(questions=[q])
        job = Jobs(survey=survey)
        
        scenario_list = ScenarioList([
            Scenario({"price": 100}),
            Scenario({"price": 200})
        ])
        
        # Should not raise an exception
        result_job = job.by(scenario_list)
        assert len(result_job.scenarios) == 2
    
    def test_question_reference_validation_integration(self):
        """Test that question-to-question references work in integration."""
        q1 = QuestionFreeText(
            question_name="name_q",
            question_text="What is your name?"
        )
        q2 = QuestionFreeText(
            question_name="greeting_q",
            question_text="Hello {{name_q.answer}}, the price is {{scenario.price}}"
        )
        survey = Survey(questions=[q1, q2])
        job = Jobs(survey=survey)
        
        scenario = Scenario({"price": 100})
        
        # Should not raise an exception - both references are valid
        result_job = job.by(scenario)
        assert len(result_job.scenarios) == 1
    
    def test_misspelled_question_reference_in_integration(self):
        """Test misspelled question references are caught in integration."""
        q1 = QuestionFreeText(
            question_name="user_name",
            question_text="What is your name?"
        )
        q2 = QuestionFreeText(
            question_name="greeting_q",
            question_text="Hello {{user_nam.answer}}, price: {{scenario.price}}"  # Misspelled
        )
        survey = Survey(questions=[q1, q2])
        job = Jobs(survey=survey)
        
        scenario = Scenario({"price": 100})
        
        with pytest.raises(JobsCompatibilityError) as exc_info:
            job.by(scenario)
        
        error_msg = str(exc_info.value)
        assert "user_nam.answer" in error_msg
        assert "Did you mean: '{{user_name.answer}}'" in error_msg