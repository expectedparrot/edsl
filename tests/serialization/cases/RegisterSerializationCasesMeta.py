import logging
from abc import ABCMeta
from edsl import Agent, Model, Scenario, Survey
from edsl.questions import *


class RegisterSerializationCasesMeta(ABCMeta):
    _test_cases = {}

    def __init__(cls, name, bases, dct):
        """Initialize the class and add its test cases to the registry."""

        super().__init__(name, bases, dct)

        if name != "SerializationBase":
            # Object should be the name of an EDSL object, e.g., Results, Agent, Notebook,...
            # This will be used in the deserialization tests
            object = dct.get("object")
            if object is None:
                raise AttributeError(f"{name} must have an 'object' attribute.")

            # Create a dict for object tests
            if object not in cls._test_cases:
                cls._test_cases[object] = {}

            # Register the class and its test methods
            cls._test_cases[object][name] = {"class": cls, "test_cases": []}
            for attr_name, attr_value in dct.items():
                if callable(attr_value) and attr_name.startswith("test_"):
                    cls._test_cases[object][name]["test_cases"].append(attr_name)

    @classmethod
    def get_registered_test_cases(cls):
        """Return the registry of registered test cases."""
        return cls._test_cases

    @classmethod
    def generate_custom_example_data(mcs, container: list):
        """
        Generate serialization data for custom examples by running the methods in the ._tests registry.

        :param container: The data from custom examples will be appended to this list.
        """

        for object_name, object_tests in mcs._test_cases.items():
            for test_class_name, test_class_info in object_tests.items():
                # Create an instance of the test class and run tests
                test_class = test_class_info["class"]
                instance = test_class()

                for method_name in test_class_info["test_cases"]:
                    logging.info(f"Running {test_class_name}.{method_name}...")
                    test_method = getattr(instance, method_name)

                    # Call test method directly
                    test_case_data = test_method()
                    container.append(
                        {"class_name": object_name, "dict": test_case_data.to_dict()}
                    )


class SerializationBase(metaclass=RegisterSerializationCasesMeta):
    pass


class ResultsSerializationCases(SerializationBase):
    object = "Results"

    @staticmethod
    def configure_agents_and_models(s: Survey):
        personas = ["You are a scientist", "You are a chef"]
        ages = [20, 40]
        agents = [
            Agent(traits={"persona": p, "age": a}) for p, a in zip(personas, ages)
        ]
        # Use multiple models
        models = [Model("gpt-3.5-turbo"), Model("gpt-4o")]

        s = s.by(agents).by(models)
        return s

    def test_simple_survey(self):
        s = Survey.example()
        s = self.configure_agents_and_models(s)
        result = s.run(
            cache=False, print_exceptions=False, disable_remote_inference=True
        )
        return result

    def test_all_questions_survey(self):
        all_question_types = [
            subclass
            for class_name, subclass in RegisterQuestionsMeta.get_registered_classes().items()
            if class_name != "QuestionFunctional"
        ]
        # Use example questions for each question class
        questions = [q.example() for q in all_question_types]
        s = Survey(questions=questions)
        # s = self.configure_agents_and_models(s)
        result = s.run(
            cache=False, print_exceptions=False, disable_remote_inference=True
        )
        return result

    def test_scenario_survey(self):
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
        # Use QuestionList and QuestionCheckboxes with different scenarios
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
        questions = [
            q_extract,
            q_list_themes,
            q_multiple_choice_sentiment,
        ]
        s = Survey(questions=questions).by(scenarios)
        # s = self.configure_agents_and_models(s)
        result = s.run(
            cache=False, print_exceptions=False, disable_remote_inference=True
        )
        return result

    def test_skip_logic_survey(self):
        #  Questions for skip rules
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
        questions = [q_color_mc, q_day_mc, q_winter_ls, q_birds_tk]
        s = Survey(questions=questions)
        # Add skip logic
        s = s.add_skip_rule(q_birds_tk, "color == 'Blue'")
        s = s.add_stop_rule(q_color_mc, "color == 'Blue'")
        s = s.add_rule(q_color_mc, "color == 'Red'", q_winter_ls)
        # Use memory
        s = s.set_lagged_memory(2)
        s = s.add_memory_collection(q_birds_tk, [q_color_mc])
        # s = self.configure_agents_and_models(s)
        result = s.run(
            cache=False, print_exceptions=False, disable_remote_inference=True
        )
        return result
