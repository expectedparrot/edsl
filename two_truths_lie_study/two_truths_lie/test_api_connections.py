#!/usr/bin/env python3
"""
Quick test to verify all API providers are working with EDSL.

Tests one model from each provider:
- OpenAI: gpt-3.5-turbo
- Anthropic: claude-3-5-haiku-20241022
- Google: gemini-2.5-flash
"""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from edsl import Model, QuestionFreeText

# Test models (one per provider)
TEST_MODELS = {
    "OpenAI": "gpt-3.5-turbo",
    "Anthropic": "claude-3-5-haiku-20241022",
    "Google": "gemini-2.5-flash",
}

# Simple test question
TEST_QUESTION = QuestionFreeText(
    question_text="Say 'API test successful' and nothing else.",
    question_name="api_test"
)


def test_model(provider_name: str, model_name: str) -> tuple[bool, str]:
    """Test if a model API is working.

    Args:
        provider_name: Name of the provider (for display)
        model_name: EDSL model name

    Returns:
        Tuple of (success, message)
    """
    try:
        print(f"  Testing {model_name}...", end=" ", flush=True)

        # Create model
        model = Model(model_name)

        # Run simple query
        results = TEST_QUESTION.by(model).run()

        # Extract response
        response = results.select("answer").first()

        print("✓")
        return True, f"Response: {response['answer'][:50]}"

    except Exception as e:
        print("✗")
        error_msg = str(e)

        # Check for common error patterns
        if "API key" in error_msg or "authentication" in error_msg.lower():
            return False, "API key invalid or not configured"
        elif "rate limit" in error_msg.lower():
            return False, "Rate limit exceeded"
        elif "not found" in error_msg.lower():
            return False, "Model not found"
        else:
            return False, f"Error: {error_msg[:100]}"


def main():
    """Main entry point."""
    print("=" * 70)
    print("API CONNECTION TEST")
    print("=" * 70)
    print()
    print("Testing one model from each provider...")
    print()

    results = {}
    all_success = True

    for provider, model in TEST_MODELS.items():
        print(f"{provider}:")
        success, message = test_model(provider, model)
        results[provider] = (success, message)
        print(f"  {message}")
        print()

        if not success:
            all_success = False

    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)

    for provider, (success, _) in results.items():
        status = "✓ Working" if success else "✗ Failed"
        print(f"  {provider:<20} {status}")

    print()

    if all_success:
        print("✅ All API providers working! Ready to run experiments.")
        return 0
    else:
        print("❌ Some API providers failed. Check API keys and try again.")
        print()
        print("Verify API keys are set:")
        print("  echo $OPENAI_API_KEY")
        print("  echo $ANTHROPIC_API_KEY")
        print("  echo $GOOGLE_API_KEY")
        return 1


if __name__ == "__main__":
    sys.exit(main())
