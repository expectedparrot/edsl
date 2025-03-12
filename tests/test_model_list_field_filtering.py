"""Tests for the Field-based filtering in ModelList."""

import pytest
from edsl import Model, ModelList, Field


def test_model_list_field_filtering():
    """Test filtering ModelList with Field expressions."""
    # Create test data using Model.example() to avoid issues with model availability
    model1 = Model.example()
    model1.parameters['temperature'] = 0.7
    model1.parameters['max_tokens'] = 1000
    
    model2 = Model.example()
    model2.parameters['temperature'] = 0.5
    model2.parameters['max_tokens'] = 2000
    
    model3 = Model.example()
    model3.parameters['temperature'] = 0.9
    model3.parameters['max_tokens'] = 500
    
    model4 = Model.example()
    model4.parameters['temperature'] = 0.6
    model4.parameters['max_tokens'] = 1500
    
    # Set different model names for testing
    model1.model = "model-a"
    model2.model = "model-b"
    model3.model = "model-c"
    model4.model = "model-d"
    
    model_list = ModelList([model1, model2, model3, model4])
    
    # Test simple Field expression
    filtered = model_list.filter(Field("model") == "model-a")
    assert len(filtered) == 1
    assert filtered[0].model == "model-a"
    
    # Test numeric comparison
    filtered = model_list.filter(Field("temperature") > 0.6)
    assert len(filtered) == 2
    assert {model.model for model in filtered} == {"model-a", "model-c"}
    
    # Test compound Field expression with &
    filtered = model_list.filter((Field("temperature") >= 0.6) & (Field("max_tokens") > 500))
    assert len(filtered) == 2
    assert {model.model for model in filtered} == {"model-a", "model-d"}
    
    # Test compound Field expression with |
    filtered = model_list.filter((Field("model").contains("model-b")) | (Field("temperature") >= 0.8))
    assert len(filtered) == 2
    assert {model.model for model in filtered} == {"model-b", "model-c"}


def test_model_list_string_operations():
    """Test string operations in ModelList Field filtering."""
    # Create test data using Model.example()
    model1 = Model.example()
    model2 = Model.example()
    model3 = Model.example()
    model4 = Model.example()
    
    # Set different model names for testing
    model1.model = "gpt-model"
    model2.model = "claude-opus"
    model3.model = "gpt-turbo"
    model4.model = "claude-sonnet"
    
    model_list = ModelList([model1, model2, model3, model4])
    
    # Test contains
    filtered = model_list.filter(Field("model").contains("gpt"))
    assert len(filtered) == 2
    assert {model.model for model in filtered} == {"gpt-model", "gpt-turbo"}
    
    # Test startswith
    filtered = model_list.filter(Field("model").startswith("claude"))
    assert len(filtered) == 2
    assert {model.model for model in filtered} == {"claude-opus", "claude-sonnet"}
    
    # Test endswith
    filtered = model_list.filter(Field("model").endswith("opus"))
    assert len(filtered) == 1
    assert filtered[0].model == "claude-opus"
    
    # Test regex matching
    filtered = model_list.filter(Field("model").matches(r".*-turbo"))
    assert len(filtered) == 1
    assert filtered[0].model == "gpt-turbo"


def test_model_list_combined_filtering():
    """Test complex combined filtering expressions for ModelList."""
    # Create test data with various parameters
    model1 = Model.example()
    model2 = Model.example()
    model3 = Model.example()
    model4 = Model.example()
    model5 = Model.example()
    
    # Set parameters
    model1.model = "model-a"
    model1.parameters['temperature'] = 0.7
    model1.parameters['max_tokens'] = 1000
    model1.parameters['top_p'] = 1.0
    
    model2.model = "model-b"
    model2.parameters['temperature'] = 0.5
    model2.parameters['max_tokens'] = 2000
    model2.parameters['top_p'] = 0.9
    
    model3.model = "model-c"
    model3.parameters['temperature'] = 0.9
    model3.parameters['max_tokens'] = 500
    model3.parameters['top_p'] = 1.0
    
    model4.model = "model-d"
    model4.parameters['temperature'] = 0.6
    model4.parameters['max_tokens'] = 1500
    model4.parameters['top_p'] = 0.8
    
    model5.model = "model-e"
    model5.parameters['temperature'] = 0.8
    model5.parameters['max_tokens'] = 1200
    model5.parameters['top_p'] = 0.95
    
    model_list = ModelList([model1, model2, model3, model4, model5])
    
    # Test complex combined expression
    complex_filter = (
        (Field("temperature") > 0.6) & 
        (
            (Field("model").contains("model-a")) | 
            (Field("max_tokens") > 1000)
        )
    )
    filtered = model_list.filter(complex_filter)
    assert len(filtered) == 2
    assert {model.model for model in filtered} == {"model-a", "model-e"}
    
    # Another complex expression
    complex_filter2 = (
        (Field("max_tokens") < 1500) & 
        (Field("top_p") >= 0.95) & 
        (Field("model") != "model-b")
    )
    filtered = model_list.filter(complex_filter2)
    assert len(filtered) == 3
    models = {model.model for model in filtered}
    assert "model-a" in models
    assert "model-c" in models
    assert "model-e" in models


def test_model_list_backward_compatibility():
    """Test that string-based filtering still works."""
    # Create test data
    model1 = Model.example()
    model2 = Model.example()
    
    model1.model = "model-a"
    model1.parameters['temperature'] = 0.7
    model1.parameters['max_tokens'] = 1000
    
    model2.model = "model-b"
    model2.parameters['temperature'] = 0.5
    model2.parameters['max_tokens'] = 2000
    
    model_list = ModelList([model1, model2])
    
    # Test string expression
    filtered = model_list.filter("temperature > 0.6")
    assert len(filtered) == 1
    assert filtered[0].model == "model-a"
    
    # Test complex string expression
    filtered = model_list.filter("model == 'model-b' and max_tokens > 1500")
    assert len(filtered) == 1
    assert filtered[0].model == "model-b"
    
    # Test that string filters and Field filters produce the same results
    string_filtered = model_list.filter("temperature > 0.6")
    field_filtered = model_list.filter(Field("temperature") > 0.6)
    assert len(string_filtered) == len(field_filtered)
    assert string_filtered[0].model == field_filtered[0].model


def test_model_list_empty_list():
    """Test filtering on empty ModelList."""
    # Test with empty model list
    empty_list = ModelList([])
    
    # Empty list with filter should return empty list
    filtered = empty_list.filter(Field("any_field") > 10)
    assert len(filtered) == 0
    assert isinstance(filtered, ModelList)
    
    # Test with a single model
    model = Model.example()
    model.parameters['temperature'] = 0.7
    single_model = ModelList([model])
    
    filtered = single_model.filter(Field("temperature") > 0.5)
    assert len(filtered) == 1
    
    # Test filtering when no models match
    filtered = single_model.filter(Field("temperature") > 0.9)
    assert len(filtered) == 0