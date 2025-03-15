from edsl import QuestionFreeText
from edsl.language_models.LanguageModel import LanguageModel
import threading
from edsl.jobs.buckets.BucketCollection import BucketCollection


def run_inference(question, model, bucket_collection, results_dict, key):
    results_dict[key] = question.by(model).run(
        n=5,
        disable_remote_inference=True,
        progress_bar=True,
        cache=False,
        disable_remote_cache=True,
        print_exceptions=True,
        bucket_collection=bucket_collection,
    )


q = QuestionFreeText.example()
m = LanguageModel.example(test_model=True, throw_exception=True)
m.tpm = 100000
m.rpm = 5000

## Multiple jobs will share this bucket collection
bc = BucketCollection()
bc.add_model(m)

# Dictionary to store results
results = {}

threads = []
for thread_number in range(2):
    key = f"results{thread_number}"
    t = threading.Thread(target=run_inference, args=(q, m, bc, results, key))
    threads.append(t)

for t in threads:
    t.start()

for t in threads:
    t.join()

results1 = results["results1"]
print(results1.select("answer.*"))
