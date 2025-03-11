from edsl import QuestionMultipleChoice, QuestionFreeText, Scenario, Survey

q0 = QuestionMultipleChoice(
    question_name = "changes",
    question_text = """
    Compare these drafts:
    First draft: {{ text_a }}
    Second draft: {{ text_b }}
    Were changes made to the first draft?
    """,
    question_options = [
        "Yes, changes were made.",
        "No changes were made.",
        "I do not know whether any changes were made."
    ]
)

q1 = QuestionFreeText(
    question_name = "review",
    question_text = "Do the changes improve the text?"
)

scenario = Scenario({"text_a":"This is a fine day.", "text_b":"This is a fine day."})

jobs = Survey([q0, q1]).add_skip_rule(q1, "{{ changes.answer}} == 'No changes were made.'").by(scenario)

jobs.run(disable_remote_inference = True, stop_on_exception = True)