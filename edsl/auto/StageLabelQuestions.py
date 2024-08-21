from textwrap import dedent
from dataclasses import dataclass
from collections import defaultdict

from typing import List, Dict, Union

from edsl.auto.StageBase import StageBase
from edsl.auto.StageBase import FlowDataBase

from edsl.auto.StageQuestions import StageQuestions

from edsl.questions import QuestionMultipleChoice, QuestionList
from edsl.scenarios import Scenario
from edsl import Model
from edsl.auto.utilities import gen_pipeline


question_purpose = {
    "multiple_choice": "When options are known and limited",
    "free_text": "When we are asking an open-ended question",
    "checkbox": "When multiple options can be selected e.g., have you heard of the following products:",
    "numerical": "When the answer is a single numerical value e.g., a float",
    "linear_scale": "When options are text like multiple choice, but can be ordered e.g., daily, weekly, monthly, etc.",
    "yes_no": "When the question can be fully answered with either a yes or a no",
}


class StageLabelQuestions(StageBase):
    input = StageQuestions.output

    @dataclass
    class Output(FlowDataBase):
        questions: List[str]
        types: List[str]
        options: Dict[str, List[str]]
        option_labels: Dict[str, Union[List[str], None]]

    output = Output

    def handle_data(self, data):
        """
        Labels each edsl question type. This is then used later to instantiate the questions
        """
        m = Model()
        label_questions_scenarios = [
            Scenario({"question": q, "question_purpose": question_purpose})
            for q in data.questions
        ]
        q_type = QuestionMultipleChoice(
            question_text=dedent(
                """\
        Consider this question: "{{ question }}"
        The question options and purpose are: {{ question_purpose }}
        Please avoid free text questions much as possible. 
        If it could be a multiple choice, use that type.
        What type of question should this be to make for an informative survey?"""
            ),
            question_options=list(question_purpose.keys()),
            question_name="question_type",
        )
        ## If it is a linear scale, multiple choice or checkbox question, we need to know the options
        option_questions = [
            "multiple_choice",
            "linear_scale",
            "checkbox",
        ]
        q_options_mc = QuestionList(
            question_text=dedent(
                """\
            Consider this question: "{{ question }}"
            What options should this question have?"""
            ),
            question_name="mc_options",
        )
        survey = q_type.add_question(q_options_mc).add_stop_rule(
            "question_type", f"question_type not in {option_questions}"
        )
        type_results = survey.by(label_questions_scenarios).by(m).run()
        type_results.select("question", "question_type", "mc_options").print()

        # breakpoint()

        question_types = type_results.select("question_type").to_list()
        options = type_results.select("mc_options").to_list()
        # question_types, options = type_results.select(
        #    "question_type", "mc_options"
        # ).to_list()

        type_results.select("question", "question_type", "mc_options").print()

        # if the question is a yes/no question, we need to set the options to be yes/no
        types_to_questions = defaultdict(list)
        for question_type, question in zip(question_types, data.questions):
            types_to_questions[question_type].append(question)

        questions_to_options = dict(zip(data.questions, options))
        question_to_option_labels = dict(
            zip(data.questions, len(data.questions) * [None])
        )
        for question in types_to_questions.get("yes_no", []):
            questions_to_options[question] = ["Yes", "No"]

        for question in types_to_questions.get("linear_scale", []):
            options = questions_to_options[question]
            questions_to_options[question] = list(range(len(options)))
            question_to_option_labels[question] = options

        return self.output(
            questions=data.questions,
            types=question_types,
            options=list(questions_to_options.values()),
            option_labels=list(question_to_option_labels.values()),
        )


if __name__ == "__main__":
    pipeline = gen_pipeline([StageQuestions, StageLabelQuestions])

    results = pipeline.process(
        pipeline.input(
            overall_question="What are some factors that could determine whether someone likes ice cream?"
        )
    )

    print(results.options)
