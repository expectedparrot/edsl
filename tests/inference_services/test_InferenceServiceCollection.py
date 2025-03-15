import pytest
from unittest.mock import Mock

from edsl.inference_services.exceptions import InferenceServiceError
from edsl.inference_services.services.test_service import TestService

from edsl.inference_services.inference_services_collection import (
    InferenceServicesCollection,
    ModelResolver,
)


class MockInferenceService:
    def __init__(self, service_name: str):
        self._inference_service_ = service_name

    def create_model(self, model_name: str):
        return f"Model({model_name})"


class TestModelResolver:
    @pytest.fixture
    def mock_services(self):
        return [MockInferenceService("service1"), MockInferenceService("service2")]

    @pytest.fixture
    def mock_models_to_services(self, mock_services):
        return {"model1": mock_services[0]}

    @pytest.fixture
    def mock_fetcher(self):
        fetcher = Mock()
        fetcher.get_available_models_by_service.return_value = "model2", "fake_serivce"
        return fetcher

    @pytest.fixture
    def resolver(self, mock_services, mock_models_to_services, mock_fetcher):
        return ModelResolver(mock_services, mock_models_to_services, mock_fetcher)

    def test_resolve_test_model(self, resolver):
        service = resolver.resolve_model("test", None)
        assert isinstance(service, TestService)

    def test_resolve_with_service_name(self, resolver):
        service = resolver.resolve_model("any_model", "service1")
        assert service._inference_service_ == "service1"

    def test_resolve_invalid_service_name(self, resolver):
        with pytest.raises(
            InferenceServiceError, match="Service invalid_service not found"
        ):
            resolver.resolve_model("any_model", "invalid_service")

    def test_resolve_from_models_to_services(self, resolver, mock_services):
        service = resolver.resolve_model("model1", None)
        assert service == mock_services[0]

    def test_resolve_from_available_models(self, resolver, mock_services):
        service = resolver.resolve_model("model2", None)
        assert service == mock_services[0]

    def test_model_not_found(self, resolver):
        with pytest.raises(
            InferenceServiceError, match="Model unknown_model not found in any services"
        ):
            resolver.resolve_model("unknown_model", None)


class TestInferenceServicesCollection:
    @pytest.fixture
    def mock_services(self):
        return [MockInferenceService("service1"), MockInferenceService("service2")]

    @pytest.fixture
    def collection(self, mock_services):
        return InferenceServicesCollection(mock_services)

    def test_add_model(self):
        InferenceServicesCollection.added_models.clear()
        InferenceServicesCollection.add_model("service1", "model1")
        assert InferenceServicesCollection.added_models["service1"] == ["model1"]

    def test_available(self, collection):
        expected_result = [("service1", "model1", 1), ("service2", "model2", 1)]
        collection.availability_fetcher.available = Mock(return_value=expected_result)

        result = collection.available("service1")
        assert result == expected_result

    def test_reset_cache(self, collection):
        collection.available("service1")  # Cache a result
        collection.reset_cache()
        assert collection.num_cache_entries == 0

    def test_register(self, collection):
        new_service = MockInferenceService("service3")
        initial_length = len(collection.services)
        collection.register(new_service)
        assert len(collection.services) == initial_length + 1
        assert collection.services[-1] == new_service

    def test_create_model_factory(self, collection):
        model = collection.create_model_factory("model1", "service1")
        assert model == "Model(model1)"

    def test_create_model_factory_invalid_service(self, collection):
        with pytest.raises(InferenceServiceError):
            collection.create_model_factory("model1", "invalid_service")

    def test_literal_matches_enum(self):
        # Get all values from the Literal type
        from typing import get_args
        from edsl.inference_services.inference_services_collection import (
            InferenceServiceLiteral,
        )
        from edsl.enums import InferenceServiceType

        literal_values = set(get_args(InferenceServiceLiteral))

        # Get all values from the enum
        enum_values = {member.value for member in InferenceServiceType}

        # Check both directions to ensure complete equality
        assert literal_values == enum_values, (
            f"Mismatch between Literal and Enum values:\n"
            f"In Literal but not in Enum: {literal_values - enum_values}\n"
            f"In Enum but not in Literal: {enum_values - literal_values}"
        )
