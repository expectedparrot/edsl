from textwrap import dedent
import random
from typing import List, TypeVar, Generator, Optional
from edsl.auto.StageBase import StageBase
from edsl.utilities.naming_utilities import sanitize_string
from edsl import Agent, Survey, Model, Cache, AgentList
from edsl import QuestionFreeText, Scenario
from edsl import QuestionMultipleChoice, Scenario, Agent, ScenarioList

StageClassType = TypeVar("StageClassType", bound=StageBase)


def gen_pipeline(stages_list: List[StageClassType]) -> StageBase:
    """Takes as input a list of Stage classes & returns a pipeline of instantiated stages.
    A pipeline is a linked list of stages where each stage has a next_stage attribute.

    """
    pipeline = stages_list[0]()
    last_stage = pipeline
    for stage in stages_list[1:]:
        while last_stage.next_stage is not None:  # find the end of the pipeline
            last_stage = last_stage.next_stage
        stage_to_add = stage()
        last_stage.next_stage = stage_to_add
    return pipeline


q_eligibility = QuestionMultipleChoice(
    question_text=dedent(
        """\
        Consider this set of question: '{{ questions }}'.
        Consider this persona: '{{ persona }}'.
        Would this persona be able to answer all of these questions?
        """
    ),
    question_options=["No", "Yes"],
    question_name="eligibility",
)


def agent_list_eligibility(
    agent_list: AgentList,
    survey: Optional[Survey] = None,
    model: Optional[Model] = None,
    cache: Optional[Cache] = None,
) -> List[bool]:
    """
    Returns whether each agent in a list is elgible for a survey i.e., can answer every question.

    >>> from edsl.language_models import LanguageModel
    >>> m = LanguageModel.example(canned_response = "1", test_model = True)
    >>> agent_list_eligibility(AgentList.example())
    [True, True]
    >>> agent_list_eligibility(AgentList.example().add_trait('persona', 2*["Cool dude"]), survey = Survey.example(), model = m)
    [True, True]
    """
    if survey is None:
        return [True] * len(agent_list)
    if "persona" not in agent_list.all_traits:
        raise ValueError(
            f"Each agent needs to have a persona attribute; traits are {agent_list.all_traits}"
        )
    sl = agent_list.select("persona").to_scenario_list()
    sl.add_value("questions", [q.question_text for q in survey._questions])
    results = q_eligibility.by(sl).by(model).run(cache=cache)
    return [r == "Yes" for r in results.select("eligibility").to_list()]


def agent_eligibility(
    agent: Agent,
    survey: Survey,
    model: Optional[Model] = None,
    cache: Optional[Cache] = None,
) -> bool:
    """NB: This could be parallelized.

    >>> from edsl.language_models import LanguageModel
    >>> m = LanguageModel.example(canned_response = "1", test_model = True)
    >>> agent_eligibility(agent = Agent.example().add_trait({'persona': "Persona"}), survey = Survey.example(), model = m)
    True

    """
    model = model or Model()

    questions = [q.question_text for q in survey._questions]
    persona = agent.traits["persona"]
    return (
        q_eligibility(model=model, questions=questions, persona=persona, cache=cache)
        == "Yes"
    )
    # results = (
    #     q.by(model)
    #     .by(Scenario({"questions": questions, "persona": persona}))
    #     .run(cache=cache)
    # )
    # return results.select("eligibility").first() == "Yes"


def gen_agent_traits(dimension_dict: dict, seed_value: Optional[str] = None):
    """
    >>> dimension_dict = {'attitude':['positive', 'negative']}
    >>> ag = gen_agent_traits(dimension_dict)
    >>> a = next(ag)
    >>> a == {'attitude': 'positive'} or a == {'attitude': 'negative'}
    True
    >>> len([next(ag) for _ in range(100)])
    100
    """
    if seed_value is None:
        seed_value = "edsl"

    random.seed(seed_value)

    while True:
        new_agent_traits = {}
        for key, list_of_values in dimension_dict.items():
            new_agent_traits[key] = random.choice(list_of_values)
        yield new_agent_traits


def agent_generator(
    persona: str,
    dimension_dict: dict,
    model: Optional[Model] = None,
    cache: Optional["Cache"] = None,
) -> Generator["Results", None, None]:
    """
    >>> from edsl.language_models import LanguageModel
    >>> m = LanguageModel.example(canned_response = "This is a cool dude.", test_model = True)
    >>> ag = agent_generator(persona = "Base person", dimension_dict = {'attitude':['Positive', 'Negative']}, model = m)
    >>> next(ag).select('new_agent_persona').first()
    'This is a cool dude.'
    >>> next(ag).select('new_agent_persona').first()
    'This is a cool dude.'
    """

    if model is None:
        model = Model()

    q = QuestionFreeText(
        question_text=dedent(
            """\
    Consider this persona: '{{ persona }}'.
    Now imagine writing a new persona with these traits: 
    '{{ new_agent_traits }}'
    Please write this persona as a narrative.
    """
        ),
        question_name="new_agent_persona",
    )
    agent_trait_generator = gen_agent_traits(dimension_dict)
    codebook = {sanitize_string(k): k for k in dimension_dict.keys()}
    while True:
        new_agent_traits = next(agent_trait_generator)
        yield q(
            persona=persona,
            new_agent_traits=new_agent_traits,
            codebook=codebook,
            just_answer=False,
            cache=cache,
            model=model,
        )


def create_agents(
    agent_generator: Generator["Results", None, None],
    survey: Optional[Survey] = None,
    num_agents=11,
) -> AgentList:
    """
    >>> from edsl.language_models import LanguageModel
    >>> m = LanguageModel.example(canned_response = "This is a cool dude.", test_model = True)
    >>> ag = agent_generator(persona = "Base person", dimension_dict = {'attitude':['Positive', 'Negative']}, model = m)
    >>> new_agent_list = create_agents(agent_generator = ag)
    >>> new_agent_list

    """
    agent_list = AgentList([])

    MAX_ITERATIONS_MULTIPLIER = 2
    iterations = 0

    while len(agent_list) < num_agents:
        iterations += 1
        candidate_agent = next(agent_generator)
        codebook = candidate_agent.select("codebook").to_list()[0]

        koobedoc = {v: k for k, v in codebook.items()}
        persona = candidate_agent.select("new_agent_persona").to_list()[0]
        traits = candidate_agent.select("new_agent_traits").to_list()[0]
        new_traits = {koobedoc[key]: value for key, value in traits.items()} | {
            "persona": persona
        }
        agent = Agent(traits=new_traits, codebook=codebook)
        if survey is not None:
            if agent_eligibility(agent, survey):
                agent_list.append(agent)
            else:
                print("Agent not eligible")
        else:
            agent_list.append(agent)

        if iterations > MAX_ITERATIONS_MULTIPLIER * num_agents:
            raise Exception("Too many failures")

    return agent_list


if __name__ == "__main__":
    import doctest

    doctest.testmod()
    # from edsl.language_models import LanguageModel

    # m = LanguageModel.example(canned_response="This is a cool dude.", test_model=True)
    # ag = agent_generator(
    #     persona="Base person",
    #     dimension_dict={"attitude": ["Positive", "Negative"]},
    #     model=m,
    # )
    # example = [next(ag).select("new_agent_persona").first() for _ in range(10)]
    # dimension_dict = {"attitude": ["positive", "negative"]}
    # ag = gen_agent_traits(dimension_dict)
    # example = [next(ag) for _ in range(100)]
