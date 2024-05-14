import itertools
import logging
import json
import os
from edsl import __version__ as edsl_version
from edsl.Base import RegisterSubclassesMeta
from edsl import Scenario, Survey, Agent, Model
from edsl.questions import *
logging.basicConfig(level=logging.INFO, format="%(levelname)s\t%(message)s")

def run_complex_survey():
    all_question_types = [subclass for class_name, subclass in RegisterQuestionsMeta.get_registered_classes().items() if class_name != "QuestionFunctional"]

    ### Use example questions for each question class
    questions = [q.example() for q in all_question_types]

    scenario_dict = {}

    ### Use question extract
    simpsons = """
    "The Simpsons" is an iconic American animated sitcom created by Matt Groening that debuted in 1989 on the Fox network. 
    The show is set in the fictional town of Springfield and centers on the Simpsons family, consisting of the bumbling but well-intentioned father Homer, the caring and patient mother Marge, and their three children: mischievous Bart, intelligent Lisa, and baby Maggie. 
    Renowned for its satirical take on the typical American family and society, the series delves into themes of politics, religion, and pop culture with a distinct blend of humor and wit. 
    Its longevity, marked by over thirty seasons, makes it one of the longest-running television series in history, influencing many other sitcoms and becoming deeply ingrained in popular culture.
    """
    q_extract = QuestionExtract(
        question_name = "q_extract",
        question_text = "Review the following text: {{ q_extract_content }}",
        answer_template = {"main_characters_list": ["name", "name"], 
                        "location": "location",
                        "genre": "genre"},
    )
    questions.append(q_extract)

    scenario_dict["q_extract_content"] = simpsons

    ####### Use QuestionList QuestionCheckboxes with different scenarios
    q_list_themes = QuestionList(
        question_name = "concepts",
        question_text = """Identify the key concepts in the following text: {{ text }}""",
        max_list_items = 4
    )
    q__multiple_choice_sentiment = QuestionMultipleChoice(
        question_name = "sentiment",
        question_text = "Identify the sentiment of this text: {{ text }}",
        question_options = ["Positive", "Neutral", "Negative"]
    )
    questions.append(q_list_themes)
    questions.append(q__multiple_choice_sentiment)
    texts = [ # POTUS recent tweets
        "Tune in as I deliver the keynote address at the U.S. Holocaust Memorial Museum’s Annual Days of Remembrance ceremony in Washington, D.C.",
        "We’re a nation of immigrants. A nation of dreamers. And as Cinco de Mayo represents, a nation of freedom.",
        "Medicare is stronger and Social Security remains strong. My economic plan has helped extend Medicare solvency by a decade. And I am committed to extending Social Security solvency by making the rich pay their fair share.",
        "Today, the Army Black Knights are taking home West Point’s 10th Commander-in-Chief Trophy. They should be proud. I’m proud of them too – not for the wins, but because after every game they hang up their uniforms and put on another: one representing the United States.",
        "This Holocaust Remembrance Day, we mourn the six million Jews who were killed by the Nazis during one of the darkest chapters in human history. And we recommit to heeding the lessons of the Shoah and realizing the responsibility of 'Never Again.'",
        "The recipients of the Presidential Medal of Freedom haven't just kept faith in freedom. They kept all of America's faith in a better tomorrow.",
        "Like Jill says, 'Teaching isn’t just a job. It’s a calling.' She knows that in her bones, and I know every educator who joined us at the White House for the first-ever Teacher State Dinner lives out that truth every day.",
        "Jill and I send warm wishes to Orthodox Christian communities around the world as they celebrate Easter. May the Lord bless and keep you this Easter Sunday and in the year ahead.",
        "Dreamers are our loved ones, nurses, teachers, and small business owners – they deserve the promise of health care just like all of us. Today, my Administration is making that real by expanding affordable health coverage through the Affordable Care Act to DACA recipients.",
        "With today’s report of 175,000 new jobs, the American comeback continues. Congressional Republicans are fighting to cut taxes for billionaires and let special interests rip folks off, I'm focused on job creation and building an economy that works for the families I grew up with."
    ]
    scenarios = [Scenario({"text":e,**scenario_dict}) for e in texts]

    ####  questions for skip rules 
    q_color_mc = QuestionMultipleChoice(
        question_name = "color",
        question_text = "What is your favorite color?",
        question_options = ["Red", "Orange", "Yellow", "Green", "Blue", "Purple"]
    )
    q_day_mc = QuestionMultipleChoice(
        question_name = "day",
        question_text = "What is your favorite day of the week?",
        question_options = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
    )
    q_winter_ls = QuestionLinearScale(
        question_name = "winter",
        question_text = "How much do you enjoy winter?",
        question_options = [0,1,2,3,4,5],
        option_labels = {0: "Hate it", 5: "Love it"}
    )
    q_birds_tk = QuestionTopK(
        question_name = "birds",
        question_text = "Which birds do you like best?",
        question_options = ["Parrot", "Osprey", "Falcon", "Eagle", "First Robin of Spring"],
        min_selections = 2,
        max_selections = 2
    )

    questions.extend([q_color_mc,q_day_mc,q_winter_ls,q_birds_tk])


    survey = Survey(questions=questions)

    ### Add skip logic
    survey = survey.add_skip_rule(q_birds_tk, "color == 'Blue'")
    survey = survey.add_stop_rule(q_color_mc, "color == 'Blue'")
    survey = survey.add_rule(q_color_mc, "color == 'Red'", q_winter_ls)

    ### Use memory
    survey = survey.set_lagged_memory(3)
    survey = survey.add_memory_collection(q_winter_ls, [questions[0], questions[1]])


    ### Use agents traits
    personas = ["You are a scientist", "You are a chef"]
    ages = [20,40,60]
    agents = [Agent(traits={"persona": p, "age": a}) for p, a in zip(personas, ages)]

    ### Use multiple models
    models = [Model("gpt-3.5-turbo"),Model("gpt-4-1106-preview")]

    # Run the survey with agents, and models
    scenario = Scenario(scenarios)
    results = survey.by(scenarios).by(agents).by(models).run()
    #results.select("answer.*").print(format = "rich")

    return results


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

    logging.info(f"Found {len(data)} registerd classes")
    # check if all registered have edsl_version in the dict
    for item in data:
        if "edsl_version" not in item["dict"]:
            logging.warning(
                f"Class: {item['class_name']} does not have edsl_version in the dict"
            )

    # C. Create custom / more complex examples

    # 1. a simple survey that has been run
    s = RegisterSubclassesMeta.get_registry()["Survey"].example()
    r = s.run()
    data.append(
        {
            "class_name": "Results",
            "class": RegisterSubclassesMeta.get_registry()["Results"],
            "example": r,
            "dict": r.to_dict(),
        }
    )
    # 2. complex example
    survey_results = run_complex_survey()
    data.append(
        {
            "class_name":"Results",
            "class": RegisterSubclassesMeta.get_registry()["Results"],
            "example": survey_results,
            "dict":survey_results.to_dict()}
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
