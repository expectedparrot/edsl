#!/usr/bin/env python3
"""
Complete remaining llama-3.3-70b-versatile rounds.

Currently: 9/60 rounds (9 judge, 0 storyteller)
Need: 51 more rounds (21 judge + 30 storyteller)
"""

import sys
from pathlib import Path
from collections import Counter

sys.path.insert(0, str(Path(__file__).parent))

from src.storage import ResultStore
from src.engine import GameEngine
from src.edsl_adapter import EDSLAdapter
from src.config.schema import ConditionConfig, LLMConfig, GameConfig
from src.facts.database import get_default_facts

MODEL = "llama-3.3-70b-versatile"
BASELINE_MODEL = "claude-3-5-haiku-20241022"
ROUNDS_PER_CONDITION = 30


def create_condition(role: str) -> ConditionConfig:
    """Create a condition configuration."""
    if role == "judge":
        judge_model = MODEL
        storyteller_model = BASELINE_MODEL
    else:
        judge_model = BASELINE_MODEL
        storyteller_model = MODEL

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


def analyze_existing():
    """Check what's already done."""
    store = ResultStore("results/phase2_small")

    condition_counts = Counter()
    for round_id in store.list_rounds():
        round_data = store.get_round(round_id)
        condition_id = round_data.setup.condition_id or "unknown"
        if MODEL in condition_id:
            condition_counts[condition_id] += 1

    judge_done = condition_counts.get(f"phase2_small_{MODEL}_judge", 0)
    storyteller_done = condition_counts.get(f"phase2_small_{MODEL}_storyteller", 0)

    return judge_done, storyteller_done


def main():
    """Complete llama rounds."""
    results_dir = "results/phase2_small"

    judge_done, storyteller_done = analyze_existing()
    judge_needed = ROUNDS_PER_CONDITION - judge_done
    storyteller_needed = ROUNDS_PER_CONDITION - storyteller_done

    print(f"\n{'='*70}")
    print(f"COMPLETING LLAMA-3.3-70B-VERSATILE ROUNDS")
    print(f"{'='*70}\n")
    print(f"Current status:")
    print(f"  Judge: {judge_done}/30 complete, need {judge_needed}")
    print(f"  Storyteller: {storyteller_done}/30 complete, need {storyteller_needed}")
    print(f"\nTotal needed: {judge_needed + storyteller_needed} rounds")
    print()

    if judge_needed == 0 and storyteller_needed == 0:
        print("✅ All llama rounds already complete!")
        return 0

    # Initialize infrastructure
    fact_db = get_default_facts()
    adapter = EDSLAdapter(LLMConfig(name=BASELINE_MODEL, temperature=1.0))
    engine = GameEngine(GameConfig(), adapter, fact_db)
    store = ResultStore(results_dir)

    total_completed = 0

    # Complete judge rounds
    if judge_needed > 0:
        print(f"{'='*70}")
        print(f"Completing JUDGE rounds ({judge_needed} needed)")
        print(f"{'='*70}\n")

        condition = create_condition("judge")
        condition_id = f"phase2_small_{MODEL}_judge"
        correct = 0

        for i in range(judge_needed):
            try:
                result = engine.run_round(condition)
                result.setup.condition_id = condition_id
                store.save_round(result)

                total_completed += 1
                if result.outcome.detection_correct:
                    correct += 1

                if (i + 1) % 5 == 0:
                    acc = correct / (i + 1)
                    print(f"  Round {judge_done + i + 1}/30 (accuracy: {acc:.1%})")

            except Exception as e:
                print(f"  ❌ Round {judge_done + i + 1} failed: {e}")

        print(f"\n  ✅ Judge rounds complete: {judge_done + judge_needed}/30")
        print()

    # Complete storyteller rounds
    if storyteller_needed > 0:
        print(f"{'='*70}")
        print(f"Completing STORYTELLER rounds ({storyteller_needed} needed)")
        print(f"{'='*70}\n")

        condition = create_condition("storyteller")
        condition_id = f"phase2_small_{MODEL}_storyteller"

        for i in range(storyteller_needed):
            try:
                result = engine.run_round(condition)
                result.setup.condition_id = condition_id
                store.save_round(result)

                total_completed += 1

                if (i + 1) % 5 == 0:
                    print(f"  Round {storyteller_done + i + 1}/30")

            except Exception as e:
                print(f"  ❌ Round {storyteller_done + i + 1} failed: {e}")

        print(f"\n  ✅ Storyteller rounds complete: {storyteller_done + storyteller_needed}/30")
        print()

    print(f"{'='*70}")
    print(f"✅ LLAMA COMPLETION DONE")
    print(f"{'='*70}")
    print(f"Rounds added: {total_completed}")
    print(f"Total Phase 2: {249 + total_completed} rounds")
    print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
