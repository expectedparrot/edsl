import unittest
from edsl.scenarios import Scenario, ScenarioList
from edsl.scenarios.exceptions import ScenarioError

class TestScenarioBasic(unittest.TestCase):
    def setUp(self):
        self.example_scenario = Scenario({"price": 100, "quantity": 2})
        
    def test_initialization(self):
        # Test that initialization works with dictionary
        s = Scenario({"key": "value"})
        self.assertEqual(s["key"], "value")
        
        # Test initialization with name
        s = Scenario({"key": "value"}, name="test")
        self.assertEqual(s.name, "test")
        
    def test_replicate(self):
        # Test replicating a scenario
        s = Scenario({"food": "pizza"})
        result = s.replicate(3)
        
        self.assertIsInstance(result, ScenarioList)
        self.assertEqual(len(result), 3)
        for item in result:
            self.assertEqual(item["food"], "pizza")
        
    def test_has_jinja_braces(self):
        # Test with jinja braces
        s1 = Scenario({"text": "Hello {{name}}"})
        self.assertTrue(s1.has_jinja_braces)
        
        # Test without jinja braces
        s2 = Scenario({"text": "Hello name"})
        self.assertFalse(s2.has_jinja_braces)
        
    def test_convert_jinja_braces(self):
        # Test converting jinja braces
        s = Scenario({"text": "Hello {{name}}"})
        result = s._convert_jinja_braces()
        self.assertEqual(result["text"], "Hello <<name>>")
        
        # Test with custom replacements
        result = s._convert_jinja_braces("[[", "]]")
        self.assertEqual(result["text"], "Hello [[name]]")
        
    def test_add(self):
        # Test adding scenarios
        s1 = Scenario({"a": 1})
        s2 = Scenario({"b": 2})
        result = s1 + s2
        
        self.assertEqual(result["a"], 1)
        self.assertEqual(result["b"], 2)
        
    def test_select(self):
        # Test selecting fields
        s = Scenario({"a": 1, "b": 2, "c": 3})
        result = s.select(["a", "c"])
        
        self.assertIn("a", result)
        self.assertIn("c", result)
        self.assertNotIn("b", result)
        
        # Single field
        result = s.select("a")
        self.assertIn("a", result)
        self.assertNotIn("b", result)
        self.assertNotIn("c", result)
        
    def test_drop(self):
        # Test dropping fields
        s = Scenario({"a": 1, "b": 2, "c": 3})
        result = s.drop(["a", "c"])
        
        self.assertNotIn("a", result)
        self.assertNotIn("c", result)
        self.assertIn("b", result)
        
    def test_keep(self):
        # Test keeping fields (alias for select)
        s = Scenario({"a": 1, "b": 2, "c": 3})
        result = s.keep(["a", "c"])
        
        self.assertIn("a", result)
        self.assertIn("c", result)
        self.assertNotIn("b", result)
        
    def test_rename(self):
        # Test renaming fields with dict
        s = Scenario({"a": 1, "b": 2})
        result = s.rename({"a": "x", "b": "y"})
        
        self.assertIn("x", result)
        self.assertIn("y", result)
        self.assertNotIn("a", result)
        self.assertNotIn("b", result)
        
        # Test renaming with string args
        s = Scenario({"a": 1, "b": 2})
        result = s.rename("a", "x")
        
        self.assertIn("x", result)
        self.assertIn("b", result)
        self.assertNotIn("a", result)
        
    def test_hash(self):
        # Test hashing
        s1 = Scenario({"a": 1})
        s2 = Scenario({"a": 1})
        s3 = Scenario({"a": 2})
        
        self.assertEqual(hash(s1), hash(s2))
        self.assertNotEqual(hash(s1), hash(s3))
        
    def test_multiply(self):
        # Test multiplication with Scenario
        s1 = Scenario({"a": 1})
        s2 = Scenario({"b": 2})
        result = s1 * s2
        
        self.assertIsInstance(result, ScenarioList)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["a"], 1)
        self.assertEqual(result[0]["b"], 2)
        
        # Test multiplication with ScenarioList
        sl = ScenarioList([Scenario({"b": 2}), Scenario({"b": 3})])
        result = s1 * sl
        
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["a"], 1)
        self.assertEqual(result[0]["b"], 2)
        self.assertEqual(result[1]["a"], 1)
        self.assertEqual(result[1]["b"], 3)
        
    def test_to_dict(self):
        # Test conversion to dict
        s = Scenario({"a": 1})
        result = s.to_dict()
        
        self.assertIn("a", result)
        self.assertEqual(result["a"], 1)
        self.assertIn("edsl_version", result)
        self.assertIn("edsl_class_name", result)
        
        # Test without version info
        result = s.to_dict(add_edsl_version=False)
        self.assertIn("a", result)
        self.assertNotIn("edsl_version", result)
        self.assertNotIn("edsl_class_name", result)
        
    def test_from_dict(self):
        # Test creation from dict
        d = {"a": 1, "b": 2}
        s = Scenario.from_dict(d)
        
        self.assertEqual(s["a"], 1)
        self.assertEqual(s["b"], 2)
        
    def test_example(self):
        # Test example method
        s = Scenario.example()
        
        self.assertIsInstance(s, Scenario)
        self.assertIn("persona", s)
        
        # Test randomize
        s1 = Scenario.example(randomize=True)
        s2 = Scenario.example(randomize=True)
        self.assertNotEqual(s1["persona"], s2["persona"])
        
    def test_code(self):
        # Test code generation
        s = Scenario({"a": 1})
        code = s.code()
        
        self.assertIsInstance(code, list)
        self.assertEqual(len(code), 2)
        self.assertIn("from edsl.scenario import Scenario", code[0])
        

if __name__ == "__main__":
    unittest.main()