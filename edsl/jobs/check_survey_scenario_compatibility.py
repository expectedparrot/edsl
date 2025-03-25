import warnings
from typing import TYPE_CHECKING
from ..scenarios import ScenarioList
from ..surveys import Survey
from .exceptions import JobsCompatibilityError

if TYPE_CHECKING:
    from ..surveys.survey import Survey
    from ..scenarios.scenario_list import ScenarioList


class CheckSurveyScenarioCompatibility:

    def __init__(self, survey: "Survey", scenarios: "ScenarioList"):
        self.survey = survey
        self.scenarios = scenarios

    def check(self, strict: bool = False, warn: bool = False) -> None:
        """Check if the parameters in the survey and scenarios are consistent.

        >>> from edsl.jobs import Jobs
        >>> from edsl.questions import QuestionFreeText
        >>> from edsl.surveys import Survey
        >>> from edsl.scenarios import Scenario
        >>> q = QuestionFreeText(question_text = "{{poo}}", question_name = "ugly_question")
        >>> j = Jobs(survey = Survey(questions=[q]))
        >>> cs = CheckSurveyScenarioCompatibility(j.survey, j.scenarios)
        >>> with warnings.catch_warnings(record=True) as w:
        ...     cs.check(warn = True)
        ...     assert len(w) == 1
        ...     assert issubclass(w[-1].category, UserWarning)
        ...     assert "The following parameters are in the survey but not in the scenarios" in str(w[-1].message)

        >>> q = QuestionFreeText(question_text = "{{poo}}", question_name = "ugly_question")
        >>> s = Scenario({'plop': "A", 'poo': "B"})
        >>> j = Jobs(survey = Survey(questions=[q])).by(s)
        >>> cs = CheckSurveyScenarioCompatibility(j.survey, j.scenarios)
        >>> cs.check(strict = True)  # doctest: +ELLIPSIS
        Traceback (most recent call last):
        ...
        edsl.jobs.exceptions.JobsCompatibilityError: The following parameters are in the scenarios but not in the survey: {'plop'}...

        >>> q = QuestionFreeText(question_text = "Hello", question_name = "ugly_question")
        >>> s = Scenario({'ugly_question': "B"})
        >>> from edsl.scenarios import ScenarioList
        >>> cs = CheckSurveyScenarioCompatibility(Survey(questions=[q]), ScenarioList([s]))
        >>> cs.check()  # doctest: +ELLIPSIS
        Traceback (most recent call last):
        ...
        edsl.jobs.exceptions.JobsCompatibilityError: The following names are in both the survey question_names and the scenario keys: {'ugly_question'}. This will create issues...
        """
        survey_parameters: set = self.survey.parameters
        scenario_parameters: set = self.scenarios.parameters

        msg0, msg1, msg2 = None, None, None

        # look for key issues
        if intersection := set(self.scenarios.parameters) & set(
            self.survey.question_names
        ):
            msg0 = f"The following names are in both the survey question_names and the scenario keys: {intersection}. This will create issues."

            raise JobsCompatibilityError(msg0)

        if in_survey_but_not_in_scenarios := survey_parameters - scenario_parameters:
            msg1 = f"The following parameters are in the survey but not in the scenarios: {in_survey_but_not_in_scenarios}"
        if in_scenarios_but_not_in_survey := scenario_parameters - survey_parameters:
            msg2 = f"The following parameters are in the scenarios but not in the survey: {in_scenarios_but_not_in_survey}"

        if msg1 or msg2:
            message = "\n".join(filter(None, [msg1, msg2]))
            if strict:
                raise JobsCompatibilityError(message)
            else:
                if warn:
                    warnings.warn(message)

        # if self.scenarios.has_jinja_braces:
        #     warnings.warn(
        #         "The scenarios have Jinja braces ({{ and }}). Converting to '<<' and '>>'. If you want a different conversion, use the convert_jinja_braces method first to modify the scenario."
        #     )
        #     self.scenarios = self.scenarios._convert_jinja_braces()


if __name__ == "__main__":
    import doctest

    doctest.testmod()
