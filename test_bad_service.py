from edsl import QuestionFreeText 
from edsl import Model 
from edsl import Cache 

m = Model("fake_claude", service_name = "anthropic")
local_cache = Cache()

q = QuestionFreeText(
    question_name="q0",
    question_text="What is your name?",
)
#results = q.by(m).run(disable_remote_inference = True, cache = local_cache, stop_on_exception = True)
results = q.by(m).run(disable_remote_inference = True, cache = local_cache)
