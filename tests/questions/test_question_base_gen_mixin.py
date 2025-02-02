import pytest
from unittest.mock import patch
from edsl import QuestionFreeText, QuestionMultipleChoice, ScenarioList, Agent, Model


class TestQuestionBaseGenMixin:
    def test_copy(self):
        """Test that the copy method returns a deep copy."""
        q = QuestionFreeText(question_name="color", question_text="What is your favorite color?")
        q_copy = q.copy()
        
        assert q_copy is not q  # Ensure it's a new object
        assert q_copy.question_name == q.question_name
        assert q_copy.question_text == q.question_text

    def test_option_permutations(self):
        """Test that option_permutations generates correct permutations."""
        q = QuestionMultipleChoice(question_name="fruit", question_text="Pick a fruit", question_options=["Apple", "Banana", "Cherry"])
        permutations = q.option_permutations()
        
        assert len(permutations) == 6  # 3! = 6 permutations
        assert all(len(p.question_options) == len(q.question_options) for p in permutations)

    def test_draw(self):
        """Test that draw returns a new question with shuffled options."""
        q = QuestionMultipleChoice(question_name="drink", question_text="Pick a drink", question_options=["Tea", "Coffee", "Juice"])
        
        with patch("random.sample", return_value=["Juice", "Tea", "Coffee"]):
            drawn = q.draw()

        assert drawn is not q
        assert set(drawn.question_options) == set(q.question_options)
        assert drawn.question_options == ["Juice", "Tea", "Coffee"]

    def test_loop(self):
        """Test that loop creates correctly named questions based on scenarios."""
        q = QuestionFreeText(question_name="base_{{subject}}", question_text="What are your thoughts on: {{subject}}?")
        scenarios = ScenarioList.from_list("subject", ["Math", "Economics", "Chemistry"])
        looped_questions = q.loop(scenarios)

        assert len(looped_questions) == 3
        assert looped_questions[0].question_name == "base_Math"
        assert looped_questions[1].question_name == "base_Economics"
        assert looped_questions[2].question_name == "base_Chemistry"

    def test_render(self):
        """Test that render correctly replaces variables in text."""
        m = Model("test")
        a = Agent(traits = {"hair_color":"red"})
        q = QuestionFreeText(question_name = "test", question_text = "How do you say '{{ agent.hair_color }}' in German?")
        rendered_q = q.render({"agent.hair_color": "red"})

        assert rendered_q.question_text == "How do you say 'red' in German?"
        
        rendered_q.run(disable_remote_inference=True, stop_on_exception=True)


    def test_apply_function(self):
        """Test that apply_function transforms question fields correctly."""
        q = QuestionFreeText(question_name="color", question_text="What is your favorite color?")
        upper_case_func = lambda x: x.upper()
        
        transformed_q = q.apply_function(upper_case_func)
        
        assert transformed_q.question_text == "WHAT IS YOUR FAVORITE COLOR?"
        assert transformed_q.question_name == "color"  # Should remain unchanged


if __name__ == "__main__":
    pytest.main()
