from edsl import QuestionMultipleChoice, Model


q = QuestionMultipleChoice(
    question_text="Who is most trustworthy?",
    question_options=["Sam Altman", "Elon Musk", "Dario Amodei"],
    question_name = "trustworthy"
)

models = Model.available()
results = q.by(models).run()








