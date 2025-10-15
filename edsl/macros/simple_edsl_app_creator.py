#!/usr/bin/env python3
"""
Simple EDSL App Creator

Creates EDSL apps based on descriptions by analyzing existing patterns
and generating new apps following established conventions.
"""

import os
import sys
import re
from pathlib import Path
from typing import Dict, List, Any, Optional


class SimpleEDSLAppCreator:
    """Creates EDSL apps by analyzing patterns in existing apps"""

    def __init__(self):
        self.examples_dir = Path(__file__).parent
        self.guide_path = self.examples_dir / "EDSL_App_Development_Guide.md"
        self.patterns = self._analyze_patterns()

    def _analyze_patterns(self) -> Dict[str, Any]:
        """Analyze existing apps to extract common patterns"""
        patterns = {
            "imports": {
                "common": [
                    "from edsl.macros.macro import Macro",
                    "from edsl.macros.output_formatter import OutputFormatter",
                    "from edsl.surveys import Survey",
                    "from edsl.questions import QuestionFreeText, QuestionList, QuestionNumerical, QuestionMultipleChoice"
                ],
                "agent_patterns": [
                    "from edsl.agents import AgentList",
                    "from edsl.scenarios import ScenarioList"
                ]
            },
            "question_types": {
                "text_input": "QuestionFreeText",
                "list_input": "QuestionList",
                "number_input": "QuestionNumerical",
                "choice_input": "QuestionMultipleChoice"
            },
            "app_templates": {
                "general": self._get_general_template(),
                "agent_augmentation": self._get_agent_augmentation_template()
            }
        }
        return patterns

    def _get_general_template(self) -> str:
        """Template for general purpose apps"""
        return '''from edsl.macros.macro import Macro
from edsl.macros.output_formatter import OutputFormatter
from edsl.surveys import Survey
from edsl.questions import QuestionFreeText, QuestionList, QuestionNumerical

# Define questions
{questions}

# Create initial survey
initial_survey = Survey([
{survey_questions}
])

# Create jobs pipeline
jobs_object = {jobs_logic}

# Define output formatter
output_formatter = (
    OutputFormatter(description="{app_title}")
    .select({output_fields})
    .to_markdown()
)

# Create the app
app = App(
    description="{description}",
    application_name="{app_name}",
    initial_survey=initial_survey,
    jobs_object=jobs_object,
    output_formatters={{"default": output_formatter}},
    default_formatter_name="default",
)

if __name__ == "__main__":
    result = app.output(params={example_params})
    print(result)
'''

    def _get_agent_augmentation_template(self) -> str:
        """Template for apps that augment agent lists"""
        return '''from edsl.macros.macro import Macro
from edsl.macros.output_formatter import OutputFormatter
from edsl.surveys import Survey
from edsl.questions import QuestionFreeText
from edsl.agents import AgentList
from edsl.scenarios import ScenarioList

# Define the generation question
generation_question = QuestionFreeText(
    question_name="generated_content",
    question_text="""{generation_prompt}"""
)

# Create initial survey for user input
initial_survey = Survey([
    QuestionFreeText(
        question_name="agent_list_input",
        question_text="Provide the AgentList (or description of agents) to augment"
    ),
    QuestionFreeText(
        question_name="generation_instructions",
        question_text="What should be generated for each agent? (e.g., 'Write a persona', 'List jobs they might have had')"
    )
])

# Create jobs pipeline that uses the agent list with the generation question
def create_jobs_pipeline():
    # This would need to be customized based on how AgentList is provided
    # Basic pattern: take agents and apply generation question to each
    return Survey([generation_question]).to_jobs()

jobs_object = create_jobs_pipeline()

# Define output formatter to return augmented scenarios
output_formatter = (
    OutputFormatter(description="{app_title}")
    .select("scenario.*", "answer.*")
    .to_scenario_list()
)

# Create the app
app = App(
    description="{description}",
    application_name="{app_name}",
    initial_survey=initial_survey,
    jobs_object=jobs_object,
    output_formatters={{"default": output_formatter}},
    default_formatter_name="default",
)

if __name__ == "__main__":
    # Example usage
    result = app.output(params={example_params})
    print(result)
'''

    def create_app(self, description: str, app_name: str, output_path: Optional[str] = None) -> Dict[str, Any]:
        """Create an EDSL app based on description"""
        try:
            if output_path is None:
                output_path = self.examples_dir / f"{app_name}.py"

            # Determine app type based on description
            app_type = self._determine_app_type(description)

            # Generate the app code
            if app_type == "agent_augmentation":
                code = self._create_agent_augmentation_app(description, app_name)
            else:
                code = self._create_general_app(description, app_name)

            # Write the file
            with open(output_path, 'w') as f:
                f.write(code)

            return {
                "status": "success",
                "app_name": app_name,
                "output_path": str(output_path),
                "description": description,
                "app_type": app_type
            }

        except Exception as e:
            return {
                "status": "error",
                "error": f"Error creating app: {e}"
            }

    def _determine_app_type(self, description: str) -> str:
        """Determine the type of app based on description"""
        description_lower = description.lower()

        agent_keywords = ["agentlist", "agent list", "agents", "personas", "augment"]

        if any(keyword in description_lower for keyword in agent_keywords):
            return "agent_augmentation"
        else:
            return "general"

    def _create_agent_augmentation_app(self, description: str, app_name: str) -> str:
        """Create an agent augmentation app"""
        template = self.patterns["app_templates"]["agent_augmentation"]

        # Generate a prompt for the generation question
        generation_prompt = self._extract_generation_prompt(description)

        return template.format(
            app_title=app_name.replace("_", " ").title(),
            description=description,
            app_name=app_name,
            generation_prompt=generation_prompt,
            example_params="""{
        "agent_list_input": "Example agent list or description",
        "generation_instructions": "Example generation instructions"
    }"""
        )

    def _create_general_app(self, description: str, app_name: str) -> str:
        """Create a general purpose app"""
        template = self.patterns["app_templates"]["general"]

        # Extract key components from description
        questions, survey_questions, jobs_logic, output_fields, example_params = self._analyze_description(description)

        return template.format(
            questions=questions,
            survey_questions=survey_questions,
            jobs_logic=jobs_logic,
            output_fields=output_fields,
            example_params=example_params,
            app_title=app_name.replace("_", " ").title(),
            description=description,
            app_name=app_name
        )

    def _extract_generation_prompt(self, description: str) -> str:
        """Extract or create a generation prompt from the description"""
        # Look for examples in the description
        if "e.g." in description or "example" in description.lower():
            # Try to extract examples
            examples_match = re.search(r'e\.g\..*?([^.]+)', description, re.IGNORECASE)
            if examples_match:
                return f"Based on this agent's characteristics, please {examples_match.group(1).strip()}."

        # Default generation prompt
        return """Based on this agent's characteristics and background, please generate {{{{ scenario.generation_instructions }}}} for this person.

Agent details: {{{{ agent }}}}

Instructions: {{{{ scenario.generation_instructions }}}}

Provide a detailed, realistic response that fits this agent's profile."""

    def _analyze_description(self, description: str) -> tuple:
        """Analyze description to extract app components"""
        # Simple heuristic-based analysis
        questions = """q_input = QuestionFreeText(
    question_name="user_input",
    question_text="Enter your input:"
)"""

        survey_questions = "    q_input"

        jobs_logic = "Survey([q_input]).to_jobs()"

        output_fields = '"answer.user_input"'

        example_params = '{"user_input": "Example input"}'

        return questions, survey_questions, jobs_logic, output_fields, example_params

    def interactive_mode(self):
        """Interactive mode for creating apps"""
        print("🤖 Simple EDSL App Creator - Interactive Mode")
        print("=" * 50)

        while True:
            print("\nOptions:")
            print("1. Create new app")
            print("2. Exit")

            choice = input("Choose option (1-2): ").strip()

            if choice == "2":
                print("Goodbye! 👋")
                break
            elif choice == "1":
                description = input("\n📝 Describe the app you want to create: ").strip()
                if not description:
                    print("❌ Description cannot be empty")
                    continue

                app_name = input("📁 Enter app name (without .py): ").strip()
                if not app_name:
                    print("❌ App name cannot be empty")
                    continue

                # Sanitize app name
                app_name = "".join(c for c in app_name if c.isalnum() or c in "_-").lower()

                print(f"\n🚀 Creating app: {app_name}")
                print(f"📋 Description: {description}")
                print("-" * 40)

                result = self.create_app(description, app_name)

                if result["status"] == "success":
                    print(f"✅ App created successfully!")
                    print(f"📄 File: {result['output_path']}")
                    print(f"🏷️  Type: {result['app_type']}")
                else:
                    print(f"❌ Error creating app: {result['error']}")
            else:
                print("❌ Invalid choice")


def main():
    """Main function"""
    creator = SimpleEDSLAppCreator()

    if len(sys.argv) > 1:
        # Command line mode
        if len(sys.argv) < 3:
            print("Usage: python simple_edsl_app_creator.py '<description>' '<app_name>' [output_path]")
            sys.exit(1)

        description = sys.argv[1]
        app_name = sys.argv[2]
        output_path = sys.argv[3] if len(sys.argv) > 3 else None

        print(f"🚀 Creating EDSL app: {app_name}")
        print(f"📋 Description: {description}")
        print("-" * 50)

        result = creator.create_app(description, app_name, output_path)

        if result["status"] == "success":
            print(f"✅ App created successfully!")
            print(f"📄 File: {result['output_path']}")
            print(f"🏷️  Type: {result['app_type']}")
        else:
            print(f"❌ Error: {result['error']}")
            sys.exit(1)
    else:
        # Interactive mode
        creator.interactive_mode()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n👋 Interrupted by user")
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        sys.exit(1)