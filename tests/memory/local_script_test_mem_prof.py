
from edsl import FileStore,Scenario
from memory_profiler import profile
from edsl import QuestionFreeText, QuestionList, QuestionNumerical
from edsl import Survey,Model
import json
import os
current_dir = os.path.dirname(__file__)
img_path = os.path.join(current_dir, "test_img.png")
my_print = FileStore(img_path)

s = Scenario({f"image_{i}": my_print for i in range(0, 10)})
@profile
def memory_test():
    questions = []
    for i in range(0,10):
        q0 = QuestionFreeText(
            question_name = f"topic_{i}",
            question_text = "Describe what is happening in this print: {{ scenario.image_"+f"{i}"+" }}"
        )

        q1 = QuestionList(
            question_name = f"colors_{i}",
            question_text = "List the prominent colors in this print: {{ scenario.image_"+f"{i}"+" }}",

        )

        q2 = QuestionFreeText(
            question_name = f"year_{i}",
            question_text = "Estimate the year that this print was created: {{ scenario.image_"+f"{i}"+" }}",
        )
        questions.extend([q0, q1, q2])
    survey = Survey(questions = questions)
    model = Model("test",rpm=10000,tpm=10000000)
    results = survey.by(s).by(model).run(disable_remote_inference=True,cache=False)
    out_res = results.to_dict()
    json_string = json.dumps(out_res)
    open("test.json","w").write(json.dumps(out_res))

if __name__ == "__main__":
    import time 
    for rep in range(1, 2):
        start = time.time()
        memory_test()
        print(f"Time taken for {rep} times initial questions: {time.time() - start}")
