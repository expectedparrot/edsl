from typing import Callable, Union, List
from edsl.questions.QuestionBase import QuestionBase


class MemoryManagement:

    def __init__(self, survey):
        self.survey = survey

    def _set_memory_plan(self, prior_questions_func: Callable) -> None:
        """Set memory plan based on a provided function determining prior questions.

        :param prior_questions_func: A function that takes the index of the current question and returns a list of prior questions to remember.

        >>> s = Survey.example()
        >>> s._set_memory_plan(lambda i: s.question_names[:i])

        """
        for i, question_name in enumerate(self.survey.question_names):
            self.survey.memory_plan.add_memory_collection(
                focal_question=question_name,
                prior_questions=prior_questions_func(i),
            )

    def add_targeted_memory(
        self,
        focal_question: Union[QuestionBase, str],
        prior_question: Union[QuestionBase, str],
    ) -> "Survey":
        """Add instructions to a survey than when answering focal_question.

        :param focal_question: The question that the agent is answering.
        :param prior_question: The question that the agent should remember when answering the focal question.

        Here we add instructions to a survey than when answering q2 they should remember q1:

        >>> s = Survey.example().add_targeted_memory("q2", "q0")
        >>> s.memory_plan
        {'q2': Memory(prior_questions=['q0'])}

        The agent should also remember the answers to prior_questions listed in prior_questions.
        """
        focal_question_name = self.survey.question_names[
            self.survey._get_question_index(focal_question)
        ]
        prior_question_name = self.survey.question_names[
            self.survey._get_question_index(prior_question)
        ]

        self.survey.memory_plan.add_single_memory(
            focal_question=focal_question_name,
            prior_question=prior_question_name,
        )

        return self.survey

    def add_memory_collection(
        self,
        focal_question: Union[QuestionBase, str],
        prior_questions: List[Union[QuestionBase, str]],
    ) -> "Survey":
        """Add prior questions and responses so the agent has them when answering.

        This adds instructions to a survey than when answering focal_question, the agent should also remember the answers to prior_questions listed in prior_questions.

        :param focal_question: The question that the agent is answering.
        :param prior_questions: The questions that the agent should remember when answering the focal question.

        Here we have it so that when answering q2, the agent should remember answers to q0 and q1:

        >>> s = Survey.example().add_memory_collection("q2", ["q0", "q1"])
        >>> s.memory_plan
        {'q2': Memory(prior_questions=['q0', 'q1'])}
        """
        focal_question_name = self.survey.question_names[
            self.survey._get_question_index(focal_question)
        ]

        prior_question_names = [
            self.survey.question_names[self.survey._get_question_index(prior_question)]
            for prior_question in prior_questions
        ]

        self.survey.memory_plan.add_memory_collection(
            focal_question=focal_question_name, prior_questions=prior_question_names
        )
        return self.survey
