import pytest
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime
from collections import defaultdict
from typing import Dict, List, Any, Optional

from edsl.inference_services.inference_service_registry import InferenceServiceRegistry
from edsl.inference_services.source_preference_handler import SourcePreferenceHandler
from edsl.inference_services.inference_service_abc import InferenceServiceABC


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
    
    def create_model(self, model_name: str):
        return f"MockModel({model_name})"


class TestInferenceServiceRegistry:
    
    @pytest.fixture
    def registry(self):
        """Create a fresh registry for each test."""
        return InferenceServiceRegistry(classes_to_register=[])
    
    @pytest.fixture
    def mock_source_handler(self):
        """Create a mock source preference handler."""
        handler = Mock(spec=SourcePreferenceHandler)
        handler.fetch_model_info_data.return_value = {
            "service1": ["model1", "model2"],
            "service2": ["model3", "model4"],
            "anthropic": ["claude-3-opus", "claude-3-sonnet"],
            "openai": ["gpt-4", "gpt-3.5-turbo"]
        }
        handler.used_source = "test_source"
        return handler
    
    def test_init_default_parameters(self):
        """Test registry initialization with default parameters."""
        registry = InferenceServiceRegistry(classes_to_register=[])
        
        assert registry.verbose is False
        assert registry._service_preferences == registry._default_service_preferences
        assert isinstance(registry._source_handler, SourcePreferenceHandler)
        assert registry._services == {}
        assert registry._model_to_services is None
        assert registry._service_to_models is None
        assert registry._model_info_data is None
    
    def test_init_custom_parameters(self):
        """Test registry initialization with custom parameters."""
        custom_service_prefs = ("custom1", "custom2")
        custom_source_prefs = ("source1", "source2")
        
        registry = InferenceServiceRegistry(
            verbose=True,
            service_preferences=custom_service_prefs,
            source_preferences=custom_source_prefs
        )
        
        assert registry.verbose is True
        assert registry._service_preferences == custom_service_prefs
    
    def test_register_service(self, registry):
        """Test registering a service."""
        registry.register("test_service", MockInferenceService)
        
        assert "test_service" in registry._services
        assert registry._services["test_service"] == MockInferenceService
        assert "test_service" in registry._registration_times
        assert isinstance(registry._registration_times["test_service"], datetime)
    
    def test_register_test_service_ignored(self, registry):
        """Test that registering 'test' service is ignored."""
        registry.register("test", MockInferenceService)
        
        assert "test" not in registry._services
        assert "test" not in registry._registration_times
    
    def test_get_service_class_success(self, registry):
        """Test getting a registered service class."""
        registry.register("test_service", MockInferenceService)
        
        service_class = registry.get_service_class("test_service")
        assert service_class == MockInferenceService
    
    def test_get_service_class_not_found(self, registry):
        """Test getting a non-existent service class raises KeyError."""
        with pytest.raises(KeyError) as exc_info:
            registry.get_service_class("nonexistent")
        
        assert "Service 'nonexistent' not found in registry" in str(exc_info.value)
        assert "Available services: []" in str(exc_info.value)
    
    def test_list_registered_services(self, registry):
        """Test listing registered services."""
        registry.register("service1", MockInferenceService)
        registry.register("service2", MockInferenceService)
        
        services = registry.list_registered_services()
        assert set(services) == {"service1", "service2"}
    
    def test_services_property(self, registry):
        """Test services property returns the internal services dict."""
        registry.register("service1", MockInferenceService)
        
        services = registry.services
        assert services == registry._services
    
    def test_get_service_to_class(self, registry):
        """Test getting service to class mapping."""
        registry.register("service1", MockInferenceService)
        
        mapping = registry.get_service_to_class()
        assert mapping == {"service1": MockInferenceService}
    
    @patch('edsl.inference_services.inference_service_registry.SourcePreferenceHandler')
    def test_model_info_data_property(self, mock_handler_class, registry):
        """Test model_info_data property fetches data on first access."""
        mock_handler = Mock()
        mock_handler.fetch_model_info_data.return_value = {"service1": ["model1"]}
        mock_handler_class.return_value = mock_handler
        
        registry._source_handler = mock_handler
        
        # First access should fetch data
        data = registry.model_info_data
        assert data == {"service1": ["model1"]}
        mock_handler.fetch_model_info_data.assert_called_once()
        
        # Second access should return cached data
        data2 = registry.model_info_data
        assert data2 == {"service1": ["model1"]}
        # Should not call fetch again
        mock_handler.fetch_model_info_data.assert_called_once()
    
    def test_build_model_mappings(self, registry, mock_source_handler):
        """Test building model mappings."""
        registry._source_handler = mock_source_handler
        registry._build_model_mappings()
        
        expected_model_to_services = {
            "model1": ["service1"],
            "model2": ["service1"],
            "model3": ["service2"],
            "model4": ["service2"],
            "claude-3-opus": ["anthropic"],
            "claude-3-sonnet": ["anthropic"],
            "gpt-4": ["openai"],
            "gpt-3.5-turbo": ["openai"]
        }
        
        expected_service_to_models = {
            "service1": ["model1", "model2"],
            "service2": ["model3", "model4"],
            "anthropic": ["claude-3-opus", "claude-3-sonnet"],
            "openai": ["gpt-4", "gpt-3.5-turbo"]
        }
        
        assert dict(registry._model_to_services) == expected_model_to_services
        assert registry._service_to_models == expected_service_to_models
    
    def test_model_to_services_property(self, registry, mock_source_handler):
        """Test model_to_services property builds mappings on first access."""
        registry._source_handler = mock_source_handler
        
        model_to_services = registry.model_to_services
        
        assert "model1" in model_to_services
        assert "service1" in model_to_services["model1"]
        assert registry._model_to_services is not None
    
    def test_service_to_models_property(self, registry, mock_source_handler):
        """Test service_to_models property builds mappings on first access."""
        registry._source_handler = mock_source_handler
        
        service_to_models = registry.service_to_models
        
        assert "service1" in service_to_models
        assert "model1" in service_to_models["service1"]
        assert registry._service_to_models is not None
    
    def test_get_all_model_names(self, registry, mock_source_handler):
        """Test getting all model names."""
        registry._source_handler = mock_source_handler
        
        model_names = registry.get_all_model_names()
        
        expected_models = {"model1", "model2", "model3", "model4", 
                          "claude-3-opus", "claude-3-sonnet", "gpt-4", "gpt-3.5-turbo"}
        assert set(model_names) == expected_models
    
    def test_get_service_for_model_test(self, registry):
        """Test getting service for test model returns 'test'."""
        service = registry.get_service_for_model("test")
        assert service == "test"
    
    def test_get_service_for_model_with_preferences(self, registry, mock_source_handler):
        """Test getting service for model respects preferences."""
        registry._source_handler = mock_source_handler
        
        # Test that anthropic is preferred over openai for models available in both
        mock_source_handler.fetch_model_info_data.return_value = {
            "anthropic": ["shared_model"],
            "openai": ["shared_model"],
            "other": ["shared_model"]
        }
        registry._model_info_data = None  # Reset cache
        
        service = registry.get_service_for_model("shared_model")
        assert service == "anthropic"  # Should return first in preference order
    
    def test_get_service_for_model_fallback(self, registry, mock_source_handler):
        """Test getting service for model falls back to first available."""
        registry._source_handler = mock_source_handler
        
        # Model only available in service not in preferences
        mock_source_handler.fetch_model_info_data.return_value = {
            "uncommon_service": ["rare_model"]
        }
        registry._model_info_data = None  # Reset cache
        
        service = registry.get_service_for_model("rare_model")
        assert service == "uncommon_service"
    
    def test_get_service_for_model_not_found(self, registry, mock_source_handler):
        """Test getting service for non-existent model raises ValueError."""
        registry._source_handler = mock_source_handler
        
        with pytest.raises(ValueError) as exc_info:
            registry.get_service_for_model("nonexistent_model")
        
        assert "Model 'nonexistent_model' not found in any service" in str(exc_info.value)
    
    def test_get_services_for_model(self, registry, mock_source_handler):
        """Test getting all services for a model."""
        registry._source_handler = mock_source_handler
        
        # Add model to multiple services
        mock_source_handler.fetch_model_info_data.return_value = {
            "service1": ["shared_model"],
            "service2": ["shared_model"],
            "service3": ["other_model"]
        }
        registry._model_info_data = None
        
        services = registry.get_services_for_model("shared_model")
        assert set(services) == {"service1", "service2"}
        
        services = registry.get_services_for_model("other_model")
        assert services == ["service3"]
        
        services = registry.get_services_for_model("nonexistent")
        assert services == []
    
    def test_get_models_for_service(self, registry, mock_source_handler):
        """Test getting models for a service."""
        registry._source_handler = mock_source_handler
        
        models = registry.get_models_for_service("service1")
        assert set(models) == {"model1", "model2"}
        
        models = registry.get_models_for_service("nonexistent")
        assert models == []
    
    def test_find_services(self, registry):
        """Test finding services with wildcard patterns."""
        registry.register("service_a", MockInferenceService)
        registry.register("service_b", MockInferenceService)
        registry.register("other_service", MockInferenceService)
        
        # Test exact match
        services = registry.find_services("service_a")
        assert services == ["service_a"]
        
        # Test wildcard
        services = registry.find_services("service_*")
        assert set(services) == {"service_a", "service_b"}
        
        # Test no matches
        services = registry.find_services("nonexistent_*")
        assert services == []
    
    def test_find_models(self, registry, mock_source_handler):
        """Test finding models with wildcard patterns."""
        registry._source_handler = mock_source_handler
        
        # Test finding all models with pattern
        models = registry.find_models("model*")
        expected = ["model1", "model2", "model3", "model4"]
        assert set(models) == set(expected)
        
        # Test finding models in specific service
        models = registry.find_models("model*", service_name="service1")
        assert set(models) == {"model1", "model2"}
        
        # Test no matches
        models = registry.find_models("nonexistent*")
        assert models == []
        
        # Test service that doesn't exist
        models = registry.find_models("*", service_name="nonexistent")
        assert models == []
    
    def test_create_language_model_with_service_name(self, registry):
        """Test creating language model with explicit service name."""
        registry.register("test_service", MockInferenceService)
        
        model = registry.create_language_model("test_model", service_name="test_service")
        assert model == "MockModel(test_model)"
    
    def test_create_language_model_test_model(self, registry):
        """Test creating test language model."""
        with patch('edsl.inference_services.services.test_service.TestService') as mock_test_service:
            mock_instance = Mock()
            mock_instance.create_model.return_value = "TestModel(test)"
            mock_test_service.return_value = mock_instance
            
            model = registry.create_language_model("test")
            assert model == "TestModel(test)"
    
    def test_create_language_model_auto_lookup(self, registry, mock_source_handler):
        """Test creating language model with automatic service lookup."""
        registry._source_handler = mock_source_handler
        registry.register("service1", MockInferenceService)
        
        model = registry.create_language_model("model1")
        assert model == "MockModel(model1)"
    
    def test_create_language_model_service_not_found(self, registry):
        """Test creating language model with non-existent service raises KeyError."""
        with pytest.raises(KeyError):
            registry.create_language_model("test_model", service_name="nonexistent")
    
    def test_create_language_model_no_service_for_model(self, registry, mock_source_handler):
        """Test creating language model when no service found for model."""
        registry._source_handler = mock_source_handler
        
        with pytest.raises(ValueError) as exc_info:
            registry.create_language_model("nonexistent_model")
        
        assert "Model 'nonexistent_model' not found in any service" in str(exc_info.value)
    
    def test_source_preference_methods(self, registry):
        """Test source preference delegation methods."""
        with patch.object(registry._source_handler, 'get_source_preferences') as mock_get:
            mock_get.return_value = ["source1", "source2"]
            prefs = registry.get_source_preferences()
            assert prefs == ["source1", "source2"]
            mock_get.assert_called_once()
        
        with patch.object(registry._source_handler, 'add_source_preference') as mock_add:
            registry.add_source_preference("new_source", position=1)
            mock_add.assert_called_once_with("new_source", 1)
        
        with patch.object(registry._source_handler, 'remove_source_preference') as mock_remove:
            mock_remove.return_value = True
            result = registry.remove_source_preference("old_source")
            assert result is True
            mock_remove.assert_called_once_with("old_source")
    
    def test_get_used_source(self, registry):
        """Test getting used source."""
        # Set the private attribute directly since used_source is read-only
        registry._source_handler._used_source = "test_source"
        source = registry.get_used_source()
        assert source == "test_source"
    
    def test_refresh_model_info(self, registry, mock_source_handler):
        """Test refreshing model info resets caches."""
        registry._source_handler = mock_source_handler
        registry._model_info_data = {"old": "data"}
        registry._model_to_services = {"old": ["data"]}
        registry._service_to_models = {"old": ["data"]}
        
        with patch.object(registry._source_handler, 'reset_used_source') as mock_reset:
            registry.refresh_model_info()
            
            assert registry._model_info_data is None
            assert registry._model_to_services is None
            assert registry._service_to_models is None
            mock_reset.assert_called_once()
    
    def test_default_service_preferences_order(self):
        """Test that default service preferences are in expected order."""
        expected_order = [
            "anthropic",
            "openai", 
            "deep_infra",
            "deepseek",
            "google",
            "groq",
            "mistral",
            "openai_v2",
            "perplexity",
            "together",
            "xai",
            "open_router",
            "bedrock",
            "azure",
            "ollama",
        ]
        
        registry = InferenceServiceRegistry()
        assert registry._service_preferences == tuple(expected_order)
    
    def test_default_source_preferences(self):
        """Test default source preferences."""
        registry = InferenceServiceRegistry()
        expected_sources = ("coop_working", "coop", "archive", "local")
        
        # Check through source handler - stored as list internally
        assert tuple(registry._source_handler.source_preferences) == expected_sources