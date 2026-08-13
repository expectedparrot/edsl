import random
from ast import literal_eval
from typing import Union, TYPE_CHECKING

from .question_attribute_processor import QuestionAttributeProcessor

if TYPE_CHECKING:
    from ..scenarios import Scenario


class QuestionItemProcessor(QuestionAttributeProcessor):
    """
    Class that manages the processing of question items.
    These can be provided directly, as a template string, or fetched from prior
    answers or the scenario.
    """

    def __init__(self, scenario: "Scenario", prior_answers_dict: dict):
        super().__init__(scenario, prior_answers_dict)

    @staticmethod
    def _get_default_items() -> list:
        """Return default placeholder items."""
        return [f"<< Item {i} - Placeholder >>" for i in range(1, 4)]

    def _get_items_from_scenario(
        self, scenario: dict, item_key: tuple
    ) -> Union[list, None]:
        """
        Try to get items from scenario data.

        >>> from edsl import Scenario
        >>> scenario = Scenario({"items": ["Item 1", "Item 2"]})
        >>> processor = QuestionItemProcessor(scenario, {})
        >>> processor._get_items_from_scenario(scenario, ("items",))
        ['Item 1', 'Item 2']

        Returns:
            list | None: List of items if found in scenario, None otherwise
        """
        scenario_items = self._get_nested_key(scenario, item_key)
        return scenario_items if isinstance(scenario_items, list) else None

    def _get_items_from_prior_answers(
        self, prior_answers: dict, item_key: tuple
    ) -> Union[list, None]:
        """
        Try to get items from prior answers.

        >>> from edsl import QuestionList as Q
        >>> q = Q.example()
        >>> q.answer = ["Item 1", "Item 2"]
        >>> prior_answers = {"items": q}
        >>> from edsl import Scenario
        >>> processor = QuestionItemProcessor(Scenario({}), prior_answers)
        >>> processor._get_items_from_prior_answers(prior_answers, ("items",))
        ['Item 1', 'Item 2']
        >>> processor._get_items_from_prior_answers(prior_answers, ("wrong_key",)) is None
        True

        Returns:
            list | None: List of items if found in prior answers, None otherwise
        """
        prior_answer = self._get_nested_key(prior_answers, item_key)
        if prior_answer and hasattr(prior_answer, "answer"):
            if isinstance(prior_answer.answer, list):
                return prior_answer.answer
        return None

    def get_question_items(self, question_data: dict) -> list:
        """
        Extract and process question items from question data.

        Args:
            question_data (dict): Dictionary containing question configuration

        Returns:
            list: List of question items. Returns default placeholders if no valid
                items are found.

        >>> class MockPromptConstructor:
        ...     pass
        >>> mpc = MockPromptConstructor()
        >>> from edsl import Scenario
        >>> mpc.scenario = Scenario({"items": ["Item 1", "Item 2"]})
        >>> class MockQuestion:
        ...     pass
        >>> q0 = MockQuestion()
        >>> q0.answer = ["Item 1", "Item 2"]
        >>> mpc.prior_answers_dict = lambda: {"q0": q0}
        >>> processor = QuestionItemProcessor.from_prompt_constructor(mpc)

        The basic case where items are directly provided:

        >>> question_data = {"question_items": ["Item 1", "Item 2"]}
        >>> processor.get_question_items(question_data)
        ['Item 1', 'Item 2']

        The case where items are provided as a template string:

        >>> question_data = {"question_items": "{{ scenario.items }}"}
        >>> processor.get_question_items(question_data)
        ['Item 1', 'Item 2']

        The case where there is a template string in the prior answers:

        >>> question_data = {"question_items": "{{ q0.answer }}"}
        >>> processor.get_question_items(question_data)
        ['Item 1', 'Item 2']

        The case where the prior answer is the text of a list rather than a list,
        which is what a QuestionCompute answers with:

        >>> q1 = MockQuestion()
        >>> q1.answer = "['Item 1', 'Item 2']"
        >>> mpc.prior_answers_dict = lambda: {"q0": q0, "q1": q1}
        >>> compute_processor = QuestionItemProcessor.from_prompt_constructor(mpc)
        >>> compute_processor.get_question_items({"question_items": "{{ q1.answer }}"})
        ['Item 1', 'Item 2']

        A string that is not a list stays a lookup rather than being taken apart:

        >>> q2 = MockQuestion()
        >>> q2.answer = "Item 1, Item 2"
        >>> mpc.prior_answers_dict = lambda: {"q2": q2}
        >>> text_processor = QuestionItemProcessor.from_prompt_constructor(mpc)
        >>> text_processor.get_question_items({"question_items": "{{ q2.answer }}"})
        ['<< Item 1 - Placeholder >>', '<< Item 2 - Placeholder >>', '<< Item 3 - Placeholder >>']

        The case where no items are found:

        >>> processor.get_question_items({"question_items": "{{ missing }}"})
        ['<< Item 1 - Placeholder >>', '<< Item 2 - Placeholder >>', '<< Item 3 - Placeholder >>']

        The case where items are piped with additional static items:

        >>> question_data = {"question_items": {"from": "{{ q0.answer }}", "add": ["Item 3", "Item 4"]}}
        >>> processor.get_question_items(question_data)
        ['Item 1', 'Item 2', 'Item 3', 'Item 4']

        Randomization is applied only after a template resolves to a list:

        >>> import random
        >>> random.seed(1)
        >>> question_data = {"question_items": "{{ q0.answer }}", "randomize_items": True}
        >>> sorted(processor.get_question_items(question_data))
        ['Item 1', 'Item 2']

        Pinned rows retain their original positions:

        >>> random.seed(1)
        >>> question_data = {"question_items": ["A", "B", "Other"], "randomize_items": True, "items_to_pin": ["Other"]}
        >>> processor.get_question_items(question_data)[-1]
        'Other'
        """
        items_entry = question_data.get("question_items")

        # Handle dict format for piping with additional items
        if isinstance(items_entry, dict):
            from_template = items_entry.get("from")
            additional_items = items_entry.get("add", [])

            base_items = self._get_items_from_template(from_template)

            if base_items and base_items != self._get_default_items():
                items = base_items + additional_items
                return self._maybe_randomize(items, question_data)

            items = additional_items if additional_items else self._get_default_items()
            return self._maybe_randomize(items, question_data)

        # If not a template string or dict, return as is or default
        if not isinstance(items_entry, str):
            items = items_entry if items_entry else self._get_default_items()
            return self._maybe_randomize(items, question_data)

        # Handle simple template string
        items = self._get_items_from_template(items_entry)
        return self._maybe_randomize(items, question_data)

    @staticmethod
    def _maybe_randomize(items: list, question_data: dict) -> list:
        """Shuffle resolved matrix rows while leaving requested positions pinned."""
        if not question_data.get("randomize_items") or len(items) < 2:
            return items

        pinned_values = question_data.get("items_to_pin") or []
        pinned = {i: value for i, value in enumerate(items) if value in pinned_values}
        movable = [value for value in items if value not in pinned_values]
        seed = question_data.get("item_randomization_seed")
        rng = random.Random(seed) if seed is not None else random
        shuffled = rng.sample(movable, len(movable))
        result = [None] * len(items)
        for index, value in pinned.items():
            result[index] = value
        movable_iter = iter(shuffled)
        for index, value in enumerate(result):
            if value is None:
                result[index] = next(movable_iter)
        return result

    def _get_items_from_template(self, template_string: str) -> list:
        """
        Helper method to extract items from a template string.

        Args:
            template_string (str): Template string like "{{ q1.answer }}" or
                "{{ scenario.items }}"

        Returns:
            list: List of items or default placeholders if not found
        """
        if not template_string:
            return self._get_default_items()

        # Render the template first and take the value it produces. A prior answer is
        # not always a list even when it names one: a QuestionCompute answers with the
        # rendered text of its expression, so a matrix whose rows come from one is
        # handed "['Alpha', 'Beta']" where it needs ['Alpha', 'Beta']. Without this the
        # lookup below finds a string, treats it as no answer at all, and the question
        # is served "<< Item 1 - Placeholder >>" rows.
        #
        # QuestionOptionProcessor resolves its own templates this way and for the same
        # reason; a matrix validates its rows through the descriptor it uses for its
        # options, so the two are worth keeping in step.
        try:
            rendered_items = self._render_template_to_native_value(template_string)
            if isinstance(rendered_items, list):
                return rendered_items
            if isinstance(rendered_items, tuple):
                return list(rendered_items)
            if isinstance(rendered_items, str):
                try:
                    parsed_items = literal_eval(rendered_items)
                except (SyntaxError, ValueError):
                    parsed_items = None
                if isinstance(parsed_items, list):
                    return parsed_items
                if isinstance(parsed_items, tuple):
                    return list(parsed_items)
        except Exception:
            # Fall back to the key-lookup path below.
            pass

        raw_item_key = self._parse_template_variable(template_string)

        source_type = None

        if isinstance(raw_item_key, tuple):
            if raw_item_key[0] == "scenario":
                source_type = "scenario"
                item_key = raw_item_key[1:]
            else:
                source_type = "prior_answers"
                item_key = (raw_item_key[0],)
        else:
            item_key = (raw_item_key,)

        if source_type == "scenario":
            scenario_items = self._get_items_from_scenario(self.scenario, item_key)
            if scenario_items:
                return scenario_items

        if source_type == "prior_answers":
            prior_answer_items = self._get_items_from_prior_answers(
                self.prior_answers_dict, item_key
            )
            if prior_answer_items:
                return prior_answer_items

        return self._get_default_items()


if __name__ == "__main__":
    import doctest

    doctest.testmod()
