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
        
        # Cache important properties to prevent the need to access the interview
        self._scenario = interview.scenario
        self._model = interview.model
        self._survey = interview.survey
        self._agent = interview.agent
        self._iteration = interview.iteration
        self._cache = interview.cache
        self._raise_validation_errors = interview.raise_validation_errors
        
        # Store current answers
        if current_answers is None:
            self.current_answers = interview.answers
        else:
            self.current_answers = current_answers
            
        self.key_lookup = key_lookup

    @property
    def interview(self):
        """Access the interview via weak reference if it still exists."""
        interview = self._interview_ref()
        if interview is None:
            raise RuntimeError("Interview has been garbage collected")
        return interview

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


def test_weak_reference():
    """Test that FetchInvigilator doesn't maintain a strong reference to the interview."""
    import gc
    
    # Create test objects
    from ..interviews import Interview
    interview = Interview.example()
    
    # Create a weak reference to track the interview
    interview_ref = weakref.ref(interview)
    
    # Create the FetchInvigilator with the interview
    fetch_invigilator = FetchInvigilator(interview)
    
    # Delete the original interview reference
    del interview
    
    # Force garbage collection
    gc.collect()
    
    # Check if the interview was garbage collected
    # If our implementation works correctly, the weak reference should now be None
    if interview_ref() is None:
        print("Test passed: FetchInvigilator doesn't maintain a strong reference")
        return True
    else:
        print("Test failed: FetchInvigilator maintains a strong reference")
        return False
