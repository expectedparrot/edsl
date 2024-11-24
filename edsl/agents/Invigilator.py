"""Module for creating Invigilators, which are objects to administer a question to an Agent."""

from typing import Dict, Any, Optional

from edsl.prompts.Prompt import Prompt
from edsl.utilities.decorators import sync_wrapper, jupyter_nb_handler

# from edsl.prompts.registry import get_classes as prompt_lookup
from edsl.exceptions.questions import QuestionAnswerValidationError
from edsl.agents.InvigilatorBase import InvigilatorBase
from edsl.data_transfer_models import AgentResponseDict, EDSLResultObjectInput
from edsl.agents.PromptConstructor import PromptConstructor


class NotApplicable(str):
    def __new__(cls):
        instance = super().__new__(cls, "Not Applicable")
        instance.literal = "Not Applicable"
        return instance


class InvigilatorAI(InvigilatorBase):
    """An invigilator that uses an AI model to answer questions."""

    def get_prompts(self) -> Dict[str, Prompt]:
        """Return the prompts used."""
        return self.prompt_constructor.get_prompts()

    async def async_answer_question(self) -> AgentResponseDict:
        """Answer a question using the AI model.

        >>> i = InvigilatorAI.example()
        >>> i.answer_question()
        {'message': [{'text': 'SPAM!'}], 'usage': {'prompt_tokens': 1, 'completion_tokens': 1}}
        """
        prompts = self.get_prompts()
        params = {
            "user_prompt": prompts["user_prompt"].text,
            "system_prompt": prompts["system_prompt"].text,
        }
        if "encoded_image" in prompts:
            params["encoded_image"] = prompts["encoded_image"]
        if "files_list" in prompts:
            params["files_list"] = prompts["files_list"]

        params.update({"iteration": self.iteration, "cache": self.cache})

        params.update({"invigilator": self})
        # if hasattr(self.question, "answer_template"):
        #    breakpoint()

        agent_response_dict: AgentResponseDict = await self.model.async_get_response(
            **params
        )
        # store to self in case validation failure
        self.raw_model_response = agent_response_dict.model_outputs.response
        self.generated_tokens = agent_response_dict.edsl_dict.generated_tokens

        return self.extract_edsl_result_entry_and_validate(agent_response_dict)

    def _remove_from_cache(self, cache_key) -> None:
        """Remove an entry from the cache."""
        if cache_key:
            del self.cache.data[cache_key]

    def determine_answer(self, raw_answer: str) -> Any:
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

    def extract_edsl_result_entry_and_validate(
        self, agent_response_dict: AgentResponseDict
    ) -> EDSLResultObjectInput:
        edsl_dict = agent_response_dict.edsl_dict._asdict()
        exception_occurred = None
        validated = False
        try:
            # if the question has jinja parameters, it is easier to make a new question with the parameters
            if self.question.parameters:
                prior_answers_dict = self.prompt_constructor.prior_answers_dict()

                # question options have be treated differently because of dynamic question
                # this logic is all in the prompt constructor
                if "question_options" in self.question.data:
                    new_question_options = (
                        self.prompt_constructor._get_question_options(
                            self.question.data
                        )
                    )
                    if new_question_options != self.question.data["question_options"]:
                        # I don't love this direct writing but it seems to work
                        self.question.question_options = new_question_options

                question_with_validators = self.question.render(
                    self.scenario | prior_answers_dict
                )
                question_with_validators.use_code = self.question.use_code
            else:
                question_with_validators = self.question

            # breakpoint()
            validated_edsl_dict = question_with_validators._validate_answer(edsl_dict)
            answer = self.determine_answer(validated_edsl_dict["answer"])
            comment = validated_edsl_dict.get("comment", "")
            validated = True
        except QuestionAnswerValidationError as e:
            answer = None
            comment = "The response was not valid."
            # if self.raise_validation_errors:
            exception_occurred = e
        except Exception as non_validation_error:
            answer = None
            comment = "Some other error occurred."
            exception_occurred = non_validation_error
        finally:
            # even if validation failes, we still return the result
            data = {
                "answer": answer,
                "comment": comment,
                "generated_tokens": agent_response_dict.edsl_dict.generated_tokens,
                "question_name": self.question.question_name,
                "prompts": self.get_prompts(),
                "cached_response": agent_response_dict.model_outputs.cached_response,
                "raw_model_response": agent_response_dict.model_outputs.response,
                "cache_used": agent_response_dict.model_outputs.cache_used,
                "cache_key": agent_response_dict.model_outputs.cache_key,
                "validated": validated,
                "exception_occurred": exception_occurred,
                "cost": agent_response_dict.model_outputs.cost,
            }
            result = EDSLResultObjectInput(**data)
            return result

    answer_question = sync_wrapper(async_answer_question)


class InvigilatorHuman(InvigilatorBase):
    """An invigilator for when a human is answering the question."""

    validate_response: bool = False
    translate_response: bool = False

    async def async_answer_question(self, iteration: int = 0) -> AgentResponseDict:
        """Return the answer to the question."""
        comment = "This is a real survey response from a human."

        def __repr__(self):
            return f"{self.literal}"

        exception_occurred = None
        validated = False
        try:
            answer = self.agent.answer_question_directly(self.question, self.scenario)
            self.raw_model_response = answer

            if self.validate_response:
                _ = self.question._validate_answer({"answer": answer})
            if self.translate_response:
                answer = self.question._translate_answer_code_to_answer(
                    answer, self.scenario
                )
            validated = True
        except QuestionAnswerValidationError as e:
            answer = None
            if self.raise_validation_errors:
                exception_occurred = e
        except Exception as e:
            answer = None
            if self.raise_validation_errors:
                exception_occurred = e
        finally:
            data = {
                "generated_tokens": NotApplicable(),
                "question_name": self.question.question_name,
                "prompts": self.get_prompts(),
                "cached_response": NotApplicable(),
                "raw_model_response": NotApplicable(),
                "cache_used": NotApplicable(),
                "cache_key": NotApplicable(),
                "answer": answer,
                "comment": comment,
                "validated": validated,
                "exception_occurred": exception_occurred,
            }
            return EDSLResultObjectInput(**data)


class InvigilatorFunctional(InvigilatorBase):
    """A Invigilator for when the question has a answer_question_directly function."""

    async def async_answer_question(self, iteration: int = 0) -> AgentResponseDict:
        """Return the answer to the question."""
        func = self.question.answer_question_directly
        answer = func(scenario=self.scenario, agent_traits=self.agent.traits)

        return EDSLResultObjectInput(
            generated_tokens=str(answer),
            question_name=self.question.question_name,
            prompts=self.get_prompts(),
            cached_response=NotApplicable(),
            raw_model_response=NotApplicable(),
            cache_used=NotApplicable(),
            cache_key=NotApplicable(),
            answer=answer["answer"],
            comment="This is the result of a functional question.",
            validated=True,
            exception_occurred=None,
        )

    def get_prompts(self) -> Dict[str, Prompt]:
        """Return the prompts used."""
        return {
            "user_prompt": Prompt("NA"),
            "system_prompt": Prompt("NA"),
        }


if __name__ == "__main__":
    import doctest

    doctest.testmod(optionflags=doctest.ELLIPSIS)
