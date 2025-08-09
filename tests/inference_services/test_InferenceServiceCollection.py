import pytest

from edsl.inference_services.exceptions import InferenceServiceError
from edsl.inference_services.services.test_service import TestService
from edsl.inference_services.inference_service_abc import InferenceServiceABC

from edsl.inference_services.inference_services_collection import (
    InferenceServicesCollection,
    ModelResolver,
)
from edsl.inference_services.data_structures import LanguageModelInfo


class MockInferenceService(InferenceServiceABC):
    """Test implementation of InferenceServiceABC for testing purposes."""
    
    # Required class attributes
    key_sequence = []
    model_exclude_list = []
    usage_sequence = []
    input_token_name = "input_tokens"
    output_token_name = "output_tokens"
    _inference_service_ = None
    
    def __init__(self):
        self._last_config_fetch = None

    @classmethod
    def available(cls) -> list[str]:
        """Returns a list of available models for the service."""
        return [x + "_" + cls.get_service_name() for x in ["test_model_1", "test_model_2"]]

    def create_model(self, model_name: str):
        """Returns a mock model object."""
        return f"Model({model_name})"
    

class MockInferenceService1(MockInferenceService):
    _inference_service_ = "service1"


class MockInferenceService2(MockInferenceService):
    _inference_service_ = "service2"


class MockInferenceService3(MockInferenceService):
    _inference_service_ = "service3"


class TestInferenceServicesCollection:
    
    def test_available_single_service(self):
        """Test getting available models for a single service."""
        isc = InferenceServicesCollection(
            services=[MockInferenceService1(), MockInferenceService2(), MockInferenceService3()], 
            verbose=False
        )
        
        result = isc.available("service1")
        expected = [
            LanguageModelInfo(model_name='test_model_1_service1', service_name='service1'), 
            LanguageModelInfo(model_name='test_model_2_service1', service_name='service1')
        ]
        
        assert result == expected

    def test_available_all_services(self):
        """Test getting available models for all services."""
        isc = InferenceServicesCollection(
            services=[MockInferenceService1(), MockInferenceService2()], 
            verbose=False
        )
        
        result = isc.available()
        
        # Should contain models from both services
        model_names = [model.model_name for model in result]
        assert 'test_model_1_service1' in model_names
        assert 'test_model_2_service1' in model_names
        assert 'test_model_1_service2' in model_names
        assert 'test_model_2_service2' in model_names
        
        # Should have 4 models total
        assert len(result) == 4

    def test_register_new_service(self):
        """Test registering a new service."""
        isc = InferenceServicesCollection(services=[MockInferenceService1()], verbose=False)
        
        initial_count = len(isc.services)
        isc.register(MockInferenceService2())
        
        assert len(isc.services) == initial_count + 1
        assert any(isinstance(service, MockInferenceService2) for service in isc.services)

    def test_create_model_factory_with_service_name(self):
        """Test creating a model with explicit service name."""
        isc = InferenceServicesCollection(
            services=[MockInferenceService1(), MockInferenceService2()], 
            verbose=False
        )
        
        model = isc.create_model_factory("any_model", "service1")
        assert model == "Model(any_model)"

    def test_create_model_factory_invalid_service(self):
        """Test creating a model with invalid service name."""
        isc = InferenceServicesCollection(services=[MockInferenceService1()], verbose=False)
        
        with pytest.raises(InferenceServiceError, match="Service invalid_service not found"):
            isc.create_model_factory("any_model", "invalid_service")

    def test_create_model_factory_auto_resolve(self):
        """Test creating a model without specifying service (auto-resolution)."""
        isc = InferenceServicesCollection(services=[MockInferenceService1()], verbose=False)
        
        # This should work because test_model_1_service1 is available from service1
        model = isc.create_model_factory("test_model_1_service1", None)
        assert model == "Model(test_model_1_service1)"

    def test_service_names_to_classes(self):
        """Test the service names to classes mapping."""
        isc = InferenceServicesCollection(
            services=[MockInferenceService1(), MockInferenceService2()], 
            verbose=False
        )
        
        mapping = isc.service_names_to_classes()
        
        assert "service1" in mapping
        assert "service2" in mapping
        assert isinstance(mapping["service1"], MockInferenceService1)
        assert isinstance(mapping["service2"], MockInferenceService2)

    def test_reset_cache(self):
        """Test cache reset functionality."""
        isc = InferenceServicesCollection(services=[MockInferenceService1()], verbose=False)
        
        # Make a call to populate cache
        isc.available("service1")
        
        # Reset cache
        isc.reset_cache()
        
        # Cache should be empty
        assert isc.num_cache_entries == 0

    def test_add_model_class_method(self):
        """Test the class method for adding models."""
        # Clear any existing added models
        InferenceServicesCollection.added_models.clear()
        
        InferenceServicesCollection.add_model("service1", "custom_model")
        
        assert "service1" in InferenceServicesCollection.added_models
        assert "custom_model" in InferenceServicesCollection.added_models["service1"]

    def test_force_refresh(self):
        """Test force refresh functionality."""
        isc = InferenceServicesCollection(services=[MockInferenceService1()], verbose=False)
        
        # First call (will cache)
        result1 = isc.available("service1")
        
        # Second call with force refresh
        result2 = isc.available("service1", force_refresh=True)
        
        # Results should be the same but fetched fresh
        assert result1 == result2


class TestModelResolver:
    
    def test_resolve_test_model(self):
        """Test resolving the special 'test' model."""
        services = [MockInferenceService1(), MockInferenceService2()]
        models_to_services = {}
        
        # Create a simple availability fetcher mock
        class SimpleAvailabilityFetcher:
            def get_available_models_by_service(self, service):
                return service.available(), service.get_service_name()
        
        resolver = ModelResolver(services, models_to_services, SimpleAvailabilityFetcher())
        
        service = resolver.resolve_model("test", None)
        assert isinstance(service, TestService)

    def test_resolve_with_service_name(self):
        """Test resolving model with explicit service name."""
        services = [MockInferenceService1(), MockInferenceService2()]
        models_to_services = {}
        
        class SimpleAvailabilityFetcher:
            def get_available_models_by_service(self, service):
                return service.available(), service.get_service_name()
        
        resolver = ModelResolver(services, models_to_services, SimpleAvailabilityFetcher())
        
        service = resolver.resolve_model("any_model", "service1")
        assert service._inference_service_ == "service1"

    def test_resolve_invalid_service_name(self):
        """Test resolving model with invalid service name."""
        services = [MockInferenceService1(), MockInferenceService2()]
        models_to_services = {}
        
        class SimpleAvailabilityFetcher:
            def get_available_models_by_service(self, service):
                return service.available(), service.get_service_name()
        
        resolver = ModelResolver(services, models_to_services, SimpleAvailabilityFetcher())
        
        with pytest.raises(InferenceServiceError, match="Service invalid_service not found"):
            resolver.resolve_model("any_model", "invalid_service")

    def test_resolve_from_models_to_services_cache(self):
        """Test resolving model from cached models_to_services mapping."""
        services = [MockInferenceService1(), MockInferenceService2()]
        models_to_services = {"cached_model": MockInferenceService1()}
        
        class SimpleAvailabilityFetcher:
            def get_available_models_by_service(self, service):
                return service.available(), service.get_service_name()
        
        resolver = ModelResolver(services, models_to_services, SimpleAvailabilityFetcher())
        
        service = resolver.resolve_model("cached_model", None)
        assert isinstance(service, MockInferenceService1)

    def test_resolve_from_available_models(self):
        """Test resolving model by searching available models."""
        services = [MockInferenceService1(), MockInferenceService2()]
        models_to_services = {}
        
        class SimpleAvailabilityFetcher:
            def get_available_models_by_service(self, service):
                return service.available(), service.get_service_name()
        
        resolver = ModelResolver(services, models_to_services, SimpleAvailabilityFetcher())
        
        # Should find test_model_1_service1 in service1
        service = resolver.resolve_model("test_model_1_service1", None)
        assert isinstance(service, MockInferenceService1)
        
        # Should cache the result
        assert "test_model_1_service1" in models_to_services
        assert isinstance(models_to_services["test_model_1_service1"], MockInferenceService1)

    def test_model_not_found(self):
        """Test error when model is not found in any service."""
        services = [MockInferenceService1(), MockInferenceService2()]
        models_to_services = {}
        
        class SimpleAvailabilityFetcher:
            def get_available_models_by_service(self, service):
                return service.available(), service.get_service_name()
        
        resolver = ModelResolver(services, models_to_services, SimpleAvailabilityFetcher())
        
        with pytest.raises(InferenceServiceError, match="Model unknown_model not found in any services"):
            resolver.resolve_model("unknown_model", None)
