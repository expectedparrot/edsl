"""Agent template validation functionality.

This module provides validation utilities for Agent template fields,
specifically for validating Jinja2 template syntax in traits_presentation_template.
"""

from __future__ import annotations
from typing import TYPE_CHECKING, Optional, Dict, Any

if TYPE_CHECKING:
    from .agent import Agent


class AgentTemplateValidation:
    """Handles template validation for Agent instances.

    This class provides methods to validate Jinja2 template syntax and
    ensure that templates can be properly rendered with agent data.
    """

    def __init__(self, agent: "Agent"):
        """Initialize the AgentTemplateValidation manager.

        Args:
            agent: The agent instance this validator belongs to
        """
        self.agent = agent

    def validate_and_raise(self, template: str) -> None:
        """Validate a template and raise AgentTemplateValidationError if invalid.

        Args:
            template: The Jinja2 template string to validate

        Raises:
            AgentTemplateValidationError: If the template is invalid

        Examples:
            Valid template passes silently:

            >>> from edsl.agents import Agent
            >>> a = Agent(traits={'age': 30})
            >>> validator = AgentTemplateValidation(a)
            >>> validator.validate_and_raise("I am {{age}} years old.")  # No exception

            Invalid template raises exception:

            >>> try:
            ...     validator.validate_and_raise("I am {{age} years old.")  # Missing closing brace
            ... except Exception as e:
            ...     print(type(e).__name__)
            AgentTemplateValidationError
        """
        from .exceptions import AgentTemplateValidationError

        try:
            # Import Jinja2 environment from the prompts module to maintain consistency
            from jinja2 import Environment, TemplateSyntaxError, UndefinedError
            from ..prompts.prompt import make_env

            # Use the same environment setup as the Prompt class for consistency
            env = make_env()

            # Test parsing the template
            parsed_template = env.from_string(template)

            # Test a basic rendering attempt with dummy data to catch logical errors
            # Use the agent's actual traits plus some common template variables
            test_data = dict(self.agent.traits)
            test_data.update({
                'traits': self.agent.traits,
                'codebook': self.agent.codebook if hasattr(self.agent, 'codebook') else {}
            })

            # Attempt to render with test data
            try:
                rendered = parsed_template.render(test_data)
            except UndefinedError:
                # UndefinedError is expected for templates with variables not in test_data
                # This is still a valid template, just with undefined variables
                pass

        except TemplateSyntaxError as e:
            # Template has invalid Jinja2 syntax
            raise AgentTemplateValidationError(f"Invalid Jinja2 template syntax: {str(e)}")
        except Exception as e:
            # Any other error during parsing or rendering indicates an invalid template
            raise AgentTemplateValidationError(f"Template validation failed: {str(e)}")

    def validate_traits_presentation_template(self) -> bool:
        """Validate that the traits_presentation_template is valid Jinja2 syntax.

        This method checks whether the current traits_presentation_template can be
        successfully parsed by the Jinja2 template engine. It tests both the parsing
        and a basic rendering attempt to catch syntax and logical errors.

        Returns:
            bool: True if the template is valid Jinja2, False otherwise

        Raises:
            AgentErrors: If no traits_presentation_template is set

        Examples:
            Valid template syntax:

            >>> from edsl.agents import Agent
            >>> a = Agent(traits={'age': 30, 'occupation': 'doctor'})
            >>> validator = AgentTemplateValidation(a)
            >>> validator.validate_traits_presentation_template()
            True

            Valid custom template:

            >>> template = "I am {{age}} years old and work as a {{occupation}}."
            >>> a = Agent(traits={'age': 30, 'occupation': 'doctor'},
            ...           traits_presentation_template=template)
            >>> validator = AgentTemplateValidation(a)
            >>> validator.validate_traits_presentation_template()
            True

        """
        from .exceptions import AgentErrors

        if not hasattr(self.agent, '_traits_presentation_template'):
            raise AgentErrors("No traits_presentation_template is set for this agent")

        try:
            # Import Jinja2 environment from the prompts module to maintain consistency
            from jinja2 import Environment, TemplateSyntaxError, UndefinedError
            from ..prompts.prompt import make_env

            # Use the same environment setup as the Prompt class for consistency
            env = make_env()

            # Test parsing the template
            template = env.from_string(self.agent.traits_presentation_template)

            # Test a basic rendering attempt with dummy data to catch logical errors
            # Use the agent's actual traits plus some common template variables
            test_data = dict(self.agent.traits)
            test_data.update({
                'traits': self.agent.traits,
                'codebook': self.agent.codebook if hasattr(self.agent, 'codebook') else {}
            })

            # Attempt to render with test data to catch undefined variables or logical errors
            try:
                rendered = template.render(test_data)
                return True
            except UndefinedError:
                # UndefinedError is expected for templates with variables not in test_data
                # This is still a valid template, just with undefined variables
                return True

        except TemplateSyntaxError:
            # Template has invalid Jinja2 syntax
            return False
        except Exception:
            # Any other error during parsing or rendering indicates an invalid template
            return False

    def get_template_validation_errors(self) -> Optional[str]:
        """Get detailed error information about template validation failures.

        This method provides more detailed error information than the boolean
        validate_traits_presentation_template method, returning the specific
        error message when validation fails.

        Returns:
            str: Error message if template is invalid, None if template is valid

        Raises:
            AgentErrors: If no traits_presentation_template is set

        Examples:
            Valid template returns None:

            >>> from edsl.agents import Agent
            >>> template = "I am {{age}} years old."
            >>> a = Agent(traits={'age': 30}, traits_presentation_template=template)
            >>> validator = AgentTemplateValidation(a)
            >>> validator.get_template_validation_errors() is None
            True

        """
        from .exceptions import AgentErrors

        if not hasattr(self.agent, '_traits_presentation_template'):
            raise AgentErrors("No traits_presentation_template is set for this agent")

        try:
            # Import Jinja2 environment from the prompts module to maintain consistency
            from jinja2 import Environment, TemplateSyntaxError, UndefinedError
            from ..prompts.prompt import make_env

            # Use the same environment setup as the Prompt class for consistency
            env = make_env()

            # Test parsing the template
            template = env.from_string(self.agent.traits_presentation_template)

            # Test a basic rendering attempt with dummy data to catch logical errors
            # Use the agent's actual traits plus some common template variables
            test_data = dict(self.agent.traits)
            test_data.update({
                'traits': self.agent.traits,
                'codebook': self.agent.codebook if hasattr(self.agent, 'codebook') else {}
            })

            # Attempt to render with test data
            try:
                rendered = template.render(test_data)
                return None  # Valid template
            except UndefinedError:
                # UndefinedError is expected for templates with variables not in test_data
                # This is still a valid template, just with undefined variables
                return None

        except TemplateSyntaxError as e:
            # Template has invalid Jinja2 syntax
            return f"Template syntax error: {str(e)}"
        except Exception as e:
            # Any other error during parsing or rendering indicates an invalid template
            return f"Template validation error: {str(e)}"

    def get_undefined_template_variables(self) -> list[str]:
        """Get a list of variables referenced in the template that are not available.

        This method analyzes the traits_presentation_template to identify which
        template variables are referenced but not available in the agent's traits
        or standard template context (traits dict, codebook).

        Returns:
            list[str]: List of undefined variable names

        Raises:
            AgentErrors: If no traits_presentation_template is set or template is invalid

        Examples:
            Template with all variables defined:

            >>> from edsl.agents import Agent
            >>> template = "I am {{age}} years old and work as a {{occupation}}."
            >>> a = Agent(traits={'occupation': 'doctor', 'age': 30},
            ...           traits_presentation_template=template)
            >>> validator = AgentTemplateValidation(a)
            >>> validator.get_undefined_template_variables()
            []

            Template with undefined variables:

            >>> template = "I am {{age}} years old and live in {{city}}."
            >>> a = Agent(traits={'age': 30}, traits_presentation_template=template)
            >>> validator = AgentTemplateValidation(a)
            >>> undefined = validator.get_undefined_template_variables()
            >>> 'city' in undefined
            True
            >>> 'age' in undefined
            False
        """
        from .exceptions import AgentErrors

        if not hasattr(self.agent, '_traits_presentation_template'):
            raise AgentErrors("No traits_presentation_template is set for this agent")

        # First validate the template syntax
        if not self.validate_traits_presentation_template():
            error_msg = self.get_template_validation_errors()
            raise AgentErrors(f"Cannot analyze undefined variables: {error_msg}")

        try:
            from ..prompts.prompt import _find_template_variables

            # Get all variables referenced in the template
            template_variables = _find_template_variables(self.agent.traits_presentation_template)

            # Build available variables (traits + standard template context)
            available_variables = set(self.agent.traits.keys())
            available_variables.update(['traits', 'codebook'])

            # Find variables that are referenced but not available
            undefined_variables = [var for var in template_variables if var not in available_variables]

            return undefined_variables

        except Exception as e:
            raise AgentErrors(f"Error analyzing template variables: {str(e)}")

    def get_template_variables(self) -> list[str]:
        """Get a list of all variables referenced in the traits_presentation_template.

        Returns:
            list[str]: List of all variable names referenced in the template

        Raises:
            AgentErrors: If no traits_presentation_template is set or template is invalid

        Examples:
            >>> from edsl.agents import Agent
            >>> template = "I am {{age}} years old and work as a {{occupation}}."
            >>> a = Agent(traits={'occupation': 'doctor', 'age': 30},
            ...           traits_presentation_template=template)
            >>> validator = AgentTemplateValidation(a)
            >>> variables = validator.get_template_variables()
            >>> sorted(variables)
            ['age', 'occupation']
        """
        from .exceptions import AgentErrors

        if not hasattr(self.agent, '_traits_presentation_template'):
            raise AgentErrors("No traits_presentation_template is set for this agent")

        # First validate the template syntax
        if not self.validate_traits_presentation_template():
            error_msg = self.get_template_validation_errors()
            raise AgentErrors(f"Cannot analyze template variables: {error_msg}")

        try:
            from ..prompts.prompt import _find_template_variables
            return _find_template_variables(self.agent.traits_presentation_template)
        except Exception as e:
            raise AgentErrors(f"Error analyzing template variables: {str(e)}")