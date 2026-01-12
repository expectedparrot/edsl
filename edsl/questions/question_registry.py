"""This module provides a factory class for creating question objects."""

import textwrap
from uuid import UUID
from typing import Any, Optional, Union

from .question_base import RegisterQuestionsMeta


class QuestionVibesAccessor:
    """Accessor for Question vibes service operations.
    
    Provides a clean interface for generating questions from natural language.
    
    Example:
        >>> q = Question.vibes.generate("Ask about favorite color")  # doctest: +SKIP
        >>> q = Question.vibes.create("A satisfaction question")  # doctest: +SKIP
    """
    
    def __repr__(self) -> str:
        return (
            "QuestionVibesAccessor - Generate questions from natural language\n\n"
            "Methods:\n"
            "  .generate(description) - Generate a question from description\n"
            "  .create(description)   - Alias for generate\n\n"
            "Example:\n"
            "  >>> q = Question.vibes.generate('Ask about favorite color')\n"
            "  >>> q.question_type\n"
            "  'multiple_choice'"
        )
    
    def _repr_html_(self) -> str:
        return """
<div style="font-family: monospace; padding: 10px; border: 1px solid #ddd; border-radius: 8px; background: #f9f9f9;">
<b style="color: #3498db;">QuestionVibesAccessor</b><br>
Generate questions from natural language<br><br>
<b>Methods:</b> <code>.generate()</code>, <code>.create()</code><br><br>
<b>Example:</b><br>
<code>q = Question.vibes.generate("Ask about favorite color")</code>
</div>
"""
    
    def generate(
        self,
        description: str,
        *,
        model: str = "gpt-4o",
        temperature: float = 0.7,
        verbose: bool = True,
    ):
        """Generate a question from a natural language description.
        
        Args:
            description: Natural language description of the question
            model: OpenAI model to use (default: gpt-4o)
            temperature: Temperature for generation (default: 0.7)
            verbose: Show progress messages (default: True)
            
        Returns:
            A Question instance of the appropriate type
            
        Example:
            >>> q = Question.vibes.generate("Ask what their favorite color is")  # doctest: +SKIP
            >>> print(q.question_type)  # doctest: +SKIP
            multiple_choice
        """
        from edsl_services.question_vibes.service import QuestionVibesService
        
        if verbose:
            print(f"[question_vibes] Generating question...")
        
        params = QuestionVibesService.create_task(
            description=description,
            model=model,
            temperature=temperature,
        )
        result = QuestionVibesService.execute(params)
        question = QuestionVibesService.parse_result(result)
        
        if verbose:
            print(f"[question_vibes] ✓ Created {question.question_type} question: '{question.question_name}'")
        
        return question
    
    # Alias
    create = generate


# Singleton instance
_question_vibes_accessor = QuestionVibesAccessor()


class Meta(type):
    """Metaclass for QuestionBase that provides a __repr__ method that lists all available questions."""

    def __repr__(cls):
        """Return a string that lists all available questions."""

        s = textwrap.dedent(
            """
        You can use the Question class to create objects by name. 
        For example, to create a multiple choice question, you can do:

        >>> from edsl import Question
        >>> q = Question('multiple_choice', question_text='What is your favorite color?', question_name='color')
        
        Question Types:\n"""
        )
        for question_type, question_class in cls.available(
            show_class_names=True
        ).items():
            line_info = (
                f"{question_type} ({question_class.__name__}): {question_class.__doc__}"
            )
            s += line_info + "\n"
        return s
    
    @property
    def vibes(cls) -> "QuestionVibesAccessor":
        """Access question generation via vibes service.
        
        Example:
            >>> q = Question.vibes.generate("Ask about favorite color")  # doctest: +SKIP
        """
        return _question_vibes_accessor


class Question(metaclass=Meta):
    """Factory class for creating question objects."""

    def __new__(cls, question_type, *args, **kwargs):
        """Create a new question object."""
        get_question_classes = RegisterQuestionsMeta.question_types_to_classes()

        subclass = get_question_classes.get(question_type, None)
        if subclass is None:
            # they might be trying to pull a question from coop by name
            try:
                q = Question.pull(question_type)
                return q
            except Exception:
                from .exceptions import QuestionValueError

                raise QuestionValueError(
                    f"No question registered with question_type {question_type}"
                )

        # Create an instance of the selected subclass
        instance = object.__new__(subclass)
        instance.__init__(*args, **kwargs)
        return instance

    @classmethod
    def example(cls, question_type: str):
        """Return an example question of the given type."""
        get_question_classes = RegisterQuestionsMeta.question_types_to_classes()
        q = get_question_classes.get(question_type, None)
        return q.example()

    @classmethod
    def pull(cls, url_or_uuid: Union[str, UUID]):
        """Pull the object from coop.

        Args:
            url_or_uuid: Identifier for the question to retrieve.
                Can be one of:
                - UUID string (e.g., "123e4567-e89b-12d3-a456-426614174000")
                - Full URL (e.g., "https://expectedparrot.com/content/123e4567...")
                - Alias URL (e.g., "https://expectedparrot.com/content/username/my-question")
                - Shorthand alias (e.g., "username/my-question")

        Returns:
            The question object retrieved from coop
        """
        from ..coop import Coop
        from ..config import CONFIG

        # Convert shorthand syntax to full URL if needed
        if isinstance(url_or_uuid, str) and not url_or_uuid.startswith(
            ("http://", "https://")
        ):
            # Check if it looks like a UUID (basic check for UUID format)
            is_uuid = len(url_or_uuid) == 36 and url_or_uuid.count("-") == 4
            if not is_uuid and "/" in url_or_uuid:
                # Looks like shorthand format "username/alias"
                url_or_uuid = f"{CONFIG.EXPECTED_PARROT_URL}/content/{url_or_uuid}"

        coop = Coop()
        return coop.pull(url_or_uuid, "question")

    @classmethod
    def delete(cls, url_or_uuid: Union[str, UUID]):
        """Delete the object from coop."""
        from ..coop import Coop

        coop = Coop()
        return coop.delete(url_or_uuid)

    @classmethod
    def patch(
        cls,
        url_or_uuid: Union[str, UUID],
        description: Optional[str] = None,
        value: Optional[Any] = None,
        visibility: Optional[str] = None,
    ):
        """Patch the object on coop."""
        from ..coop import Coop

        coop = Coop()
        return coop.patch(url_or_uuid, description, value, visibility)

    @classmethod
    def list_question_types(cls):
        """Return a list of available question types.

        >>> from edsl import Question
        >>> Question.list_question_types()
        ['checkbox', 'compute', 'demand', 'dict', 'dropdown', 'edsl_object', 'extract', 'file_upload', 'free_text', 'functional', 'interview', 'likert_five', 'linear_scale', 'list', 'markdown', 'matrix', 'multiple_choice', 'multiple_choice_with_other', 'numerical', 'pydantic', 'random', 'rank', 'top_k', 'yes_no']
        """
        return [
            q
            for q in sorted(
                list(RegisterQuestionsMeta.question_types_to_classes().keys())
            )
            if q not in ["budget"]
        ]

    @classmethod
    def available(cls, show_class_names: bool = False) -> Union[list, dict]:
        """Return a list of available question types.

        :param show_class_names: If True, return a dictionary of question types to class names. If False, return a set of question types.

        Example usage:

        """
        from ..dataset import Dataset

        exclude = ["budget"]
        if show_class_names:
            return RegisterQuestionsMeta.question_types_to_classes()
        else:
            question_list = [
                q
                for q in sorted(
                    set(RegisterQuestionsMeta.question_types_to_classes().keys())
                )
                if q not in exclude
            ]
            d = RegisterQuestionsMeta.question_types_to_classes()
            question_classes = [d[q] for q in question_list]
            example_questions = [q.example()._eval_repr_() for q in question_classes]

            return Dataset(
                [
                    {"question_type": [q for q in question_list]},
                    {"question_class": [q.__name__ for q in question_classes]},
                    {"example_question": example_questions},
                ],
                print_parameters={"containerHeight": "auto"},
            )

    @classmethod
    def from_vibes(
        cls,
        description: str,
        *,
        model: str = "gpt-4o",
        temperature: float = 0.7,
        verbose: bool = True,
    ):
        """Generate a question from a natural language description.

        This method uses an LLM to generate an appropriate EDSL question based on a
        description of what the question should ask. It automatically selects appropriate
        question types and formats.

        Args:
            description: Natural language description of what the question should ask
            model: OpenAI model to use for generation (default: "gpt-4o")
            temperature: Temperature for generation (default: 0.7)
            verbose: Show progress messages (default: True)

        Returns:
            QuestionBase: A new Question instance with the appropriate type

        Examples:
            >>> from edsl import Question
            >>> q = Question.from_vibes("Ask what their favorite color is")  # doctest: +SKIP
            >>> print(q.question_name, q.question_type)  # doctest: +SKIP
            favorite_color multiple_choice

            >>> q = Question.from_vibes("Find out how satisfied they are with the product")  # doctest: +SKIP
            >>> print(q.question_type)  # doctest: +SKIP
            multiple_choice

            >>> q = Question.from_vibes("Ask if they would recommend this to a friend")  # doctest: +SKIP
            >>> print(q.question_type)  # doctest: +SKIP
            yes_no
        """
        # Delegate to vibes accessor for consistent service behavior
        return cls.vibes.generate(
            description,
            model=model,
            temperature=temperature,
            verbose=verbose,
        )


def get_question_class(question_type):
    """Return the class for the given question type."""
    q2c = RegisterQuestionsMeta.question_types_to_classes()
    if question_type not in q2c:
        from .exceptions import QuestionValueError

        raise QuestionValueError(
            f"The question type, {question_type}, is not recognized. Recognied types are: {q2c.keys()}"
        )
    return q2c.get(question_type)


question_purpose = {
    "multiple_choice": "When options are known and limited",
    "multiple_choice_with_other": "When options are known but you want to allow for custom responses",
    "free_text": "When options are unknown or unlimited",
    "checkbox": "When multiple options can be selected",
    "numerical": "When the answer is a single numerical value e.g., a float",
    "linear_scale": "When options are text, but can be ordered, e.g., daily, weekly, monthly, etc.",
    "yes_no": "When the question can be fully answered with either a yes or a no",
    "list": "When the answer should be a list of items",
    "rank": "When the answer should be a ranked list of items",
    "budget": "When the answer should be an amount allocated among a set of options",
    "top_k": "When the answer should be a list of the top k items",
    "likert_five": "When the answer should be a value on the Likert scale from 1 to 5",
    "extract": "When the answer should be information extracted or extrapolated from a text in a given format",
}


if __name__ == "__main__":
    import doctest

    doctest.testmod()
