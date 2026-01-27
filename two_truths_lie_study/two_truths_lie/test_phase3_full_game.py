#!/usr/bin/env python3
"""
Full end-to-end test of Phase 3 models through the game engine.

Tests each model in both judge and storyteller roles.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.config.schema import ConditionConfig, LLMConfig, GameConfig
from src.engine import GameEngine
from src.facts.database import get_default_facts
from src.edsl_adapter import EDSLAdapter

PHASE3_MODELS = [
    "claude-opus-4-5-20251101",
    "claude-sonnet-4-20250514",
    "gpt-5-2025-08-07",
    "o3-2025-04-16",
]

BASELINE_MODEL = "claude-3-5-haiku-20241022"


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


def test_model_role(engine: GameEngine, model_name: str, role: str):
    """Test a model in a specific role."""
    print(f"\n{model_name} as {role.upper()}")
    print("-" * 70)

    try:
        condition = create_condition(model_name, role)
        result = engine.run_round(condition)

        # Check result structure
        assert result.setup is not None
        assert result.stories is not None
        assert len(result.stories) == 3
        assert result.questions is not None
        assert result.answers is not None
        assert result.verdict is not None
        assert result.outcome is not None

        # Log key details
        print(f"✅ Round completed successfully")
        print(f"   Liar: Storyteller {result.setup.liar_id}")
        print(f"   Accused: {result.verdict.accused_id}")
        print(f"   Correct: {result.outcome.detection_correct}")
        print(f"   Confidence: {result.verdict.confidence}")

        return True

    except Exception as e:
        print(f"❌ FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Test all Phase 3 models."""
    print("\n" + "="*70)
    print("PHASE 3 FULL GAME ENGINE TEST")
    print("="*70)
    print("\nTesting each model in both judge and storyteller roles")
    print("This verifies the complete pipeline works for all models\n")

    # Initialize game engine
    fact_db = get_default_facts()
    adapter = EDSLAdapter(LLMConfig(name=BASELINE_MODEL, temperature=1.0))
    engine = GameEngine(GameConfig(), adapter, fact_db)

    results = {}

    for model_name in PHASE3_MODELS:
        print(f"\n{'='*70}")
        print(f"TESTING: {model_name}")
        print(f"{'='*70}")

        judge_success = test_model_role(engine, model_name, "judge")
        storyteller_success = test_model_role(engine, model_name, "storyteller")

        results[model_name] = {
            "judge": judge_success,
            "storyteller": storyteller_success,
            "both": judge_success and storyteller_success
        }

    # Summary
    print("\n\n" + "="*70)
    print("SUMMARY")
    print("="*70 + "\n")

    all_working = True
    for model_name, model_results in results.items():
        judge_status = "✅" if model_results["judge"] else "❌"
        storyteller_status = "✅" if model_results["storyteller"] else "❌"

        print(f"{model_name}:")
        print(f"  Judge: {judge_status}")
        print(f"  Storyteller: {storyteller_status}")

        if not model_results["both"]:
            all_working = False

    print("\n" + "="*70)
    if all_working:
        print("🎉 ALL MODELS READY FOR PHASE 3!")
        print("="*70)
        print("\nAll 4 flagship models work in both roles.")
        print("Ready to run full Phase 3 experiment (240 rounds).")
    else:
        print("❌ SOME MODELS HAVE ISSUES")
        print("="*70)
        print("\nFix the issues above before running Phase 3.")

    print("\n" + "="*70 + "\n")

    return 0 if all_working else 1


if __name__ == "__main__":
    sys.exit(main())
