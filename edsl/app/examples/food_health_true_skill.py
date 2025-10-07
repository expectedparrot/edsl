from edsl import ScenarioList, QuestionMultipleChoice
from edsl.app import TrueSkillApp

"""Construct a TrueSkillApp configured to rank foods by healthiness using TrueSkill algorithm.

The app expects a ScenarioList with a single field 'food', and it will
generate batch comparisons automatically and return a ranked ScenarioList
with TrueSkill ratings and ranks.
"""

q = QuestionMultipleChoice(
    question_name="rank_food_batch",
    question_text="Please rank these foods from healthiest to least healthy:",
    question_options=[
        "{{ scenario.food_1 }}",
        "{{ scenario.food_2 }}"
    ],
)

app = TrueSkillApp(
    ranking_question=q,
    option_fields=['food_1', 'food_2'],
    application_name="food_health_trueskill",
    display_name="Food Health TrueSkill Ranking",
    short_description="Ranks foods from healthiest to least healthy using TrueSkill algorithm.",
    long_description="Ranks foods from healthiest to least healthy using TrueSkill algorithm with pairwise comparisons.",
    option_base="food",
    rank_field="health_rank",
    batch_size=2,
    num_matches=10,
)

sl = ScenarioList.from_list(
    "food",
    [
        "spinach",
        "broccoli",
        "salmon",
        "quinoa",
        "blueberries",
        "avocado",
        "chicken breast",
        "sweet potato",
        "pizza",
        "burgers",
        "soda",
        "ice cream",
        "candy bars",
        "french fries",
        "donuts",
        "cookies",
    ],
)


if __name__ == "__main__":
    ranked = app.output({"input_items": sl})
    print(ranked)