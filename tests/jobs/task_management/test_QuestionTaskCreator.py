import asyncio
import pytest
from collections import namedtuple

from edsl.tasks import TaskStatus
from edsl.tasks import QuestionTaskCreator
from edsl.questions import QuestionFreeText
from edsl.buckets import ModelBuckets

AnswerTuple = namedtuple("AnswerTuple", ["answer", "cache_used"])

answer = AnswerTuple(answer=42, cache_used=False)


async def answer_question_func(question, task=None):
    await asyncio.sleep(1)
    return answer


def test_instantiation():
    creator = QuestionTaskCreator(
        question=QuestionFreeText.example(),
        answer_question_func=answer_question_func,
        model_buckets=ModelBuckets.infinity_bucket(),
    )
    assert creator is not None


@pytest.mark.asyncio
async def test_task_creation():
    creator = QuestionTaskCreator(
        question=QuestionFreeText.example(),
        answer_question_func=answer_question_func,
        model_buckets=ModelBuckets.infinity_bucket(),
    )

    task = await creator.generate_task()

    results = await creator._run_focal_task()
    assert results == answer

    assert creator.task_status == TaskStatus.SUCCESS


@pytest.mark.asyncio
async def test_task_add_dependency():

    async def answer_question_func(question):
        await asyncio.sleep(1)
        return answer

    creator_1 = QuestionTaskCreator(
        question=QuestionFreeText.example(),
        answer_question_func=answer_question_func,
        model_buckets=ModelBuckets.infinity_bucket(),
    )

    creator_2 = QuestionTaskCreator(
        question=QuestionFreeText.example(),
        answer_question_func=answer_question_func,
        model_buckets=ModelBuckets.infinity_bucket(),
    )

    creator_2.add_dependency(creator_1.generate_task())

    assert creator_2.generate_task().depends_on == [
        QuestionFreeText.example().question_name
    ]

    asyncio.run(creator_2._run_task_async())


@pytest.mark.asyncio
async def test_task_add_dependency():

    async def answer_question_func(question):
        await asyncio.sleep(1)
        return AnswerTuple(answer=42)

    creator_1 = QuestionTaskCreator(
        question=QuestionFreeText.example(),
        answer_question_func=answer_question_func,
        model_buckets=ModelBuckets.infinity_bucket(),
    )

    creator_2 = QuestionTaskCreator(
        question=QuestionFreeText.example(),
        answer_question_func=answer_question_func,
        model_buckets=ModelBuckets.infinity_bucket(),
    )

    task_1 = creator_1.generate_task()
    creator_2.add_dependency(task_1)
