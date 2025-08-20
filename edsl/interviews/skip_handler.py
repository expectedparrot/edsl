import weakref
from typing import TYPE_CHECKING, Any, Callable, Union

if TYPE_CHECKING:
    from ..questions import QuestionBase
    from .interview import Interview

from ..surveys.base import EndOfSurvey


class SkipHandler:
    def __init__(self, interview: "Interview"):
        # Store a weak reference to the interview
        self._interview_ref = weakref.ref(interview)

        # Cache only the skip function which doesn't maintain a reference to the interview
        try:
            self.skip_function: Callable = (
                interview.survey.rule_collection.skip_question_before_running
            )
        except (AttributeError, KeyError):
            # Fallback for test environments
            self.skip_function = lambda *args: False

    @property
    def interview(self):
        """Access the interview via weak reference if it still exists."""
        interview = self._interview_ref()
        if interview is None:
            raise RuntimeError("Interview has been garbage collected")
        return interview

    @property
    def _to_index(self):
        return self.interview.to_index

    @property
    def _survey(self):
        return self.interview.survey

    @property
    def _answers(self):
        return self.interview.answers

    @property
    def _scenario(self):
        return self.interview.scenario

    @property
    def _agent_traits(self):
        try:
            return self.interview.agent["traits"]
        except (AttributeError, KeyError):
            return {}

    @property
    def _skip_flags(self):
        return self.interview.skip_flags

    def should_skip(self, current_question: "QuestionBase") -> bool:
        """Determine if the current question should be skipped."""
        current_question_index = self._to_index[current_question.question_name]

        # Handle ScenarioList case - convert to dict first
        scenario_dict = {}
        if hasattr(self._scenario, "items"):
            # Handle standard dict scenario
            scenario_dict = self._scenario
        else:
            # Handle ScenarioList or other scenario object
            # Access as a dict if possible, otherwise try to convert
            scenario_dict = (
                dict(self._scenario) if hasattr(self._scenario, "__iter__") else {}
            )

        combined_answers = dict(self._answers)
        combined_answers.update(scenario_dict)
        combined_answers.update(self._agent_traits)

        return self.skip_function(current_question_index, combined_answers)

    def _current_info_env(self) -> dict[str, Any]:
        """
        - The current answers are "generated_tokens" and "comment"
        - The scenario should have "scenario." added to the keys
        - The agent traits should have "agent." added to the keys
        """
        # Check if we have cached static components
        if not hasattr(self, "_scenario_cache"):
            self._scenario_cache = {
                f"scenario.{k}": v for k, v in self._scenario.items()
            }

        if not hasattr(self, "_agent_cache"):
            self._agent_cache = {f"agent.{k}": v for k, v in self._agent_traits.items()}

        # Simple check - if answers haven't changed, return cached result
        if (
            hasattr(self, "_last_answers_id")
            and id(self._answers) == self._last_answers_id
        ):
            return self._env_cache_result

        # Process answers dictionary
        processed_answers = {}
        for key, value in self._answers.items():
            if key.endswith("_generated_tokens"):
                base_name = key.replace("_generated_tokens", "")
                processed_answers[f"{base_name}.generated_tokens"] = value
            elif key.endswith("_comment"):
                base_name = key.replace("_comment", "")
                processed_answers[f"{base_name}.comment"] = value
            else:
                # Regular answer
                processed_answers[f"{key}.answer"] = value

        result = processed_answers | self._scenario_cache | self._agent_cache

        # Cache the result with object id
        self._last_answers_id = id(self._answers)
        self._env_cache_result = result

        return result

    def cancel_skipped_questions(self, current_question: "QuestionBase") -> None:
        """Cancel the tasks for questions that should be skipped."""
        current_question_index: int = self._to_index[current_question.question_name]
        answers = self._current_info_env()

        # Get the index of the next question, which could also be the end of the survey
        next_question: Union[int, EndOfSurvey] = (
            self._survey.rule_collection.next_question(
                q_now=current_question_index,
                answers=answers,
            )
        )

        def cancel_between(start, end):
            """Cancel the tasks for questions between the start and end indices."""
            for i in range(start, end):
                # print(f"Cancelling task {i}")
                # self.interview.tasks[i].cancel()
                # self.interview.tasks[i].set_result("skipped")
                interview = self._interview_ref()
                if interview is not None:
                    interview.skip_flags[self._survey.questions[i].question_name] = True
                else:
                    # If interview is gone, there's nothing to skip anymore
                    return

        if (next_question_index := next_question.next_q) == EndOfSurvey:
            cancel_between(current_question_index + 1, len(self._survey.questions))
            return

        if next_question_index > (current_question_index + 1):
            cancel_between(current_question_index + 1, next_question_index)
