from typing import Optional, Sequence
from .app import App
from ..questions import QuestionMultipleChoice, QuestionEDSLObject
from .output_formatter import OutputFormatter, ScenarioAttachmentFormatter
from ..surveys import Survey

class RankingApp(App):
    application_type: str = "pairwise_ranking"
    default_output_formatter: OutputFormatter = OutputFormatter(name="Ranked Scenario List")

    def __init__(
        self,
        ranking_question: QuestionMultipleChoice,
        option_fields: Sequence[str],
        application_name: Optional[str] = None,
        description: Optional[str] = None,
        option_base: Optional[str] = None,
        rank_field: str = "rank",
        max_pairwise_count: int = 500,
    ):
        """An app that ranks items from a ScenarioList via pairwise comparisons.

        Args:
            ranking_question: A QuestionMultipleChoice configured to compare two options
                using Jinja placeholders like '{{ scenario.<field>_1 }}' and '{{ scenario.<field>_2 }}'.
            application_name: Optional human-readable name.
            description: Optional description.
            option_base: Optional base field name (e.g., 'food'). If omitted, inferred from the input ScenarioList.
            rank_field: Name of the rank field to include in the output ScenarioList.
            output_formatters: Optional output formatters (not used by this app's output but required by base class).
        """
        # Create a minimal Jobs object around this question; not used directly by output(),
        # but required by the base App constructor.
        survey = Survey([ranking_question])
        jobs_object = survey.to_jobs()

        self.ranking_question = ranking_question
        self.option_base = option_base
        self.rank_field = rank_field
        self.max_pairwise_count = max_pairwise_count


        output_formatters = (
            OutputFormatter(name="Ranked Scenario List")
            .to_scenario_list()
            .to_ranked_scenario_list(
                option_fields=option_fields, answer_field=ranking_question.question_name
            )
        )

        super().__init__(
            jobs_object=jobs_object,
            output_formatters=output_formatters,
            attachment_formatters=[
                # Transform the provided ScenarioList into pairwise comparisons
                ScenarioAttachmentFormatter(name="Pairwise choose_k").choose_k(2)
            ],
            description=description,
            application_name=application_name,
            initial_survey=Survey(
                [
                    QuestionEDSLObject(
                        question_name="input_items",
                        question_text="Provide the items to rank as a ScenarioList",
                        expected_object_type="ScenarioList",
                    )
                ]
            ),
        )

if __name__ == "__main__":
    pass


