from edsl.questions import QuestionFreeText
from edsl import Model


def test_failure():
    # https://github.com/goemeritus/edsl/issues/78
    m35 = Model("gpt-3.5-turbo")
    m4 = Model("gpt-4-1106-preview")

    q = QuestionFreeText(
        question_name="personas",
        question_text="Draft detailed narratives for 5 personas likely to provide diverse responses to a public opinion poll about AI.",
    )

    r_m35 = q.by(m35).run()
    r_4 = q.by(m4).run()
