from typing import Optional, Sequence, TYPE_CHECKING
from .macro import Macro
from .output_formatter import OutputFormatter, ScenarioAttachmentFormatter

if TYPE_CHECKING:
    from ..questions import QuestionMultipleChoice, QuestionEDSLObject
    from ..surveys import Survey


class TrueSkillRating:
    """Simple TrueSkill rating implementation."""

    def __init__(self, mu: float = 25.0, sigma: float = 8.333):
        self.mu = mu  # skill estimate
        self.sigma = sigma  # uncertainty

    @property
    def conservative_rating(self) -> float:
        """Conservative rating estimate (mu - 3*sigma)."""
        return self.mu - 3 * self.sigma

    def __repr__(self):
        return f"TrueSkillRating(mu={self.mu:.2f}, sigma={self.sigma:.2f})"


def create_true_skill_macro(
    ranking_question: "QuestionMultipleChoice",
    option_fields: Sequence[str],
    application_name: Optional[str] = None,
    description: Optional[str] = None,
    option_base: Optional[str] = None,
    rank_field: str = "rank",
    batch_size: int = 5,
    num_matches: int = 50,
    initial_mu: float = 25.0,
    initial_sigma: float = 8.333,
    beta: float = 4.166,  # half of initial_sigma
    tau: float = 0.083,  # additive dynamics factor
) -> Macro:
    """Create a Macro that ranks items using the TrueSkill algorithm via LLM batch comparisons.

    Args:
        ranking_question: A QuestionMultipleChoice configured to rank a batch of options.
            Should use Jinja placeholders like '{{ scenario.item_1 }}', '{{ scenario.item_2 }}', etc.
        option_fields: Fields from scenarios to use as ranking options.
        application_name: Optional human-readable name.
        description: Optional description.
        option_base: Optional base field name (e.g., 'food'). If omitted, inferred from the input ScenarioList.
        rank_field: Name of the rank field to include in the output ScenarioList.
        batch_size: Number of items to compare in each batch (default 5).
        num_matches: Number of ranking matches to perform (default 50).
        initial_mu: Initial skill rating estimate (default 25.0).
        initial_sigma: Initial uncertainty (default 8.333).
        beta: Skill class width (default 4.166, half of initial_sigma).
        tau: Additive dynamics factor (default 0.083).

    Returns:
        A Macro instance configured for TrueSkill ranking.
    """
    from ..surveys import Survey
    from ..questions import QuestionEDSLObject

    # Create a minimal Jobs object around this question
    survey = Survey([ranking_question])
    jobs_object = survey.to_jobs()

    # Use TrueSkill ranking algorithm
    output_formatters = (
        OutputFormatter(description="TrueSkill Ranked List", output_type="ScenarioList")
        .to_scenario_list()
        .to_true_skill_ranked_list(
            option_fields=option_fields,
            answer_field=ranking_question.question_name,
            initial_mu=initial_mu,
            initial_sigma=initial_sigma,
            beta=beta,
            tau=tau,
        )
    )

    return Macro(
        application_name=application_name or "true_skill_ranking",
        display_name=description or "TrueSkill Ranking",
        short_description=description or "Ranks items using TrueSkill algorithm.",
        long_description=description
        or "Ranks items using the TrueSkill algorithm via LLM batch comparisons.",
        initial_survey=Survey(
            [
                QuestionEDSLObject(
                    question_name="input_items",
                    question_text="Provide the items to rank as a ScenarioList",
                    expected_object_type="ScenarioList",
                )
            ]
        ),
        jobs_object=jobs_object,
        output_formatters={"true_skill": output_formatters},
        default_formatter_name="true_skill",
        attachment_formatters=[
            # Use the same pairwise comparison as RankingMacro for now
            ScenarioAttachmentFormatter(
                description="TrueSkill Pairwise", output_type="ScenarioList"
            ).choose_k(2)
        ],
    )


if __name__ == "__main__":
    pass
