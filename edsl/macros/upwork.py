import textwrap
from edsl.macros.examples.agent_blueprint_creator import app as blueprint_creator
from edsl.macros.examples.story_time import app as story_time

output = blueprint_creator.output(params={
    'population_description': 'Experienced Upwork freelancers',
    'num_dimensions': 8,
    'additional_details':textwrap.dedent("""\
        Focus on work preferences, skill specialization, and experience with different client types
        Should include details on country of residence and language proficiency and attitudes towards freelancing/Upwork."""
        )
})

agent_list = output.create_agent_list(n=20)

agent_list_info = agent_list.push(
    visibility = "unlisted", 
    description = "Experienced Upwork freelancers", 
    alias = "upwork-freelancers-v2")

print(agent_list_info)

s = story_time.output(params={
    'agent_list': agent_list,
    'generation_instructions': textwrap.dedent("""\
Describe the most recent job you had on Upwork and how it went. 
Include rich details and context.
Focus on issues and problems you might have encountered using the Upwork platform, the challenges you faced and so on. """),
})

recent_job_info = s.push(
    visibility = "unlisted", 
    description = "Experienced Upwork freelancers with recent job experiences", 
    alias = "upwork-freelancers-experiences-v2")

print(recent_job_info)

