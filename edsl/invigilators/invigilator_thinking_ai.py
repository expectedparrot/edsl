"""Hybrid invigilator: uses question's own model and system_prompt,
but keeps full prompt construction and validation from InvigilatorAI."""

import copy
from typing import Dict, Any, TYPE_CHECKING

from .invigilators import InvigilatorAI

if TYPE_CHECKING:
    from ..prompts import Prompt


class InvigilatorThinkingAI(InvigilatorAI):
    """An invigilator that uses the question's embedded model and system prompt
    while preserving the original question type's answering instructions,
    question presentation, and response validation.

    Unlike InvigilatorThinking (which sends raw text), this invigilator
    builds full structured prompts via PromptConstructor, then overrides
    only the system prompt and the model used for inference.
    """

    def get_prompts(self) -> Dict[str, Any]:
        """Build full prompts but replace system prompt with question._system_prompt."""
        from ..prompts import Prompt

        prompts = super().get_prompts()
        system_prompt = getattr(self.question, "_system_prompt", "")
        prompts["system_prompt"] = Prompt(system_prompt)
        return prompts

    async def async_get_agent_response(self):
        """Same as InvigilatorAI but uses question._model for inference."""
        prompts = self.get_prompts()
        params = {
            "user_prompt": prompts["user_prompt"].text,
            "system_prompt": prompts["system_prompt"].text,
        }

        if "encoded_image" in prompts:
            params["encoded_image"] = prompts["encoded_image"]
            from .exceptions import InvigilatorNotImplementedError

            raise InvigilatorNotImplementedError(
                "encoded_image not implemented for thinking_question wrapper"
            )

        if "files_list" in prompts:
            params["files_list"] = prompts["files_list"]

        if hasattr(self.question, "get_response_schema"):
            params["response_schema"] = self.question.get_response_schema()
            params["response_schema_name"] = self.question.user_pydantic_model.__name__

        params.update({"iteration": self.iteration, "cache": self.cache})
        params.update({"invigilator": self})

        # Shallow-copy the model so set_key_lookup doesn't mutate the shared
        # question object (which persists across runs / concurrent executions).
        question_model = copy.copy(self.question._model)
        if self.key_lookup:
            question_model.set_key_lookup(self.key_lookup)

        return await question_model.async_get_response(**params)
