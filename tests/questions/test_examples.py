import pytest
import shutil
from edsl.questions.question_registry import Question


@pytest.mark.parametrize("question_type", Question.list_question_types())
def test_individual_questions(question_type):
    if question_type not in ["functional", "edsl_object", 'file_upload', 'pydantic', 'dropdown']:
        if question_type == "diagram" and shutil.which("dot") is None:
            pytest.skip("Graphviz dot executable is not installed")
        q = Question.example(question_type)
        r = q.example_results()
        _ = hash(r)
        pandas = pytest.importorskip("pandas")
        _ = r._repr_html_()
    else:
        pytest.skip("Skipping functional question type")
