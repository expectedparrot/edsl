"""Module for creating Invigilators, which are objects to administer a question to an Agent."""
import json
from typing import Coroutine, Dict, Any, Optional

from edsl.exceptions import AgentRespondedWithBadJSONError
from edsl.prompts.Prompt import Prompt
from edsl.utilities.decorators import sync_wrapper, jupyter_nb_handler
from edsl.prompts.registry import get_classes as prompt_lookup
from edsl.data_transfer_models import AgentResponseDict
from edsl.exceptions.agents import FailedTaskException
from edsl.agents.PromptConstructionMixin import PromptConstructorMixin

from edsl.agents.InvigilatorBase import InvigilatorBase


class InvigilatorAI(PromptConstructorMixin, InvigilatorBase):
    """An invigilator that uses an AI model to answer questions."""

    async def async_answer_question(self, failed: bool = False) -> AgentResponseDict:
        """Answer a question using the AI model."""
        params = self.get_prompts() | {"iteration": self.iteration}
        raw_response = await self.async_get_response(**params)
        assert "raw_model_response" in raw_response
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
        return AgentResponseDict(**response)

    async def async_get_response(
        self, user_prompt: Prompt, system_prompt: Prompt, iteration: int = 1
    ) -> dict:
        """Call the LLM and gets a response. Used in the `answer_question` method."""
        try:
            response = await self.model.async_get_response(
                user_prompt=user_prompt.text,
                system_prompt=system_prompt.text,
                iteration=iteration,
                cache=self.cache,
            )

        # TODO: I *don't* think we need to delete the cache key here because I think
        # it will not have been set yet; the exception would have been raised before.
        except json.JSONDecodeError as e:
            raise AgentRespondedWithBadJSONError(
                f"Returned bad JSON: {e}"
                f"Prompt: {user_prompt}"
                f"System Prompt: {system_prompt}"
            )

        return response

    def _format_raw_response(
        self, *, agent, question, scenario, raw_response, raw_model_response
    ) -> AgentResponseDict:
        """Return formatted raw response.

        This cleans up the raw response to make it suitable to pass to AgentResponseDict.
        """
        try:
            response = question._validate_answer(raw_response)
        except Exception as e:
            print("Purging the cache key")
            if (
                "raw_model_response" in raw_response
                and "cache_key" in raw_response["raw_model_response"]
            ):
                cache_key = raw_response["raw_model_response"]["cache_key"]
            else:
                cache_key = None
            del self.cache.data[cache_key]
            raise e

        comment = response.get("comment", "")
        answer_code = response["answer"]
        answer = question._translate_answer_code_to_answer(answer_code, scenario)
        raw_model_response = raw_model_response
        data = {
            "answer": answer,
            "comment": comment,
            "question_name": question.question_name,
            "prompts": {k: v.to_dict() for k, v in self.get_prompts().items()},
            "cached_response": raw_response["cached_response"],
            "usage": raw_response.get("usage", {}),
            "raw_model_response": raw_model_response,
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
            "user_prompt": Prompt("NA").text,
            "system_prompt": Prompt("NA").text,
        }


class InvigilatorHuman(InvigilatorBase):
    """An invigilator for when a human is answering the question."""

    async def async_answer_question(self, iteration: int = 0) -> AgentResponseDict:
        """Return the answer to the question."""
        data = {
            "comment": "This is a real survey response from a human.",
            "answer": None,
            "prompts": self.get_prompts(),
            "question_name": self.question.question_name,
        }
        try:
            answer = self.agent.answer_question_directly(self.question, self.scenario)
            return AgentResponseDict(**(data | {"answer": answer}))
        except Exception as e:
            agent_response_dict = AgentResponseDict(
                **(data | {"answer": None, "comment": str(e)})
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
            return AgentResponseDict(**(data | {"answer": answer}))
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
            "user_prompt": Prompt("NA").text,
            "system_prompt": Prompt("NA").text,
        }


if __name__ == "__main__":
    pass
#    from edsl.enums import LanguageModelType

# from edsl.agents.Agent import Agent

# a = Agent(
#     instruction="You are a happy-go lucky agent.",
#     traits={"feeling": "happy", "age": "Young at heart"},
#     codebook={"feeling": "Feelings right now", "age": "Age in years"},
#     trait_presentation_template="",
# )

# class MockModel:
#     """Mock model for testing."""

#     model = LanguageModelType.GPT_4.value

# class MockQuestion:
#     """Mock question for testing."""

#     question_type = "free_text"
#     question_text = "How are you feeling?"
#     question_name = "feelings_question"
#     data = {
#         "question_name": "feelings",
#         "question_text": "How are you feeling?",
#         "question_type": "feelings_question",
#     }

# i = InvigilatorAI(
#     agent=a,
#     question=MockQuestion(),
#     scenario={},
#     model=MockModel(),
#     memory_plan=None,
#     current_answers=None,
# )
# print(i.get_prompts()["system_prompt"])
# assert i.get_prompts()["system_prompt"].text == "You are a happy-go lucky agent."

# ###############
# ## Render one
# ###############

# a = Agent(
#     instruction="You are a happy-go lucky agent.",
#     traits={"feeling": "happy", "age": "Young at heart"},
#     codebook={"feeling": "Feelings right now", "age": "Age in years"},
#     trait_presentation_template="You are feeling {{ feeling }}.",
# )

# i = InvigilatorAI(
#     agent=a,
#     question=MockQuestion(),
#     scenario={},
#     model=MockModel(),
#     memory_plan=None,
#     current_answers=None,
# )
# print(i.get_prompts()["system_prompt"])

# assert (
#     i.get_prompts()["system_prompt"].text
#     == "You are a happy-go lucky agent. You are feeling happy."
# )
# try:
#     assert i.get_prompts()["system_prompt"].unused_traits(a.traits) == ["age"]
# except AssertionError:
#     unused_traits = i.get_prompts()["system_prompt"].unused_traits(a.traits)
#     print(f"System prompt: {i.get_prompts()['system_prompt']}")
#     print(f"Agent traits: {a.traits}")
#     print(f"Unused_traits: {unused_traits}")
#     # breakpoint()

# ###############
# ## Render one
# ###############

# a = Agent(
#     instruction="You are a happy-go lucky agent.",
#     traits={"feeling": "happy", "age": "Young at heart"},
#     codebook={"feeling": "Feelings right now", "age": "Age in years"},
#     trait_presentation_template="You are feeling {{ feeling }}. You eat lots of {{ food }}.",
# )

# i = InvigilatorAI(
#     agent=a,
#     question=MockQuestion(),
#     scenario={},
#     model=MockModel(),
#     memory_plan=None,
#     current_answers=None,
# )
# print(i.get_prompts()["system_prompt"])

# ## Should raise a QuestionScenarioRenderError
# assert (
#     i.get_prompts()["system_prompt"].text
#     == "You are a happy-go lucky agent. You are feeling happy."
# )
