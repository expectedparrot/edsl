"""Regression test: render_ready_tasks must use cached_survey.memory_plan, not a blank one.

Previously, render_ready_tasks always created MemoryPlan(survey=mini_survey), discarding
any memory plan set via set_full_memory_mode() / add_targeted_memory().
"""

import unittest
from edsl.questions import QuestionFreeText
from edsl.surveys import Survey
from edsl.runner.render import RenderWorker


def _two_question_survey():
    q1 = QuestionFreeText(
        question_name="capital_of_france",
        question_text="What is the capital of France?",
    )
    q2 = QuestionFreeText(
        question_name="things_to_do",
        question_text="What are some things to do in this city?",
    )
    survey = Survey([q1, q2])
    survey.set_full_memory_mode()
    return survey


class TestResolveMemoryPlan(unittest.TestCase):
    def test_uses_cached_survey_memory_plan(self):
        """When cached_survey is available, its memory plan (with full-memory entries)
        should be returned rather than a blank one."""
        survey = _two_question_survey()
        mini_survey = Survey([survey.questions[1]])  # just the focal question

        result = RenderWorker._resolve_memory_plan(
            cached_survey=survey, mini_survey=mini_survey
        )

        self.assertIs(result, survey.memory_plan)
        self.assertIn("things_to_do", result)


if __name__ == "__main__":
    unittest.main()
