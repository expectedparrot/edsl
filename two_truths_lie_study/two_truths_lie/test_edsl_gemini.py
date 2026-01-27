#!/usr/bin/env python3
"""
Direct EDSL + Gemini compatibility test.

Tests if Gemini works at all with EDSL, independent of our game logic.
"""

from edsl import QuestionFreeText, Model

GEMINI_MODELS = [
    "gemini-2.5-flash",
    "gemini-2.0-flash",
    "gemini-1.5-pro",
    "gemini-1.5-flash",
]


def test_simple_question(model_name: str) -> bool:
    """Test if a model can answer a simple question."""
    print(f"\nTesting {model_name}...")
    print("-" * 70)

    try:
        # Create a very simple question
        question = QuestionFreeText(
            question_text="What is 2 + 2?",
            question_name="simple_math"
        )

        # Create model
        model = Model(model_name)

        # Run the question
        print(f"  Running simple question: 'What is 2 + 2?'")
        results = question.by(model).run(
            use_api_proxy=True,
            offload_execution=False,
            progress_bar=False
        )

        # Extract answer
        answer = results.select("answer.simple_math").first()

        if answer is None:
            print(f"  ❌ FAILED: Model returned None")
            print(f"     Available keys: {list(results.to_dict().keys())}")
            return False
        else:
            print(f"  ✅ SUCCESS: Model responded")
            print(f"     Answer: {answer}")
            return True

    except Exception as e:
        print(f"  ❌ FAILED: Exception occurred")
        print(f"     Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Test all available Gemini models."""
    print("\n" + "="*70)
    print("EDSL + GEMINI DIRECT COMPATIBILITY TEST")
    print("="*70)
    print("\nTesting if Gemini models work with EDSL at all...")

    results = {}
    for model_name in GEMINI_MODELS:
        try:
            results[model_name] = test_simple_question(model_name)
        except Exception as e:
            print(f"\n  ❌ {model_name} crashed: {e}")
            results[model_name] = False

    # Summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)

    working_models = []
    for model_name, passed in results.items():
        status = "✅ WORKS" if passed else "❌ FAILS"
        print(f"  {model_name:<40} {status}")
        if passed:
            working_models.append(model_name)

    print("\n" + "="*70)
    print("RECOMMENDATION FOR PHASE 2")
    print("="*70)

    if working_models:
        print(f"✅ Use one of these working Gemini models:")
        for model in working_models:
            print(f"   - {model}")
    else:
        print("❌ NO GEMINI MODELS WORK WITH EDSL")
        print("   Recommendation: Skip all Gemini models in Phase 2")
        print("   Run Phase 2 with: claude-3-7-sonnet, gpt-4o-mini, claude-3-5-haiku only")

    print()
    return 0 if working_models else 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
