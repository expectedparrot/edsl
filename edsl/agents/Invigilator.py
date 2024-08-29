"""Module for creating Invigilators, which are objects to administer a question to an Agent."""

import json
from typing import Dict, Any, Optional

from edsl.exceptions import AgentRespondedWithBadJSONError
from edsl.prompts.Prompt import Prompt
from edsl.utilities.decorators import sync_wrapper, jupyter_nb_handler
from edsl.prompts.registry import get_classes as prompt_lookup
from edsl.data_transfer_models import AgentResponseDict
from edsl.exceptions.agents import FailedTaskException
from edsl.agents.PromptConstructionMixin import PromptConstructorMixin

from edsl.agents.InvigilatorBase import InvigilatorBase

from edsl.exceptions.questions import QuestionResponseValidationError


class InvigilatorAI(PromptConstructorMixin, InvigilatorBase):
    """An invigilator that uses an AI model to answer questions."""

    async def async_answer_question(self) -> AgentResponseDict:
        """Answer a question using the AI model.

        >>> i = InvigilatorAI.example()
        >>> i.answer_question()
        {'message': '{"answer": "SPAM!"}'}
        """
        params = self.get_prompts() | {"iteration": self.iteration}
        raw_response = await self.async_get_response(**params)
        # logs the raw response in the invigilator
        self.raw_model_response = raw_response["raw_model_response"]
        data = {
            "agent": self.agent,
            "question": self.question,
            "scenario": self.scenario,
            "raw_response": raw_response,
            "raw_model_response": raw_response["raw_model_response"],
        }
        response = self._format_raw_response(**data)
        return AgentResponseDict(**response)

    async def async_get_response(
        self,
        user_prompt: Prompt,
        system_prompt: Prompt,
        iteration: int = 0,
        encoded_image=None,
    ) -> dict:
        """Call the LLM and gets a response. Used in the `answer_question` method."""
        try:
            params = {
                "user_prompt": user_prompt.text,
                "system_prompt": system_prompt.text,
                "iteration": iteration,
                "cache": self.cache,
            }
            if encoded_image:
                params["encoded_image"] = encoded_image
            response = await self.model.async_get_response(**params)

        # TODO: I *don't* think we need to delete the cache key here because I think
        # it will not have been set yet; the exception would have been raised before.
        except json.JSONDecodeError as e:
            raise AgentRespondedWithBadJSONError(
                f"Returned bad JSON: {e}"
                f"Prompt: {user_prompt}"
                f"System Prompt: {system_prompt}"
            )

        return response

    def _remove_from_cache(self, raw_response) -> None:
        """Remove an entry from the cache."""
        cache_key = raw_response.get("cache_key", None)
        if cache_key:
            del self.cache.data[cache_key]

    def _format_raw_response(
        self, *, agent, question, scenario, raw_response, raw_model_response
    ) -> AgentResponseDict:
        """Return formatted raw response.

        This cleans up the raw response to make it suitable to pass to AgentResponseDict.
        """
        _ = agent
        try:
            response = question._validate_answer(
                json.loads(json_string := self.model.parse_response(raw_model_response))
            )
            # response = question._validate_answer(
            #    json.loads(raw_model_response["message"])
            # )
        except json.JSONDecodeError as e:
            msg = f"""Error at line {e.lineno}, column {e.colno} (character {e.pos})"). Problematic part of the JSON: {json_string[e.pos-10:e.pos+10]}")"""
            self._remove_from_cache(raw_response)
            raise QuestionResponseValidationError(msg)

        except Exception as e:
            """If the response is invalid, remove it from the cache and raise the exception."""
            self._remove_from_cache(raw_response)
            raise e

        question_dict = self.survey.question_names_to_questions()
        for other_question, answer in self.current_answers.items():
            if other_question in question_dict:
                question_dict[other_question].answer = answer
            else:
                # adds a comment to the question
                if (
                    new_question := other_question.split("_comment")[0]
                ) in question_dict:
                    question_dict[new_question].comment = answer

        combined_dict = {**question_dict, **scenario}
        answer = question._translate_answer_code_to_answer(
            response["answer"], combined_dict
        )
        data = {
            "answer": answer,
            "comment": response.get(
                "comment", ""
            ),  # not all question have comment fields,
            "question_name": question.question_name,
            "prompts": self.get_prompts(),
            "cached_response": raw_response.get("cached_response", None),
            "usage": raw_response.get("usage", {}),
            "raw_model_response": raw_model_response,
            "cache_used": raw_response.get("cache_used", False),
            "cache_key": raw_response.get("cache_key", None),
        }
        return AgentResponseDict(**data)

    get_response = sync_wrapper(async_get_response)
    answer_question = sync_wrapper(async_answer_question)


class InvigilatorSidecar(InvigilatorAI):
    """An invigilator that presents the 'raw' question to the agent
    & uses a sidecar model to answer questions."""

    async def async_answer_question(self, failed: bool = False) -> AgentResponseDict:
        """Answer a question using the AI model."""
        from edsl import Model

        advanced_model = self.sidecar_model
        simple_model = self.model
        question = self.question
        human_readable_question = (
            "Please answer this single question: " + question.human_readable()
        )
        print("Getting the simple model response to: ", human_readable_question)
        raw_simple_response = await simple_model.async_execute_model_call(
            user_prompt=human_readable_question,
            system_prompt="""Pretend you are a human answering a question. Do not break character.""",
        )
        simple_response = simple_model.parse_response(raw_simple_response)
        instructions = question.get_instructions()

        main_model_prompt = Prompt(
            text="""
        A simpler language model was asked this question: 

        To the simpel model:
        {{ human_readable_question }}

        The simple model responded:
        <response>
        {{ simple_response }}
        </response>

        It was suppose to respond according to these instructions:                                                      
        <instructions>
        {{ instructions }}
        </instructions>
                                
        Please format the simple model's response as it should have been formmated, given the instructions.
        Only respond in valid JSON, like so {"answer": "SPAM!"} or {"answer": "SPAM!", "comment": "I am a robot."}
        Do not inlcude the word 'json'
        """
        )

        d = {
            "human_readable_question": human_readable_question,
            "simple_response": simple_response,
            "instructions": instructions,
        }

        print("The human-readable question is: ", human_readable_question)
        print("The simple response is: ", simple_response)

        raw_response_data = await advanced_model.async_execute_model_call(
            user_prompt=main_model_prompt.render(d).text,
            system_prompt="You are a helpful assistant.",
        )

        raw_response = await advanced_model.async_get_response(
            user_prompt=main_model_prompt.render(d).text,
            system_prompt="You are a helpful assistant.",
            iteration=0,
            cache=self.cache,
        )

        data = {
            "agent": self.agent,
            "question": self.question,
            "scenario": self.scenario,
        }
        raw_response_data = {
            "raw_response": raw_response,
            "raw_model_response": raw_response["raw_model_response"],
        }
        params = data | raw_response_data
        response = self._format_raw_response(**params)
        response.update({"simple_model_raw_response": simple_response})
        return AgentResponseDict(**response)

    # get_response = sync_wrapper(async_get_response)
    answer_question = sync_wrapper(async_answer_question)


class InvigilatorDebug(InvigilatorBase):
    """An invigilator class for debugging purposes."""

    async def async_answer_question(self, iteration: int = 0) -> AgentResponseDict:
        """Return the answer to the question."""
        results = self.question._simulate_answer(human_readable=True)
        results["prompts"] = self.get_prompts()
        results["question_name"] = self.question.question_name
        results["comment"] = "Debug comment"
        return AgentResponseDict(**results)

    def get_prompts(self) -> Dict[str, Prompt]:
        """Return the prompts used."""
        return {
            "user_prompt": Prompt("NA"),
            "system_prompt": Prompt("NA"),
        }


class InvigilatorHuman(InvigilatorBase):
    """An invigilator for when a human is answering the question."""

    validate_response: bool = False
    translate_response: bool = False

    async def async_answer_question(self, iteration: int = 0) -> AgentResponseDict:
        """Return the answer to the question."""

        data = {
            "comment": "This is a real survey response from a human.",
            "answer": None,
            "prompts": self.get_prompts(),
            "question_name": self.question.question_name,
        }
        answer = None
        try:
            answer = self.agent.answer_question_directly(self.question, self.scenario)
            self.raw_model_response = answer
            if self.validate_response:
                _ = self.question._validate_answer({"answer": answer})
            if self.translate_response:
                answer = self.question._translate_answer_code_to_answer(
                    answer, self.scenario
                )
            return AgentResponseDict(**(data | {"answer": answer}))
        except Exception as e:
            agent_response_dict = AgentResponseDict(
                **(
                    data
                    | {"answer": None, "comment": str(e)}
                    | {"raw_model_response": answer}
                )
            )
            raise FailedTaskException(
                f"Failed to get response. The exception is {str(e)}",
                agent_response_dict,
            ) from e


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
