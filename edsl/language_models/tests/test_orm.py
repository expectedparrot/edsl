"""
Tests for the LanguageModel ORM implementation.

This module tests the ORM functionality for persisting LanguageModel objects
to a database, including serialization, deserialization, and CRUD operations.
"""

import unittest
from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from edsl.language_models.model import Model
from edsl.language_models.orm import (
    Base,
    SQLLanguageModel,
    SQLModelParameter,
    save_language_model,
    load_language_model,
    update_language_model,
    delete_language_model,
    list_language_models,
    find_language_models_by_service,
    find_language_models_by_name
)


class TestLanguageModelOrm(unittest.TestCase):
    """Test the LanguageModel ORM implementation."""

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

    def test_save_and_load_model(self):
        """Test saving and loading a LanguageModel with different parameter types."""
        # Create a test LanguageModel with common parameters
        model = Model("test", temperature=0.7, canned_response="This is a test response")
        
        # Print model parameters for debugging
        print("Original model parameters:", model.parameters)
        
        # Save the model
        model_orm = save_language_model(self.session, model)
        self.session.commit()
        model_id = model_orm.id
        
        # Verify the model has an ORM ID
        self.assertTrue(hasattr(model, '_orm_id'))
        self.assertEqual(model._orm_id, model_id)
        
        # Print ORM parameters for debugging
        print("Parameters saved to ORM:")
        for param in model_orm.parameters:
            print(f"  {param.key}: {param.value_type} = {param.value_text}")

        # Load the model
        loaded_model = load_language_model(self.session, model_id)
        
        # Print loaded model parameters for debugging
        print("Loaded model parameters:", loaded_model.parameters)
        
        # Verify that model attributes were loaded correctly
        self.assertEqual(loaded_model.model, "test")
        self.assertEqual(loaded_model._inference_service_, "test")
        
        # Verify that parameters were loaded correctly
        self.assertEqual(loaded_model.parameters["temperature"], 0.7)
        self.assertEqual(loaded_model.parameters["canned_response"], "This is a test response")

    def test_remote_flag(self):
        """Test saving and loading a LanguageModel with remote flag."""
        # Create a test LanguageModel
        model = Model("test", temperature=0.7)
        model.remote = True
        
        # Save the model
        model_orm = save_language_model(self.session, model)
        self.session.commit()
        model_id = model_orm.id
        
        # Verify the remote flag was saved
        self.assertTrue(model_orm.remote)
        
        # Load the model
        loaded_model = load_language_model(self.session, model_id)
        
        # Verify the remote flag was loaded
        self.assertTrue(loaded_model.remote)

    def test_rate_limits(self):
        """Test saving and loading a LanguageModel with custom rate limits."""
        # Create a test LanguageModel
        model = Model("test", temperature=0.7)
        model.rpm = 50
        model.tpm = 500
        
        # Save the model
        model_orm = save_language_model(self.session, model)
        self.session.commit()
        model_id = model_orm.id
        
        # Verify the rate limits were saved
        self.assertEqual(model_orm.rpm, 50)
        self.assertEqual(model_orm.tpm, 500)
        
        # Load the model
        loaded_model = load_language_model(self.session, model_id)
        
        # Verify the rate limits were loaded
        self.assertEqual(loaded_model.rpm, 50)
        self.assertEqual(loaded_model.tpm, 500)

    def test_update_model(self):
        """Test updating an existing LanguageModel."""
        # Create and save an initial model
        model = Model("test", temperature=0.7)
        model_orm = save_language_model(self.session, model)
        self.session.commit()
        model_id = model_orm.id
        
        # Create a new model with updated parameters
        updated_model = Model("test", temperature=0.9, max_tokens=200, logprobs=True)
        updated_model._orm_id = model._orm_id
        
        # Print model parameters for debugging
        print("Original model parameters:", model.parameters)
        print("Updated model parameters:", updated_model.parameters)
        print("Updated model max_tokens:", getattr(updated_model, 'max_tokens', None))
        print("Updated model logprobs:", getattr(updated_model, 'logprobs', None))
        
        # Save the updated model
        update_success = update_language_model(self.session, model_id, updated_model)
        self.session.commit()
        
        # Verify update was successful
        self.assertTrue(update_success)
        
        # Load the model again
        loaded_model = load_language_model(self.session, model_id)
        
        # Print loaded model parameters for debugging
        print("Loaded model parameters:", loaded_model.parameters)
        print("Loaded model max_tokens:", getattr(loaded_model, 'max_tokens', None))
        print("Loaded model logprobs:", getattr(loaded_model, 'logprobs', None))
        
        # Verify the updates
        self.assertEqual(loaded_model.parameters["temperature"], 0.9)
        self.assertEqual(loaded_model.parameters["max_tokens"], 200)
        self.assertEqual(loaded_model.parameters["logprobs"], True)
        
        # Also check attributes are set correctly
        self.assertEqual(getattr(loaded_model, 'max_tokens', None), 200)
        self.assertEqual(getattr(loaded_model, 'logprobs', None), True)

    def test_delete_model(self):
        """Test deleting a LanguageModel."""
        # Create and save a model
        model = Model("test", temperature=0.7)
        model_orm = save_language_model(self.session, model)
        self.session.commit()
        model_id = model_orm.id
        
        # Delete the model
        success = delete_language_model(self.session, model_id)
        self.session.commit()
        
        # Verify deletion was successful
        self.assertTrue(success)
        self.assertIsNone(load_language_model(self.session, model_id))

    def test_list_models(self):
        """Test listing LanguageModels with pagination."""
        # Create and save multiple models
        for i in range(5):
            model = Model("test", temperature=0.5 + (i * 0.1))
            save_language_model(self.session, model)
            
        # Create models with different service
        for i in range(3):
            model = Model("gpt-4", service_name="openai", temperature=0.5 + (i * 0.1))
            save_language_model(self.session, model)
            
        self.session.commit()
        
        # List all models
        models = list_language_models(self.session)
        self.assertEqual(len(models), 8)
        
        # Test pagination
        models_page1 = list_language_models(self.session, limit=5, offset=0)
        models_page2 = list_language_models(self.session, limit=5, offset=5)
        self.assertEqual(len(models_page1), 5)
        self.assertEqual(len(models_page2), 3)

    def test_find_by_service(self):
        """Test finding models by service."""
        # Create and save models with different services
        model1 = Model("test", temperature=0.7)
        model2 = Model("claude-3-opus-20240229", service_name="anthropic", temperature=0.7)
        model3 = Model("gpt-4", service_name="openai", temperature=0.7)
        
        save_language_model(self.session, model1)
        save_language_model(self.session, model2)
        save_language_model(self.session, model3)
        self.session.commit()
        
        # Find models by service
        test_models = find_language_models_by_service(self.session, "test")
        anthropic_models = find_language_models_by_service(self.session, "anthropic")
        openai_models = find_language_models_by_service(self.session, "openai")
        
        self.assertEqual(len(test_models), 1)
        self.assertEqual(len(anthropic_models), 1)
        self.assertEqual(len(openai_models), 1)
        
        self.assertEqual(test_models[0].model_name, "test")
        self.assertEqual(anthropic_models[0].model_name, "claude-3-opus-20240229")
        self.assertEqual(openai_models[0].model_name, "gpt-4")

    def test_find_by_name(self):
        """Test finding models by name."""
        # Create and save models with different names but same service
        model1 = Model("test", temperature=0.7)
        model2 = Model("test", temperature=0.9, max_tokens=100)
        
        save_language_model(self.session, model1)
        save_language_model(self.session, model2)
        self.session.commit()
        
        # Find models by name
        test_models = find_language_models_by_name(self.session, "test")
        
        # Should find both models with name "test"
        self.assertEqual(len(test_models), 2)
        self.assertEqual(test_models[0].model_name, "test")
        self.assertEqual(test_models[1].model_name, "test")


if __name__ == '__main__':
    unittest.main()