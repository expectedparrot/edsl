from importlib import resources
from typing import Optional, TYPE_CHECKING
from functools import lru_cache

from .exceptions import QuestionAnswerValidationError

if TYPE_CHECKING:
    from pydantic import BaseModel
    from ..prompts import Prompt
    from ..prompts.prompt import PromptBase

class TemplateManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._template_cache = {}
        return cls._instance

    @lru_cache(maxsize=None)
    def get_template(self, question_type, template_name):
        if (question_type, template_name) not in self._template_cache:
            with resources.open_text(
                f"edsl.questions.templates.{question_type}", template_name
            ) as file:
                self._template_cache[(question_type, template_name)] = file.read()
        return self._template_cache[(question_type, template_name)]


# Global instance
template_manager = TemplateManager()


class QuestionBasePromptsMixin:
    @property
    def model_instructions(self) -> dict:
        """Get the model-specific instructions for the question."""
        if not hasattr(self, "_model_instructions"):
            self._model_instructions = {}
        return self._model_instructions

    def _all_text(self) -> str:
        """Return the question text.

        >>> from edsl import QuestionMultipleChoice as Q
        >>> Q.example()._all_text()
        "how_feelingHow are you?['Good', 'Great', 'OK', 'Bad']"
        """
        txt = ""
        for key, value in self.data.items():
            if isinstance(value, str):
                txt += value
            elif isinstance(value, list):
                txt += "".join(str(value))
        return txt

    @model_instructions.setter
    def model_instructions(self, data: dict):
        """Set the model-specific instructions for the question."""
        self._model_instructions = data

    def add_model_instructions(
        self, *, instructions: str, model: Optional[str] = None
    ) -> None:
        """Add model-specific instructions for the question that override the default instructions.

        :param instructions: The instructions to add. This is typically a jinja2 template.
        :param model: The language model for this instruction.

        >>> from edsl.questions import QuestionFreeText
        >>> q = QuestionFreeText(question_name = "color", question_text = "What is your favorite color?")
        >>> q.add_model_instructions(instructions = "{{question_text}}. Answer in valid JSON like so {'answer': 'comment: <>}", model = "gpt3")
        >>> q.get_instructions(model = "gpt3")
        Prompt(text=\"""{{question_text}}. Answer in valid JSON like so {'answer': 'comment: <>}\""")
        """
        from ..language_models.model import Model

        if not hasattr(self, "_model_instructions"):
            self._model_instructions = {}
        if model is None:
            # if not model is passed, all the models are mapped to this instruction, including 'None'
            self._model_instructions = {
                model_name: instructions
                for model_name in Model.available(name_only=True)
            }
            self._model_instructions.update({model: instructions})
        else:
            self._model_instructions.update({model: instructions})

    @classmethod
    def path_to_folder(cls) -> str:
        return resources.files("edsl.questions.templates", cls.question_type)

    @property
    def response_model(self) -> type["BaseModel"]:
        if self._response_model is not None:
            return self._response_model
        else:
            return self.create_response_model()

    @property
    def use_code(self) -> bool:
        if hasattr(self, "_use_code"):
            return self._use_code
        return True

    @use_code.setter
    def use_code(self, value: bool) -> None:
        self._use_code = value

    @property
    def include_comment(self) -> bool:
        if hasattr(self, "_include_comment"):
            return self._include_comment
        return True

    @include_comment.setter
    def include_comment(self, value: bool) -> None:
        self._include_comment = value

    @classmethod
    def default_answering_instructions(cls) -> str:
        # template_text = cls._read_template("answering_instructions.jinja")
        template_text = template_manager.get_template(
            cls.question_type, "answering_instructions.jinja"
        )
        from ..prompts import Prompt

        return Prompt(text=template_text)

    @classmethod
    def default_question_presentation(cls):
        template_text = template_manager.get_template(
            cls.question_type, "question_presentation.jinja"
        )
        from ..prompts import Prompt

        return Prompt(text=template_text)

    @property
    def answering_instructions(self) -> str:
        if self._answering_instructions is None:
            return self.default_answering_instructions()
        return self._answering_instructions

    @answering_instructions.setter
    def answering_instructions(self, value) -> None:
        self._answering_instructions = value

    @property
    def question_presentation(self):
        if self._question_presentation is None:
            return self.default_question_presentation()
        return self._question_presentation

    @question_presentation.setter
    def question_presentation(self, value):
        self._question_presentation = value

    def prompt_preview(self, scenario=None, agent=None):
        return self.new_default_instructions.render(
            self.data
            | {
                "include_comment": getattr(self, "_include_comment", True),
                "use_code": getattr(self, "_use_code", True),
            }
            | ({"scenario": scenario} or {})
            | ({"agent": agent} or {})
        )

    @classmethod
    def self_check(cls):
        q = cls.example()
        for answer, params in q.response_validator.valid_examples:
            for key, value in params.items():
                setattr(q, key, value)
            q._validate_answer(answer)
        for answer, params, reason in q.response_validator.invalid_examples:
            for key, value in params.items():
                setattr(q, key, value)
            try:
                q._validate_answer(answer)
            except QuestionAnswerValidationError:
                pass
            else:
                from .exceptions import QuestionValueError
                raise QuestionValueError(f"Example {answer} should have failed for {reason}.")

    @property
    def new_default_instructions(self) -> "Prompt":
        "This is set up as a property because there are mutable question values that determine how it is rendered."
        from ..prompts import Prompt

        return Prompt(self.question_presentation) + Prompt(self.answering_instructions)
    

    def detailed_parameters_by_key(self) -> dict[str, set[tuple[str, ...]]]:
        """
        Return a dictionary of parameters by key.

        >>> from edsl import QuestionMultipleChoice
        >>> QuestionMultipleChoice.example().detailed_parameters_by_key()
        {'question_name': set(), 'question_text': set()}

        >>> from edsl import QuestionFreeText
        >>> q = QuestionFreeText(question_name = "example", question_text = "What is your name, {{ nickname }}, based on {{ q0.answer }}?")
        >>> r = q.detailed_parameters_by_key()
        >>> r == {'question_name': set(), 'question_text': {('q0', 'answer'), ('nickname',)}}
        True
        """
        params_by_key = {}
        for key, value in self.data.items():
            if isinstance(value, str):
                params_by_key[key] = self.extract_parameters(value)
        return params_by_key

    @staticmethod
    def extract_parameters(txt: str) -> set[tuple[str, ...]]:
        """Return all parameters of the question as tuples representing their full paths.
        
        :param txt: The text to extract parameters from.
        :return: A set of tuples representing the parameters.

        >>> from edsl.questions import QuestionMultipleChoice
        >>> d = QuestionMultipleChoice.example().extract_parameters("What is your name, {{ nickname }}, based on {{ q0.answer }}?")
        >>> d =={('nickname',), ('q0', 'answer')}
        True
        """
        from jinja2 import Environment, nodes

        env = Environment()
        #txt = self._all_text()
        ast = env.parse(txt)
        
        variables = set()
        processed_nodes = set()  # Keep track of nodes we've processed
        
        def visit_node(node, path=()):
            if id(node) in processed_nodes:
                return
            processed_nodes.add(id(node))
            
            if isinstance(node, nodes.Name):
                # Only add the name if we're not in the middle of building a longer path
                if not path:
                    variables.add((node.name,))
                else:
                    variables.add((node.name,) + path)
            elif isinstance(node, nodes.Getattr):
                # Build path from bottom up
                new_path = (node.attr,) + path
                visit_node(node.node, new_path)
        
        for node in ast.find_all((nodes.Name, nodes.Getattr)):
            visit_node(node)

        return variables
    
    @property
    def detailed_parameters(self):
        return [".".join(p) for p in self.extract_parameters(self._all_text())]

    @property
    def parameters(self) -> set[str]:
        """Return the parameters of the question."""
        from jinja2 import Environment, meta

        env = Environment()
        # Parse the template
        txt = self._all_text()
        # txt = self.question_text
        # if hasattr(self, "question_options"):
        #    txt += " ".join(self.question_options)
        parsed_content = env.parse(txt)
        # Extract undeclared variables
        variables = meta.find_undeclared_variables(parsed_content)
        # Return as a list
        return set(variables)

    def get_instructions(self, model: Optional[str] = None) -> type["PromptBase"]:
        """Get the mathcing question-answering instructions for the question.

        :param model: The language model to use.
        """
        from ..prompts import Prompt

        if model in self.model_instructions:
            return Prompt(text=self.model_instructions[model])
        else:
            if hasattr(self, "new_default_instructions"):
                return self.new_default_instructions
            else:
                return self.applicable_prompts(model)[0]()

    @staticmethod
    def sequence_in_dict(d: dict, path: tuple[str, ...]) -> tuple[bool, any]:
        """Check if a sequence of nested keys exists in a dictionary and return the value.
        
        Args:
            d: The dictionary to check
            path: Tuple of keys representing the nested path
            
        Returns:
            tuple[bool, any]: (True, value) if the path exists, (False, None) otherwise
            
        Example:
            >>> sequence_in_dict = QuestionBasePromptsMixin.sequence_in_dict
            >>> d = {'a': {'b': {'c': 1}}}
            >>> sequence_in_dict(d, ('a', 'b', 'c'))
            (True, 1)
            >>> sequence_in_dict(d, ('a', 'b', 'd'))
            (False, None)
            >>> sequence_in_dict(d, ('x',))
            (False, None)
        """
        try:
            current = d
            for key in path:
                current = current.get(key)
                if current is None:
                    return (False, None)
            return (True, current)
        except (AttributeError, TypeError):
            return (False, None)


if __name__ == "__main__":
    import doctest
    doctest.testmod()