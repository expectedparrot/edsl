import itertools
import logging
import json
import os
from edsl import __version__ as edsl_version
from edsl.Base import RegisterSubclassesMeta
from edsl import Agent, Model, Jobs, Scenario, Survey
from edsl.questions import *
from typing import Union

logging.basicConfig(level=logging.INFO, format="%(levelname)s\t%(message)s")


def create_custom_surveys() -> list[Union[Jobs, Survey]]:

    # 1. Example survey
    simple_survey = Survey.example()

    # 2. All questions
    all_question_types = [
        subclass
        for class_name, subclass in RegisterQuestionsMeta.get_registered_classes().items()
        if class_name != "QuestionFunctional"
    ]
    ### Use example questions for each question class
    all_questions = [q.example() for q in all_question_types]
    all_questions_survey = Survey(questions=all_questions)

    # 3. Scenarios
    scenario_dict = {}
    simpsons = """
    "The Simpsons" is an iconic American animated sitcom created by Matt Groening that debuted in 1989 on the Fox network. 
    The show is set in the fictional town of Springfield and centers on the Simpsons family, consisting of the bumbling but well-intentioned father Homer, the caring and patient mother Marge, and their three children: mischievous Bart, intelligent Lisa, and baby Maggie. 
    Renowned for its satirical take on the typical American family and society, the series delves into themes of politics, religion, and pop culture with a distinct blend of humor and wit. 
    Its longevity, marked by over thirty seasons, makes it one of the longest-running television series in history, influencing many other sitcoms and becoming deeply ingrained in popular culture.
    """
    q_extract = QuestionExtract(
        question_name="q_extract",
        question_text="Review the following text: {{ q_extract_content }}",
        answer_template={
            "main_characters_list": ["name", "name"],
            "location": "location",
            "genre": "genre",
        },
    )
    scenario_dict["q_extract_content"] = simpsons
    ####### Use QuestionList and QuestionCheckboxes with different scenarios
    q_list_themes = QuestionList(
        question_name="concepts",
        question_text="""Identify the key concepts in the following text: {{ text }}""",
        max_list_items=4,
    )
    q_multiple_choice_sentiment = QuestionMultipleChoice(
        question_name="sentiment",
        question_text="Identify the sentiment of this text: {{ text }}",
        question_options=["Positive", "Neutral", "Negative"],
    )
    texts = [  # POTUS recent tweets
        "Tune in as I deliver the keynote address at the U.S. Holocaust Memorial Museum’s Annual Days of Remembrance ceremony in Washington, D.C.",
        "We’re a nation of immigrants. A nation of dreamers. And as Cinco de Mayo represents, a nation of freedom.",
        "Medicare is stronger and Social Security remains strong. My economic plan has helped extend Medicare solvency by a decade. And I am committed to extending Social Security solvency by making the rich pay their fair share.",
    ]
    scenarios = [Scenario({"text": e, **scenario_dict}) for e in texts]
    scenario_survey_questions = [q_extract, q_list_themes, q_multiple_choice_sentiment]
    scenario_survey = Survey(questions=scenario_survey_questions).by(scenarios)

    # 4. Skip logic
    ####  Questions for skip rules
    q_color_mc = QuestionMultipleChoice(
        question_name="color",
        question_text="What is your favorite color?",
        question_options=["Red", "Orange", "Yellow", "Green", "Blue", "Purple"],
    )
    q_day_mc = QuestionMultipleChoice(
        question_name="day",
        question_text="What is your favorite day of the week?",
        question_options=["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"],
    )
    q_winter_ls = QuestionLinearScale(
        question_name="winter",
        question_text="How much do you enjoy winter?",
        question_options=[0, 1, 2, 3, 4, 5],
        option_labels={0: "Hate it", 5: "Love it"},
    )
    q_birds_tk = QuestionTopK(
        question_name="birds",
        question_text="Which birds do you like best?",
        question_options=[
            "Parrot",
            "Osprey",
            "Falcon",
            "Eagle",
            "First Robin of Spring",
        ],
        min_selections=2,
        max_selections=2,
    )
    skip_logic_survey_questions = [q_color_mc, q_day_mc, q_winter_ls, q_birds_tk]
    skip_logic_survey = Survey(questions=skip_logic_survey_questions)
    ### Add skip logic
    skip_logic_survey = skip_logic_survey.add_skip_rule(q_birds_tk, "color == 'Blue'")
    skip_logic_survey = skip_logic_survey.add_stop_rule(q_color_mc, "color == 'Blue'")
    skip_logic_survey = skip_logic_survey.add_rule(
        q_color_mc, "color == 'Red'", q_winter_ls
    )
    ### Use memory
    skip_logic_survey = skip_logic_survey.set_lagged_memory(2)
    skip_logic_survey = skip_logic_survey.add_memory_collection(
        q_birds_tk, [q_color_mc]
    )
    surveys = [simple_survey, all_questions_survey, scenario_survey, skip_logic_survey]

    # Finally: configure models and agents
    ### Use agent traits
    personas = ["You are a scientist", "You are a chef"]
    ages = [20, 40, 60]
    agents = [Agent(traits={"persona": p, "age": a}) for p, a in zip(personas, ages)]
    ### Use multiple models
    models = [Model("gpt-3.5-turbo"), Model("gpt-4o")]

    # Finally: configure models and agents
    final_surveys = [survey.by(models).by(agents) for survey in surveys]

    return final_surveys


def create_serialization_test_data():
    global edsl_version
    if ".dev" in edsl_version:
        version = edsl_version.split(".dev")[0]
    else:
        version = edsl_version

    data = []
    path = f"tests/serialization/data/{version}.json"

    # A. check if the file already exists
    if os.path.exists(path):
        logging.info(f"`{path}` already exists.")
        return

    # B. Collect all registered classes
    combined_items = itertools.chain(
        RegisterSubclassesMeta.get_registry().items(),
        RegisterQuestionsMeta.get_registered_classes().items(),
    )

    for subclass_name, subclass in combined_items:
        example = subclass.example()
        data.append(
            {
                "class_name": subclass_name,
                "class": subclass,
                "example": example,
                "dict": example.to_dict(),
            }
        )

    logging.info(f"Found {len(data)} registered classes")
    # check if all registered have edsl_version in the dict
    for item in data:
        if "edsl_version" not in item["dict"]:
            logging.warning(
                f"Class: {item['class_name']} does not have edsl_version in the dict"
            )

    # C. Create custom / more complex examples

    custom_surveys = create_custom_surveys()
    for survey in custom_surveys:
        result = survey.run(cache=False)
        data.append(
            {
                "class_name": "Results",
                "class": RegisterSubclassesMeta.get_registry()["Results"],
                "example": result,
                "dict": result.to_dict(),
            }
        )

    # D. Write data to the file
    data_to_write = [
        {"class_name": item["class_name"], "dict": item["dict"]} for item in data
    ]
    with open(path, "w") as f:
        json.dump(data_to_write, f)
    logging.info(f"Serialization test data written to `{path}`.")
    logging.info("!!! DO NOT FORGET TO FORCE PUSH IT TO THE REPO !!!")


if __name__ == "__main__":
    create_serialization_test_data()
