from typing import List, Dict, Any, Optional


class FetchInvigilator:

    def __init__(self, interview, current_answers: Optional[Dict[str, Any]] = None):
        self.interview = interview
        if current_answers is None:
            self.current_answers = self.interview.answers
        else:
            self.current_answers = current_answers

    def get_invigilator(self, question: "QuestionBase") -> "InvigilatorBase":
        """Return an invigilator for the given question.

        :param question: the question to be answered
        :param debug: whether to use debug mode, in which case `InvigilatorDebug` is used.
        """

        invigilator = self.interview.agent.create_invigilator(
            question=question,
            scenario=self.interview.scenario,
            model=self.interview.model,
            debug=False,
            survey=self.interview.survey,
            memory_plan=self.interview.survey.memory_plan,
            current_answers=self.current_answers,  # not yet known
            iteration=self.interview.iteration,
            cache=self.interview.cache,
            sidecar_model=self.interview.sidecar_model,
            raise_validation_errors=self.interview.raise_validation_errors,
        )
        """Return an invigilator for the given question."""
        return invigilator

    def __call__(self, question):
        return self.get_invigilator(question)
