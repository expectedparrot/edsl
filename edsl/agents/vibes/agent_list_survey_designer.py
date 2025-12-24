"""Agent list survey design functionality.

This module provides the core functionality for optimizing agent lists for survey-specific
responses. It analyzes survey questions to select relevant traits, generates optimized
trait presentation templates, and creates survey-specific instructions to maximize
response accuracy.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Any, List, TYPE_CHECKING
from pydantic import BaseModel, Field
import json
import logging

if TYPE_CHECKING:
    from ..agent_list import AgentList
    from ..agent import Agent
    from ...surveys import Survey


class TraitRelevanceAnalysis(BaseModel):
    """Analysis of which traits are relevant for survey responses."""

    agent_selections: Dict[str, List[str]] = Field(
        description="Mapping of agent ID (string) to list of relevant trait names for that agent"
    )

    trait_reasoning: Dict[str, str] = Field(
        description="Mapping of trait name to explanation of why it is or isn't relevant to the survey"
    )

    survey_type: str = Field(
        description="1-2 sentence description of survey type, domain, and key themes"
    )

    model_config = {"extra": "forbid"}  # Required by OpenAI


class AgentOptimization(BaseModel):
    """Optimized agent configuration for survey."""

    traits: List[str] = Field(
        description="List of trait names that should be included for this agent"
    )

    template: str = Field(
        description="Jinja2 template for presenting selected traits, optimized for survey accuracy. Must use {{trait_name}} syntax."
    )

    instruction: str = Field(
        description="Survey-specific instruction text (2-4 sentences) to guide agent's survey responses with emphasis on accuracy"
    )

    reasoning: str = Field(
        description="Brief explanation of why these traits, template, and instructions were selected"
    )

    model_config = {"extra": "forbid"}  # Required by OpenAI


@dataclass
class SurveyAnalyzer:
    """Analyze survey questions to determine relevant agent traits."""

    model: str = "gpt-4o"
    temperature: float = 0.3

    def __post_init__(self):
        from ...base.openai_utils import create_openai_client

        self.client = create_openai_client()

    def analyze_relevance(
        self, survey_data: Dict[str, Any], agent_list: "AgentList"
    ) -> Dict[str, Any]:
        """
        Analyze which traits are relevant for each agent given the survey.

        Args:
            survey_data: Dictionary containing survey information
            agent_list: AgentList to analyze

        Returns:
            Dictionary with trait relevance analysis

        Raises:
            RuntimeError: If LLM analysis fails
        """
        # Collect unique traits across all agents
        all_traits = agent_list.all_traits

        # Prepare agent summaries
        agents_summary = []
        for i, agent in enumerate(agent_list):
            agents_summary.append(
                {
                    "agent_id": str(i),
                    "traits": list(agent.traits.keys()),
                    "name": agent.name if agent.name else None,
                }
            )

        # Build codebook if available
        codebook = {}
        if hasattr(agent_list, "codebook") and agent_list.codebook:
            codebook = agent_list.codebook

        # Call LLM for analysis
        system_prompt = self._build_system_prompt()
        user_prompt = self._build_user_prompt(
            survey_data, all_traits, agents_summary, codebook
        )

        try:
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": json.dumps(user_prompt, indent=2)},
                ],
                response_format={"type": "json_object"},
                temperature=self.temperature,
            )

            # Parse the JSON response
            try:
                result = json.loads(resp.choices[0].message.content)
                return result
            except json.JSONDecodeError as e:
                raise RuntimeError(f"Failed to parse LLM response as JSON: {e}")

        except Exception as e:
            from ...key_management.exceptions import KeyManagementMissingKeyError

            if isinstance(e, KeyManagementMissingKeyError):
                raise  # Re-raise key errors as-is
            else:
                raise RuntimeError(
                    f"Failed to analyze survey for agent optimization: {str(e)}. "
                    "This could be due to API issues or invalid survey structure."
                ) from e

    def _build_system_prompt(self) -> str:
        """Build system prompt for trait relevance analysis."""
        return """You are an expert survey researcher and AI prompt engineer. Your task is to analyze
a survey and determine which agent traits are relevant for answering the questions accurately.

GOAL: Maximize survey response accuracy by selecting traits that:
1. Directly relate to survey questions (e.g., "age" trait for age-related questions)
2. Provide necessary context for informed responses
3. Avoid irrelevant information that could distract or bias responses

IMPORTANT PRINCIPLES:
- Simple trait filtering only - DO NOT modify trait values
- Focus on accuracy over naturalness or conciseness
- Consider the survey domain and question types
- Think about which traits enable more accurate, contextually appropriate responses
- Traits can be relevant even if not directly mentioned (e.g., occupation for workplace surveys)
- When in doubt, include the trait (false positive is better than false negative)

ANALYSIS APPROACH:
1. Identify the survey's domain and main themes
2. For each trait, determine if it provides useful context for any question
3. Consider both direct relevance (trait mentioned in question) and indirect (trait provides context)
4. Select traits per agent based on their specific trait values and the survey needs

OUTPUT STRUCTURE:
Return a JSON object with these keys:
- agent_selections: Map each agent (by ID) to their list of relevant traits
- trait_reasoning: Explain why each trait is or isn't relevant
- survey_type: Describe the survey type and domain

Example JSON format:
{
  "agent_selections": {"0": ["trait1", "trait2"], "1": ["trait1", "trait3"]},
  "trait_reasoning": {"trait1": "Highly relevant because...", "trait2": "Not relevant because..."},
  "survey_type": "Workplace satisfaction survey focused on job experience"
}"""

    def _build_user_prompt(
        self, survey_data: dict, all_traits: list, agents_summary: list, codebook: dict
    ) -> dict:
        """Build user prompt for trait relevance analysis."""
        return {
            "task": "Analyze survey and determine relevant traits per agent",
            "survey": survey_data,
            "available_traits": all_traits,
            "trait_descriptions": codebook if codebook else {},
            "agents": agents_summary,
            "instructions": (
                "For each agent, determine which traits from their trait list are relevant "
                "for answering this survey accurately. Consider the survey domain, question types, "
                "and how each trait might provide useful context for responses. "
                "Return a mapping of agent_id to selected trait names."
            ),
        }


@dataclass
class AgentSurveyOptimizer:
    """Optimize individual agents for survey responses."""

    model: str = "gpt-4o"
    temperature: float = 0.5  # Slightly higher for creative template generation

    def __post_init__(self):
        from ...base.openai_utils import create_openai_client

        self.client = create_openai_client()

    def optimize_agent(
        self, agent: "Agent", relevant_traits: List[str], survey_context: Dict[str, Any]
    ) -> "Agent":
        """
        Optimize a single agent for survey responses.

        Args:
            agent: The agent to optimize
            relevant_traits: List of trait names deemed relevant
            survey_context: Context about the survey

        Returns:
            New optimized agent

        Raises:
            Exception: If optimization fails (caught by caller)
        """
        # Handle edge case: no traits
        if not relevant_traits:
            logging.warning("No relevant traits for agent, keeping all traits")
            relevant_traits = list(agent.traits.keys())

        # Validate traits exist in agent
        available_traits = set(agent.traits.keys())
        valid_traits = [t for t in relevant_traits if t in available_traits]

        if not valid_traits:
            logging.warning("Selected traits not found in agent, using all traits")
            valid_traits = list(agent.traits.keys())

        # Call LLM to generate optimization
        optimization = self._generate_optimization(agent, valid_traits, survey_context)

        # Apply optimization to agent
        optimized_agent = self._apply_optimization(agent, valid_traits, optimization)

        return optimized_agent

    def _generate_optimization(
        self, agent: "Agent", traits: List[str], survey_context: dict
    ) -> dict:
        """Call LLM to generate optimization configuration."""
        system_prompt = self._build_system_prompt()
        user_prompt = self._build_user_prompt(agent, traits, survey_context)

        resp = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(user_prompt, indent=2)},
            ],
            response_format={"type": "json_object"},
            temperature=self.temperature,
        )

        # Parse the JSON response
        try:
            result = json.loads(resp.choices[0].message.content)
            return result
        except json.JSONDecodeError as e:
            raise RuntimeError(f"Failed to parse LLM response as JSON: {e}")

    def _build_system_prompt(self) -> str:
        """Build system prompt for agent optimization."""
        return """You are an expert at optimizing AI agent prompts for survey research. Your task is
to create an optimized agent configuration that maximizes survey response accuracy.

You will:
1. Generate a traits_presentation_template using ONLY the selected traits
2. Create survey-specific instructions that emphasize accuracy
3. Ensure the template presents traits clearly and effectively

TEMPLATE REQUIREMENTS:
- Use Jinja2 syntax: {{trait_name}} for individual traits
- Can reference {{codebook}} for trait descriptions if available
- MUST be valid Jinja2 (will be validated)
- Present traits in a clear, structured format that's easy to understand
- Focus on making traits useful for answering survey questions accurately
- Use a format like:
  "Your characteristics:
   Description1: {{trait1}}
   Description2: {{trait2}}"

INSTRUCTION REQUIREMENTS:
- Emphasize accuracy and thoughtfulness in survey responses
- Reference the survey domain/topic if known
- Guide the agent to use their traits appropriately when answering
- Prioritize accuracy over naturalness or brevity
- Encourage the agent to think carefully about how their characteristics inform their answers
- Keep instructions concise but informative (2-4 sentences)

EXAMPLE OUTPUT JSON:
{
  "traits": ["age", "occupation"],
  "template": "Your profile:\\nAge: {{age}}\\nOccupation: {{occupation}}",
  "instruction": "You are answering a workplace survey. Consider your occupation and experience when responding. Focus on providing accurate, thoughtful answers based on your characteristics.",
  "reasoning": "Selected work-related traits for workplace survey. Template presents them clearly. Instruction emphasizes using work background for accurate responses."
}"""

    def _build_user_prompt(
        self, agent: "Agent", traits: list, survey_context: dict
    ) -> dict:
        """Build user prompt for agent optimization."""
        # Extract trait values for selected traits
        trait_values = {t: agent.traits[t] for t in traits}

        # Extract codebook entries for selected traits
        codebook_subset = {}
        if hasattr(agent, "codebook") and agent.codebook:
            codebook_subset = {
                t: agent.codebook[t] for t in traits if t in agent.codebook
            }

        return {
            "task": "Generate optimized agent configuration for survey",
            "selected_traits": traits,
            "trait_values": trait_values,
            "trait_descriptions": codebook_subset,
            "survey_context": survey_context,
            "instructions": (
                "Create a traits_presentation_template and survey_instruction that will help "
                "this agent provide accurate survey responses. The template should present the "
                "selected traits clearly. The instruction should guide the agent to answer "
                "thoughtfully and accurately based on their characteristics."
            ),
        }

    def _apply_optimization(
        self, agent: "Agent", traits: list, optimization: dict
    ) -> "Agent":
        """Apply optimization results to create new agent."""
        # Step 1: Filter traits using agent.select()
        filtered_agent = agent.select(*traits)

        # Step 2: Validate and set traits_presentation_template
        template = optimization["template"]
        try:
            from ..agent_template_validation import AgentTemplateValidation

            validator = AgentTemplateValidation(filtered_agent)
            validator.validate_and_raise(template)
            filtered_agent.traits_presentation_template = template
        except Exception as e:
            logging.warning(
                f"Generated template failed validation: {e}. Using default."
            )
            # Keep the default template that agent.select() created

        # Step 3: Set instruction
        instruction = optimization["instruction"]
        filtered_agent.instruction = instruction

        return filtered_agent


@dataclass
class AgentListSurveyDesigner:
    """
    Optimize agent lists for survey-specific responses.

    This class orchestrates the process of analyzing a survey and optimizing
    agents to provide accurate, contextually appropriate responses.
    """

    model: str = "gpt-4o"
    temperature: float = 0.3  # Lower temperature for consistent analysis

    def __post_init__(self):
        self.survey_analyzer = SurveyAnalyzer(self.model, self.temperature)
        self.agent_optimizer = AgentSurveyOptimizer(self.model, 0.5)

    def design_for_survey(
        self, agent_list: "AgentList", survey: "Survey", show_reasoning: bool = False
    ) -> "AgentList":
        """
        Main entry point for survey-specific agent optimization.

        Args:
            agent_list: The agent list to optimize
            survey: The survey to optimize for
            show_reasoning: If True, print trait selection reasoning

        Returns:
            New AgentList with optimized agents

        Raises:
            ValueError: If survey has no questions
            RuntimeError: If optimization fails
        """
        try:
            # Survey validation
            if not survey.questions:
                raise ValueError(
                    "Survey has no questions. Cannot optimize agents for empty survey."
                )

            # Step 1: Extract survey information
            survey_data = self._extract_survey_data(survey)

            # Step 2: Analyze trait relevance across all agents
            trait_analysis = self.survey_analyzer.analyze_relevance(
                survey_data=survey_data, agent_list=agent_list
            )

            if show_reasoning:
                self._print_analysis_reasoning(trait_analysis)

            # Step 3: Optimize each agent
            optimized_agents = []
            for i, agent in enumerate(agent_list):
                agent_id = str(i)  # Use index as ID
                relevant_traits = trait_analysis["agent_selections"].get(
                    agent_id, list(agent.traits.keys())  # Fallback to all traits
                )

                try:
                    optimized = self.agent_optimizer.optimize_agent(
                        agent=agent,
                        relevant_traits=relevant_traits,
                        survey_context={
                            "domain": trait_analysis["survey_type"],
                            "questions": survey_data["questions"],
                        },
                    )
                    optimized_agents.append(optimized)
                except Exception as e:
                    # On error, keep original agent and log
                    logging.warning(
                        f"Failed to optimize agent {i}: {e}. Keeping original."
                    )
                    optimized_agents.append(agent)

            # Step 4: Return new AgentList
            from ..agent_list import AgentList

            return AgentList(optimized_agents, codebook=agent_list.codebook)

        except Exception as e:
            # Top-level error handler
            logging.error(f"Agent list design failed: {str(e)}")
            raise

    def _extract_survey_data(self, survey: "Survey") -> Dict[str, Any]:
        """Extract relevant survey data for analysis."""
        questions_data = []
        for q in survey.questions:
            q_data = {
                "question_name": q.question_name,
                "question_text": q.question_text,
                "question_type": q.question_type,
            }
            # Add options if available
            if hasattr(q, "question_options"):
                q_data["question_options"] = q.question_options
            questions_data.append(q_data)

        return {
            "questions": questions_data,
            "question_names": [q.question_name for q in survey.questions],
            "num_questions": len(survey.questions),
            "has_skip_logic": len(survey.rule_collection.data) > 0,
        }

    def _print_analysis_reasoning(self, analysis: dict):
        """Print formatted reasoning for trait selections."""
        print("\n=== Survey Analysis ===")
        print(f"Survey Type: {analysis['survey_type']}\n")

        print("Trait Relevance Reasoning:")
        for trait, reasoning in analysis["trait_reasoning"].items():
            print(f"  {trait}: {reasoning}")

        print("\nPer-Agent Trait Selections:")
        for agent_id, traits in analysis["agent_selections"].items():
            print(f"  Agent {agent_id}: {', '.join(traits)}")
