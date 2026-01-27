#!/usr/bin/env python3
"""
Test all GPT-5, o3, and Opus 4 variants to find which work.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from edsl import QuestionFreeText, Model
import logging

logging.basicConfig(level=logging.WARNING)

GPT5_VARIANTS = [
    "gpt-5",
    "gpt-5-2025-08-07",
    "gpt-5-chat-latest",
    "gpt-5-pro",
    "gpt-5.1",
    "gpt-5.1-2025-11-13",
    "gpt-5.2",
    "gpt-5.2-2025-12-11",  # Our target
]

O3_VARIANTS = [
    "o3",  # Our target
    "o3-2025-04-16",
    "o3-mini",
    "o3-mini-2025-01-31",
    "o3-pro",
    "o3-pro-2025-06-10",
    "azure:o3-mini",
]

OPUS4_VARIANTS = [
    "claude-opus-4-20250514",
    "claude-opus-4-1-20250805",
    "claude-opus-4-5-20251101",  # Our target
]

SONNET4_VARIANTS = [
    "claude-sonnet-4-20250514",  # Known working
    "claude-sonnet-4-5-20250929",
]


def test_model_quick(model_name: str) -> tuple:
    """Quick test - just check if it returns non-None."""
    try:
        question = QuestionFreeText(
            question_name="test",
            question_text="What is 2 + 2?"
        )

        model = Model(model_name)
        results = question.by(model).run(
            use_api_proxy=True,
            offload_execution=False,
            progress_bar=False
        )

        response = results.select("answer.test").first()

        if response and response.strip():
            return (True, response[:30])
        else:
            return (False, "None")

    except Exception as e:
        error_msg = str(e)
        if "500" in error_msg:
            return (False, "500 error")
        elif "not found" in error_msg.lower():
            return (False, "not found")
        else:
            return (False, error_msg[:30])


def test_category(category_name: str, models: list):
    """Test all models in a category."""
    print(f"\n{'='*70}")
    print(f"{category_name}")
    print(f"{'='*70}\n")

    working = []

    for model_name in models:
        print(f"Testing {model_name:45} ... ", end="", flush=True)
        works, msg = test_model_quick(model_name)

        if works:
            print(f"✅ WORKS! ({msg})")
            working.append(model_name)
        else:
            print(f"❌ {msg}")

    return working


def main():
    """Test all variants."""
    print("\n" + "="*70)
    print("TESTING GPT-5, O3, AND OPUS 4 VARIANTS")
    print("="*70)

    all_working = {}

    all_working["gpt-5"] = test_category("GPT-5 VARIANTS", GPT5_VARIANTS)
    all_working["o3"] = test_category("O3 VARIANTS", O3_VARIANTS)
    all_working["opus-4"] = test_category("OPUS 4 VARIANTS", OPUS4_VARIANTS)
    all_working["sonnet-4"] = test_category("SONNET 4 VARIANTS (REFERENCE)", SONNET4_VARIANTS)

    print("\n\n" + "="*70)
    print("SUMMARY - WORKING MODELS FOR PHASE 3")
    print("="*70 + "\n")

    total_working = sum(len(models) for models in all_working.values())

    if total_working > 0:
        for category, models in all_working.items():
            if models:
                print(f"\n{category.upper()}:")
                for model in models:
                    print(f"  ✅ {model}")

        print("\n" + "-"*70)
        print("RECOMMENDED PHASE 3 MODEL LIST:")
        print("-"*70)

        # Try to pick 1 from each category
        phase3 = []
        for category, models in all_working.items():
            if models:
                # Prefer the exact model we want, otherwise pick the first working one
                if category == "gpt-5" and "gpt-5.2-2025-12-11" in models:
                    phase3.append("gpt-5.2-2025-12-11")
                elif category == "o3" and "o3" in models:
                    phase3.append("o3")
                elif category == "opus-4" and "claude-opus-4-5-20251101" in models:
                    phase3.append("claude-opus-4-5-20251101")
                elif category == "sonnet-4" and "claude-sonnet-4-20250514" in models:
                    phase3.append("claude-sonnet-4-20250514")
                else:
                    phase3.append(models[0])

        if phase3:
            print("\nTop 4 for Phase 3:")
            for i, model in enumerate(phase3, 1):
                print(f"  {i}. {model}")

    else:
        print("\n❌ No working models found in any category")

    print("\n" + "="*70 + "\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
