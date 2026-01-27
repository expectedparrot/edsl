#!/usr/bin/env python3
"""
Test Gemini models to ensure they work before running Phase 2.

Tests both gemini-2.5-flash (Phase 2) and gemini-2.0-flash (failed in Phase 1).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.config.schema import ConditionConfig, LLMConfig, GameConfig
from src.engine import GameEngine
from src.storage import ResultStore
from src.facts.database import get_default_facts
from src.edsl_adapter import EDSLAdapter

BASELINE_MODEL = "claude-3-5-haiku-20241022"
GEMINI_MODELS = [
    "gemini-2.5-flash",  # Phase 2 model
    "gemini-2.0-flash",  # Phase 1 model (failed)
]


def test_gemini_model(model_name: str) -> bool:
    """Test a single gemini model by running one complete round.

    Returns:
        True if the model works, False otherwise
    """
    print(f"\n{'='*70}")
    print(f"Testing: {model_name}")
    print(f"{'='*70}\n")

    try:
        # Initialize infrastructure
        fact_db = get_default_facts()
        default_game_config = GameConfig()
        adapter = EDSLAdapter(LLMConfig(name=BASELINE_MODEL, temperature=1.0))
        engine = GameEngine(default_game_config, adapter, fact_db)

        # Test as judge
        print(f"Test 1: {model_name} as JUDGE")
        judge_condition = ConditionConfig(
            judge_model=LLMConfig(name=model_name, temperature=1.0),
            storyteller_model=LLMConfig(name=BASELINE_MODEL, temperature=1.0),
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

        round_result = engine.run_round(judge_condition)

        print(f"  ✅ Judge test passed")
        print(f"     - Accused: {round_result.outcome.accused_id}")
        print(f"     - Correct: {round_result.outcome.detection_correct}")
        print(f"     - Confidence: {round_result.outcome.confidence}")
        print()

        # Test as storyteller
        print(f"Test 2: {model_name} as STORYTELLER")
        storyteller_condition = ConditionConfig(
            judge_model=LLMConfig(name=BASELINE_MODEL, temperature=1.0),
            storyteller_model=LLMConfig(name=model_name, temperature=1.0),
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

        round_result = engine.run_round(storyteller_condition)

        print(f"  ✅ Storyteller test passed")
        print(f"     - Liar evaded: {round_result.outcome.liar_evaded}")
        print(f"     - Judge confidence: {round_result.outcome.confidence}")
        print()

        print(f"{'='*70}")
        print(f"✅ {model_name} PASSED all tests")
        print(f"{'='*70}\n")
        return True

    except Exception as e:
        print(f"\n{'='*70}")
        print(f"❌ {model_name} FAILED")
        print(f"{'='*70}")
        print(f"Error: {e}")
        print()
        import traceback
        traceback.print_exc()
        print()
        return False


def main():
    """Test all Gemini models."""
    print("\n" + "="*70)
    print("GEMINI MODEL COMPATIBILITY TEST")
    print("="*70)
    print("\nTesting Gemini models before Phase 2 experiment...")
    print()

    results = {}
    for model_name in GEMINI_MODELS:
        results[model_name] = test_gemini_model(model_name)

    # Summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    for model_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {model_name:<40} {status}")

    # Recommendation for Phase 2
    print("\n" + "="*70)
    print("PHASE 2 RECOMMENDATION")
    print("="*70)

    phase2_model = "gemini-2.5-flash"
    if results.get(phase2_model, False):
        print(f"✅ Proceed with Phase 2 using {phase2_model}")
        print("   The model works correctly and can be included in the experiment.")
    else:
        print(f"❌ DO NOT use {phase2_model} in Phase 2")
        print("   The model failed testing and should be excluded or replaced.")

        # Check if the old model works as alternative
        alt_model = "gemini-2.0-flash"
        if results.get(alt_model, False):
            print(f"   Alternative: Use {alt_model} instead (passed testing)")
        else:
            print(f"   Alternative: Skip all Gemini models in Phase 2")

    print()

    return 0 if all(results.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
