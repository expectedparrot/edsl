from edsl import Model, QuestionFreeText
from edsl.language_models.LanguageModel import LanguageModel

# m = [LanguageModel.example(test_model=True, throw_exception=True) for _ in range(1000)]
q = QuestionFreeText.example()

m = LanguageModel.example(test_model=True, throw_exception=True)
results = q.by(m).run(
    n=1000,
    disable_remote_inference=True,
    cache=False,
    disable_remote_cache=True,
    print_exceptions=True,
)
