from edsl import QuestionList, Scenario, Model


def summarize(texts, seed_phrase, n_bullets, n_words, models=None):
    if models is None:
        models = Model()
    s = Scenario(
        text=texts, seed_phrase=seed_phrase, n_bullets=n_bullets, n_words=n_words
    ).expand("text")
    QuestionList(
        question_text="""
        I have the following TEXT EXAMPLE :
        {{ text_example_json }}
        Please summarize the main point of this EXAMPLE {{seed_phrase }} into {{ n_bullets }} bullet points, where
        each bullet point is a {{ n_words }} word phrase.
        """,
        question_name="summarize",
    ).by(s).by(models).run()
