#!/usr/bin/env python3
"""
Check availability of models required for baseline experiment.

This script verifies that all models needed for the baseline experiment
are available via EDSL and have valid API keys configured.
"""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from edsl import Model


# Models needed for experiment
EXPERIMENT_MODELS = {
    "Phase 1 (Older)": [
        "gpt-3.5-turbo",
        "claude-3-haiku-20240307",
        "gemini-2.0-flash",  # Using 2.0 instead of 1.5-pro (not in EDSL)
    ],
    "Phase 2 (Small)": [
        "claude-3-7-sonnet-20250219",
        "gemini-2.5-flash",
        "gpt-4o-mini",
        "claude-3-5-haiku-20241022",
    ],
    "Phase 3 (Flagship)": [
        "claude-opus-4-5-20251101",
        "gpt-4-turbo",
        "claude-sonnet-4-5-20250929",
        "chatgpt-4o-latest",
    ],
    "Baseline": [
        "claude-3-5-haiku-20241022",  # Used as baseline in opposite role
    ],
}


def check_model_availability(model_name: str) -> tuple[bool, bool, str]:
    """Check if a model is available.

    Args:
        model_name: Name of the model to check

    Returns:
        Tuple of (in_catalog, has_api_key, message)
    """
    try:
        # Check if model is in EDSL catalog (all models)
        all_models = Model.available(local_only=False)

        # Convert to list of model names
        all_model_names = []
        for item in all_models:
            if isinstance(item, dict):
                name = item.get("model", item.get("model_name", ""))
            else:
                name = getattr(item, "model", getattr(item, "model_name", ""))
            if name:
                all_model_names.append(name)

        in_catalog = model_name in all_model_names

        if not in_catalog:
            return False, False, "✗ NOT IN CATALOG"

        # Check if API key is configured
        local_models = Model.available(local_only=True)
        local_model_names = []
        for item in local_models:
            if isinstance(item, dict):
                name = item.get("model", item.get("model_name", ""))
            else:
                name = getattr(item, "model", getattr(item, "model_name", ""))
            if name:
                local_model_names.append(name)

        has_api_key = model_name in local_model_names

        if has_api_key:
            return True, True, "✓ Ready (in catalog + API key)"
        else:
            return True, False, "⚠ In catalog (needs API key)"

    except Exception as e:
        return False, False, f"✗ Error: {str(e)}"


def main():
    """Main entry point."""
    print("=" * 70)
    print("BASELINE EXPERIMENT - MODEL AVAILABILITY CHECK")
    print("=" * 70)
    print()

    all_available = True
    phase_results = {}

    for phase_name, models in EXPERIMENT_MODELS.items():
        print(f"{phase_name}:")
        phase_available = True

        for model_name in models:
            in_catalog, has_api_key, message = check_model_availability(model_name)

            print(f"  {model_name:<45} {message}")

            if not has_api_key:
                phase_available = False
                all_available = False

        phase_results[phase_name] = phase_available
        print()

    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)

    for phase_name, available in phase_results.items():
        status = "✓ Ready" if available else "⚠ Needs API keys"
        print(f"  {phase_name:<30} {status}")

    print()
    print("LEGEND:")
    print("  ✓ Ready              = Model in catalog + API key configured")
    print("  ⚠ In catalog         = Model exists but needs API key")
    print("  ✗ NOT IN CATALOG     = Model not found in EDSL")
    print()

    if all_available:
        print("✅ All models ready! You can run the full experiment.")
        return 0
    else:
        print("⚠️  Some models need API key configuration:")
        print()
        print("Configure API keys with:")
        print("  export ANTHROPIC_API_KEY='sk-ant-...'")
        print("  export OPENAI_API_KEY='sk-...'")
        print("  export GOOGLE_API_KEY='...'")
        print()
        print("Then run this script again to verify.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
