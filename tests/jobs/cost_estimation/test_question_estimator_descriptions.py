from edsl.jobs.cost_estimation.question_estimators import (
    ZeroCostEstimator,
    FreeTextStyleEstimator,
    StructuredAnswerEstimator,
    DemandEstimator,
    MatrixEstimator,
    DefaultEstimator,
    QuestionEstimator,
)
from edsl.jobs.cost_estimation.cost_estimation_constants import TokenAmount, TokenRatio


class TestDescribeMethods:
    def test_zero_cost_estimator(self):
        assert (
            ZeroCostEstimator().describe()
            == "No LLM call — answered locally (zero cost)"
        )

    def test_free_text_fixed(self):
        assert (
            FreeTextStyleEstimator(output=TokenAmount(500)).describe()
            == "Output fixed at 500 tokens"
        )

    def test_free_text_ratio_100(self):
        assert (
            FreeTextStyleEstimator(output=TokenRatio(1.0)).describe()
            == "Output estimated at 100% of prompt tokens"
        )

    def test_free_text_ratio_75(self):
        assert (
            FreeTextStyleEstimator(output=TokenRatio(0.75)).describe()
            == "Output estimated at 75% of prompt tokens"
        )

    def test_structured_answer_fixed_comment(self):
        assert (
            StructuredAnswerEstimator(comment=TokenAmount(60)).describe()
            == "Answer from option text length + 60 comment tokens"
        )

    def test_structured_answer_ratio_comment(self):
        assert (
            StructuredAnswerEstimator(comment=TokenRatio(0.5)).describe()
            == "Answer from option text length + 50% of prompt tokens for comment"
        )

    def test_demand_default(self):
        assert (
            DemandEstimator().describe()
            == "Answer scales with price point count (1 token/price) + 60 comment tokens"
        )

    def test_demand_custom_tokens_per_price(self):
        assert (
            DemandEstimator(tokens_per_price=2).describe()
            == "Answer scales with price point count (2 token/price) + 60 comment tokens"
        )

    def test_matrix_default(self):
        assert (
            MatrixEstimator().describe()
            == "Answer from option text + 20 comment tokens per row"
        )

    def test_matrix_custom_tokens_per_item(self):
        assert (
            MatrixEstimator(tokens_per_item=35).describe()
            == "Answer from option text + 35 comment tokens per row"
        )

    def test_default_estimator(self):
        assert (
            DefaultEstimator().describe()
            == "Unknown question type — output estimated at 100% of prompt tokens (fallback)"
        )

    def test_description_for_interview(self):
        assert (
            QuestionEstimator().description_for("interview")
            == "Output fixed at 500 tokens"
        )

    def test_description_for_free_text(self):
        assert (
            QuestionEstimator().description_for("free_text")
            == "Output estimated at 100% of prompt tokens"
        )

    def test_description_for_multiple_choice(self):
        assert (
            QuestionEstimator().description_for("multiple_choice")
            == "Answer from option text length + 60 comment tokens"
        )

    def test_description_for_override(self):
        qe = QuestionEstimator(
            overrides={"free_text": FreeTextStyleEstimator(output=TokenAmount(200))}
        )
        assert qe.description_for("free_text") == "Output fixed at 200 tokens"

    def test_description_for_unknown_type(self):
        assert (
            QuestionEstimator().description_for("nonexistent_type")
            == "Unknown question type — output estimated at 100% of prompt tokens (fallback)"
        )
