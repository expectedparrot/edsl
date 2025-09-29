from edsl import ScenarioList, QuestionMultipleChoice
from edsl.app import RankingApp

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

app = RankingApp(
    ranking_question=q,
    option_fields=['food_1', 'food_2'],
    application_name="Food Health Ranking",
    description="Ranks foods from healthiest to least healthy using pairwise comparisons.",
    option_base="food",
    rank_field="health_rank",
)

sl = ScenarioList.from_list(
    "food",
    [
        "bread",
        "cheese puffs",
        "spinach",
        "candy canes",
        "potatoes",
        "pizza",
        "burgers",
        "soda",
        "ice cream",
        "chocolate",
        "cookies",
        "cake",
    ],
)


if __name__ == "__main__":
    ranked = app.output({"input_items": sl})
    print(ranked)


