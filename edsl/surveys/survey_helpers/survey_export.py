"""A class for exporting surveys to different formats.

Note: Most export methods (docx, html, latex, code) are handled by services
in edsl-services. Use the service accessors on Survey objects instead:
    survey.docx_export.export()
    survey.html_export.export()
    survey.latex_export.export()
    survey.code.generate()
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ...scenarios import ScenarioList


class SurveyExport:
    """A class for exporting surveys to different formats."""

    def __init__(self, survey):
        """Initialize with a Survey object."""
        self.survey = survey

    def show(self):
        self.to_scenario_list(questions_only=False, rename=True).print(format="rich")

    def to_scenario_list(
        self,
        questions_only: bool = True,
        rename=False,
        remove_jinja2_syntax: bool = False,
    ) -> "ScenarioList":
        import re
        from ...scenarios import ScenarioList, Scenario

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
            scenarios = scenarios.append(Scenario(d))

        for scenario in scenarios:
            for key in all_keys:
                if key not in scenario:
                    scenario[key] = None

        return scenarios


if __name__ == "__main__":
    import doctest

    doctest.testmod(optionflags=doctest.ELLIPSIS)
