import textwrap
from abc import ABC
from typing import Any, List

from jinja2 import Template, Environment, meta

from edsl.exceptions.prompts import TemplateRenderError
from edsl.prompts.prompt_config import (
    C2A,
    names_to_component_types,
    ComponentTypes,
    NEGATIVE_INFINITY,
)
from edsl.prompts.registry import RegisterPromptsMeta


class PromptBase(ABC, metaclass=RegisterPromptsMeta):
    component_type = ComponentTypes.GENERIC

    def __init__(self, text=None):
        if text is None:
            if hasattr(self, "default_instructions"):
                text = self.default_instructions
            else:
                text = ""
        self.text = text

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

    def render(self, replacements, max_nesting=100) -> None:
        """Renders the prompt with the replacements

        >>> p = Prompt("Hello, {{person}}")
        >>> p.render({"person": "John"})
        >>> p.text
        'Hello, John'
        >>> p = Prompt("Hello, {{person}}")
        >>> p.render({"person": "Mr. {{last_name}}", "last_name": "Horton"})
        >>> p.text
        'Hello, Mr. Horton'
        >>> p.render({"person": "Mr. {{last_name}}", "last_name": "Ho{{letter}}ton"}, max_nesting = 1)
        >>> p.text
        'Hello, Mr. Horton'
        """
        self.text = self._render(self.text, replacements, max_nesting)

    @staticmethod
    def _render(text, replacements: dict[str, Any], max_nesting) -> str:
        """
        Replaces the variables in the question text with the values from the scenario.
        We allow nesting, and hence we may need to do this many times. There is a nesting limit of 100.
        TODO: I'm not sure this is necessary, actually - I think jinja2 does this for us automatically.
        When I was trying to get it to fail, I couldn't.
        """
        for _ in range(max_nesting):
            t = Template(text).render(replacements)
            if t == text:
                return t
            text = t
        raise TemplateRenderError(
            "Too much nesting - you created an infnite loop here, pal"
        )

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
