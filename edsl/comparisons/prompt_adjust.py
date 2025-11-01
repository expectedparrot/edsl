"""LLM-driven persona improvement based on performance gap analysis.

This module provides the PromptAdjust class that analyzes agent performance
against gold standards and generates improved personas directly.
"""

from typing import Optional
from rich.console import Console


class PromptAdjust:
    """LLM-powered batch analysis to generate improved personas based on performance gaps.

    This class analyzes how agent responses differ from a gold standard and uses
    an LLM to generate improved personas directly. All methods operate on multiple
    agents simultaneously using EDSL ScenarioLists for efficient parallel processing.

    Examples
    --------
    >>> # Batch usage for multiple agents
    >>> adjuster = PromptAdjust(
    ...     agent_results=results,
    ...     gold_standard_dict={"nervous": "Yes", "hobbies": ["Basketball"]},
    ...     survey=survey
    ... )
    >>> # Generate improved personas for all agents at once
    >>> improved_personas = adjuster.generate_improved_personas(["agent1", "agent2", "agent3"])
    """

    def __init__(self, agent_results, gold_standard_dict: dict, survey):
        """Initialize PromptAdjust with agent responses and gold standard.

        Parameters
        ----------
        agent_results
            EDSL Results object containing agent responses to the survey
        gold_standard_dict
            Dictionary mapping question_name -> expected_answer
        survey
            The EDSL Survey object that was administered

        Raises
        ------
        ValueError
            If validation checks fail on the provided data
        """
        # Validate inputs
        if agent_results is None:
            raise ValueError("agent_results cannot be None")
        if not gold_standard_dict:
            raise ValueError("gold_standard_dict cannot be empty")
        if survey is None:
            raise ValueError("survey cannot be None")

        self.agent_results = agent_results
        self.gold_standard_dict = gold_standard_dict
        self.survey = survey

        self.agent_list = self.agent_results.agents

        # Validate all agents have names
        if not all([a.traits.get("agent_name") is not None for a in self.agent_list]):
            raise ValueError("All agents must have a name")

        # Pre-validate that all agents can be accessed from results
        agent_count = len(self.agent_list)
        try:
            # Test access to agent personas
            personas = self.agent_results.select("agent.persona").to_list()
            if len(personas) < agent_count:
                raise ValueError(
                    f"Cannot access all agent personas: expected {agent_count}, got {len(personas)}"
                )
        except Exception as e:
            raise ValueError(f"Cannot access agent personas from results: {e}")

        # Pre-validate that all gold standard questions can be accessed
        for question_name in self.gold_standard_dict.keys():
            try:
                answer_column = f"answer.{question_name}"
                answers = self.agent_results.select(answer_column).to_list()
                if len(answers) < agent_count:
                    raise ValueError(
                        f"Cannot access answers for question '{question_name}': expected {agent_count}, got {len(answers)}"
                    )
            except Exception as e:
                raise ValueError(
                    f"Cannot access answers for question '{question_name}': {e}"
                )

    def _get_agent_index_by_name(self, agent_name: str) -> Optional[int]:
        """Get the index of an agent by its name.

        Parameters
        ----------
        agent_name
            Name of the agent to find

        Returns
        -------
        Optional[int]
            Index of the agent if found, None otherwise
        """
        for idx, agent in enumerate(self.agent_list):
            if agent.traits.get("agent_name") == agent_name:
                return idx
        return None

    def get_agent_names(self) -> list[str]:
        """Get a list of all agent names.

        Returns
        -------
        list[str]
            List of agent names in the results
        """
        return [agent.traits.get("agent_name") for agent in self.agent_list]

    def analyze_agent_gap(self, agent_name: str) -> str:
        """Analyze the gap between an agent's responses and the gold standard.

        Parameters
        ----------
        agent_name
            Name of the agent to analyze

        Returns
        -------
        str
            Detailed analysis of the performance gap

        Raises
        ------
        ValueError
            If agent_name is not found in results
        """
        # Find the agent index by name
        agent_index = self._get_agent_index_by_name(agent_name)
        if agent_index is None:
            raise ValueError(f"Agent '{agent_name}' not found in results")

        # Get the specific agent's result from EDSL Results
        agent_result = list(self.agent_results)[agent_index]

        # Extract agent persona from the result using EDSL Results API
        # We know this will work due to constructor validation
        personas = self.agent_results.select("agent.persona").to_list()
        persona = personas[agent_index]

        # Compare responses to gold standard
        gaps = []
        for question_name, expected_answer in self.gold_standard_dict.items():
            # We know this will work due to constructor validation
            answer_column = f"answer.{question_name}"
            answers = self.agent_results.select(answer_column).to_list()
            actual_answer = answers[agent_index]

            # Get the actual question text for context
            question_text = "Unknown question"
            for q in self.survey.questions:
                if q.question_name == question_name:
                    question_text = q.question_text
                    break

            # Create clearer gap description
            match_status = (
                "✓ CORRECT" if actual_answer == expected_answer else "✗ INCORRECT"
            )

            gaps.append(f"Question '{question_name}': {question_text}")
            gaps.append(f"  Target answer (what we wanted): {expected_answer}")
            gaps.append(f"  Agent's actual answer: {actual_answer}")
            gaps.append(f"  Performance: {match_status}")
            gaps.append("")

        analysis = (
            f"Agent Name: {agent_name}\nOriginal Agent Persona: {persona}\n\nPERFORMANCE ANALYSIS:\n"
            + "\n".join(gaps)
        )
        return analysis

    def generate_improved_personas(
        self, agent_names: list[str]
    ) -> dict[str, dict[str, str]]:
        """Generate improved personas for multiple agents based on their performance gaps.

        Parameters
        ----------
        agent_names
            Names of the agents to analyze and improve

        Returns
        -------
        dict[str, dict[str, str]]
            Dictionary mapping agent_name -> {"improved_persona": str, "conflicts": str}
        """
        from edsl import QuestionFreeText, Agent, Model, Scenario, ScenarioList, Survey
        from edsl.utilities.local_results_cache import local_results_cache

        # Create scenarios for all agents
        scenarios = []
        for agent_name in agent_names:
            gap_analysis = self.analyze_agent_gap(agent_name)
            scenarios.append(
                Scenario({"agent_name": agent_name, "gap_analysis": gap_analysis})
            )

        scenario_list = ScenarioList(scenarios)

        # Create the LLM question to generate improved personas
        persona_question_text = """
        You are helping to improve an AI agent's persona so it will give better responses to survey questions.

        Below is the PERFORMANCE ANALYSIS showing how the current agent persona performed:

        {{ gap_analysis }}

        TASK: Create an improved version of the "Original Agent Persona" that would be more likely to give the "Target answer" responses instead of the incorrect "Agent's actual answer" responses.

        GUIDELINES for the improved persona:
        - Keep the core personality but modify traits that led to incorrect answers
        - Add specific details, experiences, or characteristics that would naturally lead to the target answers
        - Make sure the persona feels realistic and coherent
        - Focus especially on the questions marked "✗ INCORRECT"
        - The persona should naturally lead someone to give the target answers when asked those questions
        - IMPORTANT: Preserve existing details and interests that don't conflict with needed changes (e.g., if they like origami and no questions ask about origami, keep that detail)

        Return ONLY the improved persona text (2-3 sentences), nothing else.
        """

        # Create the conflict analysis question
        conflict_question_text = """
        Looking at the same performance analysis:

        {{ gap_analysis }}

        TASK: Analyze if there are any fundamental conflicts between what the current persona is and what changes would be needed to get the target answers.

        Consider:
        - Would the needed changes contradict core aspects of the original persona?
        - Are there personality traits that inherently conflict with the target answers?
        - Would achieving the target answers require changing something fundamental about who this person is?

        Identify any major conflicts or contradictions. If there are no significant conflicts, say "No major conflicts identified."

        Return ONLY your conflict analysis (1-2 sentences), nothing else.
        """

        # Create both questions
        persona_question = QuestionFreeText(
            question_name="improved_persona", question_text=persona_question_text
        )

        conflict_question = QuestionFreeText(
            question_name="conflicts", question_text=conflict_question_text
        )

        # Run both questions together
        survey = Survey([persona_question, conflict_question])
        job = survey.by(scenario_list).by(Agent()).by(Model())

        with local_results_cache(job) as results:
            improved_personas = results.select("improved_persona").to_list()
            conflicts = results.select("conflicts").to_list()

            # Map results back to agent names
            results_dict = {}
            for i, agent_name in enumerate(agent_names):
                persona = improved_personas[i] if i < len(improved_personas) else ""
                conflict = conflicts[i] if i < len(conflicts) else ""
                results_dict[agent_name] = {
                    "improved_persona": persona.strip() if persona else "",
                    "conflicts": conflict.strip() if conflict else "",
                }

            return results_dict


if __name__ == "__main__":
    from edsl import QuestionYesNo, QuestionCheckBox, QuestionFreeText, Survey, Agent
    from edsl.utilities.local_results_cache import local_results_cache

    print("\n" + "=" * 80)
    print("🔍 PROMPT ADJUST FRAMEWORK DEMO")
    print("=" * 80)

    # Create diverse candidate agents with different personas
    personas_and_names = [
        (
            "I am an extremely confident opera singer who collects vintage purple velvet curtains and spends my weekends doing synchronized swimming competitions. I've traveled extensively through Scandinavia and Northern Europe, particularly loving the fjords of Norway. My life revolves around perfecting my vibrato and teaching interpretive dance to penguins at the local zoo.",
            "confident_opera_purple_swimmer",
        ),
        (
            "I'm a supremely self-assured ice sculptor who specializes in creating massive orange installations for corporate lobbies. My hobbies include competitive yodeling and building miniature replica castles out of cheese. I've never left my home state of Montana because I believe all the beauty in the world exists within a 50-mile radius of my workshop.",
            "self_assured_ice_sculptor_orange",
        ),
        (
            "I am an unshakably confident professional whistler who performs at weddings while wearing exclusively neon pink outfits. I spend my free time training my pet ferrets to perform circus acts and collecting vintage typewriters from the 1920s. I've only ever traveled to landlocked countries because I have an inexplicable phobia of any body of water larger than a bathtub.",
            "confident_whistler_pink_ferrets",
        ),
        (
            "I'm a boldly assertive professional origami artist who works exclusively with silver metallic paper and believes that geometric perfection is the key to inner peace. My passions include competitive mushroom foraging and teaching advanced calculus to my collection of 23 houseplants. I've dedicated my life to visiting every desert in the world, having already conquered the Sahara, Gobi, and Atacama.",
            "assertive_origami_silver_mushrooms",
        ),
    ]

    # Define the survey
    q1 = QuestionYesNo(
        question_text="Are you a nervous person?", question_name="nervous"
    )
    q2 = QuestionCheckBox(
        question_text="What are your hobbies?",
        question_name="hobbies",
        question_options=[
            "Basketball",
            "Baseball",
            "Cooking",
            "Reading",
            "Writing",
            "Other",
        ],
    )
    q3 = QuestionYesNo(
        question_text="Have you ever traveled to Puerto Rico?",
        question_name="puerto_rico",
    )
    q4 = QuestionFreeText(
        question_text="What is your favorite color?", question_name="favorite_color"
    )

    survey = Survey([q1, q2, q3, q4])

    # Define gold standard - what we want the "ideal" agent to answer
    gold_standard = {
        "nervous": "Yes",
        "hobbies": ["Basketball", "Cooking"],
        "puerto_rico": "Yes",
        "favorite_color": "Chartreuse",
    }

    print("📋 Survey Questions:")
    for q in survey.questions:
        print(f"  • {q.question_name}: {q.question_text}")

    print("\n🎯 Gold Standard Answers:")
    for question, answer in gold_standard.items():
        print(f"  • {question}: {answer}")

    # Convert to EDSL agents and run survey
    print(f"\n🏃 Running survey on {len(personas_and_names)} agents...")
    edsl_agents = []
    for persona, name in personas_and_names:
        agent = Agent(traits={"persona": persona, "agent_name": name})
        edsl_agents.append(agent)

    # Run the survey
    job = survey.by(edsl_agents)

    with local_results_cache(job) as agent_results:
        print(f"✅ Survey completed! Got {len(agent_results)} responses.")

        # Initialize PromptAdjust
        adjuster = PromptAdjust(
            agent_results=agent_results, gold_standard_dict=gold_standard, survey=survey
        )

        all_agent_names = adjuster.get_agent_names()
        print(f"\n📊 Available agents: {all_agent_names}")

        # ------------------------------------------------------------------
        # GENERATE IMPROVED PERSONAS
        # ------------------------------------------------------------------
        print("\n" + "=" * 60)
        print("🚀 GENERATING IMPROVED PERSONAS")
        print("=" * 60)

        print("\n🔄 Analyzing gaps and generating improved personas for all agents...")
        improvement_results = adjuster.generate_improved_personas(all_agent_names)

        # ------------------------------------------------------------------
        # PERFORMANCE SUMMARY
        # ------------------------------------------------------------------
        print("\n" + "=" * 60)
        print("📊 PERFORMANCE SUMMARY")
        print("=" * 60)

        print("\n🎯 Agent Performance vs Gold Standard:")
        for agent_name in all_agent_names:
            analysis = adjuster.analyze_agent_gap(agent_name)

            # Count matches
            matches = analysis.count("✓ CORRECT")
            total_questions = len(gold_standard)
            accuracy = matches / total_questions

            print(
                f"  • {agent_name}: {matches}/{total_questions} correct ({accuracy:.1%})"
            )

        # ------------------------------------------------------------------
        # RESULTS TABLE
        # ------------------------------------------------------------------
        print("\n" + "=" * 60)
        print("📋 PERSONA IMPROVEMENTS")
        print("=" * 60)

        # Create a Rich table to show original vs improved personas
        from rich.table import Table
        from rich.console import Console

        console = Console()
        table = Table(
            title="🔄 Original vs Improved Personas",
            show_header=True,
            header_style="bold magenta",
            show_lines=True,
        )
        table.add_column("Agent Name", style="cyan", no_wrap=True, width=16)
        table.add_column("Original Persona", style="dim", width=32)
        table.add_column("Gap Analysis", style="yellow", width=28)
        table.add_column("Conflicts", style="red", width=28)
        table.add_column("Improved Persona", style="green", width=32)

        # Create mapping from names back to original personas
        original_personas = {name: persona for persona, name in personas_and_names}

        for agent_name in all_agent_names:
            original_persona = original_personas.get(agent_name, "Unknown")
            agent_results = improvement_results.get(agent_name, {})
            improved_persona = agent_results.get(
                "improved_persona", "No improvement generated"
            )
            conflicts = agent_results.get("conflicts", "No conflict analysis")

            # Get the gap analysis for this agent
            gap_analysis = adjuster.analyze_agent_gap(agent_name)

            # Extract just the question/answer mismatches for the table
            gap_lines = []
            lines = gap_analysis.split("\n")
            for i, line in enumerate(lines):
                if line.strip().startswith("Question '") and ":" in line:
                    question = line.strip()
                    # Get the next few lines for target/actual/performance
                    if i + 3 < len(lines):
                        target = lines[i + 1].strip()
                        actual = lines[i + 2].strip()
                        performance = lines[i + 3].strip()
                        if "✗ INCORRECT" in performance:  # Only show wrong answers
                            gap_lines.append(f"{question}\n{target}\n{actual}")

            gap_summary = (
                "\n\n".join(gap_lines) if gap_lines else "All answers correct!"
            )

            table.add_row(
                agent_name, original_persona, gap_summary, conflicts, improved_persona
            )

        console.print("\n")
        console.print(table)

        print("\n" + "=" * 80)
        print("🎉 PROMPT ADJUST DEMO COMPLETE")
        print("=" * 80)
        print("💡 Key Features Demonstrated:")
        print("  • Direct gap-to-persona improvement (no complex instruction chains)")
        print("  • Conflict analysis to identify contradictions in persona changes")
        print("  • Batch processing for efficient multi-agent analysis")
        print("  • Performance measurement against gold standards")
        print("  • Rich table visualization of persona transformations")
        print("  • Clean, simple API with parallel LLM calls")
        print(
            "\n🔗 This framework enables direct, data-driven persona optimization with conflict awareness!"
        )


__all__ = ["PromptAdjust"]
