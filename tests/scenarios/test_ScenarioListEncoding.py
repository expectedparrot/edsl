import os
import unittest
from pathlib import Path

from edsl.scenarios.scenario_list import ScenarioList


class TestScenarioListEncoding(unittest.TestCase):
    """Tests for ScenarioList encoding handling with CSV files."""

    def setUp(self):
        # Get the path to the test data file
        current_dir = Path(__file__).parent
        self.test_file_path = str(current_dir / "test_data" / "non_utf8_test.csv")
        
        # Make sure test file exists
        self.assertTrue(os.path.exists(self.test_file_path), 
                        f"Test file not found: {self.test_file_path}")
    
    def test_load_non_utf8_csv(self):
        """Test loading a CSV file with non-UTF8 encoding."""
        try:
            # This would fail before the fix
            scenarios = ScenarioList.from_csv(self.test_file_path)
            
            # If we get here, make sure data is properly loaded
            self.assertEqual(len(scenarios), 5, "Expected 5 scenarios in the list")
            
            # Verify some of the content to ensure it's properly decoded
            self.assertEqual(scenarios[0]["name"], "John Doe")
            self.assertTrue("María" in scenarios[2]["name"] or "Maria" in scenarios[2]["name"], 
                           f"Special character name not found, got: {scenarios[2]['name']}")
            self.assertTrue("François" in scenarios[3]["name"] or "Francois" in scenarios[3]["name"], 
                           f"Special character name not found, got: {scenarios[3]['name']}")
            
        except UnicodeDecodeError:
            self.fail("Failed to decode non-UTF8 CSV file")
        except Exception as e:
            self.fail(f"Unexpected error loading non-UTF8 CSV: {str(e)}")


if __name__ == "__main__":
    unittest.main()