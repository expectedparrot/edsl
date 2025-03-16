import unittest
import os
import tempfile
import pandas as pd
import numpy as np
from unittest.mock import patch, MagicMock
from edsl.scenarios import Scenario, ScenarioList
from edsl.scenarios.exceptions import ScenarioError

class TestScenarioListCoverage(unittest.TestCase):
    def setUp(self):
        self.s1 = Scenario({"name": "Alice", "age": 30, "city": "New York"})
        self.s2 = Scenario({"name": "Bob", "age": 25, "city": "Chicago"})
        self.s3 = Scenario({"name": "Charlie", "age": 35, "city": "Los Angeles"})
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
        
    def test_str_representation(self):
        # Test string representation
        str_result = str(self.scenario_list)
        self.assertIn("ScenarioList", str_result)
        self.assertIn("length=3", str_result)
        
    def test_repr_representation(self):
        # Test repr representation
        repr_result = repr(self.scenario_list)
        self.assertIn("ScenarioList([", repr_result)
        self.assertIn("Scenario({", repr_result)
        self.assertIn("'name': 'Alice'", repr_result)
        
    def test_method_chaining(self):
        # Test that methods can be chained
        result = self.scenario_list.filter("age > 25").select("name", "age")
        
        self.assertEqual(len(result), 2)  # Alice and Charlie (age > 25)
        self.assertIn("name", result[0])
        self.assertIn("age", result[0])
        self.assertNotIn("city", result[0])
        
    def test_to_dict(self):
        # Test conversion to dictionary
        result = self.scenario_list.to_dict()
        
        self.assertIn("scenarios", result)
        self.assertEqual(len(result["scenarios"]), 3)
        self.assertEqual(result["scenarios"][0]["name"], "Alice")
        self.assertEqual(result["scenarios"][1]["name"], "Bob")
        self.assertEqual(result["scenarios"][2]["name"], "Charlie")
        
        # Test without EDSL version
        result = self.scenario_list.to_dict(add_edsl_version=False)
        self.assertNotIn("edsl_version", result)
        self.assertNotIn("edsl_class_name", result)
        
    def test_from_dict(self):
        # Create dictionary representation
        dict_repr = {
            "scenarios": [
                {"name": "Alice", "age": 30},
                {"name": "Bob", "age": 25}
            ]
        }
        
        # Test from_dict method
        scenario_list = ScenarioList.from_dict(dict_repr)
        
        self.assertEqual(len(scenario_list), 2)
        self.assertEqual(scenario_list[0]["name"], "Alice")
        self.assertEqual(scenario_list[1]["name"], "Bob")
        
    def test_hash(self):
        # Create two identical ScenarioLists
        sl1 = ScenarioList([
            Scenario({"name": "Alice", "age": 30}),
            Scenario({"name": "Bob", "age": 25})
        ])
        
        sl2 = ScenarioList([
            Scenario({"name": "Alice", "age": 30}),
            Scenario({"name": "Bob", "age": 25})
        ])
        
        # Test that identical ScenarioLists have the same hash
        self.assertEqual(hash(sl1), hash(sl2))
        
        # Test that different ScenarioLists have different hashes
        sl3 = ScenarioList([
            Scenario({"name": "Alice", "age": 31}),  # Changed age
            Scenario({"name": "Bob", "age": 25})
        ])
        
        self.assertNotEqual(hash(sl1), hash(sl3))
        
    def test_shuffle(self):
        # Since shuffle is random, we'll use a seed to make it deterministic
        original = ScenarioList(self.scenario_list)
        shuffled = self.scenario_list.shuffle(seed=42)
        
        # Test that shuffle returns the same object (in-place operation)
        self.assertIs(shuffled, self.scenario_list)
        
        # Test that the content has changed
        self.assertNotEqual([s.data for s in original], [s.data for s in shuffled])
        
        # Test with a fixed seed for reproducibility
        sl1 = ScenarioList([self.s1, self.s2, self.s3]).shuffle(seed=123)
        sl2 = ScenarioList([self.s1, self.s2, self.s3]).shuffle(seed=123)
        
        # Both should be shuffled the same way
        for i in range(len(sl1)):
            self.assertEqual(sl1[i], sl2[i])
            
    def test_sample(self):
        # Test sampling without replacement
        sample = self.scenario_list.sample(2, seed=42)
        
        self.assertIsInstance(sample, ScenarioList)
        self.assertEqual(len(sample), 2)
        
        # Each sampled scenario should be from the original list
        for s in sample:
            self.assertIn(s, self.scenario_list)
            
        # Test reproducibility with seed
        sample1 = self.scenario_list.sample(2, seed=123)
        sample2 = self.scenario_list.sample(2, seed=123)
        
        for i in range(len(sample1)):
            self.assertEqual(sample1[i], sample2[i])
            
    def test_sort(self):
        # Create an unsorted scenario list
        unsorted = ScenarioList([
            Scenario({"name": "Charlie", "age": 35}),
            Scenario({"name": "Alice", "age": 30}),
            Scenario({"name": "Bob", "age": 25})
        ])
        
        # Sort by name
        sorted_by_name = unsorted.sort("name")
        self.assertEqual(sorted_by_name[0]["name"], "Alice")
        self.assertEqual(sorted_by_name[1]["name"], "Bob")
        self.assertEqual(sorted_by_name[2]["name"], "Charlie")
        
        # Sort by age (descending)
        sorted_by_age_desc = unsorted.sort("age", reverse=True)
        self.assertEqual(sorted_by_age_desc[0]["name"], "Charlie")  # 35
        self.assertEqual(sorted_by_age_desc[1]["name"], "Alice")    # 30
        self.assertEqual(sorted_by_age_desc[2]["name"], "Bob")      # 25
        
        # Test with custom key function
        sorted_by_name_length = unsorted.sort(key=lambda s: len(s["name"]))
        self.assertEqual(sorted_by_name_length[0]["name"], "Bob")      # 3 letters
        self.assertEqual(sorted_by_name_length[1]["name"], "Alice")    # 5 letters
        self.assertEqual(sorted_by_name_length[2]["name"], "Charlie")  # 7 letters
        
    def test_filter(self):
        # Filter by age
        filtered = self.scenario_list.filter("age > 25")
        
        self.assertEqual(len(filtered), 2)  # Alice and Charlie
        self.assertIn(self.s1, filtered)    # Alice
        self.assertIn(self.s3, filtered)    # Charlie
        self.assertNotIn(self.s2, filtered) # Bob
        
        # Filter by city
        filtered = self.scenario_list.filter("city == 'New York'")
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0]["name"], "Alice")
        
        # Filter with combination
        filtered = self.scenario_list.filter("age >= 30 and city != 'Chicago'")
        self.assertEqual(len(filtered), 2)
        
        # Test with invalid expression
        with self.assertRaises(ScenarioError):
            self.scenario_list.filter("invalid_field > 10")
            
    def test_select(self):
        # Select specific fields
        selected = self.scenario_list.select("name", "age")
        
        for s in selected:
            self.assertIn("name", s)
            self.assertIn("age", s)
            self.assertNotIn("city", s)
            
        # Test with a single field
        selected = self.scenario_list.select("name")
        for s in selected:
            self.assertIn("name", s)
            self.assertNotIn("age", s)
            self.assertNotIn("city", s)
            
    def test_drop(self):
        # Drop specific fields
        dropped = self.scenario_list.drop("city")
        
        for s in dropped:
            self.assertIn("name", s)
            self.assertIn("age", s)
            self.assertNotIn("city", s)
            
        # Drop multiple fields
        dropped = self.scenario_list.drop("age", "city")
        for s in dropped:
            self.assertIn("name", s)
            self.assertNotIn("age", s)
            self.assertNotIn("city", s)
            
    def test_pivot(self):
        # Create a scenario list with repeated values
        sl = ScenarioList([
            Scenario({"country": "USA", "city": "New York", "population": 8400000}),
            Scenario({"country": "USA", "city": "Los Angeles", "population": 3900000}),
            Scenario({"country": "Canada", "city": "Toronto", "population": 2900000})
        ])
        
        # Pivot by country
        pivoted = sl.pivot("country", "city", "population")
        
        # Check structure
        self.assertIn("country", pivoted[0])
        self.assertIn("New York", pivoted[0])
        self.assertIn("Los Angeles", pivoted[0])
        self.assertIn("Toronto", pivoted[0])
        
        # Check values
        usa_row = [s for s in pivoted if s["country"] == "USA"][0]
        canada_row = [s for s in pivoted if s["country"] == "Canada"][0]
        
        self.assertEqual(usa_row["New York"], 8400000)
        self.assertEqual(usa_row["Los Angeles"], 3900000)
        self.assertIsNone(usa_row["Toronto"])
        
        self.assertEqual(canada_row["Toronto"], 2900000)
        self.assertIsNone(canada_row["New York"])
        self.assertIsNone(canada_row["Los Angeles"])
        
    def test_to_dataset(self):
        # Convert to dataset
        dataset = self.scenario_list.to_dataset()
        
        # Dataset should contain all keys from all scenarios
        self.assertTrue(any("name" in d for d in dataset))
        self.assertTrue(any("age" in d for d in dataset))
        self.assertTrue(any("city" in d for d in dataset))
        
        # Convert dataset to pandas to check values
        df = dataset.to_pandas()
        
        # Check DataFrame's values 
        self.assertEqual(list(df["name"]), ["Alice", "Bob", "Charlie"])
        self.assertEqual(list(df["age"]), [30, 25, 35])
        
    def test_to_pandas(self):
        # Convert directly to pandas
        df = self.scenario_list.to_pandas()
        
        # Check DataFrame structure and values
        self.assertIsInstance(df, pd.DataFrame)
        self.assertEqual(list(df.columns), ["name", "age", "city"])
        self.assertEqual(list(df["name"]), ["Alice", "Bob", "Charlie"])
        self.assertEqual(list(df["age"]), [30, 25, 35])
        
    def test_from_pandas(self):
        # Create a test DataFrame
        df = pd.DataFrame({
            "name": ["Alice", "Bob"],
            "age": [30, 25],
            "city": ["New York", "Chicago"]
        })
        
        # Convert to ScenarioList
        scenario_list = ScenarioList.from_pandas(df)
        
        self.assertEqual(len(scenario_list), 2)
        self.assertEqual(scenario_list[0]["name"], "Alice")
        self.assertEqual(scenario_list[0]["age"], 30)
        self.assertEqual(scenario_list[0]["city"], "New York")
        self.assertEqual(scenario_list[1]["name"], "Bob")
        
    def test_to_csv(self):
        # Convert to CSV string
        csv_str = self.scenario_list.to_csv()
        
        # Check CSV content
        self.assertIn("name,age,city", csv_str)
        self.assertIn("Alice,30,New York", csv_str)
        self.assertIn("Bob,25,Chicago", csv_str)
        self.assertIn("Charlie,35,Los Angeles", csv_str)
        
    def test_from_csv(self):
        # Create a temporary CSV file
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".csv") as f:
            f.write("name,age,city\n")
            f.write("Alice,30,New York\n")
            f.write("Bob,25,Chicago\n")
            csv_path = f.name
            
        try:
            # Load from CSV
            scenario_list = ScenarioList.from_csv(csv_path)
            
            self.assertEqual(len(scenario_list), 2)
            self.assertEqual(scenario_list[0]["name"], "Alice")
            self.assertEqual(scenario_list[0]["age"], "30")  # Note: CSV imports as strings
            self.assertEqual(scenario_list[1]["city"], "Chicago")
            
        finally:
            # Clean up
            os.unlink(csv_path)
            
    def test_to_json(self):
        # Convert to JSON
        json_str = self.scenario_list.to_json()
        
        # Check JSON content
        self.assertIn('"name": "Alice"', json_str)
        self.assertIn('"age": 30', json_str)
        self.assertIn('"city": "New York"', json_str)
        
        # Convert with indentation
        json_indented = self.scenario_list.to_json(indent=2)
        self.assertIn('  "name": "Alice"', json_indented)
        
    def test_to_dict_list(self):
        # Convert to list of dictionaries
        dict_list = self.scenario_list.to_dicts()
        
        self.assertEqual(len(dict_list), 3)
        self.assertEqual(dict_list[0]["name"], "Alice")
        self.assertEqual(dict_list[1]["age"], 25)
        self.assertEqual(dict_list[2]["city"], "Los Angeles")
        
    def test_to_list(self):
        # Create ScenarioList with a specific field
        sl = ScenarioList([
            Scenario({"value": 10}),
            Scenario({"value": 20}),
            Scenario({"value": 30})
        ])
        
        # Convert to list of values
        value_list = sl.to_list("value")
        self.assertEqual(value_list, [10, 20, 30])
        
    def test_append_and_extend(self):
        # Create a new ScenarioList
        sl = ScenarioList([Scenario({"name": "Alice"})])
        
        # Append a Scenario
        sl.append(Scenario({"name": "Bob"}))
        self.assertEqual(len(sl), 2)
        self.assertEqual(sl[1]["name"], "Bob")
        
        # Extend with multiple Scenarios
        sl.extend([Scenario({"name": "Charlie"}), Scenario({"name": "David"})])
        self.assertEqual(len(sl), 4)
        self.assertEqual(sl[2]["name"], "Charlie")
        self.assertEqual(sl[3]["name"], "David")
        
    def test_multiplication(self):
        # Create two simple ScenarioLists
        sl1 = ScenarioList([Scenario({"a": 1}), Scenario({"a": 2})])
        sl2 = ScenarioList([Scenario({"b": 3}), Scenario({"b": 4})])
        
        # Multiply them to get a cross product
        result = sl1 * sl2
        
        # Should get 4 scenarios (2×2)
        self.assertEqual(len(result), 4)
        
        # Check all combinations
        combinations = [{"a": 1, "b": 3}, {"a": 1, "b": 4}, {"a": 2, "b": 3}, {"a": 2, "b": 4}]
        for scenario in result:
            # Convert scenario to dict for comparison
            scenario_dict = {k: v for k, v in scenario.items()}
            self.assertIn(scenario_dict, combinations)
            
    def test_rename(self):
        # Rename fields in the entire ScenarioList
        renamed = self.scenario_list.rename({"name": "person", "city": "location"})
        
        for s in renamed:
            self.assertIn("person", s)
            self.assertIn("location", s)
            self.assertNotIn("name", s)
            self.assertNotIn("city", s)
            self.assertIn("age", s)  # Not renamed
            
    def test_rename_with_args(self):
        # Rename using positional arguments
        renamed = self.scenario_list.rename("name", "person")
        
        for s in renamed:
            self.assertIn("person", s)
            self.assertNotIn("name", s)
            self.assertIn("age", s)
            self.assertIn("city", s)
            
    def test_expand(self):
        # Create a ScenarioList with a list field to expand
        sl = ScenarioList([
            Scenario({"name": "Alice", "skills": ["Python", "JavaScript"]}),
            Scenario({"name": "Bob", "skills": ["Java", "C++", "Ruby"]})
        ])
        
        # Expand the skills field
        expanded = sl.expand("skills")
        
        self.assertEqual(len(expanded), 5)  # 2 + 3 skills
        
        # Check Alice's expanded scenarios
        alice_scenarios = [s for s in expanded if s["name"] == "Alice"]
        self.assertEqual(len(alice_scenarios), 2)
        skills = [s["skills"] for s in alice_scenarios]
        self.assertIn("Python", skills)
        self.assertIn("JavaScript", skills)
        
        # Check Bob's expanded scenarios
        bob_scenarios = [s for s in expanded if s["name"] == "Bob"]
        self.assertEqual(len(bob_scenarios), 3)
        skills = [s["skills"] for s in bob_scenarios]
        self.assertIn("Java", skills)
        self.assertIn("C++", skills)
        self.assertIn("Ruby", skills)
        
    def test_table(self):
        # Generate a table
        table = self.scenario_list.table()
        
        # It's hard to test the exact output, so just check it's a string
        self.assertIsInstance(table, str)
        self.assertIn("name", table)
        self.assertIn("age", table)
        self.assertIn("city", table)
        self.assertIn("Alice", table)
        
        # Test with specific format
        table = self.scenario_list.table(tablefmt="grid")
        self.assertIn("+", table)  # Grid format uses + for corners
        
        # Test with specific columns
        table = self.scenario_list.table("name", "age")
        self.assertIn("name", table)
        self.assertIn("age", table)
        self.assertNotIn("city", table)
        
    def test_duplicate(self):
        # Create a deep copy
        duplicate = self.scenario_list.duplicate()
        
        # Should be equal but not the same object
        self.assertEqual(duplicate, self.scenario_list)
        self.assertIsNot(duplicate, self.scenario_list)
        
        # Modifying the duplicate shouldn't affect the original
        duplicate[0]["name"] = "Modified"
        self.assertEqual(self.scenario_list[0]["name"], "Alice")
        
    def test_equals(self):
        # Create two identical ScenarioLists
        sl1 = ScenarioList([Scenario({"name": "Alice"}), Scenario({"name": "Bob"})])
        sl2 = ScenarioList([Scenario({"name": "Alice"}), Scenario({"name": "Bob"})])
        
        # Test equality
        self.assertEqual(sl1, sl2)
        
        # Different order should still be equal
        sl3 = ScenarioList([Scenario({"name": "Bob"}), Scenario({"name": "Alice"})])
        self.assertEqual(sl1, sl3)
        
        # Different content should not be equal
        sl4 = ScenarioList([Scenario({"name": "Alice"}), Scenario({"name": "Charlie"})])
        self.assertNotEqual(sl1, sl4)
        
    def test_aggregate(self):
        # Create a ScenarioList with numeric data
        sl = ScenarioList([
            Scenario({"group": "A", "value": 10}),
            Scenario({"group": "A", "value": 20}),
            Scenario({"group": "B", "value": 30}),
            Scenario({"group": "B", "value": 40})
        ])
        
        # Aggregate by group
        aggregated = sl.aggregate("group", {"value": "mean"})
        
        self.assertEqual(len(aggregated), 2)
        
        # Check aggregated values
        group_a = [s for s in aggregated if s["group"] == "A"][0]
        group_b = [s for s in aggregated if s["group"] == "B"][0]
        
        self.assertEqual(group_a["value"], 15.0)  # Mean of 10 and 20
        self.assertEqual(group_b["value"], 35.0)  # Mean of 30 and 40
        
        # Test with multiple aggregations
        aggregated = sl.aggregate("group", {"value": ["mean", "sum", "min", "max"]})
        
        group_a = [s for s in aggregated if s["group"] == "A"][0]
        self.assertEqual(group_a["value_mean"], 15.0)
        self.assertEqual(group_a["value_sum"], 30)
        self.assertEqual(group_a["value_min"], 10)
        self.assertEqual(group_a["value_max"], 20)
        
    def test_codebook(self):
        # Create a ScenarioList with a codebook
        codebook = {
            "name": "Person's full name",
            "age": "Age in years"
        }
        
        sl = ScenarioList([self.s1, self.s2], codebook=codebook)
        
        # Check codebook is set
        self.assertEqual(sl.codebook, codebook)
        
        # Test to_dict with codebook
        result = sl.to_dict()
        self.assertIn("codebook", result)
        self.assertEqual(result["codebook"], codebook)
        
        # Test adding codebook after creation
        sl2 = ScenarioList([self.s1, self.s2])
        sl2.codebook = codebook
        self.assertEqual(sl2.codebook, codebook)
        
    def test_example(self):
        # Get an example ScenarioList
        example = ScenarioList.example()
        
        self.assertIsInstance(example, ScenarioList)
        self.assertGreater(len(example), 0)
        
        # Test with size parameter
        example = ScenarioList.example(size=5)
        self.assertEqual(len(example), 5)
        
        # Test with randomize
        example1 = ScenarioList.example(randomize=True)
        example2 = ScenarioList.example(randomize=True)
        self.assertNotEqual(example1[0], example2[0])  # Should be different due to randomization
        
    def test_select_random(self):
        # Select a random scenario
        random_scenario = self.scenario_list.select_random(seed=42)
        
        self.assertIsInstance(random_scenario, Scenario)
        self.assertIn(random_scenario, self.scenario_list)
        
        # Test reproducibility with seed
        s1 = self.scenario_list.select_random(seed=123)
        s2 = self.scenario_list.select_random(seed=123)
        self.assertEqual(s1, s2)
        
    def test_from_list(self):
        # Create from a list of values
        values = ["Alice", "Bob", "Charlie"]
        sl = ScenarioList.from_list("name", values)
        
        self.assertEqual(len(sl), 3)
        self.assertEqual(sl[0]["name"], "Alice")
        self.assertEqual(sl[1]["name"], "Bob")
        self.assertEqual(sl[2]["name"], "Charlie")
        
    def test_join(self):
        # Create two ScenarioLists to join
        people = ScenarioList([
            Scenario({"id": 1, "name": "Alice"}),
            Scenario({"id": 2, "name": "Bob"}),
            Scenario({"id": 3, "name": "Charlie"})
        ])
        
        departments = ScenarioList([
            Scenario({"id": 1, "department": "HR"}),
            Scenario({"id": 2, "department": "Engineering"}),
            Scenario({"id": 4, "department": "Marketing"})  # No match for id=4
        ])
        
        # Inner join
        inner_joined = people.join(departments, "id", "id", how="inner")
        
        self.assertEqual(len(inner_joined), 2)  # Only 2 matches (id 1 and 2)
        
        # Check joined data
        self.assertEqual(inner_joined[0]["name"], "Alice")
        self.assertEqual(inner_joined[0]["department"], "HR")
        self.assertEqual(inner_joined[1]["name"], "Bob")
        self.assertEqual(inner_joined[1]["department"], "Engineering")
        
        # Left join
        left_joined = people.join(departments, "id", "id", how="left")
        
        self.assertEqual(len(left_joined), 3)  # All people
        
        # Check joined data including null
        self.assertEqual(left_joined[2]["name"], "Charlie")
        self.assertEqual(left_joined[2]["department"], None)  # No match
        
        # Right join
        right_joined = people.join(departments, "id", "id", how="right")
        
        self.assertEqual(len(right_joined), 3)  # All departments
        
        # Check for the marketing department (id=4) which has no matching person
        marketing = [s for s in right_joined if s["department"] == "Marketing"][0]
        self.assertEqual(marketing["name"], None)
        
        # Outer join
        outer_joined = people.join(departments, "id", "id", how="outer")
        
        self.assertEqual(len(outer_joined), 4)  # All records from both sides
        
        # Check that includes Charlie (person with no dept) and Marketing (dept with no person)
        charlie = [s for s in outer_joined if s.get("name") == "Charlie"][0]
        self.assertEqual(charlie["department"], None)
        
        marketing = [s for s in outer_joined if s.get("department") == "Marketing"][0]
        self.assertEqual(marketing["name"], None)
        
    def test_describe(self):
        # Create a ScenarioList with numeric data
        sl = ScenarioList([
            Scenario({"value": 10}),
            Scenario({"value": 20}),
            Scenario({"value": 30}),
            Scenario({"value": 40}),
            Scenario({"value": 50})
        ])
        
        # Get descriptive statistics
        stats = sl.describe()
        
        # Check stats for the 'value' column
        self.assertEqual(stats["value"]["count"], 5)
        self.assertEqual(stats["value"]["mean"], 30.0)
        self.assertEqual(stats["value"]["min"], 10)
        self.assertEqual(stats["value"]["max"], 50)
        
        # Add a non-numeric column and check it's handled correctly
        sl.append(Scenario({"value": 60, "category": "A"}))
        stats = sl.describe()
        
        self.assertEqual(stats["value"]["count"], 6)
        self.assertEqual(stats["category"]["count"], 1)  # Only one non-null value
        self.assertEqual(stats["category"]["unique"], 1)  # Only one unique value
        
    def test_code(self):
        # Generate code to recreate the ScenarioList
        code = self.scenario_list.code()
        
        self.assertIsInstance(code, list)
        self.assertGreater(len(code), 0)
        self.assertTrue(any("from edsl.scenarios import ScenarioList" in line for line in code))
        self.assertTrue(any("from edsl.scenarios import Scenario" in line for line in code))
        
        # Test string version
        code_str = self.scenario_list.code(string=True)
        self.assertIsInstance(code_str, str)
        self.assertIn("from edsl.scenarios import ScenarioList", code_str)
        
    def test_summary(self):
        # Get a summary of the ScenarioList
        summary = self.scenario_list._summary()
        
        self.assertIsInstance(summary, dict)
        self.assertEqual(summary["scenarios"], 3)  # 3 scenarios in our list
        
    def test_transform(self):
        # Create a function to transform scenarios
        def add_greeting(scenario):
            new_scenario = scenario.duplicate()
            new_scenario["greeting"] = f"Hello, {scenario['name']}!"
            return new_scenario
        
        # Apply the transformation
        transformed = self.scenario_list.transform(add_greeting)
        
        self.assertEqual(len(transformed), 3)
        
        # Check the transformation was applied
        self.assertEqual(transformed[0]["greeting"], "Hello, Alice!")
        self.assertEqual(transformed[1]["greeting"], "Hello, Bob!")
        self.assertEqual(transformed[2]["greeting"], "Hello, Charlie!")
        
        # Original should be unchanged
        self.assertNotIn("greeting", self.scenario_list[0])
        
    def test_map(self):
        # Map the age field to a new calculated field
        mapped = self.scenario_list.map("age_in_months", lambda s: s["age"] * 12)
        
        self.assertEqual(len(mapped), 3)
        
        # Check mapping was applied
        self.assertEqual(mapped[0]["age_in_months"], 360)  # 30 * 12
        self.assertEqual(mapped[1]["age_in_months"], 300)  # 25 * 12
        self.assertEqual(mapped[2]["age_in_months"], 420)  # 35 * 12
        
        # Original fields should still be present
        self.assertEqual(mapped[0]["name"], "Alice")
        self.assertEqual(mapped[0]["age"], 30)
        
    def test_group_by(self):
        # Create data with groups
        sl = ScenarioList([
            Scenario({"department": "HR", "name": "Alice", "salary": 50000}),
            Scenario({"department": "HR", "name": "Bob", "salary": 55000}),
            Scenario({"department": "Engineering", "name": "Charlie", "salary": 70000}),
            Scenario({"department": "Engineering", "name": "David", "salary": 75000}),
            Scenario({"department": "Engineering", "name": "Eve", "salary": 80000})
        ])
        
        # Group by department
        grouped = sl.group_by("department")
        
        self.assertEqual(len(grouped), 2)  # Two departments
        
        # Check group contents
        hr_group = [g for g in grouped if g["department"] == "HR"][0]
        eng_group = [g for g in grouped if g["department"] == "Engineering"][0]
        
        self.assertEqual(len(hr_group["scenarios"]), 2)  # 2 people in HR
        self.assertEqual(len(eng_group["scenarios"]), 3)  # 3 people in Engineering
        
        # Check all scenarios in the groups
        hr_names = [s["name"] for s in hr_group["scenarios"]]
        self.assertIn("Alice", hr_names)
        self.assertIn("Bob", hr_names)
        
        eng_names = [s["name"] for s in eng_group["scenarios"]]
        self.assertIn("Charlie", eng_names)
        self.assertIn("David", eng_names)
        self.assertIn("Eve", eng_names)


if __name__ == "__main__":
    unittest.main()