"""A mixin class for exporting surveys to different formats."""
from docx import Document


class SurveyExportMixin:
    """A mixin class for exporting surveys to different formats."""

    def docx(self) -> "Document":
        """Generate a docx document for the survey."""
        doc = Document()
        doc.add_heading("EDSL Auto-Generated Survey")
        doc.add_paragraph(f"\n")
        for index, question in enumerate(self._questions):
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
        return doc

    def code(self) -> list[str]:
        ## TODO: Refactor to only use the questions actually in the survey
        """Create the Python code representation of a survey."""
        header_lines = ["from edsl.surveys.Survey import Survey"]
        header_lines.append(
            "from edsl.questions.QuestionMultipleChoice import QuestionMultipleChoice"
        )
        header_lines.append(
            "from edsl.questions.QuestionFreeText import QuestionFreeText"
        )
        header_lines.append(
            "from edsl.questions.derived.QuestionLinearScale import QuestionLinearScale"
        )
        header_lines.append(
            "from edsl.questions.QuestionNumerical import QuestionNumerical"
        )
        header_lines.append(
            "from edsl.questions.QuestionCheckBox import QuestionCheckBox"
        )
        header_lines.append(
            "from edsl.questions.derived.QuestionYesNo import QuestionYesNo"
        )
        lines = ["\n".join(header_lines)]
        for question in self._questions:
            lines.append(f"{question.question_name} = " + repr(question))
        lines.append(f"survey = Survey(questions = [{', '.join(self.question_names)}])")
        return lines

    def html(self) -> str:
        """Generate the html for the survey."""
        html_text = []
        for question in self._questions:
            html_text.append(
                f"<p><b>{question.question_name}</b> ({question.question_type}): {question.question_text}</p>"
            )
            html_text.append("<ul>")
            for option in getattr(question, "question_options", []):
                html_text.append(f"<li>{option}</li>")
            html_text.append("</ul>")
        return "\n".join(html_text)
