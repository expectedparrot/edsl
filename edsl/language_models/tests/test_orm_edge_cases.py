"""
Tests for the LanguageModel ORM edge cases and error handling.

This module tests edge cases and error handling in the LanguageModel ORM
implementation, ensuring robustness in unusual situations.
"""

import unittest
import pickle
from datetime import datetime

from sqlalchemy import create_engine, Table, Column, Integer, String
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import IntegrityError

from edsl.language_models.model import Model
from edsl.language_models.language_model import LanguageModel
from edsl.language_models.orm import (
    Base,
    SQLLanguageModel,
    SQLModelParameter,
    save_language_model,
    load_language_model,
    update_language_model,
    delete_language_model,
    LanguageModelOrmException
)


class TestLanguageModelOrmEdgeCases(unittest.TestCase):
    """Test edge cases and error handling in the LanguageModel ORM."""

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

    def test_nonexistent_model_id(self):
        """Test loading a model with a nonexistent ID."""
        # Try to load a model with a nonexistent ID
        model = load_language_model(self.session, 999)
        self.assertIsNone(model)

    def test_delete_nonexistent_model(self):
        """Test deleting a model with a nonexistent ID."""
        # Try to delete a model with a nonexistent ID
        result = delete_language_model(self.session, 999)
        self.assertFalse(result)

    def test_update_nonexistent_model(self):
        """Test updating a model with a nonexistent ID."""
        # Create a model
        model = Model("test", temperature=0.7)
        
        # Try to update a model with a nonexistent ID
        result = update_language_model(self.session, 999, model)
        self.assertFalse(result)
        
    def test_load_after_schema_change(self):
        """Test loading a model after schema changes (adding models with different parameter sets)."""
        # Create and save a model with one set of parameters
        model1 = Model("test")
        model1.parameters["temperature"] = 0.7
        model_orm1 = save_language_model(self.session, model1)
        self.session.commit()
        model_id1 = model_orm1.id
        
        # Create and save a model with a completely different set of parameters
        model2 = Model("test")
        model2.parameters["max_tokens"] = 100
        model2.parameters["top_p"] = 0.9
        model2.parameters["frequency_penalty"] = 0.5
        model_orm2 = save_language_model(self.session, model2)
        self.session.commit()
        model_id2 = model_orm2.id
        
        # Load both models
        loaded_model1 = load_language_model(self.session, model_id1)
        loaded_model2 = load_language_model(self.session, model_id2)
        
        # Verify each model has its specific parameters 
        self.assertEqual(loaded_model1.parameters.get("temperature"), 0.7)
        self.assertNotIn("max_tokens", loaded_model1.parameters)
        self.assertNotIn("top_p", loaded_model1.parameters)
        self.assertNotIn("frequency_penalty", loaded_model1.parameters)
        
        self.assertEqual(loaded_model2.parameters.get("max_tokens"), 100)
        self.assertEqual(loaded_model2.parameters.get("top_p"), 0.9)
        self.assertEqual(loaded_model2.parameters.get("frequency_penalty"), 0.5)
        # Note: The Model class may initialize a default temperature so we skip checking that

    def test_orm_id_preservation(self):
        """Test that _orm_id is preserved and updated correctly."""
        # Create and save a model
        model = Model("test", temperature=0.7)
        model_orm = save_language_model(self.session, model)
        self.session.commit()
        model_id = model_orm.id
        
        # Verify _orm_id is set on the original model
        self.assertEqual(model._orm_id, model_id)
        
        # Load the model
        loaded_model = load_language_model(self.session, model_id)
        
        # Verify _orm_id is preserved
        self.assertEqual(loaded_model._orm_id, model_id)
        
        # Update the model
        loaded_model.parameters["temperature"] = 0.9
        update_language_model(self.session, model_id, loaded_model)
        self.session.commit()
        
        # Load again
        reloaded_model = load_language_model(self.session, model_id)
        
        # Verify _orm_id is still preserved
        self.assertEqual(reloaded_model._orm_id, model_id)
        self.assertEqual(reloaded_model.parameters["temperature"], 0.9)
    
    def test_corrupt_serialized_value(self):
        """Test handling of corrupt serialized values."""
        # Manually create a model and parameter with invalid serialized data
        model_orm = SQLLanguageModel(
            model_name="test",
            inference_service="test"
        )
        self.session.add(model_orm)
        self.session.flush()
        
        # Create parameter with invalid pickle data
        corrupt_param = SQLModelParameter(
            model_id=model_orm.id,
            key="corrupt_data",
            value_type="pickle:dict",
            value_text="not_valid_hex_data"  # This is not valid hex-encoded pickle data
        )
        self.session.add(corrupt_param)
        self.session.commit()
        
        # Load the model - should handle corruption gracefully
        loaded_model = load_language_model(self.session, model_orm.id)
        
        # The corrupt parameter should be skipped and not included in parameters
        self.assertNotIn("corrupt_data", loaded_model.parameters)

    def test_very_large_number_of_parameters(self):
        """Test handling models with a very large number of parameters."""
        # Create a model with 100 custom parameters
        model = Model("test")
        starting_param_count = len(model.parameters)
        for i in range(100):
            model.parameters[f"param{i}"] = i
        
        # Save the model
        model_orm = save_language_model(self.session, model)
        self.session.commit()
        
        # Verify parameters were saved (plus any default ones)
        expected_param_count = 100 + starting_param_count
        self.assertEqual(len(model_orm.parameters), expected_param_count)
        
        # Load the model
        loaded_model = load_language_model(self.session, model_orm.id)
        
        # Verify all parameters were loaded
        self.assertEqual(len(loaded_model.parameters), expected_param_count)
        
        # Check all our custom parameters are there
        for i in range(100):
            self.assertEqual(loaded_model.parameters[f"param{i}"], i)
            
    def test_save_duplicate_model(self):
        """Test saving a model multiple times."""
        # Create and save a model
        model = Model("test", temperature=0.7)
        model_orm1 = save_language_model(self.session, model)
        self.session.commit()
        model_id1 = model_orm1.id
        
        # Save the same model again (should be treated as update)
        model_orm2 = save_language_model(self.session, model)
        self.session.commit()
        model_id2 = model_orm2.id
        
        # IDs should be the same since it's an update
        self.assertEqual(model_id1, model_id2)
        
        # Verify there's only one model in the database
        models = self.session.query(SQLLanguageModel).all()
        self.assertEqual(len(models), 1)


if __name__ == '__main__':
    unittest.main()