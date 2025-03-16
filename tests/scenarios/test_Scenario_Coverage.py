import unittest
import os
import tempfile
import hashlib
from unittest.mock import patch, MagicMock
from edsl.scenarios import Scenario, ScenarioList, FileStore
from edsl.scenarios.exceptions import ScenarioError

class TestScenarioCoverage(unittest.TestCase):
    def setUp(self):
        self.example_scenario = Scenario({"price": 100, "quantity": 2})
        self.text_scenario = Scenario({"text": "This is a test.\nThis is another test.\nThis is a final test."})
        
    def test_initialization_error(self):
        # Test error when non-dict data can't be converted
        with self.assertRaises(ScenarioError):
            Scenario(123)  # Can't convert int to dict
    
    def test_multiply_with_scenario(self):
        s1 = Scenario({"a": 1})
        s2 = Scenario({"b": 2})
        result = s1 * s2
        
        self.assertIsInstance(result, ScenarioList)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0], Scenario({"a": 1, "b": 2}))
    
    def test_multiply_with_scenario_list(self):
        s1 = Scenario({"a": 1})
        sl = ScenarioList([Scenario({"b": 2}), Scenario({"b": 3})])
        
        result = s1 * sl
        
        self.assertIsInstance(result, ScenarioList)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0], Scenario({"a": 1, "b": 2}))
        self.assertEqual(result[1], Scenario({"a": 1, "b": 3}))
        
    def test_multiply_with_invalid_type(self):
        s = Scenario({"a": 1})
        with self.assertRaises(TypeError):
            s * "not a scenario or scenario list"
    
    def test_replicate(self):
        s = Scenario({"food": "wood chips"})
        result = s.replicate(3)
        
        self.assertIsInstance(result, ScenarioList)
        self.assertEqual(len(result), 3)
        for scenario in result:
            self.assertEqual(scenario, s)
            # Check they're different objects (deep copy)
            self.assertIsNot(scenario, s)
    
    def test_has_jinja_braces(self):
        # Scenario with jinja braces
        s1 = Scenario({"food": "I love {{wood chips}}"})
        self.assertTrue(s1.has_jinja_braces)
        
        # Scenario without jinja braces
        s2 = Scenario({"food": "I love wood chips"})
        self.assertFalse(s2.has_jinja_braces)
        
        # Scenario with non-string values
        s3 = Scenario({"price": 100})
        self.assertFalse(s3.has_jinja_braces)
    
    def test_convert_jinja_braces(self):
        s = Scenario({"food": "I love {{wood chips}}"})
        result = s._convert_jinja_braces()
        
        self.assertEqual(result["food"], "I love <<wood chips>>")
        
        # Test with custom replacements
        result = s._convert_jinja_braces("[[", "]]")
        self.assertEqual(result["food"], "I love [[wood chips]]")
        
        # Test with non-string values
        s2 = Scenario({"price": 100, "food": "{{test}}"})
        result = s2._convert_jinja_braces()
        self.assertEqual(result["price"], 100)
        self.assertEqual(result["food"], "<<test>>")
    
    def test_add_with_none(self):
        result = self.example_scenario + None
        self.assertEqual(result, self.example_scenario)
        self.assertIsNot(result, self.example_scenario)  # Should be a copy
    
    def test_rename_with_dict(self):
        s = Scenario({"food": "pizza", "drink": "water"})
        result = s.rename({"food": "meal", "drink": "beverage"})
        
        self.assertEqual(result["meal"], "pizza")
        self.assertEqual(result["beverage"], "water")
        self.assertNotIn("food", result)
        self.assertNotIn("drink", result)
    
    def test_rename_with_string_args(self):
        s = Scenario({"food": "pizza", "drink": "water"})
        result = s.rename("food", "meal")
        
        self.assertEqual(result["meal"], "pizza")
        self.assertEqual(result["drink"], "water")
        self.assertNotIn("food", result)
    
    def test_new_column_names(self):
        s = Scenario({"food": "pizza", "drink": "water"})
        result = s.new_column_names(["meal", "beverage"])
        
        self.assertEqual(result["meal"], "pizza")
        self.assertEqual(result["beverage"], "water")
        self.assertNotIn("food", result)
        self.assertNotIn("drink", result)
    
    def test_table(self):
        # Simple test to ensure table method doesn't raise an exception
        table = self.example_scenario.table(tablefmt="grid")
        self.assertIsInstance(table, str)
    
    def test_to_dict(self):
        result = self.example_scenario.to_dict()
        
        # Check the basic data
        self.assertEqual(result["price"], 100)
        self.assertEqual(result["quantity"], 2)
        
        # Check the EDSL version is added
        self.assertIn("edsl_version", result)
        self.assertIn("edsl_class_name", result)
        self.assertEqual(result["edsl_class_name"], "Scenario")
        
        # Test without EDSL version
        result = self.example_scenario.to_dict(add_edsl_version=False)
        self.assertNotIn("edsl_version", result)
        self.assertNotIn("edsl_class_name", result)
    
    def test_hash(self):
        s1 = Scenario({"food": "pizza"})
        s2 = Scenario({"food": "pizza"})
        s3 = Scenario({"food": "burger"})
        
        # Same content should have same hash
        self.assertEqual(hash(s1), hash(s2))
        
        # Different content should have different hash
        self.assertNotEqual(hash(s1), hash(s3))
    
    def test_to_dataset(self):
        dataset = self.example_scenario.to_dataset()
        
        # Check type
        self.assertEqual(dataset.__class__.__name__, "Dataset")
        
        # Convert to dataframe to check content
        df = dataset.to_pandas()
        self.assertEqual(list(df["key"]), ["price", "quantity"])
        self.assertEqual(list(df["value"]), [100, 2])
    
    def test_select(self):
        s = Scenario({"food": "pizza", "drink": "water", "price": 10})
        result = s.select(["food", "price"])
        
        self.assertEqual(len(result), 2)
        self.assertIn("food", result)
        self.assertIn("price", result)
        self.assertNotIn("drink", result)
        
        # Test with a set
        result = s.select({"food", "price"})
        self.assertEqual(len(result), 2)
        self.assertIn("food", result)
        self.assertIn("price", result)
        self.assertNotIn("drink", result)
    
    def test_drop(self):
        s = Scenario({"food": "pizza", "drink": "water", "price": 10})
        result = s.drop(["drink"])
        
        self.assertEqual(len(result), 2)
        self.assertIn("food", result)
        self.assertIn("price", result)
        self.assertNotIn("drink", result)
        
        # Test with a set
        result = s.drop({"drink", "price"})
        self.assertEqual(len(result), 1)
        self.assertIn("food", result)
        self.assertNotIn("drink", result)
        self.assertNotIn("price", result)
    
    def test_keep(self):
        s = Scenario({"food": "pizza", "drink": "water", "price": 10})
        result = s.keep(["food", "price"])
        
        self.assertEqual(len(result), 2)
        self.assertIn("food", result)
        self.assertIn("price", result)
        self.assertNotIn("drink", result)
    
    @patch('requests.Session.get')
    def test_from_html(self, mock_get):
        mock_response = MagicMock()
        mock_response.text = "<html><body><p>Test content</p></body></html>"
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        url = "http://example.com"
        s = Scenario.from_html(url)
        
        self.assertEqual(s["url"], url)
        self.assertEqual(s["html"], "<html><body><p>Test content</p></body></html>")
        self.assertIn("text", s)
        
        # Test with custom field name
        s = Scenario.from_html(url, field_name="content")
        self.assertEqual(s["url"], url)
        self.assertIn("content", s)
        self.assertNotIn("text", s)
    
    @patch('requests.Session.get')
    def test_fetch_html(self, mock_get):
        mock_response = MagicMock()
        mock_response.text = "<html><body><p>Test content</p></body></html>"
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        html = Scenario.fetch_html("http://example.com")
        self.assertEqual(html, "<html><body><p>Test content</p></body></html>")
        
        # Test error handling
        mock_get.side_effect = Exception("Connection error")
        html = Scenario.fetch_html("http://example.com")
        self.assertIsNone(html)
    
    def test_extract_text(self):
        html = "<html><body><p>Test content</p><script>alert('hidden');</script></body></html>"
        text = Scenario.extract_text(html)
        
        # Text should contain the paragraph content but not the script
        self.assertIn("Test content", text)
        self.assertNotIn("alert", text)
        self.assertNotIn("hidden", text)
        
        # Test with None input
        self.assertEqual(Scenario.extract_text(None), "")
        
        # Test with invalid HTML that would cause an exception
        with patch('bs4.BeautifulSoup', side_effect=Exception("Parsing error")):
            self.assertEqual(Scenario.extract_text("<broken>"), "")
    
    @patch('edsl.scenarios.scenario.convert_from_path')
    def test_from_pdf_to_image(self, mock_convert):
        # Setup mock images
        mock_image1 = MagicMock()
        mock_image2 = MagicMock()
        mock_convert.return_value = [mock_image1, mock_image2]
        
        # Create a temporary PDF file
        with tempfile.NamedTemporaryFile(suffix=".pdf") as temp_pdf:
            # Patch FileStore to avoid actual file operations
            with patch('edsl.scenarios.FileStore', return_value=MagicMock()):
                s = Scenario.from_pdf_to_image(temp_pdf.name)
                
                # Check that scenario contains expected fields
                self.assertIn("filepath", s)
                self.assertIn("page_0", s)
                self.assertIn("page_1", s)
                self.assertEqual(s["filepath"], temp_pdf.name)
                
                # Check with different format
                s = Scenario.from_pdf_to_image(temp_pdf.name, image_format="png")
                mock_image1.save.assert_called()
    
    @patch('edsl.scenarios.DocxScenario.DocxScenario')
    def test_from_docx(self, mock_docx):
        mock_instance = MagicMock()
        mock_instance.get_scenario_dict.return_value = {
            "file_path": "test.docx",
            "text": "This is a test document."
        }
        mock_docx.return_value = mock_instance
        
        s = Scenario.from_docx("test.docx")
        self.assertEqual(s["file_path"], "test.docx")
        self.assertEqual(s["text"], "This is a test document.")
    
    def test_chunk_by_words(self):
        s = Scenario({"text": "This is a test document with multiple words."})
        result = s.chunk("text", num_words=2)
        
        self.assertIsInstance(result, ScenarioList)
        self.assertEqual(len(result), 4)  # 8 words / 2 words per chunk = 4 chunks
        
        # Check first chunk
        self.assertEqual(result[0]["text"], "This is")
        self.assertEqual(result[0]["text_chunk"], 0)
        self.assertEqual(result[0]["text_word_count"], 2)
        
        # Include original
        result = s.chunk("text", num_words=2, include_original=True)
        self.assertIn("text_original", result[0])
        self.assertEqual(result[0]["text_original"], "This is a test document with multiple words.")
        
        # Hash original
        result = s.chunk("text", num_words=2, include_original=True, hash_original=True)
        self.assertIn("text_original", result[0])
        # The hash should be the same as what we'd compute for the original text
        original_hash = hashlib.md5("This is a test document with multiple words.".encode()).hexdigest()
        self.assertEqual(result[0]["text_original"], original_hash)
    
    def test_chunk_by_lines(self):
        s = Scenario({"text": "Line 1\nLine 2\nLine 3"})
        result = s.chunk("text", num_lines=1)
        
        self.assertIsInstance(result, ScenarioList)
        self.assertEqual(len(result), 3)
        
        # Check chunks
        self.assertEqual(result[0]["text"], "Line 1")
        self.assertEqual(result[1]["text"], "Line 2")
        self.assertEqual(result[2]["text"], "Line 3")
    
    def test_chunk_errors(self):
        s = Scenario({"text": "Test text"})
        
        # Neither num_words nor num_lines specified
        with self.assertRaises(ValueError):
            s.chunk("text")
            
        # Both num_words and num_lines specified
        with self.assertRaises(ValueError):
            s.chunk("text", num_words=2, num_lines=1)
            
        # Field doesn't exist
        with self.assertRaises(KeyError):
            s.chunk("nonexistent", num_words=2)
    
    def test_from_dict(self):
        # Basic dictionary
        d = {"food": "pizza", "price": 10}
        s = Scenario.from_dict(d)
        self.assertEqual(s["food"], "pizza")
        self.assertEqual(s["price"], 10)
        
        # Dictionary with FileStore-like dict
        with patch('edsl.scenarios.FileStore.from_dict', return_value="mock_filestore"):
            file_dict = {"path": "test.txt", "base64_string": "dGVzdA=="}
            d = {"document": file_dict}
            s = Scenario.from_dict(d)
            self.assertEqual(s["document"], "mock_filestore")
    
    def test_table_data(self):
        s = Scenario({"food": "pizza"})
        table_data, column_names = s._table()
        
        self.assertEqual(column_names, ["Attribute", "Value"])
        self.assertEqual(len(table_data), 2)  # data and name attributes
        
        # Check data attribute
        data_row = [row for row in table_data if row["Attribute"] == "data"][0]
        self.assertEqual(data_row["Value"], "{'food': 'pizza'}")
        
        # Check name attribute
        name_row = [row for row in table_data if row["Attribute"] == "name"][0]
        self.assertEqual(name_row["Value"], "None")
    
    def test_example(self):
        s = Scenario.example()
        self.assertIn("persona", s)
        self.assertIsInstance(s["persona"], str)
        
        # Test with randomization
        s_random = Scenario.example(randomize=True)
        self.assertIn("persona", s_random)
        self.assertNotEqual(s["persona"], s_random["persona"])
    
    def test_code(self):
        s = Scenario({"food": "pizza"})
        code = s.code()
        
        self.assertIsInstance(code, list)
        self.assertEqual(len(code), 2)
        self.assertEqual(code[0], "from edsl.scenario import Scenario")
        self.assertEqual(code[1], "s = Scenario({'food': 'pizza'})")
    
    def test_from_dict_with_filestore(self):
        # Create a test dictionary with a nested dict that looks like a FileStore
        test_dict = {
            "food": "pizza",
            "document": {
                "path": "test.txt",
                "base64_string": "dGVzdA=="
            }
        }
        
        # Mock FileStore.from_dict to return a recognizable value
        with patch('edsl.scenarios.FileStore.from_dict') as mock_from_dict:
            mock_from_dict.return_value = "FILESTORE_OBJECT"
            
            # Call the method under test
            result = Scenario.from_dict(test_dict)
            
            # Check that regular fields are copied correctly
            self.assertEqual(result["food"], "pizza")
            
            # Check that the FileStore-like dict was converted
            self.assertEqual(result["document"], "FILESTORE_OBJECT")
            mock_from_dict.assert_called_once_with(test_dict["document"])


if __name__ == "__main__":
    unittest.main()