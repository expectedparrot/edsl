"""This module contains the RegisterPromptsMeta metaclass, which is used to register prompts."""
import traceback
from collections import defaultdict
from typing import List, Any

from abc import ABCMeta, abstractmethod

from edsl.prompts.prompt_config import (
    C2A,
    names_to_component_types,
    ComponentTypes,
    NEGATIVE_INFINITY,
)

from edsl.enums import QuestionType  # , LanguageModelType

from edsl.exceptions.prompts import (
    PromptBadQuestionTypeError,
    PromptBadLanguageModelTypeError,
)


class RegisterPromptsMeta(ABCMeta):
    """Metaclass to register prompts."""

    _registry = defaultdict(list)  # Initialize the registry as a dictionary
    _prompts_by_component_type = defaultdict(list)
    # _instances = {}

    # def __new__(mcs, name, bases, dct):
    #     if mcs not in mcs._instances:
    #         mcs._instances[mcs] = super(RegisterPromptsMeta, mcs).__new__(
    #             mcs, name, bases, dct
    #         )
    #     return mcs._instances[mcs]

    def __init__(cls, name, bases, dct):
        """
        We can only have one prompt class per name.

        Each prompt class must have a component type from the ComponentTypes enum.

        Example usage:
        >>> class Prompt1(PromptBase):
        ...     component_type = ComponentTypes.TEST

        >>> class Prompt1(PromptBase):
        ...     component_type = ComponentTypes.TEST
        Traceback (most recent call last):
        ...
        Exception: We already have a Prompt class named Prompt1.
        """
        super(RegisterPromptsMeta, cls).__init__(name, bases, dct)
        # print(f"Current state of registry: {RegisterPromptsMeta._registry}")
        # print(f"Registry called with {name}")
        if "Base" in name or name == "Prompt":
            # print("Exiting")
            return None  # We don't want to register the base class

        if name in RegisterPromptsMeta._registry:
            if RegisterPromptsMeta._registry[name] != cls:
                raise Exception(f"We already have a Prompt class named {name}.")
            else:
                # print("It's the same thing - it's fine.")
                return None

        RegisterPromptsMeta._registry[name] = cls
        # print(f"Current registry: {RegisterPromptsMeta._registry}")
        if (
            component_type := getattr(cls, "component_type", None)
        ) not in ComponentTypes:
            raise Exception(f"Prompt {name} is not in the list of component types")

        ## Make sure that the prompt has a question_type class attribute & it's valid
        if component_type == ComponentTypes.QUESTION_INSTRUCTIONS:
            if not hasattr(cls, "question_type"):
                raise PromptBadQuestionTypeError(
                    "A QuestionInstructions prompt must has a question_type value"
                )
            if not QuestionType.is_value_valid(cls.question_type):
                acceptable_values = [item.value for item in QuestionType]
                raise PromptBadQuestionTypeError(
                    f"""
                A Prompt's question_type must be one of {QuestionType} values, which are 
                currently {acceptable_values}. You passed {cls.question_type}."""
                )

        ## Make sure that if the prompt has a model class attribute, it's valid
        # if hasattr(cls, "model"):
        #     if not LanguageModelType.is_value_valid(cls.model):
        #         acceptable_values = [item.value for item in LanguageModelType]
        #         raise PromptBadLanguageModelTypeError(
        #             f"""
        #         A Prompt's model must be one of {LanguageModelType} values, which are
        #         currently {acceptable_values}. You passed {cls.model}."""
        #         )

        key = cls._create_prompt_class_key(dct, component_type)
        cls.data = key
        RegisterPromptsMeta._prompts_by_component_type[component_type].append(cls)

    @classmethod
    def _create_prompt_class_key(cls, dct, component_type) -> tuple[tuple[str, Any]]:
        """Create a key for the prompt class.

        This is a helper function.
        """
        attributes = [attribute.value for attribute in C2A.get(component_type, [])]
        cls_data = {key: value for key, value in dct.items() if key in attributes}
        return tuple(cls_data.items())

    @classmethod
    def _get_classes_with_scores(cls, **kwargs) -> List[tuple[float, "PromptBase"]]:
        """
        Find matching prompts.

        NB that _get_classes_with_scores returns a list of tuples.
        The first element of the tuple is the score, and the second element is the prompt class.
        There is a public-facing function called get_classes that returns only the prompt classes.

        The kwargs are the attributes that we want to match on. E.g., supposed you
        wanted a prompt with component_type = "question_instructions" and question_type = "multiple_choice".
        You would run:

        >>> get_classes(component_type="question_instructions", question_type="multiple_choice", model="gpt-4-1106-preview")
        [<class '__main__.MultipleChoice'>, <class '__main__.MultipleChoiceTurbo'>]

        In the above example, we have two prompts that match. Note that the order of the prompts is determined by the score and the regular MultipleChoice
        is ranked higher because it matches on the model as well.

        Scores are computed by the _score method. The score is the number of attributes that match, with their weights.
        However, if a required attribute doesn't match, then the score is -inf and it can never be selected.

        The function will throw an exception if you don't specify a component type that's in the ComponentTypes enum.

        >>> get_classes(component_type="chicken_tenders", question_type="multiple_choice")
        Traceback (most recent call last):
        ...
        Exception: You must specify a component type. It must be one of dict_keys([...])

        >>> get_classes(component_type="generic")
        []
        """
        component_type_string = kwargs.get("component_type", None)
        component_type = names_to_component_types.get(component_type_string, None)

        if component_type is None:
            raise Exception(
                f"You must specify a component type. It must be one of {names_to_component_types.keys()}"
            )

        try:
            prompts = cls._prompts_by_component_type[component_type]
        except KeyError:
            raise Exception(f"No prompts for component type {component_type}")

        with_scores = [(cls._score(kwargs, prompt), prompt) for prompt in prompts]
        with_scores = sorted(with_scores, key=lambda x: -x[0])
        # filter out the ones with -inf
        matches_with_scores = cls._filter_out_non_matches(with_scores)
        return matches_with_scores

    @classmethod
    def _filter_out_non_matches(cls, prompts_with_scores):
        """Filter out the prompts that have a score of -inf."""
        return [
            (score, prompt)
            for score, prompt in prompts_with_scores
            if score > NEGATIVE_INFINITY
        ]

    @classmethod
    def get_classes(cls, **kwargs):
        """Return only the prompt classes and not the scores.

        Public-facing function.
        """
        with_scores = cls._get_classes_with_scores(**kwargs)
        return [prompt for _, prompt in with_scores]
        # return with_scores

    @classmethod
    def _score(cls, kwargs, prompt):
        """Score the prompt based on the attributes that match."""
        required_list = ["question_type"]
        score = 0
        for key, value in kwargs.items():
            if prompt_value := getattr(prompt, key, None) == value:
                score += 1
            else:
                if key in required_list:
                    score += NEGATIVE_INFINITY
        return score

    @classmethod
    def get_registered_classes(cls):
        """Return the registry."""
        return cls._registry


get_classes = RegisterPromptsMeta.get_classes
