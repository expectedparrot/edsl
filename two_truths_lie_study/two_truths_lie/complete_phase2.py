#!/usr/bin/env python3
"""
Complete Phase 2 by replacing Gemini with open models.

Adds 2 open models to Phase 2:
- deepseek-chat (30 judge + 30 storyteller = 60 rounds)
- llama-3.3-70b-versatile (30 judge + 30 storyteller = 60 rounds)

This brings Phase 2 from 180 to 300 total rounds (5 models × 60 rounds).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.config.schema import ConditionConfig, LLMConfig, GameConfig
from src.engine import GameEngine
from src.storage import ResultStore
from src.facts.database import get_default_facts
from src.edsl_adapter import EDSLAdapter

# Open models to add
ADDITIONAL_MODELS = [
    "deepseek-chat",
    "llama-3.3-70b-versatile",
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


def main():
    """Run additional models to complete Phase 2."""
    results_dir = "results/phase2_small"

    # Initialize infrastructure
    fact_db = get_default_facts()
    default_game_config = GameConfig()
    adapter = EDSLAdapter(LLMConfig(name=BASELINE_MODEL, temperature=1.0))
    engine = GameEngine(default_game_config, adapter, fact_db)
    store = ResultStore(results_dir)

    total_rounds = len(ADDITIONAL_MODELS) * 2 * ROUNDS_PER_CONDITION  # 2 models × 2 roles × 30 rounds
    completed_rounds = 0

    print(f"\n{'='*70}")
    print(f"PHASE 2 COMPLETION: OPEN MODELS")
    print(f"{'='*70}\n")
    print(f"Adding models: {', '.join(ADDITIONAL_MODELS)}")
    print(f"Rounds to add: {total_rounds}")
    print(f"Current Phase 2 total: 180 rounds")
    print(f"New Phase 2 total: {180 + total_rounds} rounds")
    print(f"Results directory: {results_dir}")
    print()

    # Run each model in both roles
    for model_name in ADDITIONAL_MODELS:
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
    print(f"✅ PHASE 2 COMPLETION DONE")
    print(f"{'='*70}")
    print(f"Rounds added: {completed_rounds}/{total_rounds}")
    print(f"New Phase 2 total: {180 + completed_rounds} rounds")
    print(f"Results saved to: {results_dir}")
    print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
