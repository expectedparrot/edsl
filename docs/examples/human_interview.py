from edsl import QuestionInterview, QuestionLinearScale, QuestionMultipleChoice, Survey

frequency = QuestionMultipleChoice(
    question_name="export_frequency",
    question_text="How often do you export reports?",
    question_options=["Daily", "Weekly", "Less often"],
)

interview = QuestionInterview(
    question_name="export_experience",
    question_text="Describe your experience exporting a report.",
    interview_guide=(
        # Pipe the participant's earlier answer into the interviewer's guide.
        "The participant exports reports {{ export_frequency.answer }}. "
        "Ask about the participant's most recent attempt to export a report. "
        "Explore how that experience fits their usual reporting routine. "
        "Ask what they tried, where they encountered difficulty, and what helped. "
        "Use neutral follow-ups to clarify details; do not suggest problems."
    ),
    max_turns=8,
)

ease = QuestionLinearScale(
    question_name="export_ease",
    question_text="Overall, how easy was your most recent attempt to export a report?",
    question_options=[1, 2, 3, 4, 5],
    option_labels={1: "Very difficult", 5: "Very easy"},
)

# The interview is one question in the same survey as the structured questions.
survey = Survey([frequency, interview, ease])
humanize_schema = {
    "questions": {"export_experience": {"interview_mode": "text"}}
}
