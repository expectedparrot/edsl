#!/usr/bin/env python3
"""
Run Phase 2: Small/Fast Models

Tests 4 small, fast models:
- claude-3-7-sonnet-20250219
- gemini-2.5-flash
- gpt-4o-mini
- claude-3-5-haiku-20241022

Each model tested in both judge and storyteller roles (30 rounds each = 60 rounds per model).
Total: 4 models × 60 rounds = 240 rounds
"""

import sys
from pathlib import Path
from typing import List
import argparse

sys.path.insert(0, str(Path(__file__).parent))

from src.config.schema import ConditionConfig, LLMConfig, GameConfig
from src.engine import GameEngine
from src.storage import ResultStore
from src.facts.database import get_default_facts
from src.edsl_adapter import EDSLAdapter

# Phase 2: Small/Fast Models
PHASE2_MODELS = [
    "claude-3-7-sonnet-20250219",
    "gemini-2.5-flash",
    "gpt-4o-mini",
    "claude-3-5-haiku-20241022",
]

BASELINE_MODEL = "claude-3-5-haiku-20241022"
ROUNDS_PER_CONDITION = 30


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
        fact_category=None,
    )


def run_phase2(results_dir: str = "results/phase2_small"):
    """Run Phase 2 experiment."""

    # Initialize infrastructure
    fact_db = get_default_facts()
    default_game_config = GameConfig()
    adapter = EDSLAdapter(LLMConfig(name=BASELINE_MODEL, temperature=1.0))
    engine = GameEngine(default_game_config, adapter, fact_db)
    store = ResultStore(results_dir)

    total_rounds = len(PHASE2_MODELS) * 2 * ROUNDS_PER_CONDITION  # 4 models × 2 roles × 30 rounds
    completed_rounds = 0

    print(f"\n{'='*70}")
    print(f"PHASE 2: SMALL/FAST MODELS EXPERIMENT")
    print(f"{'='*70}\n")
    print(f"Models to test: {', '.join(PHASE2_MODELS)}")
    print(f"Rounds per condition: {ROUNDS_PER_CONDITION}")
    print(f"Total rounds: {total_rounds}")
    print(f"Results directory: {results_dir}")
    print()

    # Run each model in both roles
    for model_name in PHASE2_MODELS:
        for role in ["judge", "storyteller"]:
            condition_id = f"phase2_small_{model_name}_{role}"

            print(f"{'='*70}")
            print(f"Condition: {model_name} as {role.upper()}")
            print(f"{'='*70}\n")

            condition = create_condition(model_name, role)
            condition_correct = 0
            condition_failed = 0

            for round_num in range(ROUNDS_PER_CONDITION):
                try:
                    # Run the round
                    round_result = engine.run_round(condition)

                    # Set condition_id for tracking
                    round_result.setup.condition_id = condition_id

                    # Save result
                    store.save_round(round_result)

                    completed_rounds += 1
                    if round_result.outcome.detection_correct:
                        condition_correct += 1

                    # Log progress every 5 rounds
                    if (round_num + 1) % 5 == 0:
                        acc = condition_correct / (round_num + 1 - condition_failed)
                        progress = (completed_rounds / total_rounds) * 100
                        print(f"  Round {round_num + 1}/{ROUNDS_PER_CONDITION} "
                              f"(accuracy: {acc:.1%}, overall progress: {progress:.1f}%)")

                except Exception as e:
                    condition_failed += 1
                    print(f"  ❌ Round {round_num + 1} failed: {e}")
                    continue

            # Summary for this condition
            successful_rounds = ROUNDS_PER_CONDITION - condition_failed
            condition_accuracy = condition_correct / successful_rounds if successful_rounds > 0 else 0.0

            print(f"\n  ✅ Condition complete:")
            print(f"     Successful: {successful_rounds}/{ROUNDS_PER_CONDITION} rounds")
            print(f"     Failed: {condition_failed}")
            print(f"     Accuracy: {condition_accuracy:.1%}")
            print()

    print(f"{'='*70}")
    print(f"✅ PHASE 2 COMPLETE")
    print(f"{'='*70}")
    print(f"Total rounds completed: {completed_rounds}/{total_rounds}")
    print(f"Results saved to: {results_dir}")
    print()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Run Phase 2: Small/Fast Models Experiment")
    parser.add_argument(
        "--results-dir",
        default="results/phase2_small",
        help="Directory to save results (default: results/phase2_small)"
    )
    args = parser.parse_args()

    run_phase2(results_dir=args.results_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
