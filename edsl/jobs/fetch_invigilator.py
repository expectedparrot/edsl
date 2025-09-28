from typing import Dict, Any, Optional, TYPE_CHECKING
import weakref

if TYPE_CHECKING:
    from ..questions import QuestionBase
    from ..agents import InvigilatorBase
    from ..key_management import KeyLookup
    from ..interviews import Interview


class FetchInvigilator:
    def __init__(
        self,
        interview: "Interview",
        current_answers: Optional[Dict[str, Any]] = None,
        key_lookup: Optional["KeyLookup"] = None,
    ):
        # Store a weak reference to the interview instead of a strong reference
        self._interview_ref = weakref.ref(interview)

        # Store external parameters that don't create reference cycles
        self._current_answers = current_answers
        self.key_lookup = key_lookup

    @property
    def interview(self):
        """Access the interview via weak reference if it still exists."""
        interview = self._interview_ref()
        if interview is None:
            raise RuntimeError("Interview has been garbage collected")
        return interview

    @property
    def _scenario(self):
        return self.interview.scenario

    @property
    def _model(self):
        return self.interview.model

    @property
    def _survey(self):
        return self.interview.survey

    @property
    def _agent(self):
        return self.interview.agent

    @property
    def _iteration(self):
        return self.interview.iteration

    @property
    def _cache(self):
        return self.interview.cache

    @property
    def _raise_validation_errors(self):
        return self.interview.raise_validation_errors

    @property
    def current_answers(self):
        if self._current_answers is not None:
            return self._current_answers
        return self.interview.answers

    def get_invigilator(self, question: "QuestionBase") -> "InvigilatorBase":
        """Return an invigilator for the given question.

        :param question: the question to be answered
        :param debug: whether to use debug mode, in which case `InvigilatorDebug` is used.
        """
        # Use cached properties instead of accessing through the interview reference
        invigilator = self._agent.create_invigilator(
            question=question,
            scenario=self._scenario,
            model=self._model,
            survey=self._survey,
            memory_plan=self._survey.memory_plan,
            current_answers=self.current_answers,
            iteration=self._iteration,
            cache=self._cache,
            raise_validation_errors=self._raise_validation_errors,
            key_lookup=self.key_lookup,
        )
        return invigilator

    def __call__(self, question):
        return self.get_invigilator(question)
