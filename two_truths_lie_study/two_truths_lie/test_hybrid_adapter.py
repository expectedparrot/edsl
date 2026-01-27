#!/usr/bin/env python3
"""
Test the hybrid EDSLAdapter with both direct API and EDSL proxy.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.edsl_adapter import EDSLAdapter
from src.config.schema import LLMConfig


def test_model(adapter: EDSLAdapter, model_name: str):
    """Test a model through the adapter."""
    print(f"\nTesting {model_name}:")
    print("-" * 70)

    try:
        response, metadata = adapter._run_question(
            prompt_text="What is 2 + 2? Answer with just the number.",
            question_name="math_test",
            model_name=model_name,
            temperature=1.0
        )

        print(f"✅ SUCCESS!")
        print(f"Response: {response[:100]}")
        print(f"API Type: {metadata.get('api_type', 'edsl_proxy')}")
        if 'usage' in metadata:
            print(f"Tokens: {metadata['usage']}")
        print(f"Duration: {metadata.get('duration_seconds', 0):.2f}s")
        return True

    except Exception as e:
        print(f"❌ FAILED: {e}")
        return False


def main():
    """Test all Phase 3 models."""
    print("\n" + "="*70)
    print("TESTING HYBRID EDSL ADAPTER")
    print("="*70)
    print("\nDirect API models use Anthropic API")
    print("Other models use EDSL proxy")

    adapter = EDSLAdapter(LLMConfig(name="claude-3-5-haiku-20241022", temperature=1.0))

    # Models that should use direct API
    direct_api_models = [
        "claude-opus-4-5-20251101",
        "claude-sonnet-4-5-20250929",
    ]

    # Models that should use EDSL proxy
    edsl_proxy_models = [
        "gpt-5-2025-08-07",
        "o3-2025-04-16",
        "claude-sonnet-4-20250514",
    ]

    print("\n" + "="*70)
    print("DIRECT API MODELS (Anthropic API)")
    print("="*70)

    direct_results = {}
    for model in direct_api_models:
        direct_results[model] = test_model(adapter, model)

    print("\n" + "="*70)
    print("EDSL PROXY MODELS")
    print("="*70)

    proxy_results = {}
    for model in edsl_proxy_models:
        proxy_results[model] = test_model(adapter, model)

    print("\n\n" + "="*70)
    print("SUMMARY")
    print("="*70)

    all_results = {**direct_results, **proxy_results}
    working = [m for m, works in all_results.items() if works]
    failed = [m for m, works in all_results.items() if not works]

    if working:
        print(f"\n✅ {len(working)} model(s) working:")
        for model in working:
            api_type = "Direct API" if model in direct_api_models else "EDSL Proxy"
            print(f"  - {model} ({api_type})")

    if failed:
        print(f"\n❌ {len(failed)} model(s) failed:")
        for model in failed:
            print(f"  - {model}")

    if len(working) >= 4:
        print("\n" + "="*70)
        print("🎉 SUCCESS! At least 4 flagship models working!")
        print("="*70)
        print("\nRecommended Phase 3 models:")
        for i, model in enumerate(working[:4], 1):
            api_type = "Direct API" if model in direct_api_models else "EDSL Proxy"
            print(f"  {i}. {model} ({api_type})")

    print("\n" + "="*70 + "\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
