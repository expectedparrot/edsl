import functools
from typing import List
from .utilities import Missing
from collections import Counter


class QuestionStatsModule:
    def __init__(self, input_data):
        self.input_data = input_data
    
    def question_statistics(self, question_name: str) -> "QuestionStats":
        """Return statistics for a question."""
        return self.input_data.QuestionStats(**self._compute_question_statistics(question_name))

    def _compute_question_statistics(self, question_name: str) -> dict:
        """
        Return a dictionary of statistics for a question.

        >>> from .input_data import InputDataABC
        >>> id = InputDataABC.example()
        >>> id.question_stats._compute_question_statistics('morning')
        {'num_responses': 2, 'num_unique_responses': 2, 'missing': 0, 'unique_responses': ..., 'frac_numerical': 0.0, 'top_5': [('1', 1), ('4', 1)], 'frac_obs_from_top_5': 1.0}
        """
        idx = self.input_data.question_names.index(question_name)
        return {attr: getattr(self, attr)[idx] for attr in self.input_data.question_attributes}

    @property
    def num_responses(self) -> List[int]:
        """
        Return the number of responses for each question.

        >>> from .input_data import InputDataABC
        >>> id = InputDataABC.example()
        >>> id.num_responses
        [2, 2]
        """
        return self.compute_num_responses()

    @functools.lru_cache(maxsize=1)
    def compute_num_responses(self):
        return [len(responses) for responses in self.input_data.raw_data]

    @property
    def num_unique_responses(self) -> List[int]:
        """
        The number of unique responses for each question.

        >>> from .input_data import InputDataABC
        >>> id = InputDataABC.example()
        >>> id.num_unique_responses
        [2, 2]
        """
        return self.compute_num_unique_responses()

    @functools.lru_cache(maxsize=1)
    def compute_num_unique_responses(self):
        return [len(set(responses)) for responses in self.input_data.raw_data]

    @property
    def missing(self) -> List[int]:
        """The number of observations that are missing.

        >>> from .input_data import InputDataABC
        >>> input_data = InputDataABC.example(raw_data = [[1,2,Missing().value()]], question_texts = ['A question'])
        >>> input_data.missing
        [1]

        """
        return self.compute_missing()

    @functools.lru_cache(maxsize=1)
    def compute_missing(self):
        return [sum([1 for x in v if x == Missing().value()]) for v in self.input_data.raw_data]

    @property
    def frac_numerical(self) -> List[float]:
        """
        The fraction of responses that are numerical for each question.

        >>> from .input_data import InputDataABC
        >>> input_data = InputDataABC.example(raw_data = [[1,2,"Poop", 3]], question_texts = ['A question'])
        >>> input_data.frac_numerical
        [0.75]
        """
        return self.compute_frac_numerical()

    @functools.lru_cache(maxsize=1)
    def compute_frac_numerical(self):
        return [
            sum([1 for x in v if isinstance(x, (int, float))]) / len(v)
            for v in self.input_data.raw_data
        ]

    @functools.lru_cache(maxsize=1)
    def top_k(self, k: int) -> List[List[tuple]]:
        """
        >>> from .input_data import InputDataABC
        >>> input_data = InputDataABC.example(raw_data = [[1,1,1,1,1,2]], question_texts = ['A question'])
        >>> input_data.question_stats.top_k(1)
        [[(1, 5)]]
        >>> input_data.question_stats.top_k(2)
        [[(1, 5), (2, 1)]]
        """
        return [Counter(value).most_common(k) for value in self.input_data.raw_data]

    @functools.lru_cache(maxsize=1)
    def frac_obs_from_top_k(self, k):
        """
        Return the fraction of observations that are in the top k for each question.

        >>> from .input_data import InputDataABC
        >>> input_data = InputDataABC.example(raw_data = [[1,1,1,1,1,1,1,1,2, 3]], question_names = ['a'])
        >>> input_data.question_stats.frac_obs_from_top_k(1)
        [0.8]
        """
        return [
            round(
                sum([x[1] for x in Counter(value).most_common(k) if x[0] != "missing"])
                / len(value),
                2,
            )
            for value in self.input_data.raw_data
        ]

    @property
    def frac_obs_from_top_5(self):
        """The fraction of observations that are in the top 5 for each question."""
        return self.frac_obs_from_top_k(5)

    @property
    def top_5(self):
        """The top 5 responses for each question."""
        return self.top_k(5)

    @property
    def unique_responses(self) -> List[List[str]]:
        """Return a list of unique responses for each question.

        >>> from .input_data import InputDataABC
        >>> id = InputDataABC.example()
        >>> id.unique_responses
        [..., ...]
        """
        return self.compute_unique_responses()

    @functools.lru_cache(maxsize=1)
    def compute_unique_responses(self):
        return [
            list(set(self.filter_missing(responses))) for responses in self.input_data.raw_data
        ]

    @staticmethod
    def filter_missing(responses) -> List[str]:
        """Return a list of responses with missing values removed."""
        return [
            v
            for v in responses
            if v != Missing().value() and v != "missing" and v != ""
        ]

    def unique_responses_more_than_k(self, k, remove_missing=True) -> List[List[str]]:
        """Return a list of unique responses that occur more than k times for each question.

        >>> from .input_data import InputDataABC
        >>> id = InputDataABC.example()
        >>> id.unique_responses_more_than_k(1)
        [[...], [...]]

        """
        counters = [Counter(responses) for responses in self.input_data.raw_data]
        new_counters = []
        for question in counters:
            top_options = []
            for option, count in question.items():
                if count > k and (option != "missing" or not remove_missing):
                    top_options.append(option)
            new_counters.append(top_options)
        return new_counters


if __name__ == "__main__":
    from .input_data import InputDataABC
    import doctest

    doctest.testmod(optionflags=doctest.ELLIPSIS)
