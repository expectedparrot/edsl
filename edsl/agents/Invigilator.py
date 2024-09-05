"""Module for creating Invigilators, which are objects to administer a question to an Agent."""

import json
from typing import Dict, Any, Optional

from edsl.exceptions import AgentRespondedWithBadJSONError
from edsl.prompts.Prompt import Prompt
from edsl.utilities.decorators import sync_wrapper, jupyter_nb_handler
from edsl.prompts.registry import get_classes as prompt_lookup

# from edsl.data_transfer_models import AgentResponseDict
from edsl.exceptions.agents import FailedTaskException
from edsl.agents.PromptConstructionMixin import PromptConstructorMixin

from edsl.agents.InvigilatorBase import InvigilatorBase

from edsl.exceptions.questions import QuestionResponseValidationError

from edsl.data_transfer_models import AgentResponseDict, EDSLResultObjectInput


class InvigilatorAI(PromptConstructorMixin, InvigilatorBase):
    """An invigilator that uses an AI model to answer questions."""

    async def async_answer_question(self) -> AgentResponseDict:
        """Answer a question using the AI model.

        >>> i = InvigilatorAI.example()
        >>> i.answer_question()
        {'message': '{"answer": "SPAM!"}'}
        """
        prompts = self.get_prompts()
        params = {
            "user_prompt": prompts["user_prompt"].text,
            "system_prompt": prompts["system_prompt"].text,
        }
        if "encoded_image" in prompts:
            params["encoded_image"] = prompts["encoded_image"]

        params.update({"iteration": self.iteration, "cache": self.cache})

        agent_response_dict = await self.model.async_get_response(**params)

        result_data = self.extract_edsl_result_entry(agent_response_dict)
        return result_data

    def _remove_from_cache(self, cache_key) -> None:
        """Remove an entry from the cache."""
        if cache_key:
            del self.cache.data[cache_key]

    def determine_answer(self, raw_answer: str) -> str:
        question_dict = self.survey.question_names_to_questions()
        # iterates through the current answers and updates the question_dict (which is all questions)
        for other_question, answer in self.current_answers.items():
            if other_question in question_dict:
                question_dict[other_question].answer = answer
            else:
                # it might be a comment
                if (
                    new_question := other_question.split("_comment")[0]
                ) in question_dict:
                    question_dict[new_question].comment = answer

        combined_dict = {**question_dict, **self.scenario}
        # sometimes the answer is a code, so we need to translate it
        return self.question._translate_answer_code_to_answer(raw_answer, combined_dict)

    def extract_edsl_result_entry(self, agent_response_dict: dict) -> AgentResponseDict:
        """Return formatted raw response."""
        # raw_model_response = augmented_response["raw_model_response"]
        validation_successful = False
        edsl_dict = agent_response_dict.edsl_dict._asdict()
        try:
            validated_edsl_dict = self.question._validate_answer(edsl_dict)
            validation_successful = True
        except QuestionResponseValidationError as e:
            """If the response is invalid, remove it from the cache and raise the exception."""
            if self.raise_validation_errors:
                raise e
        except Exception as non_validation_error:
            print("Non-validation error", non_validation_error)
            raise non_validation_error

        data = {
            "generated_tokens": agent_response_dict.edsl_dict.generated_tokens,
            "question_name": self.question.question_name,
            "prompts": self.get_prompts(),
            "cached_response": agent_response_dict.model_outputs.cached_response,
            "raw_model_response": agent_response_dict.model_outputs.response,
            "cache_used": agent_response_dict.model_outputs.cache_used,
            "cache_key": agent_response_dict.model_outputs.cache_key,
        }
        if not validation_successful:
            self._remove_from_cache(agent_response_dict.model_outputs.cache_key)
            data["answer"] = None
            data["comment"] = "The response was not valid."
        else:
            data["answer"] = self.determine_answer(validated_edsl_dict["answer"])
            data["comment"] = validated_edsl_dict.get("comment", "")

        return EDSLResultObjectInput(**data)

    answer_question = sync_wrapper(async_answer_question)


class InvigilatorHuman(InvigilatorBase):
    """An invigilator for when a human is answering the question."""

    validate_response: bool = False
    translate_response: bool = False

    async def async_answer_question(self, iteration: int = 0) -> AgentResponseDict:
        """Return the answer to the question."""

        comment = "This is a real survey response from a human."

        class NotApplicable(str):
            def __new__(cls):
                instance = super().__new__(cls, "Not Applicable")
                instance.literal = "Not Applicable"
                return instance

        def __repr__(self):
            return f"{self.literal}"

        try:
            answer = self.agent.answer_question_directly(self.question, self.scenario)
            self.raw_model_response = answer
            if self.validate_response:
                _ = self.question._validate_answer({"answer": answer})
            if self.translate_response:
                answer = self.question._translate_answer_code_to_answer(
                    answer, self.scenario
                )
        except Exception as e:
            answer = None
            comment = f"Failed to get response. The exception is {str(e)}"

        return EDSLResultObjectInput(
            generated_tokens=str(answer),
            question_name=self.question.question_name,
            prompts=self.get_prompts(),
            cached_response=NotApplicable(),
            raw_model_response=NotApplicable(),
            cache_used=NotApplicable(),
            cache_key=NotApplicable(),
            answer=answer,
            comment=comment,
        )


class InvigilatorFunctional(InvigilatorBase):
    """A Invigilator for when the question has a answer_question_directly function."""

    async def async_answer_question(self, iteration: int = 0) -> AgentResponseDict:
        """Return the answer to the question."""
        func = self.question.answer_question_directly
        data = {
            "comment": "Functional.",
            "prompts": self.get_prompts(),
            "question_name": self.question.question_name,
        }
        try:
            answer = func(scenario=self.scenario, agent_traits=self.agent.traits)
            return AgentResponseDict(**(data | answer))
        except Exception as e:
            agent_response_dict = AgentResponseDict(
                **(data | {"answer": None, "comment": str(e)})
            )
            raise FailedTaskException(
                f"Failed to get response. The exception is {str(e)}",
                agent_response_dict,
            ) from e

    def get_prompts(self) -> Dict[str, Prompt]:
        """Return the prompts used."""
        return {
            "user_prompt": Prompt("NA"),
            "system_prompt": Prompt("NA"),
        }


if __name__ == "__main__":
    import doctest

    doctest.testmod(optionflags=doctest.ELLIPSIS)
