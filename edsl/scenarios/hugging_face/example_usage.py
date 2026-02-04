"""Example usage of the Hugging Face loader functionality.

This script demonstrates how to use the from_hugging_face method.
Note: This requires the 'datasets' library to be installed.
"""

if __name__ == "__main__":
    import sys
    import os

    # Add the project root to the path for testing
    sys.path.insert(
        0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.."))
    )

    try:
        from edsl.scenarios.scenario_list import ScenarioList

        print("Testing Hugging Face loader...")

        # Test 1: Try to load a simple dataset (this will fail if datasets is not installed)
        try:
            print("\n1. Testing with a simple dataset...")
            sl = ScenarioList.from_hugging_face("squad")
            print(f"✓ Successfully loaded dataset with {len(sl)} scenarios")
            print(f"First scenario keys: {list(sl[0].keys())}")
        except ImportError as e:
            print(f"✗ Datasets library not installed: {e}")
        except Exception as e:
            print(f"✗ Error loading dataset: {e}")

        # Test 2: Try to load a dataset with multiple configurations (should fail without specifying config)
        try:
            print("\n2. Testing with multi-config dataset (should fail)...")
            sl = ScenarioList.from_hugging_face("glue")
            print("✗ Expected error for multi-config dataset")
        except ValueError as e:
            print(f"✓ Correctly caught error: {e}")
        except Exception as e:
            print(f"✗ Unexpected error: {e}")

        # Test 3: Try to load a dataset with specific configuration
        try:
            print("\n3. Testing with specific config...")
            sl = ScenarioList.from_hugging_face("glue", config_name="cola")
            print(f"✓ Successfully loaded dataset with config, {len(sl)} scenarios")
        except Exception as e:
            print(f"✗ Error loading dataset with config: {e}")

        print("\nTesting complete!")

    except ImportError as e:
        print(f"Error importing EDSL: {e}")
        print("Make sure you're running this from the correct directory.")
