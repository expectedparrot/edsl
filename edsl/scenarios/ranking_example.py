from edsl import ScenarioList 

s = ScenarioList.from_list("food", ['bread', 'cheese puffs', 'spinach', 'candy canes', 'potatoes'])

sl_combo = s.choose_k(2)

from edsl import QuestionMultipleChoice
from edsl.scenarios.ranking_algorithm import results_to_ranked_scenario_list

q = QuestionMultipleChoice(
    question_name = "rank_foods", 
    question_text = "Which food is generally considered healthier?",
    question_options = ['{{ scenario.food_1}}', '{{ scenario.food_2 }}'],
)
results = q.by(sl_combo).run(stop_on_exception = True)
print(results)

# Rank items best-to-worst using pairwise ranking
ranked_sl = results_to_ranked_scenario_list(results)
print(ranked_sl)
