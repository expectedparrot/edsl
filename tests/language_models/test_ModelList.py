import pytest
from edsl.language_models import LanguageModel
from edsl.language_models import ModelList

def test_init_with_data():
    data = [LanguageModel.example() for _ in range(3)]
    model_list = ModelList(data)
    assert len(model_list) == 3
    assert all(isinstance(model, LanguageModel) for model in model_list)


def test_init_without_data():
    model_list = ModelList()
    assert len(model_list) == 0


def test_to_dict():
    model_list = ModelList.example()
    model_dict = model_list.to_dict()
    assert "models" in model_dict
    assert isinstance(model_dict["models"], list)
    assert all(isinstance(model, dict) for model in model_dict["models"])
    assert "edsl_version" in model_dict
    assert "edsl_class_name" in model_dict
    assert model_dict["edsl_class_name"] == "ModelList"


def test_from_dict():
    example_list = ModelList.example()
    model_dict = example_list.to_dict()
    new_model_list = ModelList.from_dict(model_dict)
    assert len(new_model_list) == len(example_list)
    assert all(isinstance(model, LanguageModel) for model in new_model_list)


def test_example():
    example_list = ModelList.example()
    assert len(example_list) == 3
    assert all(isinstance(model, LanguageModel) for model in example_list)


if __name__ == "__main__":
    pytest.main()
