#!/usr/bin/env python3
"""
Test alternative model names that might work with EDSL.

Since gpt-5.2-2025-12-11, o3, and claude-opus-4-5-20251101 fail with 500 errors,
let's try variations and alternatives.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from edsl import QuestionFreeText, Model
import logging

logging.basicConfig(level=logging.WARNING)  # Suppress info logs

# Alternative model names to try
ALTERNATIVES = {
    "GPT-5 variations": [
        "gpt-5.2",
        "gpt-5",
        "gpt-5.2-turbo",
        "gpt-5-turbo",
    ],
    "o3 variations": [
        "o3-mini",
        "o3-preview",
    ],
    "Claude Opus 4.5 variations": [
        "claude-opus-4.5",
        "claude-opus-4",
        "claude-opus-latest",
        "claude-4-opus-20251101",
    ],
    "Claude Sonnet 4 variations (to find working version)": [
        "claude-sonnet-4",
        "claude-sonnet-4-20241022",
        "claude-sonnet-4-20250101",
        "claude-4-sonnet-20250514",
    ],
}


def test_model(model_name: str, verbose=False) -> bool:
    """Test if a model works with EDSL."""
    try:
        question = QuestionFreeText(
            question_name="simple_test",
            question_text="What is 2 + 2?"
        )

        model = Model(model_name)
        results = question.by(model).run(
            use_api_proxy=True,
            offload_execution=False,
            progress_bar=False
        )

        response = results.select("answer.simple_test").first()

        if response is None:
            if verbose:
                print(f"  ❌ {model_name}: Returns None")
            return False
        else:
            if verbose:
                print(f"  ✅ {model_name}: WORKS! Response: {response[:50]}")
            return True

    except Exception as e:
        if verbose:
            error_msg = str(e)
            if "500" in error_msg:
                print(f"  ❌ {model_name}: 500 Server Error")
            elif "404" in error_msg:
                print(f"  ❌ {model_name}: 404 Not Found")
            elif "401" in error_msg:
                print(f"  ❌ {model_name}: 401 Unauthorized")
            else:
                print(f"  ❌ {model_name}: {error_msg[:50]}")
        return False


def main():
    """Test all alternative model names."""
    print("\n" + "="*70)
    print("TESTING ALTERNATIVE MODEL NAMES")
    print("="*70 + "\n")

    working_models = []

    for category, models in ALTERNATIVES.items():
        print(f"\n{category}:")
        print("-" * 70)

        for model_name in models:
            works = test_model(model_name, verbose=True)
            if works:
                working_models.append(model_name)

    print("\n\n" + "="*70)
    print("SUMMARY")
    print("="*70)

    if working_models:
        print(f"\n✅ Found {len(working_models)} working model(s):")
        for model in working_models:
            print(f"  - {model}")
    else:
        print("\n❌ No working alternatives found")

    print("\n" + "="*70 + "\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
