from textwrap import dedent
from dataclasses import dataclass
from typing import List

from edsl.auto.StageBase import StageBase
from edsl.auto.StageBase import FlowDataBase
from edsl import Model
from edsl.auto.StageQuestions import StageQuestions

from edsl.questions import QuestionFreeText
from edsl.scenarios import Scenario

from edsl.auto.utilities import gen_pipeline


class StagePersona(StageBase):
    input = StageQuestions.output

    @dataclass
    class Output(FlowDataBase):
        persona: str
        questions: List[str]

    output = Output

    def handle_data(self, data):
        m = Model()
        q_persona = QuestionFreeText(
            question_text=dedent(
                """\
        Imagine a person from the population {{ population }} responding to these questions: "{{ questions }}"
        Make up a 1 paragraph persona for this person who would have answers for these questions.
        """
            ),
            question_name="persona",
        )
        results = (
            q_persona.by(m)
            .by(Scenario({"questions": data.questions, "population": data.population}))
            .run()
        )
        print("Constructing a persona that could answer the following questions:")
        print(data.questions)
        results.select("persona").print(
            pretty_labels={
                "answer.persona": f"Persona that can answer: {data.questions}"
            },
            split_at_dot=False,
        )
        persona = results.select("persona").first()
        return self.output(persona=persona, questions=data.questions)


if __name__ == "__main__":
    pipeline = gen_pipeline([StageQuestions, StagePersona])
    pipeline.process(
        pipeline.input(
            overall_question="What are some factors that could determine whether someone likes ice cream?",
            persona="People",
        )
    )
