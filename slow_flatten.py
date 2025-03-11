from edsl import Results
import os
import time

if not os.path.exists("forecasters-results.json.gz"):
    r = Results.pull("https://www.expectedparrot.com/content/RobinHorton/forecasters-results")
    r.save("forecasters-results.json.gz")
else:
    r = Results.load("forecasters-results.json.gz")

start = time.time()
new_r = r.flatten("answer.forecasts", keep_original=True)
end = time.time()
print(f"Time taken: {end - start} seconds")


sample_results = new_r.select('model', 'name', 'answer.*') #.sample(10)  #.table()