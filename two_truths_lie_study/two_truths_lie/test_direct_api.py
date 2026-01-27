#!/usr/bin/env python3
"""
Test direct API access for GPT-5, o3, and Opus 4.5.

Bypass EDSL proxy and call APIs directly to see if models actually exist.
"""

import os
import sys


def test_anthropic_opus_4_5():
    """Test Claude Opus 4.5 via direct Anthropic API."""
    print("\n" + "="*70)
    print("Testing claude-opus-4-5-20251101 via Anthropic API")
    print("="*70)

    try:
        import anthropic

        client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

        print("Making API call...", end=" ", flush=True)
        message = client.messages.create(
            model="claude-opus-4-5-20251101",
            max_tokens=100,
            messages=[
                {"role": "user", "content": "What is 2 + 2? Answer with just the number."}
            ]
        )

        response = message.content[0].text
        print(f"✅ SUCCESS!")
        print(f"Response: {response}")
        return True

    except anthropic.NotFoundError:
        print(f"❌ Model not found in Anthropic API")
        return False
    except anthropic.AuthenticationError:
        print(f"❌ Authentication error - check ANTHROPIC_API_KEY")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def test_openai_gpt5():
    """Test GPT-5.2 via direct OpenAI API."""
    print("\n" + "="*70)
    print("Testing gpt-5.2-2025-12-11 via OpenAI API")
    print("="*70)

    try:
        from openai import OpenAI

        client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

        print("Making API call...", end=" ", flush=True)
        response = client.chat.completions.create(
            model="gpt-5.2-2025-12-11",
            messages=[
                {"role": "user", "content": "What is 2 + 2? Answer with just the number."}
            ],
            max_tokens=100
        )

        answer = response.choices[0].message.content
        print(f"✅ SUCCESS!")
        print(f"Response: {answer}")
        return True

    except Exception as e:
        error_msg = str(e)
        if "does not exist" in error_msg or "not found" in error_msg.lower():
            print(f"❌ Model not found in OpenAI API")
        elif "authentication" in error_msg.lower():
            print(f"❌ Authentication error - check OPENAI_API_KEY")
        else:
            print(f"❌ Error: {error_msg[:100]}")
        return False


def test_openai_o3():
    """Test o3 via direct OpenAI API."""
    print("\n" + "="*70)
    print("Testing o3 via OpenAI API")
    print("="*70)

    try:
        from openai import OpenAI

        client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

        print("Making API call...", end=" ", flush=True)
        response = client.chat.completions.create(
            model="o3",
            messages=[
                {"role": "user", "content": "What is 2 + 2? Answer with just the number."}
            ],
            max_tokens=100
        )

        answer = response.choices[0].message.content
        print(f"✅ SUCCESS!")
        print(f"Response: {answer}")
        return True

    except Exception as e:
        error_msg = str(e)
        if "does not exist" in error_msg or "not found" in error_msg.lower():
            print(f"❌ Model not found in OpenAI API")
        elif "authentication" in error_msg.lower():
            print(f"❌ Authentication error - check OPENAI_API_KEY")
        else:
            print(f"❌ Error: {error_msg[:100]}")
        return False


def main():
    """Test all models via direct API."""
    print("\n" + "="*70)
    print("TESTING DIRECT API ACCESS FOR PHASE 3 MODELS")
    print("="*70)
    print("\nBypassing EDSL proxy to test if models exist in provider APIs.")

    results = {
        "claude-opus-4-5-20251101": test_anthropic_opus_4_5(),
        "gpt-5.2-2025-12-11": test_openai_gpt5(),
        "o3": test_openai_o3(),
    }

    print("\n\n" + "="*70)
    print("SUMMARY")
    print("="*70)

    working_direct = [model for model, works in results.items() if works]
    failed_direct = [model for model, works in results.items() if not works]

    if working_direct:
        print(f"\n✅ {len(working_direct)} model(s) work via direct API:")
        for model in working_direct:
            print(f"  - {model}")

        print("\n" + "-"*70)
        print("NEXT STEPS:")
        print("-"*70)
        print("\nIf these models work via direct API, we can:")
        print("1. Modify EDSLAdapter to use direct API calls for these models")
        print("2. This would bypass EDSL's 500 error proxy issue")
        print("3. Keep EDSL for other models that work fine")

    if failed_direct:
        print(f"\n❌ {len(failed_direct)} model(s) don't work even via direct API:")
        for model in failed_direct:
            print(f"  - {model}")

        print("\nThese models may not exist yet or require special access.")

    print("\n" + "="*70 + "\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
