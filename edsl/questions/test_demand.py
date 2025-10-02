from edsl.questions import QuestionDemand
from edsl import Agent 

a = Agent(traits = {'coffee_view': "Love it!"})
q = QuestionDemand(
      question_name="coffee_demand",
      question_text="How many cups would you buy per week at each price?",
      prices=[1.0, 2.0, 3.0, 4.0, 5.0]
)

  # With disable_remote_inference=True, you can see the generated prompts
results = q.by(a).run(disable_remote_inference=True)
# user_prompt = results.select("coffee_demand_user_prompt").to_list()[0]