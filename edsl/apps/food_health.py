from edsl import ScenarioList, QuestionMultipleChoice
from edsl.app.app import RankingApp


def build() -> RankingApp:
    """Construct a RankingApp configured to rank foods by healthiness.

    The app expects a ScenarioList with a single field 'food', and it will
    generate pairwise comparisons automatically and return a ranked ScenarioList
    with the field 'health_rank'.
    """
    q = QuestionMultipleChoice(
        question_name="rank_foods",
        question_text="Which food is generally considered healthier?",
        question_options=["{{ scenario.food_1 }}", "{{ scenario.food_2 }}"],
    )
    return RankingApp(
        ranking_question=q,
        application_name="Food Health Ranking",
        description="Ranks foods from healthiest to least healthy using pairwise comparisons.",
        option_base="food",
        rank_field="health_rank",
    )


def example_scenario_list() -> ScenarioList:
    return ScenarioList.from_list(
        "food",
        [
            "bread",
            "cheese puffs",
            "spinach",
            "candy canes",
            "potatoes",
        ],
    )


if __name__ == "__main__":
    app = build()
    sl = example_scenario_list()
    ranked = app.output(sl)
    print(ranked)


