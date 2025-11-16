import warnings
from typing import TYPE_CHECKING
from .exceptions import JobsCompatibilityError

if TYPE_CHECKING:
    from ..surveys.survey import Survey
    from ..scenarios.scenario_list import ScenarioList


class CheckSurveyScenarioCompatibility:
    def __init__(self, survey: "Survey", scenarios: "ScenarioList"):
        self.survey = survey
        self.scenarios = scenarios

    def check(self, strict: bool = False, warn: bool = False, check_unused_scenarios: bool = True) -> None:
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

        >>> q = QuestionFreeText(question_text = "What is 1+1?", question_name = "test")
        >>> s = Scenario({'topic': "reading"})
        >>> cs = CheckSurveyScenarioCompatibility(Survey(questions=[q]), ScenarioList([s]))
        >>> cs.check()  # doctest: +ELLIPSIS
        Traceback (most recent call last):
        ...
        edsl.jobs.exceptions.JobsCompatibilityError: Scenario with fields {'topic'} is attached but none of these fields are used in any question. At least one scenario field must be referenced in the survey...

        >>> q = QuestionFreeText(question_text = "Price is {{scenario.price}}", question_name = "test")
        >>> s = Scenario({'price': 100})
        >>> cs = CheckSurveyScenarioCompatibility(Survey(questions=[q]), ScenarioList([s]))
        >>> cs.check()
        """
        # Handle empty surveys gracefully
        try:
            survey_parameters: set = self.survey.parameters
        except TypeError:
            # Empty survey - no questions to check
            survey_parameters = set()
        
        scenario_parameters: set = self.scenarios.parameters

        msg0, msg1, msg2, msg3 = None, None, None, None

        # look for key issues
        if intersection := set(self.scenarios.parameters) & set(
            self.survey.question_names
        ):
            msg0 = f"The following names are in both the survey question_names and the scenario keys: {intersection}. This will create issues."

            raise JobsCompatibilityError(msg0)

        # Check if scenarios are attached but none of their fields are used
        # Skip this check if the survey has no questions (empty survey)
        if check_unused_scenarios and scenario_parameters and len(self.survey.questions) > 0:
            # Check if any question is a functional question (uses scenario data directly in functions)
            has_functional_question = any(
                q.question_type == "functional" for q in self.survey.questions
            )
            
            # Check if any scenario parameter is used in the survey
            # Also check if 'scenario' itself is used (for {{scenario.field}} pattern)
            # Skip validation if there's a functional question (scenarios are used directly in functions)
            if not has_functional_question and not (scenario_parameters & survey_parameters) and 'scenario' not in survey_parameters:
                msg3 = f"Scenario with fields {scenario_parameters} is attached but none of these fields are used in any question. At least one scenario field must be referenced in the survey."
                raise JobsCompatibilityError(msg3)

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


if __name__ == "__main__":
    import doctest

    doctest.testmod()
