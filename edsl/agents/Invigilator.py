from abc import ABC, abstractmethod
import json
from edsl.exceptions import AgentRespondedWithBadJSONError


class InvigilatorBase(ABC):
    def __init__(self, agent, question, scenario, model):
        self.agent = agent
        self.question = question
        self.scenario = scenario
        self.model = model

    @abstractmethod
    def answer_question(self):
        pass


class InvigilatorDebug(InvigilatorBase):
    def answer_question(self):
        return self.question.simulate_answer(human_readable=True)


class InvigilatorHuman(InvigilatorBase):
    def answer_question(self):
        answer = self.agent.answer_question_directly(self.question.question_name)
        response = {"answer": answer}
        response = self.question.validate_response(response)
        response["model"] = "human"
        response["scenario"] = self.scenario
        return response


class InvigilatorFunctional(InvigilatorBase):
    def answer_question(self):
        func = self.question.answer_question_directly
        return func(scenario=self.scenario, agent_traits=self.agent.traits)


class InvigilatorAI(InvigilatorBase):
    def construct_system_prompt(self) -> str:
        """Constructs the system prompt for the LLM call."""
        instruction = self.agent.instruction
        traits = f"Your traits are: {self.agent.traits}."
        return f"{instruction} {traits}"

    def get_response(self, prompt: str, system_prompt):
        """Calls the LLM and gets a response. Used in the `answer_question` method."""
        try:
            response = self.model.get_response(prompt, system_prompt)
        except json.JSONDecodeError as e:
            raise AgentRespondedWithBadJSONError(
                f"Returned bad JSON: {e}"
                f"Prompt: {prompt}"
                f"System Prompt: {system_prompt}"
            )

        return response

    def answer_question(self):
        # actual answers (w/ API call)
        #  get answer
        system_prompt = self.construct_system_prompt()
        prompt = self.question.get_prompt(self.scenario)
        response = self.get_response(prompt, system_prompt)
        #  validate answer
        response = self.question.validate_response(response)
        response = self.question.validate_answer(response)
        answer_code = response["answer"]
        response["answer"] = self.question.translate_answer_code_to_answer(
            answer_code, self.scenario
        )
        return response
