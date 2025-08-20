import pytest
from unittest.mock import Mock, MagicMock, patch, PropertyMock
from typing import Dict, List, Any, Optional

from edsl.language_models.model import Model
from edsl.language_models.exceptions import LanguageModelValueError
#from edsl.inference_services.inference_service_registry import InferenceServiceRegistry
from edsl.inference_services.inference_service_abc import InferenceServiceABC
from edsl.inference_services import InferenceServiceError


class MockInferenceService(InferenceServiceABC):
    """Mock inference service for testing."""
    
    key_sequence = ["test_key"]
    usage_sequence = ["test_usage"]
    input_token_name = "input_tokens"
    output_token_name = "output_tokens"
    _inference_service_ = "mock_service"
    
    @classmethod
    def get_model_info(cls) -> List[Any]:
        return [{"id": "mock_model_1"}, {"id": "mock_model_2"}]
    
    def create_model(self, model_name: str, *args, **kwargs):
        from edsl.language_models import LanguageModel
        return LanguageModel.example(test_model=True, model=model_name, *args, **kwargs)


from edsl.language_models import LanguageModel

class MockLanguageModel(LanguageModel):
    """Mock language model instance that inherits from LanguageModel."""
    
    def __init__(self, model_name: str = "test_model", *args, **kwargs):
        # Initialize with minimal required attributes without calling super().__init__
        self.model = model_name
        self.parameters = kwargs
        self._inference_service_ = "test_service"
        # Add attributes that LanguageModel expects
        self.model_info = None
        self.tpm = kwargs.get('tpm', 1000000)
        self.rpm = kwargs.get('rpm', 1000)
        self._tpm = self.tpm  # Set private attribute to avoid property lookup
        self._rpm = self.rpm  # Set private attribute to avoid property lookup
    
    async def async_execute_model_call(self, *args, **kwargs):
        """Stub implementation of abstract method."""
        return {"message": [{"text": "mock response"}]}


class TestModel:
    
    @pytest.fixture
    def mock_registry(self):
        """Create a mock registry with test data."""
        registry = Mock()  # Removed spec to allow any attributes
        
        # Mock model mappings
        registry.model_to_services = {
            "gpt-4": ["openai"],
            "gpt-3.5-turbo": ["openai"],
            "claude-3-opus": ["anthropic"],
            "claude-3-sonnet": ["anthropic"],
            "gemini-pro": ["google"],
            "test_model": ["test_service"]
        }
        
        registry.service_to_models = {
            "openai": ["gpt-4", "gpt-3.5-turbo"],
            "anthropic": ["claude-3-opus", "claude-3-sonnet"],
            "google": ["gemini-pro"],
            "test_service": ["test_model"]
        }
        
        # Mock methods
        registry.list_registered_services.return_value = ["openai", "anthropic", "google", "test_service"]
        registry.get_all_model_names.return_value = ["gpt-4", "gpt-3.5-turbo", "claude-3-opus", "claude-3-sonnet", "gemini-pro", "test_model"]
        registry.get_models_for_service.side_effect = lambda service: registry.service_to_models.get(service, [])
        registry.get_service_for_model.side_effect = lambda model: registry.model_to_services.get(model, [None])[0]
        registry.find_models.side_effect = lambda pattern: [m for m in registry.get_all_model_names() if pattern.replace("*", "") in m]
        registry.refresh_model_info.return_value = None
        # Removed mocks for methods that don't exist - they were eliminated from Model class
        
        # Mock create_language_model to return a mock model factory
        def mock_create_language_model(model_name, service_name=None, *args, **kwargs):
            def model_factory(*factory_args, **factory_kwargs):
                return MockLanguageModel(model_name, **factory_kwargs)
            return model_factory
        
        registry.create_language_model.side_effect = mock_create_language_model
        
        return registry
    
    @pytest.fixture
    def setup_mock_registry(self, mock_registry):
        """Set up the Model class with a mock registry with robust cleanup."""
        # Store the original registry and any cached import references
        original_registry = Model._inference_service_registry
        
        try:
            # Set our mock registry
            Model._inference_service_registry = mock_registry
            yield mock_registry
        finally:
            # Force complete restoration
            Model._inference_service_registry = original_registry
            
            # If the original was None, force a fresh import next time it's accessed
            if original_registry is None:
                Model._inference_service_registry = None
    
    def test_get_inference_service_registry_lazy_import(self):
        """Test that registry is lazily imported when None."""
        with patch.object(Model, '_inference_service_registry', None):
            with patch('edsl.inference_services.inference_service_registry.InferenceServiceRegistry') as mock_registry_class:
                mock_instance = Mock()
                mock_registry_class.return_value = mock_instance
                
                registry = Model.get_inference_service_registry()
                assert registry == mock_instance
                mock_registry_class.assert_called_once()
    
    def test_get_inference_service_registry_existing(self, mock_registry):
        """Test that existing registry is returned."""
        with patch.object(Model, '_inference_service_registry', mock_registry):
            registry = Model.get_inference_service_registry()
            assert registry == mock_registry
    
    def test_set_inference_service_registry(self, mock_registry):
        """Test setting a new inference service registry."""
        original_registry = Model._inference_service_registry
        try:
            Model.set_inference_service_registry(mock_registry)
            assert Model._inference_service_registry == mock_registry
        finally:
            Model._inference_service_registry = original_registry
    
    def test_new_with_model_name(self, setup_mock_registry):
        """Test creating a model with explicit model name."""
        model = Model("gpt-4", temperature=0.7)
        
        assert model.model == "gpt-4"
        assert model.parameters.get("temperature") == 0.7
    
    def test_new_with_service_name(self, setup_mock_registry):
        """Test creating a model with explicit service name."""
        model = Model("test_model", service_name="test_service", temperature=0.5)
        
        assert model.model == "test_model"
        assert model.parameters.get("temperature") == 0.5
    
    def test_new_default_model(self, setup_mock_registry):
        """Test creating a model with default model name."""
        with patch.object(Model, 'default_model', 'gpt-4'):
            model = Model(temperature=0.3)
            
            assert model.model == "gpt-4"
            assert model.parameters.get("temperature") == 0.3
    
    def test_new_with_args_and_kwargs(self, setup_mock_registry):
        """Test creating a model with additional arguments."""
        model = Model("gpt-4", temperature=0.8, max_tokens=100)
        
        assert model.model == "gpt-4"
        assert model.parameters.get("temperature") == 0.8
        assert model.parameters.get("max_tokens") == 100
    
    # Error handling methods have been removed from Model class
    
    def test_services(self, setup_mock_registry):
        """Test getting available services."""
        result = Model.services()
        
        # Should exclude 'test' service and sort alphabetically
        expected_services = sorted(["openai", "anthropic", "google", "test_service"])
        
        # Check that result is a ScenarioList
        from edsl.scenarios import ScenarioList
        assert isinstance(result, ScenarioList)
        
        # Check that it contains the expected services
        service_names = [scenario["service"] for scenario in result]
        assert service_names == expected_services
    
    def test_services_with_local_keys(self, setup_mock_registry):
        """Test getting services with local keys."""
        with patch.object(Model, 'key_info') as mock_key_info:
            mock_dataset = Mock()
            mock_dataset.select.return_value.to_list.return_value = ["openai", "anthropic"]
            mock_key_info.return_value = mock_dataset
            
            result = Model.services_with_local_keys()
            
            assert result == {"openai", "anthropic"}
            mock_key_info.assert_called_once()
    
    def test_key_info(self, setup_mock_registry):
        """Test getting key information."""
        with patch('edsl.key_management.KeyLookupCollection') as mock_klc_class:
            # Mock KeyLookupCollection
            mock_klc = Mock()
            mock_entry = Mock()
            mock_entry.to_dict.return_value = {"api_token": "test_key_12345678"}
            mock_klc.data = {0: {"openai": mock_entry}}
            mock_klc_class.return_value = mock_klc
            
            result = Model.key_info(obscure_api_key=True)
            
            # Check that result is a Dataset (from to_dataset() call)
            # We use real ScenarioList which will create real Scenario objects
            mock_klc.add_key_lookup.assert_called_once_with(fetch_order=None)
    
    def test_search_models_model_list_format(self, setup_mock_registry):
        """Test searching models with model_list output format."""
        result = Model.search_models("gpt*")
        
        # Check that result is a ModelList
        from edsl.language_models.model_list import ModelList
        assert isinstance(result, ModelList)
        
        setup_mock_registry.find_models.assert_called_once_with("gpt*")
    
    def test_search_models_scenario_list_format(self, setup_mock_registry):
        """Test searching models with scenario_list output format."""
        result = Model.search_models("claude*", output_format="scenario_list")
        
        # Check that result is a ScenarioList
        from edsl.scenarios import ScenarioList
        assert isinstance(result, ScenarioList)
        
        setup_mock_registry.find_models.assert_called_once_with("claude*")
    
    def test_search_models_invalid_format(self, setup_mock_registry):
        """Test search_models with invalid output format."""
        with pytest.raises(ValueError) as exc_info:
            Model.search_models("test", output_format="invalid")
        
        assert "Invalid output_format: invalid" in str(exc_info.value)
    
    def test_search_models_no_matches(self, setup_mock_registry):
        """Test searching models with no matches."""
        setup_mock_registry.find_models.return_value = []
        
        # Test ModelList format
        result = Model.search_models("nonexistent*")
        from edsl.language_models.model_list import ModelList
        assert isinstance(result, ModelList)
        assert len(result) == 0
        
        # Test ScenarioList format
        result = Model.search_models("nonexistent*", output_format="scenario_list")
        from edsl.scenarios import ScenarioList
        assert isinstance(result, ScenarioList)
        assert len(result) == 0
    
    # test_all_known_models removed - method was eliminated as redundant with available()
    
    def test_available_with_local_keys(self, setup_mock_registry):
        """Test getting available models with local keys."""
        with patch.object(Model, 'key_info') as mock_key_info:
            # Mock key_info to return services with local keys
            mock_dataset = Mock()
            mock_dataset.select.return_value.to_list.return_value = ["openai", "anthropic"]
            mock_key_info.return_value = mock_dataset
            
            # Test with real ScenarioList and ModelList
            result = Model.available_with_local_keys()
            
            # Check that result is a ModelList
            from edsl.language_models.model_list import ModelList
            assert isinstance(result, ModelList)
            
            # Should only contain models from services with local keys (openai, anthropic)
            # The exact models depend on what our mock registry returns for these services
    
    def test_available_default(self, setup_mock_registry):
        """Test getting available models with default parameters."""
        result = Model.available()
        
        # Check that result is a ModelList
        from edsl.language_models.model_list import ModelList
        assert isinstance(result, ModelList)
        
        setup_mock_registry.get_all_model_names.assert_called_once()
    
    def test_available_with_service_name(self, setup_mock_registry):
        """Test getting available models for specific service."""
        result = Model.available(service_name="openai", output_format="scenario_list")
        
        # Check that result is a ScenarioList
        from edsl.scenarios import ScenarioList
        assert isinstance(result, ScenarioList)
        
        setup_mock_registry.get_models_for_service.assert_called_once_with("openai")
    
    def test_available_with_search_term(self, setup_mock_registry):
        """Test getting available models with search term."""
        result = Model.available(search_term="gpt", output_format="scenario_list")
        
        # Check that result is a ScenarioList
        from edsl.scenarios import ScenarioList
        assert isinstance(result, ScenarioList)
        
        setup_mock_registry.find_models.assert_called_once_with("*gpt*")
    
    def test_available_with_service_and_search(self, setup_mock_registry):
        """Test getting available models with both service name and search term."""
        result = Model.available(service_name="openai", search_term="gpt", output_format="scenario_list")
        
        # Check that result is a ScenarioList
        from edsl.scenarios import ScenarioList
        assert isinstance(result, ScenarioList)
        
        setup_mock_registry.get_models_for_service.assert_called_once_with("openai")
    
    def test_available_with_force_refresh(self, setup_mock_registry):
        """Test getting available models with force refresh."""
        result = Model.available(force_refresh=True, output_format="scenario_list")
        
        # Check that result is a ScenarioList
        from edsl.scenarios import ScenarioList
        assert isinstance(result, ScenarioList)
        
        setup_mock_registry.refresh_model_info.assert_called_once()
    
    def test_available_with_local_only(self, setup_mock_registry):
        """Test getting available models with local_only filter."""
        with patch.object(Model, 'services_with_local_keys') as mock_local_services:
            mock_local_services.return_value = {"openai", "anthropic"}
            
            result = Model.available(local_only=True, output_format="scenario_list")
            
            # Check that result is a ScenarioList
            from edsl.scenarios import ScenarioList
            assert isinstance(result, ScenarioList)
    
    def test_available_invalid_service(self, setup_mock_registry):
        """Test getting available models with invalid service name."""
        with pytest.raises(LanguageModelValueError) as exc_info:
            Model.available(service_name="nonexistent_service")
        
        assert "Service nonexistent_service not found" in str(exc_info.value)
    
    def test_available_invalid_output_format(self, setup_mock_registry):
        """Test getting available models with invalid output format."""
        with pytest.raises(ValueError) as exc_info:
            Model.available(output_format="invalid")
        
        assert "Invalid output_format: invalid" in str(exc_info.value)
    
    def test_check_working_models(self, setup_mock_registry):
        """Test checking working models from Coop."""
        mock_working_models = [
            {
                "service": "openai",
                "model": "gpt-4",
                "works_with_text": True,
                "works_with_images": True,
                "usd_per_1M_input_tokens": 30.0,
                "usd_per_1M_output_tokens": 60.0
            },
            {
                "service": "anthropic",
                "model": "claude-3-opus",
                "works_with_text": True,
                "works_with_images": False,
                "usd_per_1M_input_tokens": 15.0,
                "usd_per_1M_output_tokens": 75.0
            }
        ]
        
        with patch('edsl.coop.Coop') as mock_coop_class:
            mock_coop = Mock()
            mock_coop.fetch_working_models.return_value = mock_working_models
            mock_coop_class.return_value = mock_coop
            
            result = Model.check_working_models()
            
            # Check that result is a ModelList
            from edsl.language_models.model_list import ModelList
            assert isinstance(result, ModelList)
            
            mock_coop.fetch_working_models.assert_called_once()
    
    def test_check_working_models_filtered(self, setup_mock_registry):
        """Test checking working models with filters."""
        mock_working_models = [
            {
                "service": "openai",
                "model": "gpt-4",
                "works_with_text": True,
                "works_with_images": True,
                "usd_per_1M_input_tokens": 30.0,
                "usd_per_1M_output_tokens": 60.0
            }
        ]
        
        with patch('edsl.coop.Coop') as mock_coop_class:
            mock_coop = Mock()
            mock_coop.fetch_working_models.return_value = mock_working_models
            mock_coop_class.return_value = mock_coop
            
            # Test service filter
            result = Model.check_working_models(service="openai")
            mock_coop.fetch_working_models.assert_called()
    
    def test_check_working_models_no_results(self, setup_mock_registry):
        """Test checking working models with no results."""
        with patch('edsl.coop.Coop') as mock_coop_class:
            mock_coop = Mock()
            mock_coop.fetch_working_models.return_value = []
            mock_coop_class.return_value = mock_coop
            
            result = Model.check_working_models()
            from edsl.language_models.model_list import ModelList
            assert isinstance(result, ModelList)
            assert len(result) == 0
            
            result = Model.check_working_models(output_format="scenario_list")
            from edsl.scenarios import ScenarioList
            assert isinstance(result, ScenarioList)
            assert len(result) == 0
    
    def test_example_default(self, setup_mock_registry):
        """Test creating an example model with default parameters."""
        with patch.object(Model, 'default_model', 'gpt-4'):
            model = Model.example()
            
            assert model.model == "gpt-4"
            assert model.parameters.get("temperature") == 0.5
    
    def test_example_randomized(self, setup_mock_registry):
        """Test creating an example model with randomized temperature."""
        with patch.object(Model, 'default_model', 'gpt-4'):
            with patch('edsl.language_models.model.random') as mock_random:
                mock_random.return_value = 0.73
                
                model = Model.example(randomize=True)
                
                assert model.model == "gpt-4"
                assert model.parameters.get("temperature") == 0.73
    
    def test_meta_repr(self):
        """Test the metaclass __repr__ method."""
        repr_str = repr(Model)
        
        assert "To create an instance, you can do:" in repr_str
        assert "Model.available()" in repr_str
        assert "Model.available(service='openai')" in repr_str
    
    def test_default_model_from_config(self):
        """Test that default model comes from CONFIG."""
        # The default_model should be set from CONFIG
        assert hasattr(Model, 'default_model')
    
    def test_new_with_exception_handling(self, setup_mock_registry):
        """Test that exceptions during model creation are propagated."""
        def failing_factory(*args, **kwargs):
            raise ValueError("Factory failed")
        
        # Override the side_effect to return the failing factory for this test
        setup_mock_registry.create_language_model.side_effect = lambda model_name, service_name=None, *args, **kwargs: failing_factory
        
        with pytest.raises(ValueError) as exc_info:
            Model("failing_model")
        
        assert "Factory failed" in str(exc_info.value)
    
    def test_class_level_registry_storage(self):
        """Test that the registry is stored at the class level."""
        original_registry = Model._inference_service_registry
        
        try:
            # Test setting and getting
            test_registry = Mock()
            Model.set_inference_service_registry(test_registry)
            assert Model._inference_service_registry == test_registry
            assert Model.get_inference_service_registry() == test_registry
        finally:
            # Restore original - ensure this always happens
            Model._inference_service_registry = original_registry