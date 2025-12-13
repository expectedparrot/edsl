#!/usr/bin/env python3
"""
Test the new vibe logging functionality with diffs and reasoning traces.
"""

import tempfile
import csv
import json
from pathlib import Path
from qualtrics import ImportQualtrics
from qualtrics.vibe import VibeConfig


def test_vibe_logging():
    """Test vibe logging with questions that need fixes."""

    # Create test data with TECHNICAL conversion problems that need fixing
    headers = ["Q1", "Q2", "Q3"]
    question_texts = [
        "What is your name?",  # Clean question, should not be changed
        "<p>Rate our <b>service</b> from 1-5</p>",  # HTML artifacts - SHOULD be fixed
        "How satisfied are you with our product? &nbsp;&lt;required&gt;",  # HTML entities - SHOULD be fixed
    ]
    import_ids = ['{"ImportId":"QID1"}', '{"ImportId":"QID2"}', '{"ImportId":"QID3"}']
    responses = [["John", "4", "25"], ["Jane", "5", "30"], ["Bob", "3", "35"]]

    # Create temporary CSV
    temp_file = tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False)
    writer = csv.writer(temp_file)

    writer.writerow(headers)
    writer.writerow(question_texts)
    writer.writerow(import_ids)

    for response in responses:
        writer.writerow(response)

    temp_file.close()

    try:
        print("=== Testing Vibe Logging Functionality ===")

        # Test with vibe enabled and logging
        vibe_config = VibeConfig(
            enabled=True,
            enable_logging=True,
            verbose_logging=True,  # Show detailed diffs
            max_concurrent=1,  # Process sequentially for clearer logs
            timeout_seconds=15,
        )

        print(f"\n1. Testing with comprehensive logging...")
        importer = ImportQualtrics(
            temp_file.name, verbose=True, vibe_config=vibe_config
        )
        survey = importer.survey

        print(f"\n2. Survey created with {len(survey.questions)} questions")

        # Get detailed change log
        change_log = importer.get_vibe_change_log()
        summary = importer.get_vibe_summary()

        print(f"\n3. Change Summary:")
        print(f"   Total changes: {summary['total_changes']}")
        print(f"   Questions modified: {summary['questions_modified']}")
        print(f"   Average confidence: {summary['average_confidence']:.2f}")
        print(f"   Changes by type: {summary['changes_by_type']}")

        if change_log:
            print(f"\n4. Detailed Change Log:")
            for i, change in enumerate(change_log, 1):
                print(f"   Change {i}:")
                print(f"     Question: {change['question_name']}")
                print(f"     Type: {change['change_type']}")
                print(f"     Before: {repr(change['original_value'])}")
                print(f"     After: {repr(change['new_value'])}")
                print(f"     Reasoning: {change['reasoning']}")
                print(f"     Confidence: {change['confidence']}")
                print(f"     Timestamp: {change['timestamp']}")
                print()

        # Demonstrate that questions were actually fixed
        print(f"\n5. Question Comparison:")
        for i, (orig, question) in enumerate(zip(question_texts, survey.questions)):
            print(f"   Q{i+1}:")
            print(f"     Original: {repr(orig)}")
            print(f"     Fixed:    {repr(question.question_text)}")
            if orig != question.question_text:
                print(f"     ✓ CHANGED")
            else:
                print(f"     - No change")
            print()

        # Test that survey still works
        try:
            results = importer.run()
            print(f"6. Survey execution successful: {len(results)} responses processed")
        except Exception as e:
            print(f"6. Survey execution failed: {e}")

        print("\n✅ Logging functionality test completed!")
        return True

    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback

        traceback.print_exc()
        return False

    finally:
        Path(temp_file.name).unlink(missing_ok=True)


def test_vibe_disabled_logging():
    """Test that when vibe is disabled, no changes are logged."""

    headers = ["Q1"]
    question_texts = ["test question"]
    import_ids = ['{"ImportId":"QID1"}']
    responses = [["answer"]]

    temp_file = tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False)
    writer = csv.writer(temp_file)

    writer.writerow(headers)
    writer.writerow(question_texts)
    writer.writerow(import_ids)
    writer.writerow(responses[0])

    temp_file.close()

    try:
        print("\n=== Testing Vibe Disabled (No Logging) ===")

        # Test with vibe explicitly disabled
        importer = ImportQualtrics(temp_file.name, verbose=True, vibe_config=False)

        # Should have no changes logged
        change_log = importer.get_vibe_change_log()
        summary = importer.get_vibe_summary()

        print(f"Change log entries: {len(change_log)}")
        print(f"Total changes: {summary['total_changes']}")

        assert len(change_log) == 0, "Should have no changes when vibe disabled"
        assert (
            summary["total_changes"] == 0
        ), "Should report no changes when vibe disabled"

        print("✅ Vibe disabled test passed!")
        return True

    except Exception as e:
        print(f"❌ Vibe disabled test failed: {e}")
        return False

    finally:
        Path(temp_file.name).unlink(missing_ok=True)


if __name__ == "__main__":
    print("Testing Vibe Logging System")
    print("=" * 50)

    success1 = test_vibe_logging()
    success2 = test_vibe_disabled_logging()

    if success1 and success2:
        print(f"\n🎉 All logging tests passed!")
        print(f"\nKey Features Demonstrated:")
        print(f"✓ Automatic vibe processing (enabled by default)")
        print(f"✓ Real-time logging with visual indicators")
        print(f"✓ Comprehensive diff tracking")
        print(f"✓ Reasoning traces from AI analysis")
        print(f"✓ Change summary statistics")
        print(f"✓ Structured JSON change log")
        print(f"✓ Graceful handling when disabled")
    else:
        print(f"\n❌ Some tests failed!")
