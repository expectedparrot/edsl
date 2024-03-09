import asyncio
import pytest

from edsl.jobs.task_management import QuestionTaskCreator
from edsl import QuestionFreeText
from edsl.jobs.buckets import ModelBuckets

async def answer_question_func():
    return "test"

def test_instantiation():
    creator = QuestionTaskCreator(question = QuestionFreeText.example(), 
                                  answer_question_func = answer_question_func, 
                                  model_buckets = ModelBuckets.infinity_bucket())
    assert creator is not None