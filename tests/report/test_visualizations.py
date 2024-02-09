from edsl.questions import QuestionNumerical
from edsl import Survey, Agent
import unittest
from unittest.mock import patch
import os

imagepath = os.path.join(os.getcwd(), "visualization_test_outputs")

class TestPlots(unittest.TestCase):

    def test_historgram(self):
        def answer_question_directly(self, question, scenario):
            return self.traits["age"]

        agents = [Agent(traits={"age": i}) for i in range(10, 90)]
        for agent in agents:
            agent.add_direct_question_answering_method(answer_question_directly)

        q = QuestionNumerical.example()
        results = q.by(agents).run()

        # results.select("answer.age").print()
        results.histogram_plot("age", filename=os.path.join(imagepath, "age_histogram.png"))
        results.histogram_plot("age", filename=os.path.join(imagepath, "age_histogram.pdf"))
        results.histogram_plot("age", filename=os.path.join(imagepath, "age_histogram.svg"))

    def test_wordcloud(self):
        from edsl.results import Results
        example = Results.example()

        example.word_cloud_plot("how_feeling", filename=os.path.join(imagepath, "how_feeling_wordcloud.png"))
        example.word_cloud_plot("how_feeling", filename=os.path.join(imagepath, "how_feeling_wordcloud.pdf"))
        example.word_cloud_plot("how_feeling", filename=os.path.join(imagepath, "how_feeling_wordcloud.svg"))

    def test_bar_chart(self):
        from edsl.results import Results
        example = Results.example()

        example.bar_chart("how_feeling", filename=os.path.join(imagepath, "how_feeling_bar_chart.png"))
        example.bar_chart("how_feeling", filename=os.path.join(imagepath, "how_feeling_bar_chart.svg"))
        example.bar_chart("how_feeling", filename=os.path.join(imagepath, "how_feeling_bar_chart.pdf"))

    def test_faceted_bar_chart(self):
        from edsl.results import Results
        example = Results.example()

        example.faceted_bar_chart("how_feeling", "period", filename=os.path.join(imagepath, "how_feeling_faceted_bar_chart.png"))
        example.faceted_bar_chart("how_feeling", "period", filename=os.path.join(imagepath, "how_feeling_faceted_bar_chart.svg"))
        example.faceted_bar_chart("how_feeling", "period", filename=os.path.join(imagepath, "how_feeling_faceted_bar_chart.pdf"))

    def test_scatter_plot(self):

        def answer_question_directly(self, question, scenario):
            if question.question_name == "age":
                return self.traits["age"]
            if question.question_name == "height":
                return self.traits["height"]

        agents = [Agent(traits={"age": i, "height": i}) for i in range(10, 90)]
        for agent in agents:
            agent.add_direct_question_answering_method(answer_question_directly)

        q_age = QuestionNumerical(question_text = "How old are you?", question_name = "age")
        q_height = QuestionNumerical(question_text = "How tall are you?", question_name = "height")
        s = q_age.add_question(q_height)
        results = s.by(agents).run()

        results.scatter_plot("age", "height", filename=os.path.join(imagepath,"age_v_height_scatter.png"))
        results.scatter_plot("age", "height", filename=os.path.join(imagepath,"age_v_height_scatter.pdf"))
        results.scatter_plot("age", "height", filename=os.path.join(imagepath,"age_v_height_scatter.svg"))

