import asyncio
import pytest

from edsl.jobs.tasks.task_status_enum import TaskStatus
from edsl.jobs.tasks.QuestionTaskCreator import QuestionTaskCreator
from edsl import QuestionFreeText
from edsl.jobs.buckets.ModelBuckets import ModelBuckets


async def answer_question_func(question, debug, task = None):
    await asyncio.sleep(1)
    return {"answer": 42}


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

    task = await creator.generate_task(debug=False)

    results = await creator._run_focal_task(debug=False)
    assert results == {"answer": 42}

    assert creator.task_status == TaskStatus.SUCCESS


@pytest.mark.asyncio
async def test_task_add_dependency():

    async def answer_question_func(question, debug):
        await asyncio.sleep(1)
        return {"answer": 42}

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

    creator_2.add_dependency(creator_1.generate_task(debug=False))

    assert creator_2.generate_task(debug=False).depends_on == [QuestionFreeText.example().question_name]

    asyncio.run(creator_2._run_task_async(debug=False))
    #breakpoint()

    #results = await creator._run_focal_task(debug=False)
    #assert results == {"answer": 42}

    #assert creator.task_status == TaskStatus.FINISHED


@pytest.mark.asyncio
async def test_task_add_dependency():

    async def answer_question_func(question, debug):
        await asyncio.sleep(1)
        return {"answer": 42}

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

    task_1 = creator_1.generate_task(debug=False)
    creator_2.add_dependency(task_1)

    ## What should we do here?
    task_1.cancel()
    #assert creator_2.generate_task(debug=False).depends_on == [QuestionFreeText.example().question_name]
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(creator_2._run_task_async(debug=False))
    
    #breakpoint()