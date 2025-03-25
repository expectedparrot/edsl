from __future__ import annotations
from typing import Any, List, Union, Dict, Optional
from pathlib import Path
import time
import logging
from functools import lru_cache

from jinja2 import Environment, meta, Undefined

from .exceptions import TemplateRenderError, PromptValueError, PromptImplementationError
from ..base import PersistenceMixin, RepresentationMixin

logger = logging.getLogger(__name__)

MAX_NESTING = 100

class PreserveUndefined(Undefined):
    def __str__(self):
        return "{{ " + str(self._undefined_name) + " }}"

class TemplateVars:
    """Stores variables set during template rendering."""
    def __init__(self):
        self.data = {}
    
    def set(self, name, value):
        """Store a variable with its name and value,
        returning an empty string for direct use in the template.
        """
        self.data[name] = value
        return ""
    
    def get(self, name, default=None):
        """Retrieve a stored variable."""
        return self.data.get(name, default)
    
    def get_all(self) -> Dict[str, Any]:
        """Return all captured variables."""
        return self.data

def make_env() -> Environment:
    """Create a fresh Jinja environment each time,
    so we don't mix captured variables across multiple renders.
    """
    return Environment(undefined=PreserveUndefined)

@lru_cache(maxsize=1024)
def _find_template_variables(template_text: str) -> List[str]:
    env = make_env()
    ast = env.parse(template_text)
    return list(meta.find_undeclared_variables(ast))

def _make_hashable(value):
    """Convert unhashable types to hashable ones."""
    if isinstance(value, list):
        return tuple(_make_hashable(item) for item in value)
    if isinstance(value, dict):
        return frozenset((k, _make_hashable(v)) for k, v in value.items())
    return value

@lru_cache(maxsize=1024)
def _compile_template(text: str):
    """Compile a Jinja template with caching."""
    env = make_env()
    return env.from_string(text)

@lru_cache(maxsize=1024)
def _cached_render(text: str, frozen_replacements: frozenset) -> str:
    """Cached version of template rendering with frozen replacements."""
    # Print cache info on every call
    cache_info = _cached_render.cache_info()
    print(f"\t\t\t\t\t Cache status - hits: {cache_info.hits}, misses: {cache_info.misses}, current size: {cache_info.currsize}")
    
    # Convert back to dict with original types for rendering
    replacements = {k: v for k, v in frozen_replacements}
    
    template = _compile_template(text)
    result = template.render(replacements)
    
    return result

class Prompt(PersistenceMixin, RepresentationMixin):
    """Class for creating a prompt to be used in a survey."""

    default_instructions: Optional[str] = "Do good things, friendly LLM!"

    def __len__(self):
        """Return the length of the prompt text."""
        return len(self.text)

    @classmethod
    def prompt_attributes(cls) -> List[str]:
        """Return the prompt class attributes."""
        return {k: v for k, v in cls.__dict__.items() if not k.startswith("_")}

    def __init__(self, text: Optional[str] = None):
        """Create a `Prompt` object.

        :param text: The text of the prompt.
        """
        if text is None:
            if hasattr(self, "default_instructions"):
                text = self.default_instructions
            else:
                text = ""
        if isinstance(text, Prompt):
            # make it idempotent w/ a prompt
            text = text.text
        self._text = text
        self.captured_variables = {}

    @classmethod
    def from_txt(cls, filename: str) -> 'Prompt':
        """Create a `Prompt` from text.

        :param text: The text of the prompt.
        """
        with open(filename, "r") as f:
            text = f.read()
        return cls(text=text)

    @classmethod
    def from_template(
        cls,
        file_name: str,
        path_to_folder: Optional[Union[str, Path]] = None,
        **kwargs: Dict[str, Any],
    ) -> "Prompt":
        """Create a `PromptBase` from a Jinja template.

        Args:
            file_name (str): The name of the Jinja template file.
            path_to_folder (Union[str, Path]): The path to the folder containing the template.
                            Can be absolute or relative.
            **kwargs: Variables to be passed to the template for rendering.

        Returns:
            PromptBase: An instance of PromptBase with the rendered template as text.
        """
        # if file_name lacks the .j2 extension, add it
        if not file_name.endswith(".jinja"):
            file_name += ".jinja"

        # Convert path_to_folder to a Path object if it's a string
        if path_to_folder is None:
            from importlib import resources

            path_to_folder = resources.path("..questions", "prompt_templates")

        try:
            folder_path = Path(path_to_folder)
        except Exception as e:
            raise PromptValueError(f"Invalid path: {path_to_folder}. Error: {e}")

        with open(folder_path.joinpath(file_name), "r") as f:
            text = f.read()
        return cls(text=text)

    @property
    def text(self) -> str:
        """Return the `Prompt` text."""
        return self._text

    def __add__(self, other_prompt) -> 'Prompt':
        """Add two prompts together.

        Example:

        >>> p = Prompt("Hello, {{person}}")
        >>> p2 = Prompt("How are you?")
        >>> p + p2
        Prompt(text=\"""Hello, {{person}}How are you?\""")

        >>> p + "How are you?"
        Prompt(text=\"""Hello, {{person}}How are you?\""")
        """
        if isinstance(other_prompt, str):
            return self.__class__(self.text + other_prompt)
        else:
            return self.__class__(text=self.text + other_prompt.text)

    def __str__(self):
        """Return the `Prompt` text.

        Example:
        >>> p = Prompt("Hello, {{person}}")
        >>> str(p)
        'Hello, {{person}}'
        """
        return self.text

    def __contains__(self, text_to_check) -> bool:
        """Check if the text_to_check is in the `Prompt` text.

        Example:

        >>> p = Prompt("Hello, {{person}}")
        >>> "person" in p
        True
        >>> "person2" in p
        False
        """
        return text_to_check in self.text

    def __repr__(self):
        """Return the `Prompt` text.

        Example:
        >>> p = Prompt("Hello, {{person}}")
        >>> p
        Prompt(text=\"""Hello, {{person}}\""")
        """
        return f'Prompt(text="""{self.text}""")'

    def template_variables(self) -> list[str]:
        """Return the variables in the template."""
        return _find_template_variables(self.text)

    def undefined_template_variables(self, replacement_dict: dict) -> list[str]:
        """Return the variables in the template that are not in the replacement_dict.

        :param replacement_dict: A dictionary of replacements to populate the template.

        Example:

        >>> p = Prompt("Hello, {{person}}")
        >>> p.undefined_template_variables({"person": "John"})
        []

        >>> p = Prompt("Hello, {{title}} {{person}}")
        >>> p.undefined_template_variables({"person": "John"})
        ['title']
        """
        return [var for var in self.template_variables() if var not in replacement_dict]

    def unused_traits(self, traits: dict) -> list[str]:
        """Return the traits that are not used in the template."""
        return [trait for trait in traits if trait not in self.template_variables()]

    @property
    def has_variables(self) -> bool:
        """Return True if the prompt has variables.

        Example:

        >>> p = Prompt("Hello, {{person}}")
        >>> p.has_variables
        True

        >>> p = Prompt("Hello, person")
        >>> p.has_variables
        False
        """
        return len(self.template_variables()) > 0

    def render(self, primary_replacement: dict, **additional_replacements) -> "Prompt":
        """
        Render the prompt with the replacements.

        :param primary_replacement: The primary replacement dictionary.
        :param additional_replacements: Additional replacement dictionaries.

        >>> p = Prompt("Hello, {{person}}")
        >>> p.render({"person": "John"})
        Prompt(text=\"""Hello, John\""")

        >>> p.render({"person": "Mr. {{last_name}}", "last_name": "Horton"})
        Prompt(text=\"""Hello, Mr. Horton\""")

        >>> p.render({"person": "Mr. {{last_name}}", "last_name": "Ho{{letter}}ton"}, max_nesting = 1)
        Prompt(text=\"""Hello, Mr. Ho{{ letter }}ton\""")

        >>> p.render({"person": "Mr. {{last_name}}"})
        Prompt(text=\"""Hello, Mr. {{ last_name }}\""")

        >>> p = Prompt("The sum is {% set x = 2 + 3 %}{{ vars.set('x', x) }}{{x}}")
        >>> result = p.render({})
        >>> print(result.captured_variables)
        {'x': 5}
        >>> result.captured_variables['x']
        5
        """
        try:
            template_vars = TemplateVars()
            new_text, captured_vars = self._render(
                self.text, primary_replacement, template_vars, **additional_replacements
            )
            result = Prompt(text=new_text)
            result.captured_variables = captured_vars
            return result
        except Exception as e:
            print(f"Error rendering prompt: {e}")
            return self

    @staticmethod
    def _render(
        text: str,
        primary_replacement: dict,
        template_vars: TemplateVars,
        **additional_replacements
    ) -> tuple[str, Dict[str, Any]]:
        """
        Render the template text with variables replaced.
        Returns (rendered_text, captured_variables).
        """
        # Combine replacements.
        all_replacements = {**primary_replacement, **additional_replacements}

        # If no replacements and no Jinja variables, just return the text.
        if not all_replacements and not _find_template_variables(text):
            return text, template_vars.get_all()

        env = make_env()
        # Provide access to the 'vars' object inside the template.
        env.globals['vars'] = template_vars

        # Start with the original text
        current_text = text

        for _ in range(MAX_NESTING):
            template = env.from_string(current_text)
            rendered_text = template.render(**all_replacements)

            if rendered_text == current_text:
                # No more changes, return final text with captured variables.
                return rendered_text, template_vars.get_all()

            # Update current_text for next iteration
            current_text = rendered_text

        raise TemplateRenderError(
            "Too much nesting - you created an infinite loop here, pal"
        )

    def to_dict(self, add_edsl_version=False) -> dict[str, Any]:
        """Return the `Prompt` as a dictionary.

        Example:

        >>> p = Prompt("Hello, {{person}}")
        >>> p.to_dict()
        {'text': 'Hello, {{person}}', 'class_name': 'Prompt'}

        """
        return {"text": self.text, "class_name": self.__class__.__name__}

    @classmethod
    def from_dict(cls, data) -> 'Prompt':
        """Create a `Prompt` from a dictionary.

        Example:

        >>> p = Prompt("Hello, {{person}}")
        >>> p2 = Prompt.from_dict(p.to_dict())
        >>> p2
        Prompt(text=\"""Hello, {{person}}\""")

        """
        # class_name = data["class_name"]
        return Prompt(text=data["text"])


    @classmethod
    def example(cls):
        """Return an example of the prompt."""
        return cls(cls.default_instructions)

    def get_prompts(self) -> Dict[str, Any]:
        """Get the prompts for the question.        

        >>> p = Prompt("Hello, {{person}}")
        """

        raise PromptImplementationError("This method should be implemented by the subclass.")
        start = time.time()
        
        # Build all the components
        instr_start = time.time()
        agent_instructions = self.agent_instructions_prompt
        instr_end = time.time()
        logger.debug(f"Time taken for agent instructions: {instr_end - instr_start:.4f}s")
        
        persona_start = time.time()
        agent_persona = self.agent_persona_prompt
        persona_end = time.time()
        logger.debug(f"Time taken for agent persona: {persona_end - persona_start:.4f}s")
        
        q_instr_start = time.time()
        question_instructions = self.question_instructions_prompt
        q_instr_end = time.time()
        logger.debug(f"Time taken for question instructions: {q_instr_end - q_instr_start:.4f}s")
        
        memory_start = time.time()
        prior_question_memory = self.prior_question_memory_prompt
        memory_end = time.time()
        logger.debug(f"Time taken for prior question memory: {memory_end - memory_start:.4f}s")

        # Get components dict
        components = {
            "agent_instructions": agent_instructions.text,
            "agent_persona": agent_persona.text,
            "question_instructions": question_instructions.text,
            "prior_question_memory": prior_question_memory.text,
        }

        # Use PromptPlan's get_prompts method
        plan_start = time.time()
        prompts = self.prompt_plan.get_prompts(**components)
        plan_end = time.time()
        logger.debug(f"Time taken for prompt processing: {plan_end - plan_start:.4f}s")
        
        # Handle file keys if present
        if hasattr(self, 'question_file_keys') and self.question_file_keys:
            files_start = time.time()
            files_list = []
            for key in self.question_file_keys:
                files_list.append(self.scenario[key])
            prompts["files_list"] = files_list
            files_end = time.time()
            logger.debug(f"Time taken for file key processing: {files_end - files_start:.4f}s")
        
        end = time.time()
        logger.debug(f"Total time in get_prompts: {end - start:.4f}s")
        return prompts

if __name__ == "__main__":
    import doctest
    doctest.testmod()

