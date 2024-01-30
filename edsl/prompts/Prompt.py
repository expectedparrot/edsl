import textwrap
from abc import ABC
from typing import Any, List
import io

from rich.console import Console
from rich.table import Table

from jinja2 import Template, Environment, meta, TemplateSyntaxError

from edsl.exceptions.prompts import TemplateRenderError
from edsl.prompts.prompt_config import (
    C2A,
    names_to_component_types,
    ComponentTypes,
    NEGATIVE_INFINITY,
)
from edsl.prompts.registry import RegisterPromptsMeta

from edsl.Base import PersistenceMixin, RichPrintingMixin

MAX_NESTING = 100


class PromptBase(
    PersistenceMixin, RichPrintingMixin, ABC, metaclass=RegisterPromptsMeta
):
    component_type = ComponentTypes.GENERIC

    def __init__(self, text=None):
        if text is None:
            if hasattr(self, "default_instructions"):
                text = self.default_instructions
            else:
                text = ""
        self._text = text

    @property
    def text(self):
        return self._text

    def __add__(self, other_prompt):
        """
        >>> p = Prompt("Hello, {{person}}")
        >>> p2 = Prompt("How are you?")
        >>> p + p2
        Prompt(text='Hello, {{person}}How are you?')
        >>> p + "How are you?"
        Prompt(text='Hello, {{person}}How are you?')
        """
        if isinstance(other_prompt, str):
            return self.__class__(self.text + other_prompt)
        else:
            return self.__class__(text=self.text + other_prompt.text)

    def __str__(self):
        """
        >>> p = Prompt("Hello, {{person}}")
        >>> str(p)
        'Hello, {{person}}'
        """
        return self.text

    def __contains__(self, text_to_check):
        """
        >>> p = Prompt("Hello, {{person}}")
        >>> "person" in p
        True
        >>> "person2" in p
        False
        """
        return text_to_check in self.text

    def __repr__(self):
        """
        >>> p = Prompt("Hello, {{person}}")
        >>> p
        Prompt(text='Hello, {{person}}')
        """
        return f"Prompt(text='{self.text}')"

    def template_variables(
        self,
    ) -> list[str]:
        """
        >>> p = Prompt("Hello, {{person}}")
        >>> p.template_variables()
        ['person']
        """
        return self._template_variables(self.text)

    @staticmethod
    def _template_variables(template: str) -> list[str]:
        """ """
        env = Environment()
        ast = env.parse(template)
        return list(meta.find_undeclared_variables(ast))

    def undefined_template_variables(self, replcement_dict):
        return [var for var in self.template_variables() if var not in replcement_dict]

    def unused_traits(self, traits: dict):
        return [trait for trait in traits if trait not in self.template_variables()]

    @property
    def has_variables(self) -> bool:
        """
        >>> p = Prompt("Hello, {{person}}")
        >>> p.has_variables
        True
        >>> p = Prompt("Hello, person")
        >>> p.has_variables
        False
        """
        return len(self.template_variables()) > 0

    def render(self, primary_replacement: dict, **additional_replacements) -> str:
        """Renders the prompt with the replacements

        >>> p = Prompt("Hello, {{person}}")
        >>> p.render({"person": "John"})
        'Hello, John'
        >>> p.render({"person": "Mr. {{last_name}}", "last_name": "Horton"})
        'Hello, Mr. Horton'
        >>> p.render({"person": "Mr. {{last_name}}", "last_name": "Ho{{letter}}ton"}, max_nesting = 1)
        'Hello, Mr. Horton'
        """
        new_text = self._render(
            self.text, primary_replacement, **additional_replacements
        )
        return self.__class__(text=new_text)

    @staticmethod
    def _render(text, primary_replacement, **additional_replacements) -> "PromptBase":
        """
            Renders the template text with variables replaced from the provided named dictionaries.
            Allows for nested variable resolution up to a specified maximum nesting depth.

        >>> codebook = {"age": "Age"}
        >>> p = Prompt("You are an agent named {{ name }}. {{ codebook['age']}}: {{ age }}")
        >>> p.render({"name": "John", "age": 44}, codebook=codebook)
        'You are an agent named John. Age: 44'

        """
        try:
            previous_text = None
            for _ in range(MAX_NESTING):
                rendered_text = Template(text).render(
                    primary_replacement, **additional_replacements
                )
                if rendered_text == previous_text:
                    # No more changes, so return the rendered text
                    return rendered_text
                previous_text = text
                text = rendered_text

            # If the loop exits without returning, it indicates too much nesting
            raise TemplateRenderError(
                "Too much nesting - you created an infinite loop here, pal"
            )
        except TemplateSyntaxError as e:
            raise TemplateRenderError(f"Template syntax error: {e}")

    def to_dict(self):
        """
        >>> p = Prompt("Hello, {{person}}")
        >>> p.to_dict()
        {'text': 'Hello, {{person}}', 'class_name': 'Prompt'}
        """
        return {"text": self.text, "class_name": self.__class__.__name__}

    @classmethod
    def from_dict(cls, data):
        """
        >>> p = Prompt("Hello, {{person}}")
        >>> p2 = Prompt.from_dict(p.to_dict())
        >>> p2
        Prompt(text='Hello, {{person}}')
        """
        class_name = data["class_name"]
        cls = RegisterPromptsMeta._registry.get(class_name, Prompt)
        return cls(text=data["text"])

    def rich_print(self):
        """Displays an object as a table."""
        table = Table(title="Prompt")
        table.add_column("Attribute", style="bold")
        table.add_column("Value")

        to_display = self.__dict__.copy()
        for attr_name, attr_value in to_display.items():
            table.add_row(attr_name, repr(attr_value))
        table.add_row("Component type", str(self.component_type))
        table.add_row("Model", str(getattr(self, "model", "Not specified")))
        return table

    @classmethod
    def example(cls):
        return cls(cls.default_instructions)


class Prompt(PromptBase):
    component_type = ComponentTypes.GENERIC


from edsl.prompts.library.question_multiple_choice import *
from edsl.prompts.library.agent_instructions import *
from edsl.prompts.library.agent_persona import *

from edsl.prompts.library.question_budget import *
from edsl.prompts.library.question_checkbox import *
from edsl.prompts.library.question_freetext import *
from edsl.prompts.library.question_linear_scale import *
from edsl.prompts.library.question_numerical import *
from edsl.prompts.library.question_rank import *
from edsl.prompts.library.question_extract import *
from edsl.prompts.library.question_list import *


if __name__ == "__main__":
    import doctest

    doctest.testmod()
