"""Agent from result functionality.

This module provides the AgentFromResult class that handles creating Agent instances
from Result objects, including extracting traits from answers, building codebooks
from question metadata, and generating appropriate presentation templates.
"""

from __future__ import annotations
from typing import Optional, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from .agent import Agent
    from ..results import Result


class AgentFromResult:
    """Handles creating Agent instances from Result objects.
    
    This class provides methods to convert Result objects into Agent instances,
    extracting traits from the answers, building codebooks from question metadata,
    and generating appropriate presentation templates for displaying the Q&A pairs.
    """

    @staticmethod
    def from_result(
        result: "Result",
        name: Optional[str] = None,
    ) -> "Agent":
        """Create an Agent instance from a Result object.

        The agent's traits will correspond to the questions asked during the
        interview (the keys of result.answer) with their respective answers
        as the values.

        A simple, readable traits_presentation_template is automatically
        generated so that rendering the agent will look like::

            This person was asked the following questions – here are the answers:
            Q: <question 1>
            A: <answer 1>

            Q: <question 2>
            A: <answer 2>
            ...

        Args:
            result: The Result instance from which to build the agent
            name: Optional explicit name for the new agent. If omitted, we attempt
                to reuse result.agent.name if it exists

        Returns:
            A new Agent instance created from the result

        Raises:
            TypeError: If result is not a Result object

        Examples:
            Create an agent from a result (basic example):

            >>> from edsl.agents.agent_from_result import AgentFromResult
            >>> # Assuming we have a result object
            >>> # result = some_result_object
            >>> # agent = AgentFromResult.from_result(result, name="Interview Subject")
            >>> # agent.traits would contain the answers as traits
            >>> # agent.codebook would map question names to question text

            The generated agent will have traits corresponding to the answers:

            >>> # If result.answer = {"age": 30, "favorite_color": "blue"}
            >>> # Then agent.traits = {"age": 30, "favorite_color": "blue"}

            And a codebook mapping question names to readable text:

            >>> # If questions were "What is your age?" and "What's your favorite color?"
            >>> # Then agent.codebook = {"age": "What is your age?", "favorite_color": "What's your favorite color?"}
        """
        # Import locally to avoid an import cycle when the agents module is
        # imported from results and vice-versa.
        from ..results import result as _result_module  # local import by design

        if not isinstance(result, _result_module.Result):
            raise TypeError("from_result expects an edsl.results.Result object")

        # Extract traits from the result answers
        traits = AgentFromResult._extract_traits(result)
        
        # Build codebook from question metadata
        codebook = AgentFromResult._build_codebook(result)
        
        # Generate presentation template for Q&A display
        traits_presentation_template = AgentFromResult._generate_presentation_template()
        
        # Determine agent name
        agent_name = AgentFromResult._determine_name(result, name)

        # Create the agent
        from .agent import Agent
        return Agent(
            traits=traits,
            name=agent_name,
            codebook=codebook,
            traits_presentation_template=traits_presentation_template,
        )

    @staticmethod
    def _extract_traits(result: "Result") -> dict[str, Any]:
        """Extract traits from the result's answers.
        
        Args:
            result: The Result instance to extract traits from
            
        Returns:
            Dictionary of traits (question keys mapped to answers)
            
        Examples:
            >>> # If result.answer = {"age": 30, "name": "John"}
            >>> # Returns {"age": 30, "name": "John"}
        """
        # Traits are simply the answers dictionary (shallow-copied)
        return dict(result.answer)

    @staticmethod
    def _build_codebook(result: "Result") -> dict[str, str]:
        """Build a codebook mapping question keys to human-readable question text.
        
        This improves prompt readability by using the actual question text instead
        of just the question keys. Falls back gracefully if information is missing.
        
        Args:
            result: The Result instance to build codebook from
            
        Returns:
            Dictionary mapping question keys to rendered question text
            
        Examples:
            >>> # If result has question "What is your age?" with key "age"
            >>> # Returns {"age": "What is your age?"}
        """
        codebook: dict[str, str] = {}
        question_attrs = getattr(result, "question_to_attributes", None)
        
        if question_attrs:
            from ..prompts import Prompt

            for qname, attrs in question_attrs.items():
                qtext_template = attrs.get("question_text", qname)

                # If the question text contains Jinja variables, render it with the
                # scenario context so it becomes a fully populated human-readable
                # string. We fall back gracefully if rendering fails for any
                # reason (e.g. missing variables).
                try:
                    rendered_qtext = (
                        Prompt(text=qtext_template)
                        .render(result.scenario)  # scenario provides replacement vars
                        .text
                    )
                except Exception:
                    rendered_qtext = qtext_template

                codebook[qname] = rendered_qtext
                
        return codebook

    @staticmethod
    def _generate_presentation_template() -> str:
        """Generate a presentation template for displaying Q&A pairs.
        
        Creates a Jinja2 template that gracefully handles repeated observations
        (i.e. when a trait value is a list because the question was asked
        more than once).
        
        Returns:
            Jinja2 template string for presenting the Q&A pairs
            
        Examples:
            The template will render Q&A pairs like:
            
            This person was asked the following questions – here are the answers:
            Q: What is your age?
            A: 30
            
            Q: What is your favorite color?
            A: blue
        """
        template_lines = [
            "This person was asked the following questions – here are the answers:",
            "{% for key, value in traits.items() %}",
            "Q: {{ codebook[key] if codebook and key in codebook else key }}",
            "{% if value is iterable and value is not string %}",
            "    {% for v in value %}",
            "A: {{ v }}",
            "    {% endfor %}",
            "{% else %}",
            "A: {{ value }}",
            "{% endif %}",
            "",
            "{% endfor %}",
        ]
        return "\n".join(template_lines)

    @staticmethod
    def _determine_name(result: "Result", explicit_name: Optional[str]) -> Optional[str]:
        """Determine the appropriate name for the agent.
        
        Uses the explicit name if provided, otherwise falls back to the name
        from the original agent in the result if available.
        
        Args:
            result: The Result instance to extract name from
            explicit_name: Explicitly provided name (takes precedence)
            
        Returns:
            The determined name for the agent, or None if no name available
            
        Examples:
            >>> # If explicit_name is provided, use it
            >>> # AgentFromResult._determine_name(result, "John") -> "John"
            
            >>> # If no explicit name, try to use result.agent.name
            >>> # AgentFromResult._determine_name(result, None) -> result.agent.name or None
        """
        if explicit_name is not None:
            return explicit_name
            
        # Fallback to the name inside the original agent if not provided
        if (
            hasattr(result, "agent")
            and getattr(result.agent, "name", None)
        ):
            return result.agent.name
            
        return None

    def __repr__(self) -> str:
        """Return a string representation of the class.
        
        Returns:
            String representation of the AgentFromResult class
        """
        return "AgentFromResult()" 