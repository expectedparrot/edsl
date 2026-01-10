import pytest

from edsl.language_models import Model
from edsl.questions import QuestionFreeText

m = Model("test", canned_response="Hi", exception_probability=0.1, throw_exception=True)
q = QuestionFreeText(question_text="What is your name?", question_name="name")


def test_repair_enabled():
    results = q.by(m).run(n=100, progress_bar=False, cache=False, stop_on_exception=False, disable_remote_inference=True)
    assert len([x for x in results.select("answer.name").to_list() if x == None]) == 0


def test_repair_off():
    with pytest.raises(Exception):
        results = q.by(m).run(
            n=100, progress_bar=False, cache=False, stop_on_exception=True, disable_remote_inference=True
        )

