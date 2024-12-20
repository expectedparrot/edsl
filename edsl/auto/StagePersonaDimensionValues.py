from textwrap import dedent
from dataclasses import dataclass

from typing import List, Dict

from edsl.auto.StageBase import StageBase
from edsl.auto.StageBase import FlowDataBase

from edsl.auto.StagePersonaDimensions import StagePersonaDimensions
from edsl import Model
from edsl.questions import QuestionList, QuestionExtract
from edsl.scenarios import Scenario

from edsl.auto.utilities import gen_pipeline


class StagePersonaDimensionValues(StageBase):
    input = StagePersonaDimensions.output

    @dataclass
    class Output(FlowDataBase):
        attribute_results: List[str]
        dimension_values: Dict[str, str]
        persona: str

    output = Output

    def handle_data(self, data):
        attribute_results = data.attribute_results
        persona = data.persona
        m = Model()
        q = QuestionExtract(
            question_text=dedent(
                """\
            This is a persona: "{{ persona }}"
            They vary on the following dimensions: "{{ attribute_results }}"
            For each dimenion, what are some values that this persona might have for that dimension?
            Please keep answers very short, ideally one word.
            """
            ),
            answer_template={k: None for k in attribute_results},
            question_name="dimension_values",
        )
        results = (
            q.by(Scenario({"attribute_results": attribute_results, "persona": persona}))
            .by(m)
            .run()
        )
        results.select("attribute_results", "dimension_values").print()
        return self.output(
            dimension_values=results.select("dimension_values").first(),
            attribute_results=attribute_results,
            persona=persona,
        )


if __name__ == "__main__":
    from edsl.auto.StageQuestions import StageQuestions
    from edsl.auto.StagePersona import StagePersona
    from edsl.auto.StagePersonaDimensions import StagePersonaDimensions

    pipeline = gen_pipeline(
        [
            StageQuestions,
            StagePersona,
            StagePersonaDimensions,
            StagePersonaDimensionValues,
        ]
    )
    pipeline.process(
        pipeline.input(
            overall_question="What are some factors that could determine whether someone likes ice cream?"
        )
    )
