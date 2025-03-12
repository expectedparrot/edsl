import asyncio
from typing import Any, Optional, List
from ..enums import InferenceServiceType
from ..surveys import Survey

from .language_model import LanguageModel

def create_survey(num_questions: int, chained: bool = True, take_scenario=False):
    from ..questions import QuestionFreeText

    survey = Survey()
    for i in range(num_questions):
        if take_scenario:
            q = QuestionFreeText(
                question_text=f"XX{i}XX and {{scenario_value }}",
                question_name=f"question_{i}",
            )
        else:
            q = QuestionFreeText(
                question_text=f"XX{i}XX", question_name=f"question_{i}"
            )
        survey.add_question(q)
        if i > 0 and chained:
            survey.add_targeted_memory(f"question_{i}", f"question_{i-1}")
    return survey


def create_language_model(
    exception: Exception, fail_at_number: int, never_ending=False
):

    class LanguageModelFromUtilities(LanguageModel):
        _model_ = "test"
        _parameters_ = {"temperature": 0.5}
        _inference_service_ = InferenceServiceType.TEST.value
        key_sequence = ["message", 0, "text"]
        usage_sequence = ["usage"]
        input_token_name = "prompt_tokens"
        output_token_name = "completion_tokens"
        _rpm = 1000000000000
        _tpm = 1000000000000

        async def async_execute_model_call(
            self,
            user_prompt: str,
            system_prompt: str,
            files_list: Optional[List[Any]] = None,
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
            return {
                "message": [{"text": "SPAM!"}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1},
            }

    return LanguageModelFromUtilities
