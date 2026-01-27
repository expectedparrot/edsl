#!/usr/bin/env python3
"""
Complete Phase 1 baseline experiment by running missing rounds.

Analyzes existing results and runs only the incomplete conditions.
"""

import sys
import argparse
from pathlib import Path
from collections import Counter

sys.path.insert(0, str(Path(__file__).parent))

from src.storage import ResultStore
from src.engine import GameEngine
from src.edsl_adapter import EDSLAdapter
from src.config.schema import ConditionConfig, LLMConfig, GameConfig
from src.facts.database import get_default_facts

# Phase 1 models
PHASE1_MODELS = [
    "gpt-3.5-turbo",
    "claude-3-haiku-20240307",
    "gemini-2.0-flash",
]

BASELINE_MODEL = "claude-3-5-haiku-20241022"
ROUNDS_PER_CONDITION = 30


def analyze_existing_results(results_dir: str) -> dict:
    """Analyze existing results to find missing rounds.

    Returns:
        dict mapping condition_id to (completed_count, needed_count)
    """
    store = ResultStore(results_dir)

    # Count rounds by condition
    condition_counts = Counter()
    for round_id in store.list_rounds():
        round_data = store.get_round(round_id)
        condition_id = round_data.setup.condition_id or "unknown"
        condition_counts[condition_id] += 1

    # Determine what's missing
    missing = {}
    for model in PHASE1_MODELS:
        for role in ["judge", "storyteller"]:
            condition_id = f"phase1_older_{model}_{role}"
            completed = condition_counts.get(condition_id, 0)
            needed = ROUNDS_PER_CONDITION - completed

            if needed > 0:
                missing[condition_id] = {
                    "model": model,
                    "role": role,
                    "completed": completed,
                    "needed": needed,
                }

    return missing


def create_condition(model_name: str, role: str) -> ConditionConfig:
    """Create a condition configuration."""
    if role == "judge":
        judge_model = model_name
        storyteller_model = BASELINE_MODEL
    else:
        judge_model = BASELINE_MODEL
        storyteller_model = model_name

    return ConditionConfig(
        judge_model=LLMConfig(name=judge_model, temperature=1.0),
        storyteller_model=LLMConfig(name=storyteller_model, temperature=1.0),
        game=GameConfig(
            num_storytellers=3,
            num_truth_tellers=2,
            questions_per_storyteller=1,
            story_word_min=250,
            story_word_max=500,
            answer_word_min=25,
            answer_word_max=150,
            game_type="standard",
        ),
        storyteller_strategy="baseline",
        judge_question_style="curious",
        fact_category=None,  # Random selection from all facts
    )


def run_missing_rounds(
    missing_conditions: dict,
    results_dir: str = "results/phase1_older"
):
    """Run the missing rounds to complete Phase 1."""

    # Initialize infrastructure
    fact_db = get_default_facts()
    default_game_config = GameConfig()
    adapter = EDSLAdapter(LLMConfig(name=BASELINE_MODEL, temperature=1.0))
    engine = GameEngine(default_game_config, adapter, fact_db)
    store = ResultStore(results_dir)

    total_needed = sum(cond["needed"] for cond in missing_conditions.values())
    total_completed = 0

    print(f"Phase 1 Completion - Running {total_needed} missing rounds")
    print("=" * 70)
    print()

    for condition_id, info in missing_conditions.items():
        model = info["model"]
        role = info["role"]
        needed = info["needed"]

        print(f"Condition: {model} as {role}")
        print(f"  Need: {needed} rounds")

        condition = create_condition(model, role)
        condition_correct = 0

        for round_num in range(needed):
            try:
                # Run the round
                round_result = engine.run_round(condition)

                # Set condition_id for tracking
                round_result.setup.condition_id = condition_id

                # Save result
                store.save_round(round_result)

                total_completed += 1
                if round_result.outcome.detection_correct:
                    condition_correct += 1

                # Log progress every 5 rounds
                if (round_num + 1) % 5 == 0:
                    acc = condition_correct / (round_num + 1)
                    print(f"    Round {round_num + 1}/{needed} (accuracy: {acc:.1%})")

            except Exception as e:
                print(f"    Round {round_num + 1} failed: {e}")
                continue

        # Summary for this condition
        condition_accuracy = condition_correct / needed if needed > 0 else 0.0
        print(f"  Completed: {needed}/{needed} rounds")
        print(f"  Accuracy: {condition_accuracy:.1%}")
        print()

    print("=" * 70)
    print(f"✅ Phase 1 Completion: {total_completed} rounds added")
    print(f"   Total Phase 1 rounds now: {104 + total_completed}/180")
    print("=" * 70)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Complete Phase 1 baseline experiment")
    parser.add_argument("--yes", "-y", action="store_true", help="Skip confirmation prompt")
    args = parser.parse_args()

    results_dir = "results/phase1_older"

    print("Analyzing existing Phase 1 results...")
    print()

    missing = analyze_existing_results(results_dir)

    if not missing:
        print("✅ Phase 1 already complete! No missing rounds.")
        return 0

    print("Missing Conditions:")
    print("-" * 70)
    total_missing = 0
    for condition_id, info in missing.items():
        print(f"  {info['model']:<40} {info['role']:<12} "
              f"{info['completed']}/30 complete, need {info['needed']}")
        total_missing += info["needed"]
    print()
    print(f"Total missing: {total_missing} rounds")
    print()

    # Confirm before running (unless --yes flag is provided)
    if not args.yes:
        response = input("Run missing rounds? (y/n): ")
        if response.lower() != 'y':
            print("Cancelled.")
            return 1

    # Run completion
    run_missing_rounds(missing, results_dir)

    return 0


if __name__ == "__main__":
    sys.exit(main())
