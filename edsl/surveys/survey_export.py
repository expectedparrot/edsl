"""A class for exporting surveys to different formats."""

from typing import Optional, TYPE_CHECKING
import json

import subprocess
import platform
import os
import tempfile
import re

if TYPE_CHECKING:
    from ..scenarios import ScenarioList, FileStore


def _translate_rule_expression(expression, questions, question_ids):
    """Translate simple answer comparisons to vendor IDs and option codes.

    Returns None when an expression contains a comparison that cannot be
    translated without changing its meaning.
    """
    by_name = {question.question_name: question for question in questions}
    comparison = re.compile(
        r"\{\{\s*([A-Za-z_]\w*)\.answer\s*\}\}\s*(==|!=|>=|<=|>|<)\s*(?:'([^']*)'|\"([^\"]*)\"|(-?\d+(?:\.\d+)?))"
    )

    def replace(match):
        name, operator = match.group(1), match.group(2)
        value = match.group(3) if match.group(3) is not None else match.group(4)
        if value is None:
            value = match.group(5)
        question = by_name.get(name)
        if question is None:
            raise ValueError("unknown question")
        options = getattr(question, "question_options", None)
        if options is not None and operator in ("==", "!="):
            matching = [i for i, option in enumerate(options, 1) if str(option) == str(value)]
            if not matching:
                raise ValueError("option not found")
            value = str(matching[0])
        elif value is None:
            raise ValueError("unsupported comparison")
        return f"{question_ids[name]} {operator} {value}"

    try:
        translated = comparison.sub(replace, expression)
    except ValueError:
        return None
    # Do not claim this is vendor-readable if any EDSL answer reference remains.
    if re.search(r"\{\{.*?\.answer.*?\}\}", translated):
        return None
    return translated


def survey_from_docx(source):
    """Rebuild a Survey by reading the visible programming specification."""
    from docx import Document
    from ..questions.question_base import QuestionBase
    from .survey import Survey
    from ..instructions import Instruction

    path = getattr(source, "path", source)
    doc = Document(path)
    paragraphs = doc.paragraphs
    records = []
    current = None
    current_rule_lines = []
    for paragraph in paragraphs:
        text = paragraph.text.strip()
        if paragraph.style.name == "Heading 2" and text.startswith("Q_") and " (" in text:
            if current is not None:
                current["rules"] = current_rule_lines
                records.append(current)
            qid, name = text.split(" (", 1)
            current = {"id": qid, "name": name[:-1], "rules": [], "options": [], "anchors": {}, "fields": {}}
            current_rule_lines = []
            continue
        if paragraph.style.name == "Heading 2" and text == "Section transition":
            if current is not None:
                current["rules"] = current_rule_lines
                records.append(current)
                current = None
            records.append({"instruction": True})
            continue
        if paragraph.style.name == "Heading 2" and text.startswith("Section transition ("):
            if current is not None:
                current["rules"] = current_rule_lines
                records.append(current)
                current = None
            records.append({"instruction": True, "name": text[len("Section transition ("):-1]})
            continue
        if current is None:
            if records and records[-1].get("instruction") and "text" not in records[-1] and text:
                records[-1]["text"] = text
            continue
        if text.startswith("Question type: "):
            current["type"] = text.partition(": ")[2]
        elif text.startswith("[PROGRAMMER: SCALE ANCHORS]"):
            current["reading_anchors"] = True
        elif text.startswith("[PROGRAMMER:") or text.startswith("[EDSL SOURCE LOGIC:"):
            if text.startswith("[PROGRAMMER:") and "GO TO" in text:
                current_rule_lines.append(text)
        elif text.startswith("Minimum selections:"):
            current["fields"]["min_selections"] = int(text.partition(":")[2].strip())
        elif text.startswith("Maximum selections:"):
            current["fields"]["max_selections"] = int(text.partition(":")[2].strip())
        elif text.startswith("Minimum value:"):
            current["fields"]["min_value"] = _parse_docx_scalar(text.partition(":")[2].strip())
        elif text.startswith("Maximum value:"):
            current["fields"]["max_value"] = _parse_docx_scalar(text.partition(":")[2].strip())
        elif text.startswith("Character limit:"):
            current["fields"]["max_characters"] = int(text.partition(":")[2].strip())
        elif text.startswith("[EDSL SETTING: ") and text.endswith("]"):
            setting = text[len("[EDSL SETTING: "):-1]
            key, separator, value = setting.partition(" = ")
            if separator:
                current["fields"][key] = _parse_docx_scalar(value)
        else:
            coded = re.match(r"^(\d+) = (.*)$", text)
            if coded:
                value = _parse_docx_scalar(coded.group(2))
                if current.get("reading_anchors"):
                    current["anchors"][coded.group(1)] = value
                else:
                    current["options"].append(value)
            elif "type" in current and "text" not in current and text and not text.startswith("Response format:"):
                current["text"] = text
    if current is not None:
        current["rules"] = current_rule_lines
        records.append(current)

    questions = []
    by_id = {}
    for record in records:
        if record.get("instruction"):
            continue
        if not all(key in record for key in ("name", "type", "text")):
            raise ValueError("A question in the DOCX is missing its ID, type, or respondent-facing text.")
        data = {"question_name": record["name"], "question_text": record["text"], "question_type": record["type"]}
        if record["options"]:
            data["question_options"] = record["options"]
        if record["anchors"]:
            data["option_labels"] = {int(k): v for k, v in record["anchors"].items()}
        data.update(record["fields"])
        try:
            question = QuestionBase.from_dict(data)
        except Exception as exc:
            raise ValueError(f"Could not rebuild DOCX question {record['id']} ({record['type']}): {exc}") from exc
        questions.append(question)
        by_id[record["id"]] = (record, question)

    survey = Survey()
    for record in records:
        if record.get("instruction"):
            survey.add_instruction(Instruction(name=record.get("name") or f"docx_instruction_{len(survey._instruction_names_to_instructions) + 1}", text=record.get("text", "")))
        else:
            survey.add_question(by_id[record["id"]][1])

    for record in records:
        if record.get("instruction"):
            continue
        question = by_id[record["id"]][1]
        for line in record.get("rules", []):
            match = re.match(r"^\[PROGRAMMER: (BEFORE DISPLAY|AFTER RESPONSE); IF (.*), GO TO (.*)\]$", line)
            if not match:
                if "GO TO" in line:
                    raise ValueError(f"This DOCX contains logic that cannot be round-tripped safely: {line}")
                continue
            timing, condition, destination = match.groups()
            expression = _docx_logic_to_expression(condition, by_id)
            if expression is None:
                raise ValueError(f"Could not translate DOCX logic for {record['id']}: {condition}")
            if destination in ("END OF SURVEY", "TERMINATE / END SURVEY"):
                target = len(survey.questions)
                if destination.startswith("TERMINATE"):
                    from .base import EndOfSurvey
                    target = EndOfSurvey
            elif destination in by_id:
                target = by_id[destination][1]
            else:
                raise ValueError(f"Unknown question destination in DOCX: {destination}")
            survey.add_rule(question, expression, target, before_rule=(timing == "BEFORE DISPLAY"))
    return survey


def _parse_docx_scalar(value):
    import ast
    try:
        return json.loads(value)
    except (ValueError, TypeError):
        try:
            return ast.literal_eval(value)
        except (ValueError, SyntaxError):
            return value


def _docx_logic_to_expression(condition, by_id):
    """Convert simple coded comparisons in the visible DOCX back to EDSL."""
    pattern = re.compile(r"\b(Q_[A-Za-z_]\w*)\s*(==|!=|>=|<=|>|<)\s*(-?\d+(?:\.\d+)?)")
    def replace(match):
        qid, operator, code = match.groups()
        if qid not in by_id:
            raise ValueError(f"Unknown question ID {qid}")
        question = by_id[qid][1]
        options = getattr(question, "question_options", None)
        if options is not None and operator in ("==", "!="):
            i = int(float(code)) - 1
            if i < 0 or i >= len(options):
                raise ValueError(f"Invalid option code {code} for {qid}")
            answer = repr(options[i])
        else:
            answer = code
        return f"{{{{ {question.question_name}.answer }}}} {operator} {answer}"
    try:
        result, count = pattern.subn(replace, condition)
    except ValueError:
        return None
    return result if count and not re.search(r"\bQ_", result) else None


def _add_logo_watermark(section):
    """Add the repository Expected Parrot mark as a pale, page-centered watermark."""
    from copy import deepcopy
    from docx.shared import Inches
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn

    logo = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../docs/logo.png"))
    if not os.path.exists(logo):
        return
    paragraph = section.header.paragraphs[0]
    paragraph.text = ""
    inline = paragraph.add_run().add_picture(logo, width=Inches(6.0))._inline
    anchor = OxmlElement("wp:anchor")
    for name, value in (("distT", "0"), ("distB", "0"), ("distL", "0"), ("distR", "0"),
                        ("simplePos", "0"), ("relativeHeight", "0"), ("behindDoc", "1"),
                        ("locked", "0"), ("layoutInCell", "1"), ("allowOverlap", "1")):
        anchor.set(name, value)
    simple = OxmlElement("wp:simplePos")
    simple.set("x", "0")
    simple.set("y", "0")
    pos_h = OxmlElement("wp:positionH")
    pos_h.set("relativeFrom", "page")
    offset_h = OxmlElement("wp:posOffset")
    offset_h.text = str(int((section.page_width - Inches(6.0)) / 2))
    pos_h.append(offset_h)
    pos_v = OxmlElement("wp:positionV")
    pos_v.set("relativeFrom", "page")
    offset_v = OxmlElement("wp:posOffset")
    offset_v.text = str(int(section.page_height / 2 - Inches(0.9)))
    pos_v.append(offset_v)
    anchor.append(simple)
    anchor.append(pos_h)
    anchor.append(pos_v)
    for child in inline:
        anchor.append(deepcopy(child))
    extent = anchor.find(qn("wp:extent"))
    effect_extent = OxmlElement("wp:effectExtent")
    for side in ("l", "t", "r", "b"):
        effect_extent.set(side, "0")
    anchor.insert(anchor.index(extent) + 1, effect_extent)
    wrap = OxmlElement("wp:wrapNone")
    anchor.insert(anchor.index(effect_extent) + 1, wrap)
    blip = anchor.find(".//" + qn("a:blip"))
    if blip is not None:
        alpha = OxmlElement("a:alphaModFix")
        alpha.set("amt", "18000")
        blip.append(alpha)
    inline.getparent().replace(inline, anchor)


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

    # def get_description(self) -> str:
    #     """Return the description of the survey."""
    #     from edsl import QuestionFreeText

    #     question_texts = "\n".join([q.question_text for q in self.survey._questions])
    #     q = QuestionFreeText(
    #         question_name="description",
    #         question_text=f"""A survey was conducted with the following questions:
    #                          {question_texts}
    #                          Please write a description of the survey.
    #                          """,
    #     )
    #     return q.run().select("description").first()

    def docx(
        self,
        filename: Optional[str] = None,
    ) -> "FileStore":
        """Generate a vendor-oriented survey programming specification."""
        from docx import Document
        from edsl import FileStore

        if not filename:  # handles None and ""
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".docx")
            filename = tmp.name
            tmp.close()

        doc = Document()
        # Stable vendor IDs derive from names, so inserting a question does not
        # renumber existing questions in a later draft.
        question_ids = {q.question_name: f"Q_{q.question_name}" for q in self.survey._questions}
        for section in doc.sections:
            header = section.header.paragraphs[0]
            _add_logo_watermark(section)
            section.footer.paragraphs[0].text = "EDSL Survey Programming Specification | Version: [add] | Date: [add]"
        doc.add_heading("Survey Programming Specification", 0)
        doc.add_paragraph("Version: [add]    Date: [add]")
        doc.add_heading("Project and fielding details", level=1)
        for label in ("Target audience", "Target sample size", "Quotas", "Expected interview length",
                      "Languages", "Devices / mobile requirements", "Fielding dates",
                      "Data deliverables (format; labeled or coded)", "Vendor template / platform"):
            doc.add_paragraph(f"{label}: [to be supplied]")
        doc.add_heading("Programming conventions", level=1)
        doc.add_paragraph("Respondent-facing text appears as normal text. Programmer notes are in ALL CAPS inside square brackets.")
        doc.add_paragraph("Question IDs use the stable question names shown below. Preserve IDs across revisions; use letter suffixes for additions (for example, Q_namea).")

        ordered = self.survey.recombined_questions_and_instructions()
        for item in ordered:
            if item.__class__.__name__ == "Instruction":
                doc.add_heading(f"Section transition ({item.name})", level=2)
                text = getattr(item, "text", None) or getattr(item, "instruction", None) or str(item)
                doc.add_paragraph(str(text))
                continue
            qid = question_ids[item.question_name]
            doc.add_heading(f"{qid} ({item.question_name})", level=2)
            p = doc.add_paragraph()
            p.add_run("Question type: ").bold = True
            p.add_run(str(item.question_type))
            doc.add_paragraph(str(item.question_text))
            options = getattr(item, "question_options", None)
            if options is not None:
                doc.add_paragraph("[PROGRAMMER: CODE RESPONSE OPTIONS AS FOLLOWS]")
                for code, option in enumerate(options, 1):
                    doc.add_paragraph(f"{code} = {json.dumps(option, ensure_ascii=False)}")
                if "other" in str(item.question_type).lower():
                    doc.add_paragraph("[PROGRAMMER: CONFIRM 'OTHER' TEXT ENTRY AND RESPONSE CODING]")
                if "check" in str(item.question_type).lower() or "top_k" in str(item.question_type).lower():
                    limit = getattr(item, "max_selections", None)
                    doc.add_paragraph("Response format: multi-select" + (f"; select up to {limit}" if limit else "; select all that apply"))
            labels = getattr(item, "option_labels", None)
            if labels:
                doc.add_paragraph("[PROGRAMMER: SCALE ANCHORS]")
                for code, label in labels.items():
                    doc.add_paragraph(f"{code} = {json.dumps(label, ensure_ascii=False)}")
            for attr, label in (("min_selections", "Minimum selections"), ("max_selections", "Maximum selections"),
                                ("min_value", "Minimum value"), ("max_value", "Maximum value"),
                                ("max_characters", "Character limit")):
                value = getattr(item, attr, None)
                if value is not None:
                    doc.add_paragraph(f"{label}: {value}")
            displayed_fields = {
                "question_name", "question_text", "question_type", "question_options",
                "option_labels", "min_selections", "max_selections", "min_value",
                "max_value", "max_characters",
            }
            for key, value in item.to_dict(add_edsl_version=False).items():
                if key not in displayed_fields:
                    doc.add_paragraph(f"[EDSL SETTING: {key} = {json.dumps(value, ensure_ascii=False)}]")
            # Surface all non-default navigation rules at the affected question.
            index = self.survey.question_names.index(item.question_name)
            for rule in self.survey.rule_collection.non_default_rules:
                if rule.current_q != index:
                    continue
                destination = rule.next_q
                if isinstance(destination, int) and destination < len(self.survey._questions):
                    destination = question_ids[self.survey._questions[destination].question_name]
                elif isinstance(destination, int) and destination >= len(self.survey._questions):
                    destination = "END OF SURVEY"
                elif str(destination) == "EndOfSurvey" or destination.__class__.__name__ == "EndOfSurvey":
                    destination = "TERMINATE / END SURVEY"
                timing = "BEFORE DISPLAY" if rule.before_rule else "AFTER RESPONSE"
                note = doc.add_paragraph()
                coded_logic = _translate_rule_expression(
                    rule.expression, self.survey._questions, question_ids
                )
                if coded_logic is not None:
                    note.add_run(
                        f"[PROGRAMMER: {timing}; IF {coded_logic}, GO TO {destination}]"
                    ).bold = True
                    note = doc.add_paragraph()
                    note.add_run(f"[EDSL SOURCE LOGIC: {rule.expression}]").italic = True
                else:
                    note.add_run(
                        f"[PROGRAMMER: {timing}; TRANSLATE THIS LOGIC BEFORE PROGRAMMING: {rule.expression}; GO TO {destination}]"
                    ).bold = True
            if getattr(item, "question_type", "") in {"free_text", "text", "numerical"}:
                doc.add_paragraph("[PROGRAMMER: CONFIRM VALIDATION / CHARACTER OR NUMERIC LIMITS WITH STUDY OWNER]")

        doc.add_heading("Closing and screen-out text", level=1)
        doc.add_paragraph("Thank-you message: [to be supplied]")
        doc.add_paragraph("Screen-out / termination message: [to be supplied]")
        doc.add_heading("Programming notes", level=1)
        doc.add_paragraph("Randomization, exclusive options, specify fields, quotas, and answer piping: [confirm and specify where applicable]")
        # Determine filename: use provided filename or create a temporary one
        if filename is None:
            current_directory = os.getcwd()
            # Create a temporary file to hold the .docx content
            temp_file = tempfile.NamedTemporaryFile(
                "wb", delete=False, suffix=".docx", dir=current_directory
            )
            filename = temp_file.name
            temp_file.close()

        # Save the document to the determined filename
        doc.save(filename)

        # Return a FileStore object for the generated file
        return FileStore(filename)

    def show(self):
        self.to_scenario_list(questions_only=False, rename=True).print(format="rich")

    def to_scenario_list(
        self,
        questions_only: bool = True,
        rename=False,
        remove_jinja2_syntax: bool = False,
    ) -> "ScenarioList":
        import re
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

        all_keys = []
        scenarios = ScenarioList()
        for item in to_iterate_over:
            d = item.to_dict()
            if item.__class__.__name__ == "Instruction":
                d["question_type"] = "NA / instruction"

            # Remove Jinja2 syntax from question_text if requested
            if remove_jinja2_syntax and "question_text" in d:
                # Remove {{ }} brackets and their contents, preserving spacing
                d["question_text"] = re.sub(
                    r"\s*\{\{.*?\}\}\s*", " ", d["question_text"]
                )
                # Clean up extra whitespace that may result from removal
                d["question_text"] = " ".join(d["question_text"].split()).strip()

            for key in renaming_dict:
                if key in d:
                    d[renaming_dict[key]] = d.pop(key)
            # Preserve order by using list with manual deduplication
            for key in d.keys():
                if key not in all_keys:
                    all_keys.append(key)
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
        >>> 'Survey(questions' in survey.code()
        True
        """
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
        code_string = "\n".join(lines)
        try:
            import black

            formatted_code = black.format_str(code_string, mode=black.FileMode())
        except ImportError:
            formatted_code = code_string

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
        import os
        from edsl import FileStore  # Added import for FileStore

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

        return FileStore(filename)

    def latex(
        self,
        filename: Optional[str] = None,
        include_question_name: bool = False,
        standalone: bool = True,
    ) -> "FileStore":
        """Generate a LaTeX (.tex) document for the survey.

        Parameters
        ----------
        filename : Optional[str]
            The filename to write to. If not provided, a temporary file is created
            in the current working directory with a ``.tex`` suffix.
        include_question_name : bool, default False
            If True, includes the internal ``question_name`` of each question in
            the rendered LaTeX.
        standalone : bool, default True
            If True, a full LaTeX document is produced with ``\\documentclass`` and
            ``\\begin{document}`` / ``\\end{document}``. If False, only the snippet
            corresponding to the survey content is written (suitable for inclusion
            in a larger document).

        Returns
        -------
        FileStore
            A ``FileStore`` object pointing to the generated ``.tex`` file so it
            can easily be downloaded, viewed, or further processed.
        """
        # Local import to avoid heavy dependency at import-time.
        from edsl import FileStore

        # Determine filename
        if filename is None:
            current_directory = os.getcwd()
            temp_file = tempfile.NamedTemporaryFile(
                "w", delete=False, suffix=".tex", dir=current_directory
            )
            filename = temp_file.name
            temp_file.close()

        # Basic LaTeX document structure (optional)
        if standalone:
            header = r"""\documentclass{article}
\usepackage[utf8]{inputenc}
\usepackage{enumitem}
\begin{document}
\section*{EDSL Survey}
"""
            footer = "\n\\end{document}\n"
        else:
            header = ""
            footer = ""

        def _escape_latex(text: str) -> str:
            """Escape characters that have special meaning in LaTeX."""
            replacements = {
                "&": r"\&",
                "%": r"\%",
                "$": r"\$",
                "#": r"\#",
                "_": r"\\_",
                "{": r"\{",
                "}": r"\}",
                "~": r"\textasciitilde{}",
                "^": r"\textasciicircum{}",
                "\\": r"\textbackslash{}",
            }
            for k, v in replacements.items():
                text = text.replace(k, v)
            return text

        with open(filename, "w", encoding="utf-8") as f:
            f.write(header)
            for idx, question in enumerate(self.survey._questions):
                # Heading for each question
                heading_parts = [f"Question {idx + 1}"]
                if include_question_name:
                    heading_parts.append(
                        f"(\\texttt{{{_escape_latex(question.question_name)}}})"
                    )
                heading_parts.append(
                    f"-- \\textit{{{_escape_latex(question.question_type)}}}"
                )
                heading = " ".join(heading_parts)
                f.write(f"\\subsection*{{{heading}}}\n")

                # Question text
                f.write(f"{_escape_latex(question.question_text)}\\\n\n")

                # Handle options or labels depending on question type
                if question.question_type == "linear_scale":
                    option_labels = getattr(question, "option_labels", {}) or {}
                    if option_labels:
                        f.write("\\begin{itemize}\n")
                        for key, value in option_labels.items():
                            f.write(
                                f"  \\item {_escape_latex(str(key))}: {_escape_latex(str(value))}\n"
                            )
                        f.write("\\end{itemize}\n\n")
                else:
                    if hasattr(question, "question_options"):
                        options = getattr(question, "question_options", []) or []
                        if options:
                            f.write("\\begin{enumerate}[label=\\alph*)]\n")
                            for option in options:
                                f.write(f"  \\item {_escape_latex(str(option))}\n")
                            f.write("\\end{enumerate}\n\n")

            f.write(footer)

        # Return a FileStore object for the generated file
        return FileStore(filename)


if __name__ == "__main__":
    import doctest

    doctest.testmod(optionflags=doctest.ELLIPSIS)
