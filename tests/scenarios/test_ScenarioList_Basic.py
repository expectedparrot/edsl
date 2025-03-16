import unittest
import os
import tempfile
from edsl.scenarios import Scenario, ScenarioList
from edsl.scenarios.exceptions import ScenarioError

class TestScenarioListBasic(unittest.TestCase):
    def setUp(self):
        self.s1 = Scenario({"name": "Alice", "age": 30})
        self.s2 = Scenario({"name": "Bob", "age": 25})
        self.s3 = Scenario({"name": "Charlie", "age": 35})
        self.scenario_list = ScenarioList([self.s1, self.s2, self.s3])
        
    def test_initialization(self):
        # Test empty initialization
        empty_list = ScenarioList()
        self.assertEqual(len(empty_list), 0)
        
        # Test initialization with data
        self.assertEqual(len(self.scenario_list), 3)
        self.assertEqual(self.scenario_list[0], self.s1)
        self.assertEqual(self.scenario_list[1], self.s2)
        self.assertEqual(self.scenario_list[2], self.s3)
        
    def test_filter(self):
        # Test filtering by age
        filtered = self.scenario_list.filter("age > 25")
        
        self.assertEqual(len(filtered), 2)  # Alice and Charlie
        self.assertIn(self.s1, filtered)  # Alice (30)
        self.assertIn(self.s3, filtered)  # Charlie (35)
        self.assertNotIn(self.s2, filtered)  # Bob (25)
        
    def test_select(self):
        # Test selecting just one field
        selected = self.scenario_list.select("name")
        
        self.assertEqual(len(selected), 3)
        for s in selected:
            self.assertIn("name", s)
            self.assertNotIn("age", s)
        
    def test_shuffle(self):
        # Create a copy to compare against
        original = ScenarioList([self.s1, self.s2, self.s3])
        
        # Set seed for reproducibility
        shuffled = self.scenario_list.duplicate().shuffle(seed=42)
        
        # Order should be different
        self.assertNotEqual([s.data for s in original], [s.data for s in shuffled])
        
        # Contents should be the same
        for s in original:
            self.assertIn(s, shuffled)
            
    def test_sample(self):
        # Sample 2 scenarios
        sample = self.scenario_list.sample(2, seed=42)
        
        self.assertEqual(len(sample), 2)
        for s in sample:
            self.assertIn(s, self.scenario_list)
            
    def test_to_dict(self):
        # Test conversion to dict
        result = self.scenario_list.to_dict()
        
        self.assertIn("scenarios", result)
        self.assertEqual(len(result["scenarios"]), 3)
        
        # Test with add_edsl_version=False
        result = self.scenario_list.to_dict(add_edsl_version=False)
        self.assertIn("scenarios", result)
        self.assertNotIn("edsl_version", result)
        
    def test_from_dict(self):
        # Create a test dictionary
        d = {
            "scenarios": [
                {"name": "Alice", "age": 30},
                {"name": "Bob", "age": 25}
            ]
        }
        
        # Create from dict
        sl = ScenarioList.from_dict(d)
        
        self.assertEqual(len(sl), 2)
        self.assertEqual(sl[0]["name"], "Alice")
        self.assertEqual(sl[1]["age"], 25)
        
    def test_to_pandas(self):
        # Convert to pandas DataFrame
        df = self.scenario_list.to_pandas()
        
        # Check column names
        self.assertEqual(set(df.columns), {"name", "age"})
        
        # Check values
        self.assertEqual(list(df["name"]), ["Alice", "Bob", "Charlie"])
        self.assertEqual(list(df["age"]), [30, 25, 35])
        
    def test_to_csv(self):
        # Convert to CSV string - returns a FileStore
        csv_file = self.scenario_list.to_csv()
        
        # This should be a FileStore with text data
        self.assertIn("name", csv_file.extracted_text)
        self.assertIn("Alice", csv_file.extracted_text)
        
    def test_from_csv(self):
        # Create a temporary CSV file
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".csv") as f:
            f.write("name,age\n")
            f.write("David,40\n")
            f.write("Eve,22\n")
            csv_path = f.name
            
        try:
            # Load from CSV
            sl = ScenarioList.from_csv(csv_path)
            
            self.assertEqual(len(sl), 2)
            self.assertEqual(sl[0]["name"], "David")
            self.assertEqual(sl[1]["age"], "22")  # Note: CSV imports as strings
        finally:
            # Clean up
            os.unlink(csv_path)
            
    def test_to_list(self):
        # Create a single-field ScenarioList to test to_list
        sl = ScenarioList([
            Scenario({"value": 10}),
            Scenario({"value": 20}),
            Scenario({"value": 30})
        ])
        
        # Extract the field as a list
        values = sl.to_list("value")
        
        self.assertEqual(values, [10, 20, 30])
        
    def test_to_dicts(self):
        # Convert to list of dicts
        dicts = self.scenario_list.to_dicts()
        
        self.assertEqual(len(dicts), 3)
        self.assertEqual(dicts[0]["name"], "Alice")
        self.assertEqual(dicts[1]["age"], 25)
        
    def test_example(self):
        # Get an example ScenarioList
        example = ScenarioList.example()
        
        self.assertIsInstance(example, ScenarioList)
        self.assertGreater(len(example), 0)
        
    def test_expand(self):
        # Create a ScenarioList with a list field to expand
        sl = ScenarioList([
            Scenario({"name": "Alice", "skills": ["Python", "Java"]}),
            Scenario({"name": "Bob", "skills": ["C++"]})
        ])
        
        # Expand the list field
        expanded = sl.expand("skills")
        
        self.assertEqual(len(expanded), 3)  # 2 + 1 skills
        
        # Check expanded scenarios
        python_scenario = [s for s in expanded if s["skills"] == "Python"][0]
        java_scenario = [s for s in expanded if s["skills"] == "Java"][0]
        cpp_scenario = [s for s in expanded if s["skills"] == "C++"][0]
        
        self.assertEqual(python_scenario["name"], "Alice")
        self.assertEqual(java_scenario["name"], "Alice")
        self.assertEqual(cpp_scenario["name"], "Bob")
        
    def test_duplicate(self):
        # Create a duplicate
        duplicate = self.scenario_list.duplicate()
        
        # Should be equal but not the same object
        self.assertEqual(duplicate, self.scenario_list)
        self.assertIsNot(duplicate, self.scenario_list)
        
        # Modifying one shouldn't affect the other
        duplicate[0]["name"] = "Modified"
        self.assertEqual(self.scenario_list[0]["name"], "Alice")

if __name__ == "__main__":
    unittest.main()