from typing import Optional, Union, Sequence
from pathlib import Path
from .app import App, HeadAttachments
from ..questions import QuestionMultipleChoice
from .output_formatter import OutputFormatter
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


        output_formatters = (OutputFormatter(
            name="Ranked Scenario List")
            .to_scenario_list()
            .to_ranked_scenario_list(option_fields = option_fields, 
             answer_field = ranking_question.question_name)
        )

        super().__init__(
            jobs_object=jobs_object,
            output_formatters=output_formatters,
            description=description,
            application_name=application_name,
            initial_survey=None,
        )

    def _prepare_from_params(self, params: 'ScenarioList') -> 'HeadAttachments':
        # Construct pairwise comparisons (choose 2) for the provided ScenarioList
        from ..scenarios import ScenarioList as _ScenarioList
        from ..scenarios import FileStore

        # Normalize input to ScenarioList
        if isinstance(params, (str, Path)):
            scenario_list: _ScenarioList = FileStore(path=str(params)).to_scenario_list()
        else:
            scenario_list = params

        if scenario_list is None or len(scenario_list) == 0:
            return _ScenarioList([])

        # Enforce maximum number of pairwise comparisons unless forced
        num_items = len(scenario_list)
        pairwise_needed = (num_items * (num_items - 1)) // 2
        if pairwise_needed > self.max_pairwise_count:
            raise ValueError(
                f"Pairwise comparisons required ({pairwise_needed}) exceed the limit ({self.max_pairwise_count}). "
                f"Pass force=True to override or initialize RankingApp with a higher max_pairwise_count."
            )

        # Determine option base from input if not provided
        base_field = self.option_base
        if base_field is None:
            first_keys = list(scenario_list[0].keys())
            if len(first_keys) != 1:
                raise ValueError("Input ScenarioList must have exactly one field per scenario to infer option_base.")
            base_field = first_keys[0]

        # Generate pairwise comparisons and run the ranking question
        pairwise_sl = scenario_list.choose_k(2)
        return HeadAttachments(scenario=pairwise_sl)

if __name__ == "__main__":
    pass


