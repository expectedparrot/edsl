from __future__ import annotations

"""LLM similarity comparison metric for EDSL answers."""

from typing import List, Optional, Any
from ..metrics_abc import ComparisonFunction


class LLMSimilarity(ComparisonFunction):
    """Similarity judged by an LLM via EDSL linear scale question."""

    short_name = "llm_similarity"

    def execute(
        self,
        answers_A: List[str],
        answers_B: List[str],
        questions: List[Any] | None = None,
    ) -> List[Optional[float]]:
        try:
            from edsl import QuestionLinearScale, ScenarioList
        except ImportError:
            return [None] * len(answers_A)

        q = QuestionLinearScale(
            question_name="similarity",
            question_text=(
                "A question was asked. One of the answers was: {{ scenario.answer_A }}. "
                "The other answer was: {{ scenario.answer_B }}.\nHow similar are the answers?"
            ),
            question_options=[1, 2, 3, 4, 5],
            option_labels={
                1: "Not at all similar",
                2: "Somewhat similar",
                3: "Moderately similar",
                4: "Very similar",
                5: "Completely similar",
            },
        )
        sl = ScenarioList.from_list("answer_A", answers_A).add_list(
            "answer_B", answers_B
        )
        try:
            return [float(x) for x in q.by(sl).run().select("similarity").to_list()]
        except Exception:
            return [None] * len(answers_A)
