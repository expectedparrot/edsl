from abc import ABC, abstractmethod
from typing import Dict, Callable, Optional, List
from collections import namedtuple, Counter
import pandas as pd

from edsl import ScenarioList
from edsl.conjure.SurveyResponses import SurveyResponses
from edsl.conjure.naming_utilities import sanitize_string
from edsl.conjure.utilities import convert_value, Missing

from dataclasses import dataclass, field
from typing import List

import functools
    
@dataclass
class RawQuestion:
    question_type: str
    question_name: str
    question_text: str
    responses: List[str] = field(default_factory=list)
    question_options: Optional[List[str]] = None

    def __post_init__(self):
        self.responses = [convert_value(r) for r in self.responses]

    def to_question(self):
        # TODO: Remove this once we have a better way to handle multiple_choice_with_other
        if self.question_type == "multiple_choice_with_other":
            question_type = "multiple_choice"
        else:
            question_type = self.question_type
        from edsl import Question
        d = {k:v for k,v in {
            "question_type": question_type,
            "question_name": self.question_name,
            "question_text": self.question_text,
            "responses": self.responses,
            "question_options": self.question_options,
        }.items() if v is not None and k != "responses"}
        return Question(**d)




class InputDataMixinQuestionStats:

    def _question_statistics(self, question_name: str) -> dict:
        """
        Return a dictionary of statistics for a question.

        >>> id = InputData.example()
        >>> id._question_statistics('morning')
        {'num_responses': 2, 'num_unique_responses': 2, 'missing': 0, 'unique_responses': ..., 'frac_numerical': 0.0, 'top_5': [('1', 1), ('4', 1)], 'frac_obs_from_top_5': 1.0}
        """
        idx = self.question_names.index(question_name)
        stats =  {attr: getattr(self, attr)[idx] for attr in self.question_attributes}

        return stats

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
        return self.compute_num_responses()
    
    @functools.lru_cache(maxsize=1)
    def compute_num_responses(self):
        return [len(responses) for responses in self.raw_data]

    @property
    def num_unique_responses(self) -> List[int]:
        """
        Return the number of unique responses for each question.

        >>> id = InputData.example()
        >>> id.num_unique_responses
        [2, 2]
        """
        return self.compute_num_unique_responses()
    
    @functools.lru_cache(maxsize=1)
    def compute_num_unique_responses(self):
        return [len(set(responses)) for responses in self.raw_data]

    @property
    def missing(self) -> List[int]:
        """
        >>> input_data = InputData.example(raw_data = [[1,2,Missing().value()]], question_texts = ['A question'])
        >>> input_data.missing
        [1]
        
        """
        return self.compute_missing()
    
    @functools.lru_cache(maxsize=1)
    def compute_missing(self):
        return [
            sum([1 for x in v if x == Missing().value()])
            for v in self.raw_data
        ]

    @property
    def frac_numerical(self) -> List[float]:
        """
        >>> input_data = InputData.example(raw_data = [[1,2,"Poop", 3]], question_texts = ['A question'])
        >>> input_data.frac_numerical
        [0.75]
        """
        return self.compute_frac_numerical()
    
    @functools.lru_cache(maxsize=1)
    def compute_frac_numerical(self):
        return [
            sum([1 for x in v if isinstance(x, (int, float))]) / len(v)
            for v in self.raw_data
        ]

    @functools.lru_cache(maxsize=1)
    def top_k(self, k:int) -> List[List[tuple]]:
        """
        >>> input_data = InputData.example(raw_data = [[1,1,1,1,1,2]], question_texts = ['A question'])
        >>> input_data.top_k(1)
        [[(1, 5)]]
        >>> input_data.top_k(2)
        [[(1, 5), (2, 1)]]
        """
        return [Counter(value).most_common(k) for value in self.raw_data]

    @functools.lru_cache(maxsize=1)
    def frac_obs_from_top_k(self, k):
        """
        >>> input_data = InputData.example(raw_data = [[1,1,1,1,1,1,1,1,2, 3]], question_names = ['a'])
        >>> input_data.frac_obs_from_top_k(1)
        [0.8]
        """
        return [
            round(
                sum([x[1] for x in Counter(value).most_common(k) if x[0] != "missing"])
                / len(value),
                2,
            )
            for value in self.raw_data
        ]

    @property
    def frac_obs_from_top_5(self):
        return self.frac_obs_from_top_k(5)

    @property
    def top_5(self):
        return self.top_k(5)
    
    @property
    def unique_responses(self) -> List[List[str]]:
        """Return a list of unique responses for each question.

        >>> id = InputData.example()
        >>> id.unique_responses
        [..., ...]
        """
        return self.compute_unique_responses()
         
    @staticmethod
    def filter_missing(responses) -> List[str]:
        return [
            v for v in responses if v != Missing().value() and v != "missing" and v != ""
        ]

    @functools.lru_cache(maxsize=1)
    def compute_unique_responses(self):
        return [list(set(self.filter_missing(responses))) for responses in self.raw_data]

    def unique_responses_more_than_k(self, k, remove_missing=True):
        counters = [Counter(responses) for responses in self.raw_data]
        new_counters = []
        for question in counters:
            top_options = []
            for option, count in question.items():
                if count > k and (option != "missing" or not remove_missing):
                    top_options.append(option)
            new_counters.append(top_options)
        return new_counters


class AgentConstructionMixin:

    def agent(self, index):
        """Return an agent constructed from the data."""
        from edsl import Agent
        responses = [responses[index] for responses in self.raw_data]
        traits = {qn: r for qn, r in zip(self.question_names, responses)}
        
        def construct_answer_dict_function(traits: dict) -> Callable:
            def func(self, question: 'QuestionBase', scenario=None):
                return traits.get(question.question_name, None)

            return func
        a = Agent(traits=traits)
        a.add_direct_question_answering_method(construct_answer_dict_function(traits))
        return a
    
    def agents(self):
        for i in range(len(self.raw_data[0])):
            yield self.agent(i)

    def results(self):
        return self.survey().by(list(self.agents())).run()


class QuestionOptionMixin:

    @property
    def question_options(self):
        if not hasattr(self, "_question_options"):
            self.question_options = None
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
        

            
class QuestionTypeMixin:

    @property
    def question_types(self):
        if not hasattr(self, "_question_types"):
            self.question_types = None
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


class InputData(ABC, InputDataMixinQuestionStats, AgentConstructionMixin, QuestionOptionMixin, QuestionTypeMixin):
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
        raw_data: Optional[List] = None,
        question_names: Optional[List[str]] = None,
        question_texts: Optional[List[str]] = None,
        answer_codebook: Optional[Dict] = None,
        question_types: Optional[List[str]] = None,
        question_options: Optional[List] = None,
        auto_infer: bool = True,
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
    def get_raw_data(self) -> List[List[str]]:
        """Returns a dataframe of responses by reading the datafile_name."""
        raise NotImplementedError
    
    @abstractmethod
    def get_question_names(self) -> List[str]:
        """Get the names of the questions"""
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
        if not hasattr(self, "_question_names"):
            self.question_names = None
        return self._question_names

    @question_names.setter
    def question_names(self, value):
        if value is None:
            value = self.get_question_names()
            if len(set(value)) != len(value):
                raise ValueError("Question names must be unique.")
        self._question_names = value

    @property
    def question_texts(self) -> List[str]:
        """
        Return a list of question texts.

        >>> id = InputData.example()
        >>> id.question_texts
        ['how are you doing this morning?', 'how are you feeling?']
        """
        if not hasattr(self, "_question_texts"):
            self.question_texts = None
        return self._question_texts

    @question_texts.setter
    def question_texts(self, value):
        if value is None:
            value = self.get_question_texts()
        self._question_texts = value

    @property
    def raw_data(self):
        """

        >>> id = InputData.example()
        >>> id.raw_data
        [['1', '4'], ['3', '6']]

        >>> id = InputData.example(question_texts = ["A question"], question_names = ['a'], raw_data = {'A question':[1,2]})
        >>> id.raw_data
        {'A question': [1, 2]}
        """
        if not hasattr(self, "_raw_data"):
            self.raw_data = None
        return self._raw_data

    @raw_data.setter
    def raw_data(self, value):
        """
        """
        if value is None:
            value = self.get_raw_data()                
        self._raw_data = value

    
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
    
    def raw_questions(self):
        for qn in self.question_names:
            idx = self.question_names.index(qn)
            yield RawQuestion(
                question_type = self.question_types[idx],
                question_name = qn,
                question_text = self.question_texts[idx],
                responses = self.raw_data[idx],
                question_options = self.question_options[idx]
            )
    
    def questions(self):
        for rq in self.raw_questions():
            yield rq.to_question()

    def survey(self):
        from edsl import Survey
        return Survey(list(self.questions()))
    
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


    @classmethod
    def example(cls, **kwargs):
        class InputDataExample(InputData):

            def get_question_texts(self) -> List[str]:
                """Get the text of the questions"""
                return ["how are you doing this morning?", "how are you feeling?"]

            def get_raw_data(self) -> SurveyResponses:
                """Returns a dataframe of responses by reading the datafile_name."""
                return [["1", "4"], ["3", "6"]]
            
            def get_question_names(self):
                new_names = [self.naming_function(q) for q in self.question_texts]
                if len(new_names) != len(set(new_names)):
                    new_names = [f"{q}_{i}" for i, q in enumerate(new_names)]
                return new_names

        return InputDataExample("notneeded.csv", config = {}, **kwargs)


class InputDataCSV(InputData):

    def __init__(self, datafile_name: str, config: dict, **kwargs):
        super().__init__(datafile_name, config, **kwargs)

    def get_df(self) -> pd.DataFrame:
        if not hasattr(self, "_df"):
            self._df = pd.read_csv(self.datafile_name, skiprows=self.config["skiprows"])
            self._df.fillna("", inplace=True)
            self._df = self._df.astype(str)
        return self._df

    def get_raw_data(self) -> List[List[str]]:
        data = [
            [convert_value(obs) for obs in v]
            for k, v in self.get_df().to_dict(orient="list").items()
        ]
        return data 

    def get_question_texts(self):
        return list(self.get_df().columns)
    
    def get_question_names(self):
        new_names = [self.naming_function(q) for q in self.question_texts]
        if len(new_names) != len(set(new_names)):
            new_names = [f"{q}_{i}" for i, q in enumerate(new_names)]
        return new_names

class InputDataSPSS(InputData):

    def _parse(self) -> None:
        from pyreadstat import read_sav
        df, meta = read_sav(self.datafile_name)
        df.fillna("", inplace=True)
        df = df.astype(str)
        self._df = df
        self._meta = meta

    def get_df(self) -> pd.DataFrame:
        if not hasattr(self, "_df"):
            self._parse()
        return self._df
    
    def get_raw_data(self) -> List[List[str]]:
        df = self.get_df()
        data = [
            [convert_value(obs) for obs in v]
            for k, v in df.to_dict(orient="list").items()
        ]
        return data 

    def get_question_texts(self):
        if not hasattr(self, "_meta"):
            self._parse()
        return [self._meta.column_names_to_labels[qn] for qn in self.question_names]
    
    def get_question_names(self):
        new_names = [self.naming_function(q) for q in self.question_texts]
        if len(new_names) != len(set(new_names)):
            new_names = [f"{q}_{i}" for i, q in enumerate(new_names)]
        return new_names
    
class InputDataStata(InputData):

    def _parse(self) -> None:
        from pyreadstat import read_dta
        df, meta = read_dta(self.datafile_name)
        df.fillna("", inplace=True)
        df = df.astype(str)
        self._df = df
        self._meta = meta

    def get_df(self) -> pd.DataFrame:
        if not hasattr(self, "_df"):
            self._parse()
        return self._df
    
    def get_raw_data(self) -> List[List[str]]:
        df = self.get_df()
        data = [
            [convert_value(obs) for obs in v]
            for k, v in df.to_dict(orient="list").items()
        ]
        return data 

    def get_question_texts(self):
        if not hasattr(self, "_meta"):
            self._parse()
        return [self._meta.column_names_to_labels[qn] for qn in self.question_names]
    
    def get_question_names(self):
        return self.get_df().columns.tolist()



if __name__ == "__main__":
    import doctest
    doctest.testmod(optionflags=doctest.ELLIPSIS)
    #doctest.testmod()
    # config = {"skiprows": 1}
    ##sloan = InputDataCSV("sloan_search.csv", config = {'skiprows': [0, 2]})

    # q_raw = RawQuestion(question_type = "multiple_choice", 
    #                     question_name = "morning", 
    #                     question_text = "how are you doing this morning?",
    #                     question_options = ["Good", "Bad"], 
    #                     responses = ["Good", "Bad"])
    # q = q_raw.to_question()

    ##gss = InputDataSPSS("GSS7218_R3.sav", config = {"skiprows": None})

    gss = InputDataStata("GSS2022.dta", config = {}, auto_infer = True)
    # gss.question_texts = None
    # gss.raw_data = None
    # import time
    # start = time.time()
    # gss.frac_numerical
    # end = time.time()
    # print("First pass", end - start)
    # start = time.time()
    # gss.frac_numerical
    # end = time.time()
    # print("Second pass", end - start)

# jobs = InputDataSPSS("job_satisfaction.sav", config={"skiprows": None})
    #jobs.survey().html()

    # # id2 = InputDataCSV.from_dict(id.to_dict())
    if False:
        lenny = InputDataCSV("lenny.csv", config={"skiprows": None})
        #lenny.print()
        lenny.order_options()
        #lenny.print()
        survey = lenny.survey()
        a = lenny.agent(0)
        results = lenny.results()
        results.select('age').print()

