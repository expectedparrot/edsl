#!/usr/bin/env python3
"""
Comprehensive diagnostic test for Phase 3 models.

Tests each model with:
1. Simple question (no agent traits)
2. With agent traits
3. Different question types
4. Direct EDSL API test
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from edsl import QuestionFreeText, Model, Agent
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

PHASE3_MODELS = [
    "gpt-5.2-2025-12-11",
    "o3",
    "claude-opus-4-5-20251101",
    "claude-sonnet-4-20250514",
]


def test_simple_question(model_name: str):
    """Test 1: Simple question without agent traits."""
    print(f"\n{'='*70}")
    print(f"TEST 1: Simple Question (No Agent Traits)")
    print(f"Model: {model_name}")
    print(f"{'='*70}")

    try:
        question = QuestionFreeText(
            question_name="simple_test",
            question_text="What is 2 + 2? Answer with just the number."
        )

        model = Model(model_name)
        results = question.by(model).run(
            use_api_proxy=True,
            offload_execution=False,
            progress_bar=False
        )

        response = results.select("answer.simple_test").first()

        if response is None:
            print(f"❌ FAILED: Model returned None")
            return False
        else:
            print(f"✅ SUCCESS: Model returned: {response[:100]}")
            return True

    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False


def test_with_agent_traits(model_name: str):
    """Test 2: Question with agent traits."""
    print(f"\n{'='*70}")
    print(f"TEST 2: With Agent Traits")
    print(f"Model: {model_name}")
    print(f"{'='*70}")

    try:
        question = QuestionFreeText(
            question_name="agent_test",
            question_text="What is your name?"
        )

        agent = Agent(traits={"persona": "You are a helpful assistant named Bob."})
        model = Model(model_name)

        results = question.by(agent).by(model).run(
            use_api_proxy=True,
            offload_execution=False,
            progress_bar=False
        )

        response = results.select("answer.agent_test").first()

        if response is None:
            print(f"❌ FAILED: Model returned None with agent traits")
            return False
        else:
            print(f"✅ SUCCESS: Model returned: {response[:100]}")
            return True

    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False


def test_complex_prompt(model_name: str):
    """Test 3: Complex prompt similar to game."""
    print(f"\n{'='*70}")
    print(f"TEST 3: Complex Prompt (No Agent Traits)")
    print(f"Model: {model_name}")
    print(f"{'='*70}")

    try:
        question = QuestionFreeText(
            question_name="complex_test",
            question_text="""You are a judge in a deception detection game.

Three storytellers have told stories. One is lying.

Storyteller A: "I once climbed Mount Everest."
Storyteller B: "I speak 5 languages fluently."
Storyteller C: "I have never left my home country."

Based on the stories, who do you think is lying? Respond in this format:

ACCUSED: [A, B, or C]
CONFIDENCE: [0-100]
REASONING: [Your explanation]"""
        )

        model = Model(model_name)
        results = question.by(model).run(
            use_api_proxy=True,
            offload_execution=False,
            progress_bar=False
        )

        response = results.select("answer.complex_test").first()

        if response is None:
            print(f"❌ FAILED: Model returned None")
            return False
        else:
            print(f"✅ SUCCESS: Model returned: {response[:200]}")
            return True

    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False


def test_model_availability(model_name: str):
    """Test 4: Check if model is available in EDSL."""
    print(f"\n{'='*70}")
    print(f"TEST 4: Model Availability Check")
    print(f"Model: {model_name}")
    print(f"{'='*70}")

    try:
        model = Model(model_name)
        print(f"✅ Model object created successfully")
        print(f"   Model info: {model}")

        # Check if model is in available models
        from edsl import Model as ModelClass
        available = ModelClass.available()

        # Check if our model name is in the available list
        model_found = any(model_name in str(m) for m in available)

        if model_found:
            print(f"✅ Model found in available models list")
        else:
            print(f"⚠️  Model not explicitly listed in available models")
            print(f"   This doesn't necessarily mean it won't work")

        return True

    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False


def test_all_models():
    """Run all tests on all Phase 3 models."""
    print("\n" + "="*70)
    print("PHASE 3 MODEL DIAGNOSTIC TEST SUITE")
    print("="*70)
    print(f"\nTesting {len(PHASE3_MODELS)} models:")
    for i, model in enumerate(PHASE3_MODELS, 1):
        print(f"  {i}. {model}")
    print()

    results = {}

    for model_name in PHASE3_MODELS:
        print(f"\n{'#'*70}")
        print(f"# TESTING: {model_name}")
        print(f"{'#'*70}")

        results[model_name] = {
            "availability": test_model_availability(model_name),
            "simple": test_simple_question(model_name),
            "agent_traits": test_with_agent_traits(model_name),
            "complex": test_complex_prompt(model_name),
        }

    # Summary
    print(f"\n\n{'='*70}")
    print("SUMMARY")
    print(f"{'='*70}\n")

    for model_name, tests in results.items():
        print(f"\n{model_name}:")
        print(f"  Availability:  {'✅' if tests['availability'] else '❌'}")
        print(f"  Simple:        {'✅' if tests['simple'] else '❌'}")
        print(f"  Agent Traits:  {'✅' if tests['agent_traits'] else '❌'}")
        print(f"  Complex:       {'✅' if tests['complex'] else '❌'}")

        all_passed = all(tests.values())
        if all_passed:
            print(f"  STATUS: ✅ ALL TESTS PASSED - READY FOR PHASE 3")
        else:
            print(f"  STATUS: ❌ SOME TESTS FAILED - NEEDS DEBUGGING")

    # Overall status
    all_models_ready = all(all(tests.values()) for tests in results.values())

    print(f"\n{'='*70}")
    if all_models_ready:
        print("✅ ALL MODELS READY FOR PHASE 3")
    else:
        print("❌ SOME MODELS NEED FIXING BEFORE PHASE 3")
    print(f"{'='*70}\n")

    return results


if __name__ == "__main__":
    test_all_models()
