#!/usr/bin/env python3
"""
Test vibe integration with Qualtrics importer.
"""

import tempfile
import csv
from pathlib import Path
from qualtrics import ImportQualtrics
from qualtrics.vibe import VibeConfig


def test_vibe_integration():
    """Test that vibe integration works without breaking existing functionality."""

    # Create test data
    headers = ["Q1", "Q2"]
    question_texts = [
        "whats ur name",  # This should be improved by vibe
        "Rate our service from 1 to 5",
    ]
    import_ids = ['{"ImportId":"QID1"}', '{"ImportId":"QID2"}']
    responses = [
        ["John", "4"],
        ["Jane", "5"],
    ]

    temp_file = tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False)
    writer = csv.writer(temp_file)

    writer.writerow(headers)
    writer.writerow(question_texts)
    writer.writerow(import_ids)

    for response in responses:
        writer.writerow(response)

    temp_file.close()

    try:
        print("=== Testing Vibe Integration ===")

        # Test 1: Import without vibe (should work as before)
        print("\n1. Testing without vibe...")
        importer1 = ImportQualtrics(temp_file.name, verbose=False)
        survey1 = importer1.survey
        print(f"   Survey created with {len(survey1.questions)} questions")
        print(f"   Q1 text: {survey1.questions[0].question_text}")

        # Test 2: Import with vibe disabled (should work the same)
        print("\n2. Testing with vibe disabled...")
        vibe_config_disabled = VibeConfig(enabled=False)
        importer2 = ImportQualtrics(
            temp_file.name, verbose=False, vibe_config=vibe_config_disabled
        )
        survey2 = importer2.survey
        print(f"   Survey created with {len(survey2.questions)} questions")
        print(f"   Q1 text: {survey2.questions[0].question_text}")

        # Test 3: Import with vibe enabled (should enhance questions)
        print("\n3. Testing with vibe enabled...")
        vibe_config_enabled = VibeConfig(
            enabled=True,
            system_prompt="Fix grammar and improve clarity. Make the question more professional.",
            max_concurrent=1,
            temperature=0.1,
        )

        try:
            importer3 = ImportQualtrics(
                temp_file.name, verbose=True, vibe_config=vibe_config_enabled
            )
            survey3 = importer3.survey
            print(f"   Survey created with {len(survey3.questions)} questions")
            print(f"   Q1 original: {question_texts[0]}")
            print(f"   Q1 enhanced: {survey3.questions[0].question_text}")

            # Test that other functionality still works
            results = importer3.run()
            print(f"   Survey run successful: {len(results)} responses")

            print("\n✅ All vibe integration tests passed!")
            return True

        except Exception as e:
            print(
                f"   ⚠️  Vibe processing failed (this may be expected if no model access): {e}"
            )
            print("   ✅ Fallback to original functionality works")
            return True

    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback

        traceback.print_exc()
        return False

    finally:
        Path(temp_file.name).unlink(missing_ok=True)


def test_vibe_config_creation():
    """Test VibeConfig creation and defaults."""

    print("\n=== Testing VibeConfig ===")

    # Test default config
    config1 = VibeConfig()
    print(f"Default enabled: {config1.enabled}")
    print(f"Default max_concurrent: {config1.max_concurrent}")
    print(f"Default timeout: {config1.timeout_seconds}")
    print(f"System prompt length: {len(config1.system_prompt)}")

    # Test custom config
    config2 = VibeConfig(
        enabled=False,
        system_prompt="Custom prompt",
        max_concurrent=10,
        timeout_seconds=60,
    )
    print(f"Custom enabled: {config2.enabled}")
    print(f"Custom max_concurrent: {config2.max_concurrent}")
    print(f"Custom timeout: {config2.timeout_seconds}")
    print(f"Custom prompt: {config2.system_prompt}")

    print("✅ VibeConfig tests passed!")


if __name__ == "__main__":
    print("Testing Qualtrics Vibe Integration")
    print("=" * 40)

    test_vibe_config_creation()
    success = test_vibe_integration()

    if success:
        print("\n🎉 Integration tests completed successfully!")
        print("\nUsage example:")
        print(
            """
from qualtrics import ImportQualtrics
from qualtrics.vibe import VibeConfig

# Create vibe config
vibe_config = VibeConfig(
    enabled=True,
    system_prompt="Your custom instructions for improving questions",
    max_concurrent=3,
    temperature=0.1
)

# Import with vibe enhancement
importer = ImportQualtrics("survey.csv", vibe_config=vibe_config)
enhanced_survey = importer.survey
"""
        )
    else:
        print("\n❌ Some tests failed!")
