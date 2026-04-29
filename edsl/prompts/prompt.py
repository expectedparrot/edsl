from __future__ import annotations
from typing import Any, List, Union, Dict, Optional
from pathlib import Path
import logging
import time
import threading
from functools import lru_cache

from jinja2 import meta, Undefined
from jinja2.sandbox import SandboxedEnvironment

from .exceptions import TemplateRenderError, PromptValueError, PromptImplementationError
from ..base import PersistenceMixin, RepresentationMixin

logger = logging.getLogger(__name__)

# Thread-safe timing accumulators for _render() internals
_render_timing_lock = threading.Lock()
_render_timing_accum = {
    "fast_path_skips": 0,
    "find_template_vars": 0.0,
    "build_replacements": 0.0,
    "template_render": 0.0,
    "total_render": 0.0,
    "call_count": 0,
}


def reset_render_timings():
    with _render_timing_lock:
        for k in _render_timing_accum:
            _render_timing_accum[k] = (
                0.0 if isinstance(_render_timing_accum[k], float) else 0
            )


def get_render_timings() -> dict:
    with _render_timing_lock:
        return dict(_render_timing_accum)


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


def make_env() -> SandboxedEnvironment:
    """Create a fresh sandboxed Jinja environment each time.

    Uses SandboxedEnvironment to prevent Server-Side Template Injection (SSTI)
    attacks by blocking access to dangerous attributes like __class__, __mro__,
    __globals__, etc.
    """
    return SandboxedEnvironment(undefined=PreserveUndefined)


# Module-level cached environment for parsing/compilation (no globals mutation)
_PARSE_ENV = SandboxedEnvironment(undefined=PreserveUndefined)


@lru_cache(maxsize=100000)
def _find_template_variables(template_text: str) -> List[str]:
    ast = _PARSE_ENV.parse(template_text)
    return list(meta.find_undeclared_variables(ast))


@lru_cache(maxsize=100000)
def _get_compiled_template(template_text: str):
    """Cache compiled Jinja2 templates for reuse.

    This is the main performance optimization - instead of recompiling
    templates for every render, we cache compiled templates by their text.
    """
    return _PARSE_ENV.from_string(template_text)


def _make_hashable(value):
    """Convert unhashable types to hashable ones."""
    if isinstance(value, list):
        return tuple(_make_hashable(item) for item in value)
    if isinstance(value, dict):
        return frozenset((k, _make_hashable(v)) for k, v in value.items())
    return value


@lru_cache(maxsize=100000)
def _compile_template(text: str):
    """Compile a Jinja template with caching."""
    return _PARSE_ENV.from_string(text)


@lru_cache(maxsize=100000)
def _cached_render(text: str, frozen_replacements: frozenset) -> str:
    """Cached version of template rendering with frozen replacements."""
    # Convert back to dict with original types for rendering
    replacements = {k: v for k, v in frozen_replacements}

    template = _compile_template(text)
    result = template.render(replacements)

    return result


class Prompt(str, PersistenceMixin, RepresentationMixin):
    """Class for creating a prompt to be used in a survey."""

    default_instructions: Optional[str] = "Do good things, friendly LLM!"

    def __new__(cls, text: Optional[str] = None):
        """Create a new Prompt instance (required for str subclassing)."""
        if text is None:
            if hasattr(cls, "default_instructions"):
                text = cls.default_instructions
            else:
                text = ""
        if isinstance(text, Prompt):
            # make it idempotent w/ a prompt
            text = str(text)

        # Create the string instance
        instance = str.__new__(cls, text)
        return instance

    def __init__(self, text: Optional[str] = None):
        """Create a `Prompt` object.

        :param text: The text of the prompt.
        """
        # String content is already set in __new__, just initialize other attributes
        self.captured_variables = {}

    @classmethod
    def prompt_attributes(cls) -> List[str]:
        """Return the prompt class attributes."""
        return {k: v for k, v in cls.__dict__.items() if not k.startswith("_")}

    @classmethod
    def from_txt(cls, filename: str) -> "Prompt":
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
        return str(self)

    def __add__(self, other_prompt) -> "Prompt":
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
            return self.__class__(str(self) + other_prompt)
        else:
            return self.__class__(str(self) + str(other_prompt))

    def __repr__(self):
        """Return the `Prompt` text.

        Example:
        >>> p = Prompt("Hello, {{person}}")
        >>> p
        Prompt(text=\"""Hello, {{person}}\""")
        """
        return f'Prompt(text="""{str(self)}""")'

    def _repr_rich_(self):
        """Rich representation showing template with highlighted variables and control structures."""
        try:
            from rich.text import Text
            from rich.panel import Panel
            from rich.console import Console
            import re
        except ImportError:
            return repr(self)

        text = Text()
        template_str = str(self)

        # Pattern to match {{ ... }}, {% ... %}, and <...>
        pattern = r"(\{\{[^}]*\}\}|\{%[^%]*%\}|<[^>]*>)"

        parts = re.split(pattern, template_str)

        for part in parts:
            if part.startswith("{{") and part.endswith("}}"):
                # Variable placeholder - cyan/bright blue
                text.append(part, style="bold cyan")
            elif part.startswith("{%") and part.endswith("%}"):
                # Control structure (set, for, if, etc.) - magenta
                text.append(part, style="bold magenta")
            elif part.startswith("<") and part.endswith(">"):
                # Angle bracket content - yellow
                text.append(part, style="bold yellow")
            else:
                # Regular text
                text.append(part, style="white")

        panel = Panel(text, title="[bold blue]Prompt[/bold blue]", border_style="blue")

        # Print to console/terminal
        console = Console()
        console.print(panel)

        return panel

    def template_variables(self) -> list[str]:
        """Return the variables in the template."""
        # Fast path: if no template syntax, return empty list
        text = str(self)
        if "{{" not in text and "{%" not in text:
            return []
        return _find_template_variables(text)

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
        template_vars = self.template_variables()
        return [var for var in template_vars if var not in replacement_dict]

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
                str(self), primary_replacement, template_vars, **additional_replacements
            )
            result = Prompt(text=new_text)
            result.captured_variables = captured_vars
            return result
        except Exception as e:
            print(f"Error rendering prompt: {e}")
            raise e
            return self

    @staticmethod
    def _render(
        text: str,
        primary_replacement: dict,
        template_vars: TemplateVars,
        **additional_replacements,
    ) -> tuple[str, Dict[str, Any]]:
        """
        Render the template text with variables replaced.
        Returns (rendered_text, captured_variables).
        """
        _t_total = time.time()

        # FAST PATH: if no Jinja syntax in the text, skip all template processing
        if "{{" not in text and "{%" not in text:
            with _render_timing_lock:
                _render_timing_accum["fast_path_skips"] += 1
                _render_timing_accum["call_count"] += 1
                _render_timing_accum["total_render"] += time.time() - _t_total
            return text, template_vars.get_all()

        # Combine replacements.
        _t_repl = time.time()
        from ..scenarios import Scenario

        # This fixed Issue 2027 - the scenario prefix  was not being recoginized in the template
        if isinstance(primary_replacement, Scenario):
            additional = {"scenario": primary_replacement.to_dict()}
        else:
            additional = {}
        all_replacements = {
            **primary_replacement,
            **additional_replacements,
            **additional,
        }
        _t_repl_end = time.time()

        # If no replacements and no Jinja variables, just return the text.
        _t_find = time.time()
        has_vars = _find_template_variables(text)
        _t_find_end = time.time()
        if not all_replacements and not has_vars:
            with _render_timing_lock:
                _render_timing_accum["build_replacements"] += _t_repl_end - _t_repl
                _render_timing_accum["find_template_vars"] += _t_find_end - _t_find
                _render_timing_accum["call_count"] += 1
                _render_timing_accum["total_render"] += time.time() - _t_total
            return text, template_vars.get_all()

        # Start with the original text
        current_text = text
        _template_render_time = 0.0

        for _ in range(MAX_NESTING):
            if "{{" in current_text or "{%" in current_text:
                template = _get_compiled_template(current_text)

                # Inject the vars object for this render call
                template.globals["vars"] = template_vars

                _t_render = time.time()
                rendered_text = template.render(**all_replacements)
                _template_render_time += time.time() - _t_render
            else:
                # No template syntax, use text as-is
                rendered_text = current_text

            if rendered_text == current_text:
                # No more changes, return final text with captured variables.
                with _render_timing_lock:
                    _render_timing_accum["build_replacements"] += _t_repl_end - _t_repl
                    _render_timing_accum["find_template_vars"] += _t_find_end - _t_find
                    _render_timing_accum["template_render"] += _template_render_time
                    _render_timing_accum["call_count"] += 1
                    _render_timing_accum["total_render"] += time.time() - _t_total
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
        return {"text": str(self), "class_name": self.__class__.__name__}

    @classmethod
    def from_dict(cls, data) -> "Prompt":
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

        raise PromptImplementationError(
            "This method should be implemented by the subclass."
        )
        start = time.time()

        # Build all the components
        instr_start = time.time()
        agent_instructions = self.agent_instructions_prompt
        instr_end = time.time()
        logger.debug(
            f"Time taken for agent instructions: {instr_end - instr_start:.4f}s"
        )

        persona_start = time.time()
        agent_persona = self.agent_persona_prompt
        persona_end = time.time()
        logger.debug(
            f"Time taken for agent persona: {persona_end - persona_start:.4f}s"
        )

        q_instr_start = time.time()
        question_instructions = self.question_instructions_prompt
        q_instr_end = time.time()
        logger.debug(
            f"Time taken for question instructions: {q_instr_end - q_instr_start:.4f}s"
        )

        memory_start = time.time()
        prior_question_memory = self.prior_question_memory_prompt
        memory_end = time.time()
        logger.debug(
            f"Time taken for prior question memory: {memory_end - memory_start:.4f}s"
        )

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
        if hasattr(self, "question_file_keys") and self.question_file_keys:
            files_start = time.time()
            files_list = []
            for key in self.question_file_keys:
                files_list.append(self.scenario[key])
            prompts["files_list"] = files_list
            files_end = time.time()
            logger.debug(
                f"Time taken for file key processing: {files_end - files_start:.4f}s"
            )

        end = time.time()
        logger.debug(f"Total time in get_prompts: {end - start:.4f}s")
        return prompts


if __name__ == "__main__":
    import doctest

    doctest.testmod()
