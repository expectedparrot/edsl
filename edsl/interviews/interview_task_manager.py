from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..questions import QuestionBase
    from ..tokens import InterviewTokenUsage
    from . import InterviewStatusDictionary, InterviewStatusLog


class InterviewTaskManager:
    """Handles creation and management of interview tasks."""

    def __init__(self, survey, iteration=0):
        from ..tasks import TaskCreators
        from . import InterviewStatusLog

        self.survey = survey
        self.iteration = iteration
        self.task_creators = TaskCreators()
        self.to_index = {
            question_name: index
            for index, question_name in enumerate(self.survey.question_names)
        }
        self._task_status_log_dict = InterviewStatusLog()
        self.survey_dag = None

    def build_question_tasks(
        self, answer_func, token_estimator, model_buckets
    ) -> list[asyncio.Task]:
        """Create tasks for all questions with proper dependencies."""
        tasks: list[asyncio.Task] = []
        for question in self.survey.questions:
            dependencies = self._get_task_dependencies(tasks, question)
            task = self._create_single_task(
                question=question,
                dependencies=dependencies,
                answer_func=answer_func,
                token_estimator=token_estimator,
                model_buckets=model_buckets,
            )
            tasks.append(task)
        return tasks

    def _get_task_dependencies(
        self, existing_tasks: list[asyncio.Task], question: "QuestionBase"
    ) -> list[asyncio.Task]:
        """Get tasks that must be completed before the given question."""
        if self.survey_dag is None:
            self.survey_dag = self.survey.dag(textify=True)
        parents = self.survey_dag.get(question.question_name, [])
        return [existing_tasks[self.to_index[parent_name]] for parent_name in parents]

    def _create_single_task(
        self,
        question: "QuestionBase",
        dependencies: list[asyncio.Task],
        answer_func,
        token_estimator,
        model_buckets,
    ) -> asyncio.Task:
        """Create a single question task with its dependencies."""
        from ..tasks import QuestionTaskCreator

        task_creator = QuestionTaskCreator(
            question=question,
            answer_question_func=answer_func,
            token_estimator=token_estimator,
            model_buckets=model_buckets,
            iteration=self.iteration,
        )

        for dependency in dependencies:
            task_creator.add_dependency(dependency)

        self.task_creators[question.question_name] = task_creator
        return task_creator.generate_task()

    @property
    def task_status_logs(self) -> "InterviewStatusLog":
        """Return the task status logs for the interview.

        The keys are the question names; the values are the lists of status log changes for each task.
        """
        for task_creator in self.task_creators.values():
            self._task_status_log_dict[task_creator.question.question_name] = (
                task_creator.status_log
            )
        return self._task_status_log_dict

    @property
    def token_usage(self) -> "InterviewTokenUsage":
        """Determine how many tokens were used for the interview."""
        return self.task_creators.token_usage

    @property
    def interview_status(self) -> "InterviewStatusDictionary":
        """Return a dictionary mapping task status codes to counts."""
        return self.task_creators.interview_status

    def clear_references(self) -> None:
        """Clear references to help with garbage collection."""
        # Clear task creators which might hold references to the interview
        if hasattr(self, "task_creators"):
            self.task_creators = {}

        # Clear the survey reference
        if hasattr(self, "survey"):
            self.survey = None


if __name__ == "__main__":
    import doctest

    doctest.testmod()
