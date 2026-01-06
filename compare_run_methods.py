from edsl import QuestionFreeText, Model
import time
q = QuestionFreeText(question_name="example", 
                     question_text="Where is Salisbury, CT?")
m = Model()
jobs = q.by(m)
start = time.time()
newresults = jobs.new_run(cache = False, n = 20)
end = time.time()
print(f"Time taken to run new_run: {end - start}")
start = time.time()
results = jobs.run(cache = False, disable_remote_inference = True, n = 20)
end = time.time()
print(f"Time taken to run run: {end - start}")

if newresults != results:
    delta = results - newresults
    #print(delta)
else:
    print("new_run and run produced the same results")
