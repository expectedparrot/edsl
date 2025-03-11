from edsl import QuestionFreeText, Scenario

q = QuestionFreeText(
    question_text = """{% set z = 12 %}
    What is the sum of {{x}} and {{y}}?
    {{ vars.set('z', z) }}""",
    question_name = "sum"
)

results = q.by(Scenario({'x': 1, 'y': 2})).run(disable_remote_inference = True)

# from edsl.prompts import Prompt

# p = Prompt("The sum is {% set x = 2 + 3 %}{{ vars.set('x', x) }}{{x}}")
# result = p.render({})
# print(result.captured_variables)
 