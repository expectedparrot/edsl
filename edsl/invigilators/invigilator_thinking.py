"""Invigilator for QuestionThinking that bypasses agent/persona and uses the question's own model."""

from typing import Dict, TYPE_CHECKING

from ..base.data_transfer_models import EDSLResultObjectInput

from .invigilators import InvigilatorBase

if TYPE_CHECKING:
    from ..prompts import Prompt


class InvigilatorThinking(InvigilatorBase):
    """An invigilator that sends question_text directly to the question's model.

    Unlike InvigilatorAI, this invigilator:
    - Uses the model attached to the question, not the survey-level model
    - Sends question_text as the user prompt with no system prompt
    - Does not inject agent persona or instructions
    """

    def get_prompts(self) -> Dict[str, "Prompt"]:
        from ..prompts import Prompt

        system_prompt = getattr(self.question, "_system_prompt", "")
        return {
            "user_prompt": Prompt(self.question.question_text),
            "system_prompt": Prompt(system_prompt),
        }

    async def async_answer_question(self) -> EDSLResultObjectInput:
        question_model = self.question._model
        system_prompt = getattr(self.question, "_system_prompt", "")

        if self.key_lookup:
            question_model.set_key_lookup(self.key_lookup)

        agent_response_dict = await question_model.async_get_response(
            user_prompt=self.question.question_text,
            system_prompt=system_prompt,
            cache=self.cache,
            iteration=self.iteration,
            invigilator=self,
        )

        self.raw_model_response = agent_response_dict.model_outputs.response

        answer = agent_response_dict.edsl_dict.generated_tokens
        if answer is None:
            answer = agent_response_dict.edsl_dict.answer

        data = {
            "answer": answer,
            "comment": "",
            "generated_tokens": agent_response_dict.edsl_dict.generated_tokens,
            "question_name": self.question.question_name,
            "prompts": self.get_prompts(),
            "cached_response": agent_response_dict.model_outputs.cached_response,
            "raw_model_response": agent_response_dict.model_outputs.response,
            "cache_used": agent_response_dict.model_outputs.cache_used,
            "cache_key": agent_response_dict.model_outputs.cache_key,
            "validated": True,
            "exception_occurred": None,
            "input_tokens": agent_response_dict.model_outputs.input_tokens,
            "output_tokens": agent_response_dict.model_outputs.output_tokens,
            "thinking_tokens": agent_response_dict.model_outputs.thinking_tokens,
            "input_price_per_million_tokens": agent_response_dict.model_outputs.input_price_per_million_tokens,
            "output_price_per_million_tokens": agent_response_dict.model_outputs.output_price_per_million_tokens,
            "total_cost": agent_response_dict.model_outputs.total_cost,
        }
        return EDSLResultObjectInput(**data)
