from textwrap import dedent
from dataclasses import dataclass
from collections import defaultdict

from typing import List, Dict

from edsl.auto.StageBase import StageBase
from edsl.auto.utilities import gen_pipeline
from edsl.auto.StageBase import FlowDataBase

from edsl.auto.StageQuestions import StageQuestions
from edsl.auto.StageLabelQuestions import StageLabelQuestions

from edsl.questions import QuestionList
from edsl.scenarios import Scenario
from edsl import Model
from edsl.surveys import Survey
from edsl.questions import QuestionBase

from edsl.utilities.utilities import is_valid_variable_name
from edsl import Model
from edsl.questions import QuestionExtract


m = Model()


def chunker(seq, size):
    return (seq[pos : pos + size] for pos in range(0, len(seq), size))


def get_short_options(question_options, num_chars=20):
    """Gets short names for the options of a question
    >>> get_short_options(["No, I don't own a scooter", "Yes, I own a scooter"])
    {'No, I don\'t own a scooter': 'no_scooter', 'Yes, I own a scooter': 'yes_scooter'}
    """
    q = QuestionList(
        question_text=dedent(
            f"""\
            We need short (less than {num_chars} characters) names for the options of a question, with no spaces.
            E.g., if the options were "No, I don't own a scooter" and "Yes, I own a scooter", 
            you could use "no_scooter" and "yes_scooter".
            They should be all lower case. Use snake case.
            The short names have to be unique.
            The options are: {question_options}
            The names are {question_options} of them."""
        ),
        # answer_template={k: None for k in question_options},
        question_name="short_options",
    )
    results = q.by(m).run()
    return results.select("short_options").first()


def get_short_names_chunk(questions, num_chars=20):
    q = QuestionList(
        question_text=dedent(
            f"""\
            We need short (less than {num_chars} characters) names for the questions, with no spaces.
            E.g., if the question was: "What is your first name?", you could use "first_name".
            The short names have to be unique and not starting with numbers. They should be all lower case.
            The questions are: {questions}
            """
        ),
        question_name="short_names",
    )
    results = q.by(m).run()
    short_names = results.select("short_names").first()
    return {k: v for k, v in zip(questions, short_names)}


def get_short_names(questions, max_size=10, num_chars=20):
    "Gets short names for questions"
    if len(questions) <= max_size:
        short_names_dict = get_short_names_chunk(questions, num_chars)
    else:
        short_names_dict = {}
        for chunk in chunker(questions, max_size):
            results = get_short_names_chunk(chunk, num_chars)
            short_names_dict.update(results)
    return short_names_dict


class StageGenerateSurvey(StageBase):
    input = StageLabelQuestions.output

    @dataclass
    class Output(FlowDataBase):
        survey: Survey

    output = Output

    def handle_data(self, data):
        """This tage uses the question types to generate a survey
        It constucts the edsl-specific dictionary needed to create a question
        """
        # survey = Survey(name = {data.overall_question, population = data.population, description)
        survey = Survey()

        short_names = get_short_names(data.questions)

        question_count = -1
        for question, question_type, options, option_labels in zip(
            data.questions, data.types, data.options, data.option_labels
        ):
            question_count += 1
            short_names_dict = {}
            if question in short_names:
                short_names_dict[question] = short_names[question]
            data = {
                "question_text": question,
                "question_type": question_type,
                "question_name": short_names.get(question, f"q{question_count}"),
            }
            if options is not None:
                data["question_options"] = options
                # make sure it's not a linear scale question, in which case we don't want to add short names

            if option_labels is not None:
                data["option_labels"] = dict(zip(options, option_labels))
                # print(data["option_labels"])
                # breakpoint()

            if question_type == "linear_scale":
                option_keys = option_labels
            else:
                option_keys = options

            if options is not None:
                short_options = get_short_options(option_keys)
                short_names_dict.update(
                    {k: v for k, v in zip(option_keys, short_options)}
                )

            if question_type not in ["numerical", "free_text"]:
                data["short_names_dict"] = short_names_dict
            _ = data.pop("short_names_dict", None)
            q = QuestionBase.from_dict(data)
            survey.add_question(q)

        survey.print()
        return self.output(survey=survey)


if __name__ == "__main__":
    # pipeline = gen_pipeline([StageQuestions, StageLabelQuestions, StageGenerateSurvey])

    # results = pipeline.process(
    #     pipeline.input(
    #         overall_question="What are some factors that could determine whether someone likes ice cream?",
    #         population="consumers",
    #     )
    # )
    # # print(results)
    # short_options = get_short_options(
    #     ["No, I don't own a scooter", "Yes, I own a scooter"]
    # )
    # print(short_options)

    sample_questions = [
        "What are the primary goals for your company in sponsoring a research center like the MIT IDE?",
        "How does your company measure the ROI on sponsorships like this?",
        "What specific aspects of the MIT IDEs work align with your companys strategic interests?",
        "Can you describe the decision-making process your company uses to select research initiatives for sponsorship?",
        "What are the most important factors your company considers when deciding to sponsor a research center?",
        "How important is the visibility and recognition your company receives from sponsoring a research center like the MIT IDE?",
        "What kind of collaborative opportunities with the MIT IDE are you looking for?",
        "What are your companys expectations regarding intellectual property and the commercialization of research outcomes?",
        "How does your company evaluate the success of the research projects it sponsors?",
        "Would your company be interested in engaging with students or faculty at the MIT IDE for recruitment or professional development opportunities?",
        "How does your company plan to leverage the research and insights gained from the MIT IDE?",
        "What challenges has your company faced in previous sponsorships that you would want to avoid in the future?",
        "Is there any additional support or involvement your company would like to have in the MIT IDE beyond financial sponsorship?",
        "How do you see your companys role in shaping the research agenda at the MIT IDE?",
        "What can the MIT IDE do to make its sponsorship opportunities more attractive to your company?",
    ]

    short_names = get_short_names(sample_questions)
