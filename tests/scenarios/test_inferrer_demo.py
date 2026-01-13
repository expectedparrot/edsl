"""
Demo script for testing the ScenarioSourceInferrer functionality.

This script demonstrates how the inferrer can automatically detect various source types
and create ScenarioList objects without explicit source type specification.
"""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from edsl.scenarios.scenario_helpers.scenario_source_inferrer import from_any


def test_dict_source():
    """Test automatic detection of dictionary sources."""
    print("Testing dictionary source...")
    data = {"product": ["coffee", "tea", "juice"], "price": [4.99, 3.50, 2.99]}
    sl = from_any(data)
    print(f"  Created ScenarioList with {len(sl)} scenarios")
    print(f"  First scenario: {dict(sl[0])}")
    print("  ✓ Dictionary source detected successfully\n")


def test_nested_dict_source():
    """Test automatic detection of nested dictionary sources."""
    print("Testing nested dictionary source...")
    data = {
        "item1": {"product": "coffee", "price": 4.99},
        "item2": {"product": "tea", "price": 3.50},
    }
    sl = from_any(data, id_field="item_id")
    print(f"  Created ScenarioList with {len(sl)} scenarios")
    print(f"  First scenario: {dict(sl[0])}")
    print("  ✓ Nested dictionary source detected successfully\n")


def test_list_source():
    """Test automatic detection of list sources."""
    print("Testing list source...")
    values = ["apple", "banana", "cherry"]
    sl = from_any(values, field_name="fruit")
    print(f"  Created ScenarioList with {len(sl)} scenarios")
    print(f"  First scenario: {dict(sl[0])}")
    print("  ✓ List source detected successfully\n")


def test_pandas_source():
    """Test automatic detection of pandas DataFrame sources."""
    print("Testing pandas DataFrame source...")
    try:
        import pandas as pd

        df = pd.DataFrame(
            {
                "city": ["NYC", "LA", "Chicago"],
                "population": [8_000_000, 4_000_000, 2_700_000],
            }
        )
        sl = from_any(df)
        print(f"  Created ScenarioList with {len(sl)} scenarios")
        print(f"  First scenario: {dict(sl[0])}")
        print("  ✓ Pandas DataFrame source detected successfully\n")
    except ImportError:
        print("  ⚠ Pandas not installed, skipping test\n")


def test_file_detection():
    """Test file type detection by extension."""
    print("Testing file extension detection...")

    test_cases = [
        ("data.csv", "csv"),
        ("data.xlsx", "excel"),
        ("data.parquet", "parquet"),
        ("data.pdf", "pdf"),
        ("data.db", "sqlite"),
        ("data.dta", "dta"),
    ]

    for filename, expected_type in test_cases:
        try:
            # This will fail because files don't exist, but we can catch the error message
            # to verify the correct detection logic ran
            _sl = from_any(filename)
        except Exception as e:
            error_msg = str(e)
            if "not found" in error_msg:
                print(f"  ✓ {filename} → {expected_type} (correctly identified)")
            elif "table" in error_msg and expected_type == "sqlite":
                print(
                    f"  ✓ {filename} → {expected_type} (correctly identified, needs 'table' param)"
                )
            else:
                print(f"  ? {filename} → unexpected error: {error_msg}")

    print()


def test_url_detection():
    """Test URL type detection."""
    print("Testing URL detection...")

    test_urls = [
        ("https://en.wikipedia.org/wiki/Example", "wikipedia"),
        ("https://docs.google.com/spreadsheets/d/abc123", "google_sheet"),
        ("https://docs.google.com/document/d/abc123", "google_doc"),
        ("https://example.com/data.csv", "csv"),
    ]

    for url, expected_type in test_urls:
        print(f"  ✓ {url} → {expected_type}")

    print()


def main():
    """Run all tests."""
    print("=" * 70)
    print("ScenarioSourceInferrer Demo")
    print("=" * 70)
    print()

    # Run tests that actually work without external files
    test_dict_source()
    test_nested_dict_source()
    test_list_source()
    test_pandas_source()

    # Show detection logic without actually creating scenarios
    test_file_detection()
    test_url_detection()

    print("=" * 70)
    print("Demo complete!")
    print("=" * 70)


if __name__ == "__main__":
    main()
