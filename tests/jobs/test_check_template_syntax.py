import pytest
from edsl.jobs.check_template_syntax import CheckTemplateSyntax
from edsl.jobs.exceptions import JobsCompatibilityError
from edsl.questions import QuestionFreeText, QuestionMultipleChoice
from edsl.surveys import Survey


class TestCheckTemplateSyntax:
    """Test cases for CheckTemplateSyntax validator."""
    
    def test_valid_scenario_reference(self):
        """Test that valid {{scenario.field}} syntax passes validation."""
        q = QuestionFreeText(
            question_name="test_q",
            question_text="Price is {{scenario.price}} dollars"
        )
        survey = Survey(questions=[q])
        checker = CheckTemplateSyntax(survey)
        
        # Should not raise an exception
        checker.check()
    
    def test_valid_question_reference(self):
        """Test that valid {{question_name.field}} syntax passes validation."""
        q1 = QuestionFreeText(
            question_name="name_q",
            question_text="What is your name?"
        )
        q2 = QuestionFreeText(
            question_name="greeting_q", 
            question_text="Hello {{name_q.answer}}, how are you?"
        )
        survey = Survey(questions=[q1, q2])
        checker = CheckTemplateSyntax(survey)
        
        # Should not raise an exception
        checker.check()
    
    def test_multiple_valid_references(self):
        """Test multiple valid template references in same question."""
        q = QuestionFreeText(
            question_name="complex_q",
            question_text="Price: {{scenario.price}}, Quantity: {{scenario.quantity}}"
        )
        survey = Survey(questions=[q])
        checker = CheckTemplateSyntax(survey)
        
        # Should not raise an exception
        checker.check()
    
    def test_invalid_variable_name_without_suggestion(self):
        """Test that invalid variable names raise JobsCompatibilityError."""
        q = QuestionFreeText(
            question_name="test_q",
            question_text="Invalid reference: {{unknown_var.field}}"
        )
        survey = Survey(questions=[q])
        checker = CheckTemplateSyntax(survey)
        
        with pytest.raises(JobsCompatibilityError) as exc_info:
            checker.check()
        
        error_msg = str(exc_info.value)
        assert "Invalid template syntax" in error_msg
        assert "unknown_var.field" in error_msg
        assert "is not a valid reference" in error_msg
        assert "scenario.field" in error_msg
    
    def test_misspelled_question_name_with_suggestion(self):
        """Test that misspelled question names get helpful suggestions."""
        q1 = QuestionFreeText(
            question_name="user_name",
            question_text="What is your name?"
        )
        q2 = QuestionFreeText(
            question_name="greeting_q",
            question_text="Hello {{user_nam.answer}}"  # Misspelled 'user_name'
        )
        survey = Survey(questions=[q1, q2])
        checker = CheckTemplateSyntax(survey)
        
        with pytest.raises(JobsCompatibilityError) as exc_info:
            checker.check()
        
        error_msg = str(exc_info.value)
        assert "Invalid template syntax" in error_msg
        assert "user_nam.answer" in error_msg
        assert "Did you mean: '{{user_name.answer}}'" in error_msg
    
    def test_find_closest_question_name_exact_match(self):
        """Test _find_closest_question_name with high similarity."""
        q = QuestionFreeText(question_name="test_question", question_text="Test")
        survey = Survey(questions=[q])
        checker = CheckTemplateSyntax(survey)
        
        question_names = {"test_question", "other_question"}
        closest = checker._find_closest_question_name("test_questio", question_names)
        assert closest == "test_question"
    
    def test_find_closest_question_name_no_match(self):
        """Test _find_closest_question_name with low similarity."""
        q = QuestionFreeText(question_name="test_question", question_text="Test")
        survey = Survey(questions=[q])
        checker = CheckTemplateSyntax(survey)
        
        question_names = {"test_question", "other_question"}
        closest = checker._find_closest_question_name("completely_different", question_names)
        assert closest is None
    
    def test_complex_text_with_mixed_templates(self):
        """Test complex question text with multiple template types."""
        q1 = QuestionFreeText(question_name="age", question_text="What is your age?")
        q2 = QuestionMultipleChoice(
            question_name="complex",
            question_text="You are {{age.answer}} years old and the price is {{scenario.price}}",
            question_options=["Yes", "No"]
        )
        survey = Survey(questions=[q1, q2])
        checker = CheckTemplateSyntax(survey)
        
        # Should not raise an exception
        checker.check()
    
    def test_whitespace_in_templates(self):
        """Test that templates with whitespace are handled correctly."""
        q = QuestionFreeText(
            question_name="test_q",
            question_text="Price: {{ scenario.price }} and quantity: {{  scenario.quantity  }}"
        )
        survey = Survey(questions=[q])
        checker = CheckTemplateSyntax(survey)
        
        # Should not raise an exception
        checker.check()
    
    def test_invalid_template_with_whitespace(self):
        """Test invalid template with whitespace still gets caught."""
        q = QuestionFreeText(
            question_name="test_q",
            question_text="Invalid: {{ invalid_var.field }} here"
        )
        survey = Survey(questions=[q])
        checker = CheckTemplateSyntax(survey)
        
        with pytest.raises(JobsCompatibilityError) as exc_info:
            checker.check()
        
        error_msg = str(exc_info.value)
        assert "invalid_var.field" in error_msg
    
    def test_empty_survey(self):
        """Test checker with empty survey."""
        survey = Survey(questions=[])
        checker = CheckTemplateSyntax(survey)
        
        # Should not raise an exception
        checker.check()
    
    def test_question_without_templates(self):
        """Test question with no template syntax."""
        q = QuestionFreeText(
            question_name="simple_q",
            question_text="What is your favorite color?"
        )
        survey = Survey(questions=[q])
        checker = CheckTemplateSyntax(survey)
        
        # Should not raise an exception
        checker.check()
    
    def test_multiple_errors_in_same_question(self):
        """Test that first error is caught when multiple exist."""
        q = QuestionFreeText(
            question_name="test_q",
            question_text="{{invalid1.field}} and {{invalid2.field}}"
        )
        survey = Survey(questions=[q])
        checker = CheckTemplateSyntax(survey)
        
        with pytest.raises(JobsCompatibilityError) as exc_info:
            checker.check()
        
        # Should catch the first error
        error_msg = str(exc_info.value)
        assert "invalid1.field" in error_msg
    
    def test_error_message_includes_question_name(self):
        """Test that error messages include the problematic question name."""
        q = QuestionFreeText(
            question_name="problematic_question",
            question_text="{{bad_ref.field}}"
        )
        survey = Survey(questions=[q])
        checker = CheckTemplateSyntax(survey)
        
        with pytest.raises(JobsCompatibilityError) as exc_info:
            checker.check()
        
        error_msg = str(exc_info.value)
        assert "problematic_question" in error_msg
    
    def test_available_questions_in_error_message(self):
        """Test that error message shows available question names."""
        q1 = QuestionFreeText(question_name="question_one", question_text="Test 1")
        q2 = QuestionFreeText(question_name="question_two", question_text="Test 2")
        q3 = QuestionFreeText(
            question_name="bad_question",
            question_text="{{invalid_ref.field}}"
        )
        survey = Survey(questions=[q1, q2, q3])
        checker = CheckTemplateSyntax(survey)
        
        with pytest.raises(JobsCompatibilityError) as exc_info:
            checker.check()
        
        error_msg = str(exc_info.value)
        assert "Available questions:" in error_msg
        assert "question_one" in error_msg
        assert "question_two" in error_msg

    def test_valid_agent_reference(self):
        """Test that valid {{agent.field}} syntax passes validation."""
        q = QuestionFreeText(
            question_name="test_q",
            question_text="You are a {{agent.persona}} person"
        )
        survey = Survey(questions=[q])
        checker = CheckTemplateSyntax(survey)
        
        # Should not raise an exception
        checker.check()
    
    def test_mixed_agent_and_scenario_references(self):
        """Test that {{agent.field}} and {{scenario.field}} can coexist."""
        q = QuestionFreeText(
            question_name="test_q",
            question_text="As a {{agent.persona}}, what do you think about {{scenario.topic}}?"
        )
        survey = Survey(questions=[q])
        checker = CheckTemplateSyntax(survey)
        
        # Should not raise an exception
        checker.check()
    
    def test_agent_scenario_question_mix(self):
        """Test that agent, scenario, and question references work together."""
        q1 = QuestionFreeText(
            question_name="age",
            question_text="What is your age?"
        )
        q2 = QuestionFreeText(
            question_name="complex",
            question_text="You are {{agent.persona}}, aged {{age.answer}}, discussing {{scenario.topic}}"
        )
        survey = Survey(questions=[q1, q2])
        checker = CheckTemplateSyntax(survey)
        
        # Should not raise an exception
        checker.check()
    
    def test_invalid_reference_suggests_agent_option(self):
        """Test that invalid references now suggest agent as an option."""
        q = QuestionFreeText(
            question_name="test_q",
            question_text="Invalid reference: {{invalid_var.field}}"
        )
        survey = Survey(questions=[q])
        checker = CheckTemplateSyntax(survey)
        
        with pytest.raises(JobsCompatibilityError) as exc_info:
            checker.check()
        
        error_msg = str(exc_info.value)
        assert "Invalid template syntax" in error_msg
        assert "invalid_var.field" in error_msg
        assert "is not a valid reference" in error_msg
        assert "{{scenario.field}}" in error_msg
        assert "{{agent.field}}" in error_msg