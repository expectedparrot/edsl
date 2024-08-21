import random
from typing import Dict, List, Any, TypeVar, Generator, Optional

from textwrap import dedent

# from edsl.language_models.model_interfaces.LanguageModelOpenAIFour import LanguageModelOpenAIFour
from edsl import Model
from edsl.agents.AgentList import AgentList
from edsl.results.Results import Results
from edsl import Agent

from edsl import Scenario
from edsl.surveys.Survey import Survey

from edsl.questions.QuestionMultipleChoice import QuestionMultipleChoice
from edsl.questions.QuestionFreeText import QuestionFreeText
from edsl.auto.utilities import gen_pipeline
from edsl.conjure.naming_utilities import sanitize_string

random.seed("edsl")

m = Model()


def agent_eligibility(agent, survey):
    questions = [q.question_text for q in survey._questions]
    persona = agent.traits["persona"]
    q = QuestionMultipleChoice(
        question_text=dedent(
            """\
        Consider this set of question: {{ questions }}.
        Consider this persona: {{ persona }}.
        Would this persona be able to answer all of these questions?
        """
        ),
        question_options=["Yes", "No"],
        question_name="eligibility",
    )
    results = q.by(m).by(Scenario({"questions": questions, "persona": persona})).run()
    return results.select("eligibility").first() == "Yes"


def agent_generator(persona, dimension_dict: dict) -> Generator["Results", None, None]:
    q = QuestionFreeText(
        question_text=dedent(
            """\
    Consider this persona: '{{ persona }}'.
    Now imagine writing a new persona with these traits: 
    {{ new_agent_traits }}
    Please write this persona as a narrative.
    """
        ),
        question_name="new_agent_persona",
    )
    codebook = {sanitize_string(k): k for k in dimension_dict.keys()}
    while True:
        new_agent_traits = {}
        for key, list_of_values in dimension_dict.items():
            new_agent_traits[key] = random.choice(list_of_values)
        results = (
            q.by(m)
            .by(
                Scenario(
                    {
                        "persona": persona,
                        "new_agent_traits": new_agent_traits,
                        "codebook": codebook,
                    }
                )
            )
            .run()
        )
        yield results


def create_agents(
    agent_generator: Generator[Results, None, None],
    survey: Optional[Survey] = None,
    num_agents=11,
) -> AgentList:
    agent_list = AgentList([])

    while len(agent_list) < num_agents:
        candidate_agent = next(agent_generator)
        codebook = candidate_agent.select("codebook").to_list()[0]

        koobedoc = {v: k for k, v in codebook.items()}
        persona = candidate_agent.select("new_agent_persona").to_list()[0]
        traits = candidate_agent.select("new_agent_traits").to_list()[0]
        # [persona], [traits] = candidate_agent.select(
        #     "new_agent_persona", "new_agent_traits"
        # ).to_list()
        new_traits = {}
        for key, value in traits.items():
            new_traits[koobedoc[key]] = value
        new_traits.update({"persona": persona})
        agent = Agent(traits=new_traits, codebook=codebook)
        if survey is not None:
            if agent_eligibility(agent, survey):
                agent_list.append(agent)
            else:
                print("Agent not eligible")
        else:
            agent_list.append(agent)

    return agent_list
