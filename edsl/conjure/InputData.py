from abc import ABC, abstractmethod
from typing import Dict, Callable, Optional, List
from collections import namedtuple, Counter
import pandas as pd

from edsl import ScenarioList
from edsl.conjure.SurveyResponses import SurveyResponses
from edsl.conjure.naming_utilities import sanitize_string
from edsl.conjure.utilities import convert_value, Missing

class InputDataMixinQuestionStats:

    def _question_statistics(self, question_name: str) -> dict:
        """
        Return a dictionary of statistics for a question.

        >>> id = InputData.example()
        >>> id._question_statistics('morning')
        {'num_responses': 2, 'num_unique_responses': 2, 'missing': 0, 'unique_responses': ..., 'frac_numerical': 0.0, 'top_5': [('1', 1), ('4', 1)], 'frac_obs_from_top_5': 1.0}
        """
        idx = self.question_names.index(question_name)
        return {attr: getattr(self, attr)[idx] for attr in self.question_attributes}

    def question_statistics(self, question_name:str) -> "QuestionStats":
        qt = self.QuestionStats(**self._question_statistics(question_name))
        return qt

    @property
    def num_responses(self) -> List[int]:
        """
        Return the number of responses for each question.

        >>> id = InputData.example()
        >>> id.num_responses
        [2, 2]
        """
        return [len(responses) for _, responses in self.raw_data.items()]

    @property
    def num_unique_responses(self) -> List[int]:
        """
        Return the number of unique responses for each question.

        >>> id = InputData.example()
        >>> id.num_unique_responses
        [2, 2]
        """
        return [len(set(responses)) for _, responses in self.raw_data.items()]

    @property
    def missing(self) -> List[int]:
        """
        >>> input_data = InputData.example(raw_data = {'A question':[1,2,Missing().value()]}, question_texts = ['A question'])
        >>> input_data.missing
        [1]
        
        """
        return [
            sum([1 for x in v if x == Missing().value()])
            for k, v in self.raw_data.items()
        ]

    @property
    def frac_numerical(self) -> List[float]:
        """
        >>> input_data = InputData.example(raw_data = {'A question':[1,2,"Poop", 3]}, question_texts = ['A question'])
        >>> input_data.frac_numerical
        [0.75]
        """
        return [
            sum([1 for x in v if isinstance(x, (int, float))]) / len(v)
            for k, v in self.raw_data.items()
        ]

    def top_k(self, k:int) -> List[List[tuple]]:
        """
        >>> input_data = InputData.example(raw_data = {'A question':[1,1,1,1,1,2]}, question_texts = ['A question'])
        >>> input_data.top_k(1)
        [[(1, 5)]]
        >>> input_data.top_k(2)
        [[(1, 5), (2, 1)]]
        """
        return [Counter(value).most_common(k) for _, value in self.raw_data.items()]

    def frac_obs_from_top_k(self, k):
        """
        >>> input_data = InputData.example(raw_data = {'A question':[1,1,1,1,1,1,1,1,2, 3]}, question_texts = ['A question'])
        >>> input_data.frac_obs_from_top_k(1)
        [0.8]
        """
        return [
            round(
                sum([x[1] for x in Counter(value).most_common(k) if x[0] != "missing"])
                / len(value),
                2,
            )
            for key, value in self.raw_data.items()
        ]

    @property
    def frac_obs_from_top_5(self):
        return self.frac_obs_from_top_k(5)

    @property
    def top_5(self):
        return self.top_k(5)


class InputData(ABC, InputDataMixinQuestionStats):
    """A class to represent the input data for a survey.

    This class can take inputs that will be used or it will infer them.
    Each of the inferred values can be overridden by passing them in.
    """

    NUM_UNIQUE_THRESHOLD = 15
    FRAC_NUMERICAL_THRESHOLD = 0.8
    MULTIPLE_CHOICE_OTHER_THRESHOLD = 0.5
    OTHER_STRING = "Other:"

    question_attributes = [
        "num_responses",
        "num_unique_responses",
        "missing",
        "unique_responses",
        "frac_numerical",
        "top_5",
        "frac_obs_from_top_5",
    ]
    QuestionStats = namedtuple("QuestionStats", question_attributes)

    def __init__(
        self,
        datafile_name: str,
        config: dict,
        naming_function: Optional[Callable] = sanitize_string,
        raw_data: Optional[Dict] = None,
        question_names: Optional[List[str]] = None,
        question_texts: Optional[List[str]] = None,
        answer_codebook: Optional[Dict] = None,
        question_types: Optional[List[str]] = None,
        question_options: Optional[List] = None,
    ):
        """Initialize the InputData object.

        :param datafile_name: The name of the file containing the data.
        :param config: The configuration parameters for reading the data.
        :param raw_data: The raw data in the form of a dictionary.
        :param question_names: The names of the questions.
        :param question_texts: The text of the questions.
        :param answer_codebook: The codebook for the answers.
        :param question_types: The types of the questions.
        :param question_options: The options for the questions.

        >>> id = InputData.example(question_names = ['a','b'], answer_codebook = {'a': {'1':'yes', '2':'no'}, 'b': {'1':'yes', '2':'no'}})

        >>> id = InputData.example(question_names = ['a','b'], answer_codebook = {'a': {'1':'yes', '2':'no'}, 'c': {'1':'yes', '2':'no'}})
        Traceback (most recent call last):
        ...
        Exception: The keys of the answer_codebook must match the question_names.
        """

        self.datafile_name = datafile_name
        self.config = config
        self.naming_function = naming_function

        if answer_codebook is not None and question_names is not None:
            if set(answer_codebook.keys()) != set(question_names):
                raise Exception("The keys of the answer_codebook must match the question_names.")
            
        if question_names is not None and question_texts is not None:
            if len(question_names) != len(question_texts):
                raise Exception("The question_names and question_texts must have the same length.")

        # TO BE INFERRED
        self.question_texts = question_texts
        self.question_names = question_names
        self.answer_codebook = answer_codebook
        self.raw_data = raw_data
        self.question_types = question_types
        self.question_options = question_options

    @abstractmethod
    def get_question_texts(self) -> List[str]:
        """Get the text of the questions"""
        raise NotImplementedError

    @abstractmethod
    def get_raw_data(self) -> SurveyResponses:
        """Returns a dataframe of responses by reading the datafile_name."""
        raise NotImplementedError

    def to_dict(self):
        return {
            "datafile_name": self.datafile_name,
            "config": self.config,
            "raw_data": self.raw_data,
            "question_names": self.question_names,
            "question_texts": self.question_texts,
            "answer_codebook": self.answer_codebook,
            "question_types": self.question_types,
        }
    
    @classmethod
    def from_dict(cls, d: Dict):
        return cls(**d)

    def print(self):
        sl = (
            ScenarioList.from_list("question_name", self.question_names)
            .add_list("question_text", self.question_texts)
            .add_list("inferred_question_type", self.question_types)
            .add_list("num_responses", self.num_responses)
            .add_list("num_unique_responses", self.num_unique_responses)
            .add_list("missing", self.missing)
            .add_list("frac_numerical", self.frac_numerical)
            .add_list("top_5_items", self.top_k(5))
            .add_list("frac_obs_from_top_5", self.frac_obs_from_top_k(5))
        )
        sl.print()

    def print(self):
        sl = (
            ScenarioList.from_list("question_name", self.question_names)
            .add_list("question_text", self.question_texts)
            .add_list("inferred_question_type", self.question_types)
            .add_list("question_options", self.question_options)
        )
        sl.print()


    @property
    def question_types(self):
        return self._question_types

    @question_types.setter
    def question_types(self, value):
        if value is None:
            value = [self._infer_question_type(qn) for qn in self.question_names]
        self._question_types = value

    def _infer_question_type(self, question_name) -> str:

        qt = self.question_statistics(question_name)
        if qt.num_unique_responses > self.NUM_UNIQUE_THRESHOLD:
            if qt.frac_numerical > self.FRAC_NUMERICAL_THRESHOLD:
                return "numerical"
            if qt.frac_obs_from_top_5 > self.MULTIPLE_CHOICE_OTHER_THRESHOLD:
                return "multiple_choice_with_other"
            return "free_text"
        else:
            return "multiple_choice"

    @property
    def question_options(self):
        return self._question_options

    @question_options.setter
    def question_options(self, value):
        if value is None:
            value = [self._get_question_options(qn) for qn in self.question_names]
        self._question_options = value

    def _get_question_options(self, question_name):
        qt = self.question_statistics(question_name)
        idx = self.question_names.index(question_name)
        question_type = self.question_types[idx]
        if question_type == "multiple_choice":
            return qt.unique_responses
        else:
            if question_type == "multiple_choice_with_other":
                return self.unique_responses_more_than_k(2)[
                    self.question_names.index(question_name)
                ] + [self.OTHER_STRING]
            else:
                return None


    @staticmethod
    def filter_missing(responses) -> List[str]:
        return [
            v for v in responses if v != Missing().value() and v != "missing" and v != ""
        ]

    def order_options(self) -> None:
        """Order the options for multiple choice questions using an LLM."""
        from edsl import QuestionList, ScenarioList
        import textwrap

        scenarios = (
            ScenarioList.from_list("example_question_name", self.question_names)
            .add_list("example_question_text", self.question_texts)
            .add_list("example_question_type", self.question_types)
            .add_list("example_question_options", self.question_options)
        ).filter(
            'example_question_type == "multiple_choice" or example_question_type == "multiple_choice_with_other"'
        )

        question = QuestionList(
            question_text=textwrap.dedent(
                """\
            We have a survey question: `{{ example_question_text }}`.
            
            The survey had following options: '{{ example_question_options }}'.
            The options might be out of order. Please put them in the correct order.
            If there is not natural order, just put then in order they were presented.
            """
            ),
            question_name="ordering",
        )
        proposed_ordering = question.by(scenarios).run()
        d = dict(
            proposed_ordering.select("example_question_name", "ordering").to_list()
        )
        self._question_options = [d.get(qn, None) for qn in self.question_names]
        

    @property
    def unique_responses(self) -> List[List[str]]:
        """Return a list of unique responses for each question.

        >>> id = InputData.example()
        >>> id.unique_responses
        [..., ...]
        """
        return [list(set(self.filter_missing(v))) for k, v in self.raw_data.items()]

    def unique_responses_more_than_k(self, k, remove_missing=True):
        counters = [Counter(value) for _, value in self.raw_data.items()]
        new_counters = []
        for question in counters:
            top_options = []
            for option, count in question.items():
                if count > k and (option != "missing" or not remove_missing):
                    top_options.append(option)
            new_counters.append(top_options)
        return new_counters

    @property
    def raw_data(self):
        """

        >>> id = InputData.example()
        >>> id.raw_data
        {'how are you doing this morning?': ['1', '4'], 'how are you feeling?': ['3', '6']}


        >>> id = InputData.example(question_texts = ["A question"], question_names = ['a'], raw_data = {'A question':[1,2]})
        >>> id.raw_data
        {'A question': [1, 2]}
        """
        return self._raw_data

    @raw_data.setter
    def raw_data(self, value):
        """
        """
        if value is None:
            value = self.get_raw_data()                
        self._raw_data = value

    @property
    def question_texts(self) -> List[str]:
        """
        Return a list of question texts.

        >>> id = InputData.example()
        >>> id.question_texts
        ['how are you doing this morning?', 'how are you feeling?']
        """
        return self._question_texts

    @question_texts.setter
    def question_texts(self, value):
        if value is None:
            value = self.get_question_texts()
        self._question_texts = value

    @property
    def question_names(self) -> List[str]:
        """
        Return a list of question names. 

        >>> id = InputData.example()
        >>> id.question_names
        ['morning', 'feeling']
        
        We can pass question names instead: 

        >>> id = InputData.example(question_names = ['a','b'])
        >>> id.question_names
        ['a', 'b']
        
        """
        return self._question_names

    @question_names.setter
    def question_names(self, value):
        if value is None:
            value = self._get_question_names()
        self._question_names = value

    def _get_question_names(self) -> List[str]:
        """Return the question names.
        
        Here we pass in a custom naming function, but it does not produce unique names.
        The names are then modified to be unique.

        >>> id = InputData.example(naming_function = lambda x: 'a')
        >>> id._get_question_names()
        ['a_0', 'a_1']
        """
        new_names = [self.naming_function(q) for q in self.question_texts]
        if len(new_names) != len(set(new_names)):
            new_names = [f"{q}_{i}" for i, q in enumerate(new_names)]
        return new_names
    
    @property
    def names_to_texts(self) -> dict:
        """
        Return a dictionary of question names to question texts.

        >>> id = InputData.example()
        >>> id.names_to_texts
        {'morning': 'how are you doing this morning?', 'feeling': 'how are you feeling?'}
        """
        return {n: t for n, t in zip(self.question_names, self.question_texts)}

    @property
    def texts_to_names(self):
        """Return a dictionary of question texts to question names.
        
        >>> id = InputData.example()
        >>> id.texts_to_names
        {'how are you doing this morning?': 'morning', 'how are you feeling?': 'feeling'}
        
        """
        return {t: n for n, t in self.names_to_texts.items()}

    
    @classmethod
    def example(cls, **kwargs):
        class InputDataExample(InputData):

            def get_question_texts(self) -> List[str]:
                """Get the text of the questions"""
                return ["how are you doing this morning?", "how are you feeling?"]

            def get_raw_data(self) -> SurveyResponses:
                """Returns a dataframe of responses by reading the datafile_name."""
                return SurveyResponses({"how are you doing this morning?": ["1", "4"], 
                                        "how are you feeling?": ["3", "6"]})

        return InputDataExample("notneeded.csv", config = {}, **kwargs)


class InputDataCSV(InputData):

    def get_df(self) -> pd.DataFrame:
        df = pd.read_csv(self.datafile_name, skiprows=self.config["skiprows"])
        df.fillna("", inplace=True)
        df = df.astype(str)
        return df

    def get_raw_data(self) -> SurveyResponses:
        df = self.get_df()
        data = {
            k: [convert_value(obs) for obs in v]
            for k, v in df.to_dict(orient="list").items()
        }
        return SurveyResponses(data)

    def get_question_texts(self):
        return list(self.get_df().columns)


if __name__ == "__main__":
    import doctest
    doctest.testmod(optionflags=doctest.ELLIPSIS)
    #doctest.testmod()
    # config = {"skiprows": 1}
    # # sloan = InputDataCSV("sloan_search.csv", config = {'skiprows': [0, 2]})

    # # id2 = InputDataCSV.from_dict(id.to_dict())
    if False:
        lenny = InputDataCSV("lenny.csv", config={"skiprows": None})
        lenny.print()
        lenny.order_options()
        lenny.print()

