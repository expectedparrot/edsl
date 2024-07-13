from typing import Dict, Any

from edsl.prompts.Prompt import Prompt
from edsl.utilities.decorators import sync_wrapper, jupyter_nb_handler
from edsl.prompts.registry import get_classes as prompt_lookup
from edsl.exceptions import QuestionScenarioRenderError


class PromptConstructorMixin:
    """Mixin for constructing prompts for the LLM call.
    This is mixed into the Invigilator class.
    """
    def construct_system_prompt(self) -> Prompt:
        """Construct the system prompt for the LLM call."""

        agent_instructions = self._get_agent_instructions_prompt()
        persona_prompt = self._get_persona_prompt()

        return (
            agent_instructions
            + " " * int(len(persona_prompt.text) > 0)
            + persona_prompt
        )

    def _get_persona_prompt(self) -> Prompt:
        """Get the persona prompt.

        The is the description of the agent to the LLM.

        >>> from edsl.agents.InvigilatorBase import InvigilatorBase
        >>> i = InvigilatorBase.example()
        >>> i._get_persona_prompt()
        Prompt(text=\"""You are an agent with the following persona:
        {'age': 22, 'hair': 'brown', 'height': 5.5}\""")

        The agent_persona is constructed when the Agent is created.
        If the agent is passed a template for "agent_trait_presentation_template" that is used to construct the persona.
        If it does not exist, the persona is looked up in the prompt registry
        """
        if not hasattr(self.agent, "agent_persona"):
            applicable_prompts = prompt_lookup(
                component_type="agent_persona",
                model=self.model.model,
            )
            persona_prompt_template = applicable_prompts[0]()
        else:
            persona_prompt_template = self.agent.agent_persona

        # TODO: This multiple passing of agent traits - not sure if it is necessary. Not harmful.
        if undefined := persona_prompt_template.undefined_template_variables(
            self.agent.traits
            | {"traits": self.agent.traits}
            | {"codebook": self.agent.codebook}
            | {"traits": self.agent.traits}
        ):
            raise QuestionScenarioRenderError(
                f"Agent persona still has variables that were not rendered: {undefined}"
            )

        persona_prompt = persona_prompt_template.render(
            self.agent.traits | {"traits": self.agent.traits},
            codebook=self.agent.codebook,
            traits=self.agent.traits,
        )

        if persona_prompt.has_variables:
            raise QuestionScenarioRenderError(
                "Agent persona still has variables that were not rendered."
            )
        return persona_prompt

    def _get_agent_instructions_prompt(self) -> Prompt:
        """Get the agent instructions prompt.
        
        >>> from edsl.agents.InvigilatorBase import InvigilatorBase
        >>> i = InvigilatorBase.example()
        >>> i._get_agent_instructions_prompt()
        Prompt(text=\"""You are answering questions as if you were a human. Do not break character.\""")
        
        """
        applicable_prompts = prompt_lookup(
            component_type="agent_instructions",
            model=self.model.model,
        )
        if len(applicable_prompts) == 0:
            raise Exception("No applicable prompts found")
        return applicable_prompts[0](text=self.agent.instruction)

    def _get_question_instructions(self) -> Prompt:
        """Get the instructions for the question.
        
        >>> from edsl.agents.InvigilatorBase import InvigilatorBase
        >>> i = InvigilatorBase.example()
        >>> i._get_question_instructions()
        Prompt(text=\"""You are being asked the following question: Do you like school?
        The options are
        <BLANKLINE>
        0: yes
        <BLANKLINE>
        1: no
        <BLANKLINE>
        Return a valid JSON formatted like this, selecting only the number of the option:
        {"answer": <put answer code here>, "comment": "<put explanation here>"}
        Only 1 option may be selected.\""")
        

        >>> from edsl import QuestionFreeText 
        >>> q = QuestionFreeText(question_text = "Consider {{ X }}. What is your favorite color?", question_name = "q_color")
        >>> from edsl.agents.InvigilatorBase import InvigilatorBase
        >>> i = InvigilatorBase.example(question = q)
        >>> i._get_question_instructions()
        Traceback (most recent call last):
        ...
        edsl.exceptions.questions.QuestionScenarioRenderError: Question instructions still has variables: ['X'].

        
        >>> from edsl import QuestionFreeText 
        >>> q = QuestionFreeText(question_text = "You were asked the question '{{ q0.question_text }}'. What is your favorite color?", question_name = "q_color")
        >>> from edsl.agents.InvigilatorBase import InvigilatorBase
        >>> i = InvigilatorBase.example(question = q)
        >>> i._get_question_instructions()
        Prompt(text=\"""You are being asked the following question: You were asked the question 'Do you like school?'. What is your favorite color?
        Return a valid JSON formatted like this:
        {"answer": "<put free text answer here>"}\""")

        >>> from edsl import QuestionFreeText 
        >>> q = QuestionFreeText(question_text = "You stated '{{ q0.answer }}'. What is your favorite color?", question_name = "q_color")
        >>> from edsl.agents.InvigilatorBase import InvigilatorBase
        >>> i = InvigilatorBase.example(question = q)
        >>> i.current_answers = {"q0": "I like school"}
        >>> i._get_question_instructions()
        Prompt(text=\"""You are being asked the following question: You stated 'I like school'. What is your favorite color?
        Return a valid JSON formatted like this:
        {"answer": "<put free text answer here>"}\""")
                
        """
        question_prompt = self.question.get_instructions(model=self.model.model)

        # TODO: Try to populate the answers in the question object if they are available
        d = self.survey.question_names_to_questions()
        for question, answer in self.current_answers.items():
            d[question].answer = answer

        rendered_instructions = question_prompt.render(self.question.data | self.scenario | d)

        undefined_template_variables = rendered_instructions.undefined_template_variables({})

        # Check if it's the name of a question in the survey
        for question_name in self.survey.question_names:
            if question_name in undefined_template_variables:
                print("Question name found in undefined_template_variables: ", question_name) 

        if undefined_template_variables:
            print(undefined_template_variables)
            raise QuestionScenarioRenderError(
                f"Question instructions still has variables: {undefined_template_variables}."
            )
        
        return rendered_instructions
    
    def construct_user_prompt(self) -> Prompt:
        """Construct the user prompt for the LLM call.
        
        >>> from edsl.agents.InvigilatorBase import InvigilatorBase
        >>> i = InvigilatorBase.example()
        >>> i.construct_user_prompt()
        Prompt(text=\"""You are being asked the following question: Do you like school?
        The options are
        <BLANKLINE>
        0: yes
        <BLANKLINE>
        1: no
        <BLANKLINE>
        Return a valid JSON formatted like this, selecting only the number of the option:
        {"answer": <put answer code here>, "comment": "<put explanation here>"}
        Only 1 option may be selected.\""")
            
        """
        user_prompt = self._get_question_instructions()
        if self.memory_plan is not None:
            user_prompt += self.create_memory_prompt(
                self.question.question_name
            ).render(self.scenario)
        return user_prompt
    
    def _get_scenario_with_image(self) -> Dict[str, Any]:
        from edsl import Scenario
        try:
            scenario = Scenario.from_image("../../static/logo.png")
        except FileNotFoundError:
            scenario = Scenario.from_image("static/logo.png")
        return scenario
 
    def get_prompts(self) -> Dict[str, Prompt]:
        """Get both prompts for the LLM call.
        
        >>> from edsl import QuestionFreeText
        >>> from edsl.agents.InvigilatorBase import InvigilatorBase
        >>> q = QuestionFreeText(question_text="How are you today?", question_name="q0")
        >>> i = InvigilatorBase.example(question = q)
        >>> i.get_prompts()
        {'user_prompt': ..., 'system_prompt': ...}
        >>> scenario = i._get_scenario_with_image() 
        >>> scenario.has_image
        True
        >>> q = QuestionFreeText(question_text="How are you today?", question_name="q0")
        >>> i = InvigilatorBase.example(question = q, scenario = scenario)
        >>> i.get_prompts()
        {'user_prompt': ..., 'system_prompt': ..., 'encoded_image': ...'}
        """
        system_prompt = self.construct_system_prompt()
        user_prompt = self.construct_user_prompt()
        prompts = {
            "user_prompt": user_prompt,
            "system_prompt": system_prompt,
        }
        if hasattr(self.scenario, "has_image") and self.scenario.has_image:
            prompts["encoded_image"] = self.scenario["encoded_image"]
        return prompts


if __name__ == "__main__":
    import doctest
    doctest.testmod(optionflags=doctest.ELLIPSIS)
    # from edsl import Model
    # from edsl import Agent

    # a = Agent(
    #     instruction="You are a happy-go lucky agent.",
    #     traits={"feeling": "happy", "age": "Young at heart"},
    #     codebook={"feeling": "Feelings right now", "age": "Age in years"},
    #     trait_presentation_template="",
    # )
    # p = PromptConstructorMixin()
    # p.model = Model(Model.available()[0])
    # p.agent = a
    # instructions = p._get_agent_instructions_prompt()
    # repr(instructions)

    # persona = p._get_persona_prompt()
    # repr(persona)
