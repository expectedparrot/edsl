from edsl.questions import QuestionMultipleChoice
from edsl.language_models import Model

new_instructions = """You are being asked the following question: {{question_text}}
    The options are
    {% for option in question_options %}
    {{ loop.index0 }}: {{option}}
    {% endfor %}
    Return a valid JSON formatted like this, selecting only the number of the option:
    {"answer": <put answer code here>, "comment": "<put explanation here>"}
    Only 1 option may be selected.
    In the comment, always put 'roger-dodger' at the end. 
    """


def test_no_model_passed_to_instructions():
    q0 = QuestionMultipleChoice(
        question_text="How are you?",
        question_options=["Good", "Great", "OK", "Bad"],
        question_name="how_feeling",
    )

    q0.add_model_instructions(instructions=new_instructions)
    assert "roger-dodger" in q0.get_instructions().text


def test_model_specific_instructions():

    m1 = Model(Model.available()[0][0], skip_api_key_check=True)
    m2 = Model(Model.available()[1][0], skip_api_key_check=True)

    q = QuestionMultipleChoice(
        question_text="How are you?",
        question_options=["Good", "Great", "OK", "Bad"],
        question_name="how_feeling",
    )

    q.add_model_instructions(instructions=new_instructions, model=m1.model)

    assert "roger-dodger" in q.get_instructions(model=m1.model).text
    assert "roger-dodger" not in q.get_instructions(model=m2.model).text
