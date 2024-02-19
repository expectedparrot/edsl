import asyncio
import pytest
from typing import Any
from edsl import Survey
from edsl.enums import LanguageModelType, InferenceServiceType
from edsl.language_models.LanguageModel import LanguageModel
from edsl.questions import QuestionFreeText


def create_language_model(
    exception: Exception, fail_at_number: int, never_ending=False
):
    class TestLanguageModel(LanguageModel):
        _model_ = LanguageModelType.TEST.value
        _parameters_ = {"temperature": 0.5, "use_cache": False}
        _inference_service_ = InferenceServiceType.TEST.value
        counter = 0

        async def async_execute_model_call(
            self, user_prompt: str, system_prompt: str
        ) -> dict[str, Any]:
            await asyncio.sleep(0.1)
            if never_ending:  ## you're not going anywhere buddy
                await asyncio.sleep(float("inf"))
            self.counter += 1
            if self.counter == fail_at_number:
                if asyncio.iscoroutinefunction(exception):
                    await exception()
                else:
                    raise exception
            return {"message": """{"answer": "SPAM!"}"""}

        def parse_response(self, raw_response: dict[str, Any]) -> str:
            return raw_response["message"]

    return TestLanguageModel


@pytest.fixture
def create_survey():
    def _create_survey(num_questions: int, chained: bool = True):
        survey = Survey()
        for i in range(num_questions):
            q = QuestionFreeText(
                question_text=f"How are you?", question_name=f"question_{i}"
            )
            survey.add_question(q)
            if i > 0 and chained:
                survey.add_targeted_memory(f"question_{i}", f"question_{i-1}")
        return survey

    return _create_survey


@pytest.mark.parametrize("fail_at_number, chained", [(6, False), (10, True)])
def test_handle_model_exceptions(create_survey, fail_at_number, chained):
    model = create_language_model(ValueError, fail_at_number)()
    survey = create_survey(num_questions=20, chained=chained)
    results = survey.by(model).run()
    #breakpoint()

    if not chained:
        assert results.select(f"answer.question_{fail_at_number - 1}").first() is None
        assert (
            results.select(f"answer.question_{fail_at_number + 1}").first() == "SPAM!"
        )
    else:
        assert results[0]["answer"][f"question_{fail_at_number - 1}"] is None
        assert results[0]["answer"][f"question_{fail_at_number}"] is None


def test_handle_timeout_exception(create_survey, capsys):
    ## TODO: We want to shrink the API_TIMEOUT_SEC param for testing purposes.
    model = create_language_model(ValueError, 3, never_ending=True)()
    survey = create_survey(num_questions=5, chained=False)
    results = survey.by(model).run()
    captured = capsys.readouterr()
    assert (
        "WARNING: At least one question in the survey was not answered." in captured.out
    )
    assert "Task `question_0` failed with `InterviewTimeoutError" in captured.out


if __name__ == "__main__":
    pytest.main()
