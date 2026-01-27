#!/usr/bin/env python3
"""
List all available models in EDSL and find GPT-5, o3, Opus 4.5 variants.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from edsl import Model


def main():
    """List all available EDSL models."""
    print("\n" + "="*70)
    print("ALL AVAILABLE MODELS IN EDSL")
    print("="*70 + "\n")

    try:
        available_models = Model.available()

        # Organize by provider
        openai_models = []
        anthropic_models = []
        google_models = []
        other_models = []

        for model in available_models:
            model_name = str(model)

            if "gpt" in model_name.lower() or "o1" in model_name.lower() or "o3" in model_name.lower():
                openai_models.append(model_name)
            elif "claude" in model_name.lower():
                anthropic_models.append(model_name)
            elif "gemini" in model_name.lower():
                google_models.append(model_name)
            else:
                other_models.append(model_name)

        # Print organized lists
        print("OpenAI Models:")
        print("-" * 70)
        for model in sorted(openai_models):
            if "gpt-5" in model.lower() or "o3" in model.lower():
                print(f"  🔥 {model}")  # Highlight GPT-5 and o3
            else:
                print(f"  - {model}")

        print("\n\nClaude/Anthropic Models:")
        print("-" * 70)
        for model in sorted(anthropic_models):
            if "opus-4" in model.lower() or "sonnet-4" in model.lower():
                print(f"  🔥 {model}")  # Highlight Claude 4
            else:
                print(f"  - {model}")

        print("\n\nGoogle/Gemini Models:")
        print("-" * 70)
        for model in sorted(google_models):
            print(f"  - {model}")

        if other_models:
            print("\n\nOther Models:")
            print("-" * 70)
            for model in sorted(other_models):
                print(f"  - {model}")

        # Search for specific models
        print("\n\n" + "="*70)
        print("SEARCHING FOR PHASE 3 REQUESTED MODELS")
        print("="*70 + "\n")

        searches = [
            ("gpt-5", "GPT-5 models"),
            ("o3", "o3 models"),
            ("opus-4", "Claude Opus 4 models"),
            ("sonnet-4", "Claude Sonnet 4 models"),
        ]

        for search_term, description in searches:
            matches = [str(m) for m in available_models if search_term in str(m).lower()]
            if matches:
                print(f"{description} ({len(matches)} found):")
                for match in matches:
                    print(f"  - {match}")
            else:
                print(f"{description}: None found")
            print()

        print("="*70 + "\n")

    except Exception as e:
        print(f"Error listing models: {e}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
