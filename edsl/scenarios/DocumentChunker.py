from __future__ import annotations
from typing import Optional, Generator, TYPE_CHECKING
import copy
import hashlib

if TYPE_CHECKING:
    from edsl.scenarios.Scenario import Scenario
    from edsl.scenarios.ScenarioList import ScenarioList


class DocumentChunker:

    def __init__(self, scenario: "Scenario"):
        self.scenario = scenario

    @staticmethod
    def _line_chunks(text, num_lines: int) -> Generator[str, None, None]:
        """Split a text into chunks of a given size.

        :param text: The text to split.
        :param num_lines: The number of lines in each chunk.

        Example:

        >>> list(Scenario._line_chunks("This is a test.\\nThis is a test. This is a test.", 1))
        ['This is a test.', 'This is a test. This is a test.']
        """
        lines = text.split("\n")
        for i in range(0, len(lines), num_lines):
            chunk = "\n".join(lines[i : i + num_lines])
            yield chunk

    @staticmethod
    def _word_chunks(text, num_words: int) -> Generator[str, None, None]:
        """Split a text into chunks of a given size.

        :param text: The text to split.
        :param num_words: The number of words in each chunk.

        Example:

        >>> list(Scenario._word_chunks("This is a test.", 2))
        ['This is', 'a test.']
        """
        words = text.split()
        for i in range(0, len(words), num_words):
            chunk = " ".join(words[i : i + num_words])
            yield chunk

    def chunk(
        self,
        field,
        num_words: Optional[int] = None,
        num_lines: Optional[int] = None,
        include_original=False,
        hash_original=False,
    ) -> ScenarioList:
        """Split a field into chunks of a given size.

        :param field: The field to split.
        :param num_words: The number of words in each chunk.
        :param num_lines: The number of lines in each chunk.
        :param include_original: Whether to include the original field in the new scenarios.
        :param hash_original: Whether to hash the original field in the new scenarios.

        If you specify `include_original=True`, the original field will be included in the new scenarios with an "_original" suffix.

        Either `num_words` or `num_lines` must be specified, but not both.

        The `hash_original` parameter is useful if you do not want to store the original text, but still want a unique identifier for it.

        Example:

        >>> s = Scenario({"text": "This is a test.\\nThis is a test.\\n\\nThis is a test."})
        >>> s.chunk("text", num_lines = 1)
        ScenarioList([Scenario({'text': 'This is a test.', 'text_chunk': 0}), Scenario({'text': 'This is a test.', 'text_chunk': 1}), Scenario({'text': '', 'text_chunk': 2}), Scenario({'text': 'This is a test.', 'text_chunk': 3})])

        >>> s.chunk("text", num_words = 2)
        ScenarioList([Scenario({'text': 'This is', 'text_chunk': 0}), Scenario({'text': 'a test.', 'text_chunk': 1}), Scenario({'text': 'This is', 'text_chunk': 2}), Scenario({'text': 'a test.', 'text_chunk': 3}), Scenario({'text': 'This is', 'text_chunk': 4}), Scenario({'text': 'a test.', 'text_chunk': 5})])

        >>> s = Scenario({"text": "Hello World"})
        >>> s.chunk("text", num_words = 1, include_original = True)
        ScenarioList([Scenario({'text': 'Hello', 'text_chunk': 0, 'text_original': 'Hello World'}), Scenario({'text': 'World', 'text_chunk': 1, 'text_original': 'Hello World'})])

        >>> s = Scenario({"text": "Hello World"})
        >>> s.chunk("text", num_words = 1, include_original = True, hash_original = True)
        ScenarioList([Scenario({'text': 'Hello', 'text_chunk': 0, 'text_original': 'b10a8db164e0754105b7a99be72e3fe5'}), Scenario({'text': 'World', 'text_chunk': 1, 'text_original': 'b10a8db164e0754105b7a99be72e3fe5'})])

        >>> s.chunk("text")
        Traceback (most recent call last):
        ...
        ValueError: You must specify either num_words or num_lines.

        >>> s.chunk("text", num_words = 1, num_lines = 1)
        Traceback (most recent call last):
        ...
        ValueError: You must specify either num_words or num_lines, but not both.
        """
        from edsl.scenarios.ScenarioList import ScenarioList

        if num_words is not None:
            chunks = list(self._word_chunks(self.scenario[field], num_words))

        if num_lines is not None:
            chunks = list(self._line_chunks(self.scenario[field], num_lines))

        if num_words is None and num_lines is None:
            raise ValueError("You must specify either num_words or num_lines.")

        if num_words is not None and num_lines is not None:
            raise ValueError(
                "You must specify either num_words or num_lines, but not both."
            )

        scenarios = []
        for i, chunk in enumerate(chunks):
            new_scenario = copy.deepcopy(self.scenario)
            new_scenario[field] = chunk
            new_scenario[field + "_chunk"] = i
            if include_original:
                if hash_original:
                    new_scenario[field + "_original"] = hashlib.md5(
                        self.scenario[field].encode()
                    ).hexdigest()
                else:
                    new_scenario[field + "_original"] = self.scenario[field]
            scenarios.append(new_scenario)
        return ScenarioList(scenarios)
