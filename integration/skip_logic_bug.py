from edsl.questions import QuestionMultipleChoice, QuestionLinearScale, QuestionTopK
from edsl import Survey

q1 = QuestionMultipleChoice(
    question_name="color",
    question_text="What is your favorite color?",
    question_options=["Red", "Orange", "Yellow", "Green", "Blue", "Purple"],
)
q2 = QuestionMultipleChoice(
    question_name="day",
    question_text="What is your favorite day of the week?",
    question_options=["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"],
)
q3 = QuestionLinearScale(
    question_name="winter",
    question_text="How much do you enjoy winter?",
    question_options=[0, 1, 2, 3, 4, 5],
    option_labels={0: "Hate it", 5: "Love it"},
)
q4 = QuestionTopK(
    question_name="birds",
    question_text="Which birds do you like best?",
    question_options=["Parrot", "Osprey", "Falcon", "Eagle", "First Robin of Spring"],
    min_selections=2,
    max_selections=2,
)

survey = Survey(questions=[q1, q2, q3, q4])
survey = survey.add_skip_rule(q2, "{{ color.answer }} == 'Blue'")

results = survey.run()
results.select("color", "day", "winter", "birds").print(format="rich")
