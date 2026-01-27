#!/usr/bin/env python3
"""
Find the best working flagship models available in EDSL.

Tests top-tier models from each provider to find Phase 3 alternatives.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from edsl import QuestionFreeText, Model
import logging

logging.basicConfig(level=logging.WARNING)

# Flagship and high-tier models to test
FLAGSHIP_CANDIDATES = {
    "OpenAI Flagship Models": [
        "chatgpt-4o-latest",
        "gpt-4o",
        "gpt-4-turbo",
        "gpt-4",
        "o1-preview",
        "o1-mini",
    ],
    "Claude Flagship Models": [
        "claude-3-opus-20240229",  # Claude 3 Opus (most capable Claude 3)
        "claude-3-7-sonnet-20250219",  # Claude 3.7 Sonnet (Phase 2)
        "claude-sonnet-4-20250514",  # Claude Sonnet 4 (confirmed working)
    ],
    "Gemini Models": [
        "gemini-2.5-pro",
        "gemini-2.0-pro",
        "gemini-2.5-flash",
    ],
}


def test_model_thoroughly(model_name: str) -> dict:
    """Test a model with simple and complex prompts."""
    results = {"available": False, "simple": False, "complex": False}

    try:
        # Test 1: Simple question
        question = QuestionFreeText(
            question_name="simple",
            question_text="What is 2 + 2?"
        )

        model = Model(model_name)
        test_results = question.by(model).run(
            use_api_proxy=True,
            offload_execution=False,
            progress_bar=False
        )

        response = test_results.select("answer.simple").first()
        if response and response.strip():
            results["available"] = True
            results["simple"] = True

            # Test 2: Complex deception detection prompt
            complex_q = QuestionFreeText(
                question_name="complex",
                question_text="""You are a judge in a game. Three storytellers told stories. One is lying.

Storyteller A: "I climbed Mount Everest."
Storyteller B: "I speak 5 languages."
Storyteller C: "I've never left my country."

Who is lying? Format: ACCUSED: [A/B/C], CONFIDENCE: [0-100], REASONING: [explain]"""
            )

            complex_results = complex_q.by(model).run(
                use_api_proxy=True,
                offload_execution=False,
                progress_bar=False
            )

            complex_response = complex_results.select("answer.complex").first()
            if complex_response and "ACCUSED:" in complex_response:
                results["complex"] = True

    except Exception as e:
        error_msg = str(e)
        if "not found" not in error_msg.lower():
            results["available"] = True  # Model exists but might have other issues

    return results


def main():
    """Find working flagship models."""
    print("\n" + "="*70)
    print("FINDING WORKING FLAGSHIP MODELS FOR PHASE 3")
    print("="*70)

    all_working = []

    for category, models in FLAGSHIP_CANDIDATES.items():
        print(f"\n{category}:")
        print("-" * 70)

        for model_name in models:
            print(f"Testing {model_name}...", end=" ", flush=True)
            results = test_model_thoroughly(model_name)

            if results["simple"] and results["complex"]:
                print(f"✅ FULLY WORKING")
                all_working.append({
                    "name": model_name,
                    "category": category,
                    "status": "fully_working"
                })
            elif results["simple"]:
                print(f"⚠️  Works but complex prompts have issues")
                all_working.append({
                    "name": model_name,
                    "category": category,
                    "status": "partial"
                })
            elif results["available"]:
                print(f"❌ Available but returns None")
            else:
                print(f"❌ Not available")

    print("\n\n" + "="*70)
    print("RECOMMENDED MODELS FOR PHASE 3")
    print("="*70)

    fully_working = [m for m in all_working if m["status"] == "fully_working"]

    if fully_working:
        print(f"\n✅ {len(fully_working)} fully working flagship models found:\n")
        for model in fully_working:
            print(f"  - {model['name']}")

        print("\n" + "-"*70)
        print("SUGGESTED PHASE 3 MODEL LIST:")
        print("-"*70)

        # Pick best 4 for Phase 3
        if len(fully_working) >= 4:
            print("\nTop 4 flagships for Phase 3:")
            for i, model in enumerate(fully_working[:4], 1):
                print(f"  {i}. {model['name']}")
        else:
            print(f"\nAll {len(fully_working)} working models:")
            for i, model in enumerate(fully_working, 1):
                print(f"  {i}. {model['name']}")

    else:
        print("\n❌ No fully working flagship models found")

    print("\n" + "="*70 + "\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
