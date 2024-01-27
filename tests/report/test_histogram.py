from edsl.questions import QuestionNumerical
from edsl import Survey, Agent
import unittest
from unittest.mock import patch


class TestPlots(unittest.TestCase):
    @patch("webbrowser.open")
    def test_historgram(self, mock_open):
        def answer_question_directly(self, question, scenario):
            return self.traits["age"]

        agents = [Agent(traits={"age": i}) for i in range(10, 90)]
        for agent in agents:
            agent.add_direct_question_answering_method(answer_question_directly)

        q = QuestionNumerical.example()
        results = q.by(agents).run()

        # results.select("answer.age").print()
        results.histogram_plot("age")
        mock_open.assert_called_once()


class AgentKnowsAge(Agent):
    def answer_question_directly(self, question: QuestionNumerical) -> int:
        return self.traits["age"]


agents = [AgentKnowsAge(traits={"age": i}) for i in range(10, 90)]

q = QuestionNumerical.example()
results = q.by(agents).run()
