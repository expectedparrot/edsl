from typing import Sequence, Dict, Any
try:
    import trueskill
    TRUESKILL_AVAILABLE = True
except ImportError:
    TRUESKILL_AVAILABLE = False
from .scenario_list import ScenarioList
from .scenario import Scenario


def results_to_true_skill_ranked_list(
    scenario_list: "ScenarioList",
    option_fields: Sequence[str],
    answer_field: str,
    include_rank: bool = True,
    rank_field: str = "rank",
    item_field: str = "item",
    mu_field: str = "mu",
    sigma_field: str = "sigma",
    conservative_rating_field: str = "conservative_rating",
    initial_mu: float = 25.0,
    initial_sigma: float = 8.333,
    beta: float = None,
    tau: float = None,
    **kwargs
) -> "ScenarioList":
    """
    Convert pairwise comparison results into a TrueSkill-ranked ScenarioList.

    Args:
        scenario_list: The data containing pairwise comparison results.
        option_fields: List of scenario column names containing the compared options.
        answer_field: Name of the answer column containing the chosen option.
        include_rank: If True, include a rank field on each returned Scenario.
        rank_field: Name of the rank field to include when include_rank is True.
        item_field: Field name used to store the ranked item value on each Scenario.
        mu_field: Field name for TrueSkill mu (skill estimate).
        sigma_field: Field name for TrueSkill sigma (uncertainty).
        conservative_rating_field: Field name for conservative rating.
        initial_mu: Initial skill rating.
        initial_sigma: Initial uncertainty.
        beta: Skill class width (defaults to initial_sigma/2).
        tau: Dynamics factor (defaults to initial_sigma/300).

    Returns:
        ScenarioList ordered best-to-worst according to TrueSkill ranking.
    """
    if not TRUESKILL_AVAILABLE:
        raise ImportError(
            "The trueskill library is required for this function. "
            "Install it with: pip install trueskill"
        )

    if not option_fields or len(option_fields) < 2:
        raise ValueError("option_fields must include at least two scenario columns")

    # Set TrueSkill environment parameters
    if beta is None:
        beta = initial_sigma / 2
    if tau is None:
        tau = initial_sigma / 300

    # Configure TrueSkill environment
    trueskill.setup(mu=initial_mu, sigma=initial_sigma, beta=beta, tau=tau)

    # Convert to row dicts
    rows = scenario_list.to_dicts(remove_prefix=False)

    # Validate fields exist
    if not rows:
        return ScenarioList([])

    first_row_keys = set(rows[0].keys())
    missing_options = [f for f in option_fields if f not in first_row_keys]
    if missing_options:
        raise ValueError(f"Missing option fields in data: {missing_options}")
    if answer_field not in first_row_keys:
        raise ValueError(f"Missing answer field in data: {answer_field}")

    # Extract all items and initialize ratings
    all_items = set()
    for row in rows:
        option_values = [row.get(field) for field in option_fields]
        for value in option_values:
            if value is not None:
                all_items.add(value)

    if not all_items:
        return ScenarioList([])

    # Initialize TrueSkill ratings for all items
    ratings: Dict[Any, trueskill.Rating] = {
        item: trueskill.Rating() for item in all_items
    }

    # Process pairwise comparisons
    for row in rows:
        option_values = [row.get(field) for field in option_fields]
        if any(value is None for value in option_values):
            continue

        answer_value = row.get(answer_field)
        if answer_value is None:
            continue

        # Find which option was chosen as the winner
        winner_indices = [idx for idx, value in enumerate(option_values) if value == answer_value]
        if len(winner_indices) != 1:
            continue  # Skip ambiguous results

        winner_value = option_values[winner_indices[0]]

        # Update TrueSkill ratings: winner vs all other options in this comparison
        for idx, loser_value in enumerate(option_values):
            if idx != winner_indices[0]:
                # Create teams (each item is its own team)
                winner_team = [ratings[winner_value]]
                loser_team = [ratings[loser_value]]

                # Update ratings based on this match result (winner beats loser)
                new_winner_rating, new_loser_rating = trueskill.rate([winner_team, loser_team])

                # Update the stored ratings
                ratings[winner_value] = new_winner_rating[0]
                ratings[loser_value] = new_loser_rating[0]

    # Sort items by TrueSkill rating (conservative estimate: mu - 3*sigma)
    def conservative_rating(rating):
        return rating.mu - 3 * rating.sigma

    sorted_items = sorted(
        ratings.items(),
        key=lambda x: conservative_rating(x[1]),
        reverse=True
    )

    # Create output scenarios
    output_scenarios = []
    for rank, (item, rating) in enumerate(sorted_items, 1):
        scenario_data = {item_field: item}

        if include_rank:
            scenario_data[rank_field] = rank

        # Add TrueSkill-specific fields
        scenario_data[mu_field] = round(rating.mu, 3)
        scenario_data[sigma_field] = round(rating.sigma, 3)
        scenario_data[conservative_rating_field] = round(conservative_rating(rating), 3)

        output_scenarios.append(Scenario(scenario_data))

    return ScenarioList(output_scenarios)


if __name__ == "__main__":
    # Example usage with the TrueSkill library

    # Configure TrueSkill
    trueskill.setup(mu=25.0, sigma=8.333)

    # Initialize ratings for test items
    items = ["spinach", "broccoli", "salmon", "quinoa"]
    ratings = {item: trueskill.Rating() for item in items}

    print("Initial ratings:")
    for item, rating in ratings.items():
        print(f"  {item}: mu={rating.mu:.2f}, sigma={rating.sigma:.2f}, conservative={rating.mu - 3*rating.sigma:.2f}")

    # Simulate some matches where healthier foods tend to win
    matches = [
        (["spinach"], ["broccoli"]),
        (["spinach"], ["salmon"]),
        (["spinach"], ["quinoa"]),
        (["broccoli"], ["salmon"]),
        (["broccoli"], ["quinoa"]),
        (["salmon"], ["quinoa"]),
    ]

    print(f"\nSimulating {len(matches)} matches...")
    for winner_team_names, loser_team_names in matches:
        winner_team = [ratings[name] for name in winner_team_names]
        loser_team = [ratings[name] for name in loser_team_names]

        new_winner_ratings, new_loser_ratings = trueskill.rate([winner_team, loser_team])

        # Update stored ratings
        for i, name in enumerate(winner_team_names):
            ratings[name] = new_winner_ratings[0][i]
        for i, name in enumerate(loser_team_names):
            ratings[name] = new_loser_ratings[0][i]

    print("\nFinal ratings:")
    # Sort by conservative rating
    sorted_items = sorted(ratings.items(), key=lambda x: x[1].mu - 3*x[1].sigma, reverse=True)
    for rank, (item, rating) in enumerate(sorted_items, 1):
        conservative = rating.mu - 3 * rating.sigma
        print(f"  {rank}. {item}: mu={rating.mu:.2f}, sigma={rating.sigma:.2f}, conservative={conservative:.2f}")