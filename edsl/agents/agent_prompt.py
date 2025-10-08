"""Agent prompt functionality.

This module provides the AgentPrompt class that handles prompt generation and
traits presentation template management for Agent instances.
"""

from __future__ import annotations
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .agent import Agent
    from ..prompts import Prompt


class AgentPrompt:
    """Handles prompt generation and traits presentation for Agent instances.

    This class provides methods to generate formatted prompts from agent traits,
    manage traits presentation templates, and handle codebook-based trait descriptions.
    """

    def __init__(self, agent: "Agent"):
        """Initialize the AgentPrompt manager.

        Args:
            agent: The agent instance this manager belongs to
        """
        self.agent = agent

    def agent_persona(self) -> "Prompt":
        """Get the agent's persona template as a Prompt object.

        This property provides access to the template that formats the agent's traits
        for presentation in prompts. The template is wrapped in a Prompt object
        that supports rendering with variable substitution.

        Returns:
            Prompt: A prompt object containing the traits presentation template

        Example:
            >>> from edsl.agents import Agent
            >>> agent = Agent(traits={"age": 10})
            >>> persona = agent.prompt_manager.agent_persona()
            >>> isinstance(persona.text, str)
            True
        """
        from ..prompts import Prompt

        return Prompt(text=self.agent.traits_presentation_template)

    def prompt(self) -> "Prompt":
        """Generate a formatted prompt containing the agent's traits.

        This method renders the agent's traits presentation template with the
        agent's traits and codebook, creating a formatted prompt that can be
        used in language model requests.

        The method is dynamic and responsive to changes in the agent's state:

        1. If a custom template was explicitly set during initialization, it will be used
        2. If using the default template and the codebook has been updated since
           initialization, this method will recreate the template to reflect the current
           codebook values
        3. The template is rendered with access to all trait values, the complete traits
           dictionary, and the codebook

        The template rendering makes the following variables available:
        - All individual trait keys (e.g., {{age}}, {{occupation}})
        - The full traits dictionary as {{traits}}
        - The codebook as {{codebook}}

        Returns:
            Prompt: A Prompt object containing the rendered template

        Raises:
            QuestionScenarioRenderError: If any template variables remain undefined

        Examples:
            Basic trait rendering without a codebook:

            >>> from edsl.agents import Agent
            >>> agent = Agent(traits={"age": 10, "hair": "brown", "height": 5.5})
            >>> prompt = agent.prompt_manager.prompt()
            >>> "age" in prompt.text
            True

            Trait rendering with a codebook (more readable format):

            >>> codebook = {"age": "Age in years", "hair": "Hair color"}
            >>> agent = Agent(traits={"age": 10, "hair": "brown"}, codebook=codebook)
            >>> prompt = agent.prompt_manager.prompt()
            >>> "Age in years" in prompt.text
            True

            Custom templates can reference any trait directly:

            >>> template = "Profile: {{age}} year old with {{hair}} hair"
            >>> agent = Agent(traits={"age": 45, "hair": "brown"},
            ...               traits_presentation_template=template)
            >>> prompt = agent.prompt_manager.prompt()
            >>> "Profile: 45 year old with brown hair" in prompt.text
            True
        """
        import time
        from ..questions import QuestionScenarioRenderError

        # Track timing for this method
        if not hasattr(self, '_prompt_timing'):
            self._prompt_timing = {
                'template_rebuild': 0.0,
                'dict_creation': 0.0,
                'get_persona': 0.0,
                'validate': 0.0,
                'render': 0.0,
                'call_count': 0,
            }

        # If using the default template and the codebook has been updated since initialization,
        # recreate the template to use the current codebook
        t0 = time.time()
        if not self.agent.set_traits_presentation_template and self.agent.codebook:
            # Create a template that uses the codebook descriptions
            traits_lines = []
            for trait_key in self.agent.traits.keys():
                if trait_key in self.agent.codebook:
                    # Use codebook description if available
                    traits_lines.append(
                        f"{self.agent.codebook[trait_key]}: {{{{ {trait_key} }}}}"
                    )
                else:
                    # Fall back to raw key for traits without codebook entries
                    traits_lines.append(f"{trait_key}: {{{{ {trait_key} }}}}")

            # Join all trait lines with newlines
            self.agent.traits_presentation_template = "Your traits:\n" + "\n".join(
                traits_lines
            )
        self._prompt_timing['template_rebuild'] += (time.time() - t0)

        # Create a dictionary with traits, a reference to all traits, and the codebook
        t1 = time.time()
        replacement_dict = (
            self.agent.traits
            | {"traits": self.agent.traits}
            | {"codebook": self.agent.codebook}
        )
        self._prompt_timing['dict_creation'] += (time.time() - t1)

        # Get the agent persona
        t2 = time.time()
        agent_persona = self.agent_persona()
        self._prompt_timing['get_persona'] += (time.time() - t2)

        # Check for any undefined variables in the template
        t3 = time.time()
        if undefined := agent_persona.undefined_template_variables(replacement_dict):
            raise QuestionScenarioRenderError(
                f"Agent persona still has variables that were not rendered: {undefined}"
            )
        self._prompt_timing['validate'] += (time.time() - t3)

        t4 = time.time()

        # Cache the rendered result using a hash of the replacement dict
        # This avoids re-rendering the same agent persona multiple times
        cache_key = None
        if hasattr(self, '_render_cache'):
            # Create a simple cache key from traits (which are typically small)
            try:
                cache_key = hash(frozenset(self.agent.traits.items()))
                if cache_key in self._render_cache:
                    result = self._render_cache[cache_key]
                    self._prompt_timing['render'] += (time.time() - t4)
                    self._prompt_timing['call_count'] += 1
                    return result
            except (TypeError, AttributeError):
                # If traits aren't hashable, skip caching
                cache_key = None
        else:
            self._render_cache = {}

        result = agent_persona.render(replacement_dict)

        # Store in cache if we have a valid key
        if cache_key is not None:
            self._render_cache[cache_key] = result

        self._prompt_timing['render'] += (time.time() - t4)

        self._prompt_timing['call_count'] += 1

        # Print stats every 1000 calls
        if self._prompt_timing['call_count'] % 1000 == 0:
            stats = self._prompt_timing
            total = sum([stats[k] for k in stats if k != 'call_count'])
            print(f"\n[AGENT.PROMPT_MANAGER.PROMPT] Call #{stats['call_count']}")
            print(f"  Total time:        {total:.3f}s")
            print(f"  - template_rebuild:{stats['template_rebuild']:.3f}s ({100*stats['template_rebuild']/total:.1f}%)")
            print(f"  - dict_creation:   {stats['dict_creation']:.3f}s ({100*stats['dict_creation']/total:.1f}%)")
            print(f"  - get_persona:     {stats['get_persona']:.3f}s ({100*stats['get_persona']/total:.1f}%)")
            print(f"  - validate:        {stats['validate']:.3f}s ({100*stats['validate']/total:.1f}%)")
            print(f"  - render:          {stats['render']:.3f}s ({100*stats['render']/total:.1f}%)")
            print(f"  Avg per call:      {total/stats['call_count']:.4f}s")
            if hasattr(self, '_render_cache'):
                cache_size = len(self._render_cache)
                print(f"  Render cache size: {cache_size}")
            print()

        return result

    def initialize_traits_presentation_template(
        self, traits_presentation_template: Optional[str]
    ) -> None:
        """Initialize the template for presenting agent traits in prompts.

        This method sets up how the agent's traits will be formatted in language model prompts.
        The template is a Jinja2 template string that can reference trait values and other
        agent properties.

        If no template is provided:
        - If a codebook exists, the method creates a template that displays each trait with its
          codebook description instead of the raw key names (e.g., "Age in years: 30" instead of "age: 30")
        - Without a codebook, it uses a default template that displays all traits as a dictionary

        Custom templates always take precedence over automatically generated ones, giving users
        complete control over how traits are presented.

        Args:
            traits_presentation_template: Optional Jinja2 template string for formatting traits.
                If not provided, a default template will be generated.

        Examples:
            With no template or codebook, traits are shown as a dictionary:

            >>> from edsl.agents import Agent
            >>> agent = Agent(traits={"age": 25, "occupation": "engineer"})
            >>> "traits" in agent.traits_presentation_template
            True

            With a codebook but no custom template, traits are shown with descriptions:

            >>> codebook = {"age": "Age in years", "occupation": "Current profession"}
            >>> agent = Agent(traits={"age": 25, "occupation": "engineer"}, codebook=codebook)
            >>> "Age in years" in agent.traits_presentation_template
            True

            With a custom template, that format is used regardless of codebook:

            >>> template = "Person: {{age}} years old, works as {{occupation}}"
            >>> agent = Agent(traits={"age": 25, "occupation": "engineer"},
            ...               codebook=codebook, traits_presentation_template=template)
            >>> agent.traits_presentation_template == template
            True
        """
        if traits_presentation_template is not None:
            self.agent._traits_presentation_template = traits_presentation_template
            self.agent.set_traits_presentation_template = True
        else:
            # Set the default template based on whether a codebook exists
            if self.agent.codebook:
                # Create a template that uses the codebook descriptions
                traits_lines = []
                for trait_key in self.agent.traits.keys():
                    if trait_key in self.agent.codebook:
                        # Use codebook description if available
                        traits_lines.append(
                            f"{self.agent.codebook[trait_key]}: {{{{ {trait_key} }}}}"
                        )
                    else:
                        # Fall back to raw key for traits without codebook entries
                        traits_lines.append(f"{trait_key}: {{{{ {trait_key} }}}}")

                # Join all trait lines with newlines
                self.agent._traits_presentation_template = "Your traits:\n" + "\n".join(
                    traits_lines
                )
            else:
                # Use the standard dictionary format if no codebook
                self.agent._traits_presentation_template = "Your traits: {{traits}}"

            self.agent.set_traits_presentation_template = False
