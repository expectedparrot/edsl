import asyncio
import pytest

from edsl.jobs.task_management import TaskStatus
from edsl.jobs.task_management import QuestionTaskCreator
from edsl import QuestionFreeText
from edsl.jobs.buckets import ModelBuckets

async def answer_question_func(question, debug):
    await asyncio.sleep(1)
    return {'answer': 42}

def test_instantiation():
    creator = QuestionTaskCreator(question = QuestionFreeText.example(), 
                                  answer_question_func = answer_question_func, 
                                  model_buckets = ModelBuckets.infinity_bucket())
    assert creator is not None


@pytest.mark.asyncio
async def test_task_creation():
    creator = QuestionTaskCreator(question = QuestionFreeText.example(), 
                                  answer_question_func = answer_question_func, 
                                  model_buckets = ModelBuckets.infinity_bucket())

    task = await creator.generate_task(debug = False)

    results = await creator._run_focal_task(debug = False)
    assert results == {'answer': 42}

    assert creator.task_status  == TaskStatus.FINISHED