from edsl import QuestionYesNo, QuestionFreeText, Survey

used = QuestionYesNo(question_name="used", question_text="Have you used the export feature?")
problem = QuestionFreeText(
    question_name="problem",
    question_text="What problem, if any, did you encounter when exporting?",
)
followup = QuestionFreeText(
    question_name="followup",
    question_text="What would resolve this problem: {{ problem.answer }}?",
)
survey = (
    Survey([used, problem, followup])
    .add_stop_rule(used, "{{ used.answer }} == 'No'")
    .add_targeted_memory(followup, problem)
)
