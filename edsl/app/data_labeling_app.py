from __future__ import annotations

from typing import Any, TypedDict

from .app import App
from .head_attachments import HeadAttachments
from .output_formatter import OutputFormatter, OutputFormatters


class DataLabelingParams(TypedDict):
    file_path: str
    labeling_question: Any


class DataLabelingApp(App):
    application_type: str = "data_labeling"

    default_output_formatter = OutputFormatter(name="Data Labeling")

    def _prepare_from_params(self, params: DataLabelingParams) -> "HeadAttachments":
        if "labeling_question" not in params:
            raise ValueError("labeling_question is required for data labeling")
        if "file_path" not in params:
            raise ValueError("file_path is required for data labeling")

        from ..scenarios import FileStore

        file_store = FileStore(path=params["file_path"])
        try:
            sl = file_store.to_scenario_list()
        except Exception as e:
            raise ValueError(
                f"Error converting file to scenario list: {e}. Allowed formats are csv and xlsx."
            )

        labeling_question = params["labeling_question"]
        return HeadAttachments(scenario=sl, survey=labeling_question.to_survey())

    @classmethod
    def example(cls):
        from ..surveys import Survey
        from ..language_models import Model
        from ..questions import QuestionFreeText, QuestionList

        initial_survey = Survey(
            [
                QuestionFreeText(
                    question_text="What is your intended college major",
                    question_name="intended_college_major",
                )
            ]
        )

        logic_survey = QuestionList(
            question_name="courses_to_take",
            question_text="What courses do you need to take for major: {{scenario.intended_college_major}}",
        )
        m = Model()
        job = logic_survey.by(m)
        return App(
            initial_survey=initial_survey,
            jobs_object=job,
            output_formatters=OutputFormatters(
                [
                    OutputFormatter(name="Courses To Take")
                    .select("scenario.intended_college_major", "answer.courses_to_take")
                    .table()
                ]
            ),
        )


