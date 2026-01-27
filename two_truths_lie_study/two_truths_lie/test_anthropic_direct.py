#!/usr/bin/env python3
"""
Test Claude Opus 4.5 and Sonnet 4.5 via direct Anthropic API.
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load .env file
env_path = Path(__file__).parent / '.env'
load_dotenv(env_path)

# Test models
MODELS_TO_TEST = [
    "claude-opus-4-5-20251101",
    "claude-sonnet-4-5-20250929",
    "claude-sonnet-4-20250514",  # Known working in EDSL
]


def test_anthropic_model(model_name: str):
    """Test a Claude model via direct Anthropic API."""
    print(f"\nTesting {model_name}:")
    print("-" * 70)

    try:
        import anthropic

        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            print("❌ ANTHROPIC_API_KEY not found in environment")
            return False

        client = anthropic.Anthropic(api_key=api_key)

        print("Making API call...", end=" ", flush=True)
        message = client.messages.create(
            model=model_name,
            max_tokens=100,
            messages=[
                {"role": "user", "content": "What is 2 + 2? Answer with just the number."}
            ]
        )

        response = message.content[0].text
        print(f"✅ SUCCESS!")
        print(f"Response: {response}")
        print(f"Model: {message.model}")
        print(f"Tokens: input={message.usage.input_tokens}, output={message.usage.output_tokens}")
        return True

    except anthropic.NotFoundError as e:
        print(f"❌ Model not found in Anthropic API")
        print(f"Error: {e}")
        return False
    except anthropic.AuthenticationError:
        print(f"❌ Authentication error - check ANTHROPIC_API_KEY")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def main():
    """Test all Claude models."""
    print("\n" + "="*70)
    print("TESTING CLAUDE MODELS VIA DIRECT ANTHROPIC API")
    print("="*70)

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if api_key:
        print(f"\n✅ API Key found: {api_key[:20]}...")
    else:
        print(f"\n❌ API Key NOT found - check .env file")
        return 1

    results = {}
    for model in MODELS_TO_TEST:
        results[model] = test_anthropic_model(model)

    print("\n\n" + "="*70)
    print("SUMMARY")
    print("="*70)

    working = [m for m, works in results.items() if works]
    failed = [m for m, works in results.items() if not works]

    if working:
        print(f"\n✅ {len(working)} model(s) working via direct API:")
        for model in working:
            print(f"  - {model}")

    if failed:
        print(f"\n❌ {len(failed)} model(s) not working:")
        for model in failed:
            print(f"  - {model}")

    if "claude-opus-4-5-20251101" in working and "claude-sonnet-4-5-20250929" in working:
        print("\n" + "="*70)
        print("🎉 EXCELLENT! Both Opus 4.5 and Sonnet 4.5 work via direct API!")
        print("="*70)
        print("\nNext step: Modify EDSLAdapter to use direct Anthropic API")
        print("for these models instead of going through EDSL proxy.")

    print("\n" + "="*70 + "\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
