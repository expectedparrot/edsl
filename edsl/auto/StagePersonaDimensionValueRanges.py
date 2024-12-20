from textwrap import dedent
from dataclasses import dataclass

from typing import List

from edsl.auto.StageBase import StageBase
from edsl.auto.StageBase import FlowDataBase

from edsl.auto.StagePersonaDimensionValues import StagePersonaDimensionValues

from edsl.questions import QuestionList
from edsl.scenarios import Scenario
from edsl import Model
from edsl.auto.utilities import gen_pipeline


class StagePersonaDimensionValueRanges(StageBase):
    input = StagePersonaDimensionValues.output

    @dataclass
    class Output(FlowDataBase):
        focal_dimension_values: List[dict]
        mapping: dict
        persona: str

    output = Output

    def handle_data(self, data):
        # breakpoint()
        """Goal with this stage is to, for each dimension, get a range of values that the persona might have for that dimension."""
        dimension_values = data["dimension_values"]
        attribute_results = data["attribute_results"]
        persona = data["persona"]
        m = Model()
        d = dict(zip(attribute_results, dimension_values))
        q = QuestionList(
            question_text=dedent(
                """\
            Consider the following persona: {{ persona }}.
            They were categorized as having the following attributes: {{ d }}.
            For this dimension: {{ focal_dimension }}, 
            What are values that other people might have on this attribute?
            """
            ),
            question_name="focal_dimension_values",
        )
        s = [
            Scenario({"persona": persona, "d": d, "focal_dimension": k})
            for k in d.keys()
        ]
        results = q.by(s).by(m).run()
        # breakpoint()
        results.select("focal_dimension", "answer.*").print(
            pretty_labels={
                "scenario.focal_dimension": f"Dimensions of a persona",
                "answer.focal_dimension_values": f"Values a person might have for that dimension",
            },
            split_at_dot=False,
        )

        focal_dimension_values = results.select("focal_dimension_values").to_list()
        mapping = dict(zip(attribute_results, focal_dimension_values))
        return self.output(
            focal_dimension_values=focal_dimension_values,
            mapping=mapping,
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
            StagePersonaDimensionValueRanges,
        ]
    )
    pipeline.process(
        pipeline.input(
            overall_question="What are some factors that could determine whether someone likes ice cream?"
        )
    )
