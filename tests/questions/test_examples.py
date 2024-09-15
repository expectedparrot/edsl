import pytest
from edsl import Question


@pytest.mark.parametrize("question_type", Question.available())
def test_individual_questions(question_type):
    # if question_type != "functional" and question_type != "extract":
    if question_type == "multiple_choice":
        q = Question.example(question_type)
        r = q.example_results()
        _ = hash(r)
        _ = r._repr_html_()
    else:
        pytest.skip("Skipping functional question type")
