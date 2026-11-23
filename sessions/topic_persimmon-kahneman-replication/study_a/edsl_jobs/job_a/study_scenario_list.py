"""Define the approved repeated study stimuli."""

from edsl import Scenario, ScenarioList


# Counterbalance both design factors with fixed equal allocation: two prior
# conditions crossed with two response targets. Each scenario is run at n=50.
scenarios = []
for engineer_count, lawyer_count in [(30, 70), (70, 30)]:
    for target_occupation, target_count in [
        ("engineers", engineer_count),
        ("lawyers", lawyer_count),
    ]:
        scenarios.append(
            {
                "engineer_count": engineer_count,
                "lawyer_count": lawyer_count,
                "target_occupation": target_occupation,
                "target_count": target_count,
            }
        )
scenario_list = ScenarioList([Scenario(values) for values in scenarios])


if __name__ == "__main__":
    scenario_list.git.save("scenario_list.ep")
