
from edsl.language_models import Model
from edsl.questions import QuestionFreeText


def test_one_per_service():
    models = [Model(temperature=1), Model(temperature=2), Model(temperature=0)]
    q = QuestionFreeText(
        question_text="What is your favorite color?", question_name="color"
    )
    jobs = q.by(models)

    # assert len(jobs.models) == 3

    # bc = jobs.bucket_collection
    # assert len(bc) == 3
    # assert len(set(bc.values())) == 1
