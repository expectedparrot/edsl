import pytest
from edsl.coop.coop import Coop
from edsl.questions import QuestionMultipleChoice, QuestionCheckBox, QuestionFreeText


@pytest.mark.server
def test_coop_client():
    """
    Test the Coop client.
    """
    coop = Coop()
    # this is drawn from pytest.ini
    assert coop.api_key == "b"
    # should start with an empty slate
    assert coop.surveys == []
    assert coop.agents == []
    assert coop.results == []

    # A. questions
    # check questions on server (should be an empty list)
    assert coop.questions == []
    for question in coop.questions:
        coop.delete_question(question.get("id"))

    # get a question that does not exist (should return None)
    with pytest.raises(Exception):
        coop.get_question(id=100)

    # create a multiple choice question
    response = coop.create_question(QuestionMultipleChoice.example())
    assert response.get("id") == 1
    assert response.get("type") == "question"

    response = coop.create_question(QuestionCheckBox.example(), public=False)
    assert response.get("id") == 2
    assert response.get("type") == "question"

    response = coop.create_question(QuestionFreeText.example(), public=True)
    assert response.get("id") == 3
    assert response.get("type") == "question"

    assert len(coop.questions) == 3
    assert coop.questions[0].get("id") == 1
    assert coop.questions[0].get("question") == QuestionMultipleChoice.example()

    # # or get question by id
    # coop.get_question(id=1)

    # # delete the question
    # coop.delete_question(id=1)

    # # check all questions
    # coop.questions
