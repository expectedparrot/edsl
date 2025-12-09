from edsl.macros.macro import Macro
from edsl.macros.output_formatter import OutputFormatter
from edsl.surveys import Survey
from edsl.questions import QuestionFreeText, QuestionEDSLObject
from edsl.agents import AgentList, Agent


# Define the generation question that will be applied to each agent
generation_question = QuestionFreeText(
    question_name="generated_content",
    question_text="""Based on your characteristics and background, please {{ scenario.generation_instructions }}.

Provide a detailed, realistic response that authentically represents someone with your profile.""",
)

# Create initial survey to collect user input
initial_survey = Survey(
    [
        QuestionEDSLObject(
            question_name="agent_list",
            question_text="Provide the AgentList to augment",
            expected_object_type="AgentList",
        ),
        QuestionFreeText(
            question_name="generation_instructions",
            question_text="What would you like each agent to generate? (e.g., 'write a detailed persona description', 'list 5 jobs this freelancer might have had', 'describe your ideal work environment')",
        ),
    ]
)

# Create jobs pipeline - the generation question will be applied to each agent in the list
jobs_object = Survey([generation_question]).to_jobs()

# Define output formatter to return the original scenarios augmented with generated content
output_formatter = (
    OutputFormatter(description="Agent Stories", output_type="ScenarioList")
    .select("scenario.*", "answer.*", "agent.*")
    .to_scenario_list()
)

# Create the macro
macro = Macro(
    application_name="story_time",
    display_name="Story Time",
    short_description="Generate creative stories based on prompts.",
    long_description="This application generates creative stories based on user prompts, themes, or scenarios using AI storytelling capabilities.",
    initial_survey=initial_survey,
    jobs_object=jobs_object,
    output_formatters={"stories": output_formatter},
    default_formatter_name="stories",
)

if __name__ == "__main__":
    # Example usage with a sample agent list
    from edsl.agents import Agent

    # Create some example agents
    sample_agents = AgentList(
        [
            Agent(
                {
                    "persona": "Experienced web developer",
                    "age": 32,
                    "location": "San Francisco",
                    "years_experience": 8,
                    "specialization": "React and Node.js",
                }
            ),
            Agent(
                {
                    "persona": "Freelance graphic designer",
                    "age": 28,
                    "location": "Austin",
                    "years_experience": 5,
                    "specialization": "Brand identity and UI design",
                }
            ),
            Agent(
                {
                    "persona": "Data scientist consultant",
                    "age": 35,
                    "location": "New York",
                    "years_experience": 10,
                    "specialization": "Machine learning and analytics",
                }
            ),
        ]
    )

    # Run with example parameters
    result = macro.output(
        params={
            "agent_list": sample_agents,
            "generation_instructions": "write a brief persona description highlighting your professional background and current goals",
        }
    )
    print(result)
