"""A class for exporting surveys to different formats."""

from typing import Union, Optional, TYPE_CHECKING

import subprocess
import platform
import os
import tempfile

if TYPE_CHECKING:
    from docx import Document
    from ..scenarios import ScenarioList


def open_docx(file_path):
    """
    Open a docx file using the default application in a cross-platform manner.

    :param file_path: str, path to the docx file
    """
    file_path = os.path.abspath(file_path)

    if platform.system() == "Darwin":  # macOS
        subprocess.call(("open", file_path))
    elif platform.system() == "Windows":  # Windows
        os.startfile(file_path)
    else:  # linux variants
        subprocess.call(("xdg-open", file_path))


class SurveyExport:
    """A class for exporting surveys to different formats."""

    def __init__(self, survey):
        """Initialize with a Survey object."""
        self.survey = survey

    def css(self):
        from .survey_css import SurveyCSS

        return SurveyCSS.default_style().generate_css()

    def get_description(self) -> str:
        """Return the description of the survey."""
        from edsl import QuestionFreeText

        question_texts = "\n".join([q.question_text for q in self.survey._questions])
        q = QuestionFreeText(
            question_name="description",
            question_text=f"""A survey was conducted with the following questions: 
                             {question_texts}
                             Please write a description of the survey.
                             """,
        )
        return q.run().select("description").first()

    def docx(
        self,
        return_document_object: bool = False,
        filename: Optional[str] = None,
        open_file: bool = False,
    ) -> Union["Document", None]:
        """Generate a docx document for the survey."""
        from docx import Document

        doc = Document()
        doc.add_heading("EDSL Survey")
        doc.add_paragraph("\n")
        for index, question in enumerate(self.survey._questions):
            h = doc.add_paragraph()  # Add question as a paragraph
            h.add_run(f"Question {index + 1} ({question.question_name})").bold = True
            h.add_run(f"; {question.question_type}").italic = True
            p = doc.add_paragraph()
            p.add_run(question.question_text)
            if question.question_type == "linear_scale":
                for key, value in getattr(question, "option_labels", {}).items():
                    doc.add_paragraph(str(key) + ": " + str(value), style="ListBullet")
            else:
                if hasattr(question, "question_options"):
                    for option in getattr(question, "question_options", []):
                        doc.add_paragraph(str(option), style="ListBullet")

        if return_document_object:
            return doc
        else:
            doc.save(filename)
            if open_file:
                os.system(f"open {filename}")
            return None

    def show(self):
        self.to_scenario_list(questions_only=False, rename=True).print(format="rich")

    def to_scenario_list(
        self, questions_only: bool = True, rename=False
    ) -> "ScenarioList":
        from ..scenarios import ScenarioList, Scenario

        if questions_only:
            to_iterate_over = self.survey._questions
        else:
            to_iterate_over = self.survey.recombined_questions_and_instructions()

        if rename:
            renaming_dict = {
                "name": "identifier",
                "question_name": "identifier",
                "question_text": "text",
            }
        else:
            renaming_dict = {}

        all_keys = set([])
        scenarios = ScenarioList()
        for item in to_iterate_over:
            d = item.to_dict()
            if item.__class__.__name__ == "Instruction":
                d["question_type"] = "NA / instruction"
            for key in renaming_dict:
                if key in d:
                    d[renaming_dict[key]] = d.pop(key)
            all_keys.update(d.keys())
            scenarios.append(Scenario(d))

        for scenario in scenarios:
            for key in all_keys:
                if key not in scenario:
                    scenario[key] = None

        return scenarios

    def code(self, filename: str = None, survey_var_name: str = "survey") -> list[str]:
        """Create the Python code representation of a survey.

        :param filename: The name of the file to save the code to.
        :param survey_var_name: The name of the survey variable.

        >>> from edsl.surveys import Survey
        >>> survey = Survey.example()
        >>> print(survey.code())
        from edsl.surveys.Survey import Survey
        ...
        ...
        survey = Survey(questions=[q0, q1, q2])
        ...
        """
        import black

        header_lines = ["from edsl.surveys.Survey import Survey"]
        header_lines.append("from edsl import Question")
        lines = ["\n".join(header_lines)]
        for question in self.survey._questions:
            question.question_text = question["question_text"].replace("\n", " ")
            # remove dublicate spaces
            question.question_text = " ".join(question.question_text.split())
            lines.append(f"{question.question_name} = " + repr(question))
        lines.append(
            f"{survey_var_name} = Survey(questions = [{', '.join(self.survey.question_names)}])"
        )
        # return lines
        code_string = "\n".join(lines)
        formatted_code = black.format_str(code_string, mode=black.FileMode())

        if filename:
            print("The code has been saved to", filename)
            print("The survey itself is saved to 'survey' object")
            with open(filename, "w") as file:
                file.write(formatted_code)
            return

        return formatted_code

    def html(
        self,
        scenario: Optional[dict] = None,
        filename: Optional[str] = None,
        return_link=False,
        css: Optional[str] = None,
        cta: Optional[str] = "Open HTML file",
        include_question_name=False,
    ):
        from IPython.display import display, HTML
        import os
        from edsl.utilities.utilities import is_notebook

        if scenario is None:
            scenario = {}

        if css is None:
            css = self.css()

        if filename is None:
            current_directory = os.getcwd()
            filename = tempfile.NamedTemporaryFile(
                "w", delete=False, suffix=".html", dir=current_directory
            ).name

        html_header = f"""<html>
        <head><title></title>
        <style>
        { css }
        </style>
        </head>
        <body>
        <div class="survey_container">
        """

        html_footer = """
        </div>
        </body>
        </html>"""

        output = html_header

        with open(filename, "w") as f:
            f.write(html_header)
            for question in self.survey._questions:
                f.write(
                    question.html(
                        scenario=scenario, include_question_name=include_question_name
                    )
                )
                output += question.html(
                    scenario=scenario, include_question_name=include_question_name
                )
            f.write(html_footer)
            output += html_footer

        if is_notebook():
            html_url = f"/files/{filename}"
            html_link = f'<a href="{html_url}" target="_blank">{cta}</a>'
            display(HTML(html_link))

            import html

            escaped_output = html.escape(output)
            iframe = f""""
            <iframe srcdoc="{ escaped_output }" style="width: 800px; height: 600px;"></iframe>
            """
            display(HTML(iframe))

        else:
            print(f"Survey saved to {filename}")
            import webbrowser
            import os

            webbrowser.open(f"file://{os.path.abspath(filename)}")
            # webbrowser.open(filename)

        if return_link:
            return filename


if __name__ == "__main__":
    import doctest

    doctest.testmod(optionflags=doctest.ELLIPSIS)
