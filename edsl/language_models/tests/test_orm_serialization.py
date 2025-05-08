"""
Tests for the LanguageModel ORM serialization and deserialization functionality.

This module tests the serialization and deserialization capabilities of the
LanguageModel ORM, focusing on different data types and edge cases.
"""

import unittest
import pickle
from datetime import datetime
import json

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from edsl.language_models.model import Model
from edsl.language_models.orm import (
    Base,
    SQLLanguageModel,
    SQLModelParameter,
    save_language_model,
    load_language_model
)


class TestLanguageModelOrmSerialization(unittest.TestCase):
    """Test the LanguageModel ORM serialization and deserialization capabilities."""

    def setUp(self):
        """Set up a new database for each test."""
        # Create a new in-memory SQLite database for each test
        self.engine = create_engine('sqlite:///:memory:')
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.session = self.Session()

    def tearDown(self):
        """Clean up resources after each test."""
        self.session.close()
        Base.metadata.drop_all(self.engine)

    def test_complex_data_serialization(self):
        """Test serialization and deserialization of complex data types."""
        # Create a test model with various complex data types
        complex_data = {
            "list_data": [1, 2, 3, 4, 5],
            "dict_data": {"key1": "value1", "key2": "value2"},
            "nested_data": {"a": [1, 2, {"b": "c"}]}
        }
        
        model = Model("test")
        model.parameters["complex_param"] = complex_data
        
        # Save the model
        model_orm = save_language_model(self.session, model)
        self.session.commit()
        
        # Find the complex parameter in the database
        complex_param = None
        for param in model_orm.parameters:
            if param.key == "complex_param":
                complex_param = param
                break
                
        self.assertIsNotNone(complex_param)
        self.assertTrue(complex_param.value_type.startswith("pickle:"))
        
        # Load the model
        loaded_model = load_language_model(self.session, model_orm.id)
        
        # Verify complex data was restored correctly
        self.assertEqual(loaded_model.parameters["complex_param"], complex_data)

    def test_none_value_serialization(self):
        """Test the serialization and deserialization of None values directly."""
        # Test direct serialization/deserialization of None
        value_type, serialized = SQLLanguageModel.serialize_value(None)
        self.assertEqual(value_type, "null")
        
        # Deserialize and check
        deserialized = SQLLanguageModel.deserialize_value(value_type, serialized)
        self.assertIsNone(deserialized)
        
        # Note: Parameters with None values might be filtered out during loading,
        # so we test the serialization/deserialization methods directly instead

    def test_boolean_serialization(self):
        """Test serialization and deserialization of boolean values."""
        # Create a model with boolean values
        # Set boolean values through parameters dictionary directly
        model = Model("test")
        model.parameters["true_param"] = True
        model.parameters["false_param"] = False
        
        # Save the model
        model_orm = save_language_model(self.session, model)
        self.session.commit()
        
        # Load the model
        loaded_model = load_language_model(self.session, model_orm.id)
        
        # Verify booleans were preserved correctly
        self.assertTrue(loaded_model.parameters["true_param"])
        self.assertFalse(loaded_model.parameters["false_param"])
        
    def test_numeric_serialization(self):
        """Test serialization and deserialization of numeric values."""
        # Create a model with numeric values
        model = Model("test")
        model.parameters["int_param"] = 42
        model.parameters["float_param"] = 3.14159
        model.parameters["zero_param"] = 0
        model.parameters["negative_param"] = -10
        
        # Save the model
        model_orm = save_language_model(self.session, model)
        self.session.commit()
        
        # Load the model
        loaded_model = load_language_model(self.session, model_orm.id)
        
        # Verify numeric values were preserved correctly
        self.assertEqual(loaded_model.parameters["int_param"], 42)
        self.assertEqual(loaded_model.parameters["float_param"], 3.14159)
        self.assertEqual(loaded_model.parameters["zero_param"], 0)
        self.assertEqual(loaded_model.parameters["negative_param"], -10)

    def test_large_string_serialization(self):
        """Test serialization and deserialization of large string values."""
        # Create a large string
        large_string = "x" * 10000
        
        # Create a model with the large string
        model = Model("test")
        model.parameters["large_string_param"] = large_string
        
        # Save the model
        model_orm = save_language_model(self.session, model)
        self.session.commit()
        
        # Load the model
        loaded_model = load_language_model(self.session, model_orm.id)
        
        # Verify large string was preserved correctly
        self.assertEqual(loaded_model.parameters["large_string_param"], large_string)
        self.assertEqual(len(loaded_model.parameters["large_string_param"]), 10000)

    def test_direct_value_serialization(self):
        """Test the SQLLanguageModel.serialize_value and deserialize_value methods directly."""
        test_values = [
            (None, 'null', 'null'),
            (True, 'bool', 'true'),
            (False, 'bool', 'false'),
            (42, 'int', '42'),
            (3.14, 'float', '3.14'),
            ("test string", 'str', 'test string'),
            ([1, 2, 3], f'pickle:list', pickle.dumps([1, 2, 3]).hex())
        ]
        
        for value, expected_type, expected_serialized in test_values:
            if isinstance(value, list):
                # Special case for pickled values
                value_type, serialized = SQLLanguageModel.serialize_value(value)
                self.assertTrue(value_type.startswith('pickle:'))
                
                # Deserialize and check
                deserialized = SQLLanguageModel.deserialize_value(value_type, serialized)
                self.assertEqual(deserialized, value)
            else:
                # For simple types
                value_type, serialized = SQLLanguageModel.serialize_value(value)
                self.assertEqual(value_type, expected_type)
                
                if value is not None:  # Skip None checks for serialized text
                    self.assertEqual(serialized, expected_serialized)
                
                # Deserialize and check
                deserialized = SQLLanguageModel.deserialize_value(value_type, serialized)
                self.assertEqual(deserialized, value)


if __name__ == '__main__':
    unittest.main()