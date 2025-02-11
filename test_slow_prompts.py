from edsl import ScenarioList
from edsl import Survey
s = Survey.pull('da7595cd-9aa7-4270-ab9b-13021c0738dd')
print("Number of questions: ", len(s.questions))
sl = ScenarioList.pull('5a578ef9-7d56-4fb9-8b61-3af9190f93a9')
print("Number of scenarios: ", len(sl)) 

#N = 1000
#job = s.by(sl.shuffle()[:N])
#job = s.by(sl)
job = s.by(sl)

print("Number of interviews: ", len(job))
print("Checking prompts")
import time 
start = time.time()
prompts = job.prompts()
end = time.time()
elapsed_time = end - start
print("Elapsed time: ", elapsed_time)
print("Number of prompts: ", len(prompts))
time_per_prompt = elapsed_time / len(prompts)
print("Time per prompt: ", time_per_prompt)
print("Estimated time for all prompts: ", time_per_prompt * len(s.by(sl)) * len(s.questions))
