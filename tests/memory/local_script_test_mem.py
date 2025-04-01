from edsl import FileStore, Scenario
from edsl import QuestionFreeText, QuestionList
from edsl import Survey, Model
import json
import time
from memory_profiler import memory_usage

import os
current_dir = os.path.dirname(__file__)
img_path = os.path.join(current_dir, "test_img.png")
my_print = FileStore(img_path)

s = Scenario({f"image_{i}": my_print for i in range(0, 10)})

def print_memory(label):
    from memory_profiler import memory_usage
    mem = memory_usage(-1, interval=0.1, timeout=1)
    print(f"[MEM] {label}: {mem[0]:.2f} MiB")

def memory_test():
    print_memory("Start")
    
    questions = []
    for i in range(0, 2):
        q0 = QuestionFreeText(
            question_name=f"topic_{i}",
            question_text="Describe what is happening in this print: {{ scenario.image_" + f"{i}" + " }}"
        )

        q1 = QuestionFreeText(
            question_name=f"colors_{i}",
            question_text="List the prominent colors in this print: {{ scenario.image_" + f"{i}" + " }}"
        )

        q2 = QuestionFreeText(
            question_name=f"year_{i}",
            question_text="Estimate the year that this print was created: {{ scenario.image_" + f"{i}" + " }}"
        )

        questions.extend([q0, q1, q2])
    
    print_memory("After creating questions")

    survey = Survey(questions=questions)
    model = Model("test", rpm=10000, tpm=10000000)

    print_memory("Before survey run")

    results = survey.by(s).by(model).run(disable_remote_inference=True, cache=False)

    print_memory("After survey run")

    out_res = results.to_dict()
    json_string = json.dumps(out_res)
    open("test.json", "w").write(json_string)

    print_memory("After writing results")


def memory_test_with_task():
    print_memory("Start")
    
    questions = []
    for i in range(0, 10):
        q0 = QuestionFreeText(
            question_name=f"topic_{i}",
            question_text="Describe what is happening in this print: {{ scenario.image_" + f"{i}" + " }}"
        )

        q1 = QuestionList(
            question_name=f"colors_{i}",
            question_text="List the prominent colors in this print: {{ scenario.image_" + f"{i}" + " }}"
        )

        q2 = QuestionFreeText(
            question_name=f"year_{i}",
            question_text="Estimate the year that this print was created: {{ scenario.image_" + f"{i}" + " }}"
        )

        questions.extend([q0, q1, q2])
    
    print_memory("After creating questions")

    survey = Survey(questions=questions)
    model = Model("test", rpm=10000, tpm=10000000)

    print_memory("Before survey run")

    results = survey.by(s).by(model).run(disable_remote_inference=True, cache=False)

    print_memory("After survey run")

    out_res = results.to_dict()
    json_string = json.dumps(out_res)
    open("test.json", "w").write(json_string)

    print_memory("After writing results")


if __name__ == "__main__":
    for rep in range(1, 2):
        print(f"Running test {rep}")
        start_time = time.time()
        memory_test()
        end_time = time.time()

        print(f"Time taken for {rep} run: {end_time - start_time:.2f} seconds")
        memory_test_with_task()
