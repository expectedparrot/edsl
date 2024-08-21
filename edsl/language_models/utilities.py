import asyncio
from typing import Any
from edsl import Survey
from edsl.config import CONFIG
from edsl.enums import InferenceServiceType
from edsl.language_models.LanguageModel import LanguageModel
from edsl.questions import QuestionFreeText


def create_language_model(
    exception: Exception, fail_at_number: int, never_ending=False
):
    class TestLanguageModel(LanguageModel):
        _model_ = "test"
        _parameters_ = {"temperature": 0.5}
        _inference_service_ = InferenceServiceType.TEST.value

        async def async_execute_model_call(
            self, user_prompt: str, system_prompt: str
        ) -> dict[str, Any]:
            question_number = int(
                user_prompt.split("XX")[1]
            )  ## grabs the question number from the prompt
            await asyncio.sleep(0.1)
            if never_ending:  ## you're not going anywhere buddy
                await asyncio.sleep(float("inf"))
            if question_number == fail_at_number:
                if asyncio.iscoroutinefunction(exception):
                    await exception()
                else:
                    raise exception
            return {"message": """{"answer": "SPAM!"}"""}

        def parse_response(self, raw_response: dict[str, Any]) -> str:
            return raw_response["message"]

    return TestLanguageModel