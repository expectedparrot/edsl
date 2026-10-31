from edsl import Model, QuestionFreeText
from edsl.questions.question_thinking import thinking_question
from edsl.inference_services.services.anthropic_service import AnthropicService
from edsl.inference_services.services.google_service import GoogleService


def test_openai_model_default_allows_longer_answers():
    model = Model("gpt-4o", skip_api_key_check=True)
    assert model.max_tokens == 4096


def test_common_provider_defaults_allow_longer_answers():
    anthropic_model = AnthropicService.create_model("claude-3-haiku-20240307")(
        skip_api_key_check=True
    )
    google_model = GoogleService.create_model("gemini-2.0-flash")(
        skip_api_key_check=True
    )
    assert anthropic_model.max_tokens == 4096
    assert google_model.maxOutputTokens == 4096


def test_thinking_question_raises_default_limit_and_preserves_custom_limits():
    question = QuestionFreeText(question_name="feedback", question_text="Review this.")

    by_name = thinking_question(question, model="gpt-4o")
    assert by_name._model.max_tokens == 8192

    default_model = Model("gpt-4o", skip_api_key_check=True)
    by_model = thinking_question(question, model=default_model)
    assert by_model._model.max_tokens == 8192
    assert default_model.max_tokens == 4096

    custom_model = Model("gpt-4o", max_tokens=1800, skip_api_key_check=True)
    by_custom_model = thinking_question(question, model=custom_model)
    assert by_custom_model._model.max_tokens == 1800

    custom_dict = custom_model.to_dict()
    by_dict = thinking_question(question, model=custom_dict)
    assert by_dict._model.max_tokens == 1800


def test_thinking_question_sets_default_limit_for_model_dict_without_limit():
    model_dict = Model("gpt-4o", skip_api_key_check=True).to_dict()
    model_dict["parameters"].pop("max_tokens")
    question = QuestionFreeText(question_name="feedback", question_text="Review this.")

    wrapped = thinking_question(question, model=model_dict)

    assert wrapped._model.max_tokens == 8192
