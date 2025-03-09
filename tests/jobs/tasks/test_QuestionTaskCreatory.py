import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, Mock

from edsl.tasks import QuestionTaskCreator
from edsl.buckets.ModelBuckets import ModelBuckets
from edsl.tasks import TaskStatus
from edsl.questions import QuestionBase
from edsl.exceptions.jobs import InterviewErrorPriorTaskCanceled

from collections import namedtuple

AnswerTuple = namedtuple("AnswerTuple", ["answer", "cache_used", "usage"])

answer = AnswerTuple(
    answer=42, cache_used=False, usage={"prompt_tokens": 10, "completion_tokens": 20}
)


class TestQuestionTaskCreator(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.question = MagicMock(spec=QuestionBase, question_name="test_question")
        self.answer_question_func = AsyncMock(return_value=answer)
        self.model_buckets = MagicMock(spec=ModelBuckets)
        self.model_buckets.requests_bucket = Mock(
            wait_time=Mock(return_value=0), get_tokens=AsyncMock()
        )
        self.model_buckets.tokens_bucket = AsyncMock(
            wait_time=Mock(return_value=0), get_tokens=AsyncMock(), add_tokens=Mock()
        )

        self.task_creator = QuestionTaskCreator(
            question=self.question,
            answer_question_func=self.answer_question_func,
            model_buckets=self.model_buckets,
        )

    def test_initialization(self):
        self.assertEqual(self.task_creator.task_status, TaskStatus.NOT_STARTED)
        self.assertFalse(self.task_creator.from_cache)

    async def test_add_dependency(self):
        task = asyncio.create_task(asyncio.sleep(0.1))
        self.task_creator.add_dependency(task)
        self.assertIn(task, self.task_creator)

    async def test_estimated_tokens(self):
        self.task_creator.token_estimator = MagicMock(return_value=5)
        self.assertEqual(self.task_creator.estimated_tokens(), 5)

    # async def test_token_usage_reporting(self):
    #     self.task_creator.from_cache = False
    #     self.assertEqual(self.task_creator.token_usage().new_tokens.from_cache, False)

    async def test_generate_task(self):
        task = self.task_creator.generate_task()
        self.assertIsInstance(task, asyncio.Task)
        self.assertIn("test_question", task.get_name())

    async def test_run_focal_task_success(self):
        asyncio.run(self.task_creator._run_focal_task())
        self.assertEqual(self.task_creator.task_status, TaskStatus.SUCCESS)

    async def test_dependency_failure_handling(self):
        # Set up a failing task
        async def fail_task():
            raise Exception("Dependency failed")

        failing_task = asyncio.create_task(fail_task())

        self.task_creator.add_dependency(failing_task)

        with self.assertRaises(InterviewErrorPriorTaskCanceled):
            asyncio.run(self.task_creator._run_task_async())

        self.assertEqual(self.task_creator.task_status, TaskStatus.PARENT_FAILED)

    # async def test_dependency_cancellation_handling(self):
    #     async def cancel_task():
    #         await asyncio.sleep(0.1)
    #         raise asyncio.CancelledError()

    #     cancelling_task = asyncio.create_task(cancel_task())
    #     self.task_creator.add_dependency(cancelling_task)

    #     with self.assertRaises(asyncio.CancelledError):
    #         asyncio.run(self.task_creator._run_task_async(debug=False))

    #     self.assertEqual(self.task_creator.task_status, TaskStatus.CANCELLED)


if __name__ == "__main__":
    unittest.main()
