from textwrap import dedent
from dataclasses import dataclass

from typing import List

from edsl.auto.StageBase import StageBase
from edsl.auto.StageBase import FlowDataBase

from edsl.auto.StagePersona import StagePersona

from edsl.questions import QuestionList
from edsl.scenarios import Scenario
from edsl import Model

from edsl.auto.utilities import gen_pipeline


class StagePersonaDimensions(StageBase):
    input = StagePersona.output

    @dataclass
    class Output(FlowDataBase):
        attribute_results: List[str]
        persona: str

    output = Output

    def handle_data(self, data):
        q_attributes = QuestionList(
            question_text=dedent(
                """\
            Here is a persona: "{{ persona }}"
            It was construced to be someone who could answer these questions: "{{ questions }}"

            We want to identify the general dimensions that make up this persona.
            E.g., if the person is desribed as 'happy' then a dimenion would be  'mood'
            """
            ),
            question_name="find_attributes",
        )
        m = Model()
        results = (
            q_attributes.by(
                Scenario({"persona": data.persona, "questions": data.questions})
            )
            .by(m)
            .run()
        )
        (
            results.select("find_attributes").print(
                pretty_labels={
                    "answer.find_attributes": f'Persona dimensions for: "{data.persona}"'
                },
                split_at_dot=False,
            )
        )
        attribute_results = results.select("find_attributes").first()
        return self.output(attribute_results=attribute_results, persona=data.persona)


if __name__ == "__main__":
    from edsl.auto.StageQuestions import StageQuestions

    pipeline = gen_pipeline([StageQuestions, StagePersona, StagePersonaDimensions])
    pipeline.process(
        pipeline.input(
            overall_question="What are some factors that could determine whether someone likes ice cream?"
        )
    )
