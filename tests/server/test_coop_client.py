import pytest
from edsl.coop.coop import Coop
from edsl.questions import QuestionMultipleChoice, QuestionCheckBox, QuestionFreeText


@pytest.mark.server
def test_coop_client():
    """
    Test the Coop client.
    - Server must be running!!!
    """
    coop = Coop()
    # this is drawn from pytest.ini
    assert coop.api_key == "b"

    # delete all questions
    for question in coop.questions:
        coop.delete_question(question.get("id"))

    # A. questions
    # check questions on server (should be an empty list)
    assert coop.questions == []

    # get a question that does not exist (should return None)
    with pytest.raises(Exception):
        coop.get_question(id=100)

    # create a multiple choice question
    response = coop.create_question(QuestionMultipleChoice.example())
    assert response.get("id") == 2
    assert response.get("type") == "question"

    response = coop.create_question(QuestionCheckBox.example(), public=False)
    assert response.get("id") == 3
    assert response.get("type") == "question"

    response = coop.create_question(QuestionFreeText.example(), public=True)
    assert response.get("id") == 4
    assert response.get("type") == "question"

    assert len(coop.questions) == 3
    assert coop.questions[0].get("id") == 2
    assert coop.questions[0].get("question") == QuestionMultipleChoice.example()

    for question in coop.questions:
        coop.delete_question(question.get("id"))
    assert coop.questions == []
