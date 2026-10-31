from edsl import Cache, Model, QuestionFreeText

cache = Cache()
question = QuestionFreeText(
    question_name="feedback", question_text="What would improve this service?"
)
job = question.by(Model("test", canned_response="A clearer export button."))
settings = dict(
    cache=cache,
    disable_remote_inference=True,
    disable_remote_cache=True,
    progress_bar=False,
)
first = job.run(**settings)
second = job.run(**settings)
assert first.select("answer.feedback").to_list() == second.select("answer.feedback").to_list()

cache.write_jsonl("feedback-cache.jsonl")
saved_cache = Cache.from_jsonl("feedback-cache.jsonl")
assert len(saved_cache) == len(cache)
