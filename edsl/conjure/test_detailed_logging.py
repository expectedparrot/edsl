#!/usr/bin/env python3
"""
Test with detailed logging to see conversion failures.
"""


def test_detailed_logging():
    """Test with maximum verbosity to see conversion details."""
    print("Testing detailed conversion logging...")
    print("=" * 70)

    try:
        from edsl import Results
        from qualtrics.vibe import VibeConfig

        # Create custom config with maximum verbosity
        custom_config = VibeConfig(
            enabled=True,
            enable_logging=True,
            verbose_logging=True,  # This will show all the detailed conversion attempts
            max_concurrent=1,  # Process one at a time for cleaner logs
            timeout_seconds=30,
        )

        # Import with detailed logging
        from qualtrics import ImportQualtrics

        importer = ImportQualtrics(
            "ai_tracking_new.csv", verbose=True, vibe_config=custom_config
        )

        # This will trigger the vibe processing with extensive logging
        survey = importer.survey

        print("\n" + "=" * 70)
        print("✅ Detailed logging test completed")

        return True

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    test_detailed_logging()
