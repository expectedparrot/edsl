from dataclasses import dataclass
from typing import List
from textwrap import dedent


from edsl import Scenario
from edsl import Model
from edsl.questions.QuestionList import QuestionList

from edsl.auto.StageBase import StageBase
from edsl.auto.StageBase import FlowDataBase

from edsl.auto.utilities import gen_pipeline


class StageQuestions(StageBase):
    "This stages takes as input an overall question and returns a list of questions"

    @dataclass
    class Input(FlowDataBase):
        overall_question: str
        population: str

    @dataclass
    class Output(FlowDataBase):
        questions: List[str]
        population: str

    input = Input
    output = Output

    def handle_data(self, data):
        m = Model()
        overall_question = data.overall_question
        population = data.population
        s = Scenario({"overall_question": overall_question, "population": population})
        q = QuestionList(
            question_text=dedent(
                """\
            Suppose I am interested in the question: 
            "{{ overall_question }}" 
            What would be some survey questions I could ask to {{ population }} that might shed light on this question?
            """
            ),
            question_name="questions",
        )
        results = q.by(s).by(m).run()
        (
            results.select("questions").print(
                pretty_labels={
                    "answer.questions": f'Questions for overall question: "{overall_question }"'
                },
                split_at_dot=False,
            )
        )

        raw_questions = results.select("questions").first()
        questions = [q.replace("'", "").replace(":", "") for q in raw_questions]
        return self.Output(questions=questions, population=population)


if __name__ == "__main__":
    pipeline = gen_pipeline([StageQuestions])

    pipeline.process(
        pipeline.input(
            overall_question="What are some factors that could determine whether someone likes ice cream?",
            population="Consumers",
        )
    )
    StageQuestions.func(
        overall_question="Why aren't my students studying more?", population="Tech"
    )
