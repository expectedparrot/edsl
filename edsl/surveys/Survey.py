"""A Survey is collection of questions that can be administered to an Agent.

Constructing a Survey
---------------------
Key steps:

* Create questions
* Add questions to a survey
* Run the survey by sending it to an LLM

Before running the survey you can optionally:

* Add personas for AI agents that will respond to the survey
* Add rules and special logic (e.g., skip logic or memory of prior responses) (by default, questions are delivered asynchronously)
* Add values for parameterized questions (Scenario objects) 
* Specify the language models that will be used to answer the questions (the default model is GPT 4)

A survey can also be sent to Googe Forms, Survey Monkey, LimeSurvey and other survey 
platforms. 

Defining questions
^^^^^^^^^^^^^^^^^^
Questions can be defined as various types, including multiple choice, checkbox, free text, linear scale, numerical and other types.
The formats are defined in the `questions` module. Here we define some questions: 

.. code-block:: python

    from edsl.questions import QuestionMultipleChoice, 
    QuestionNumerical, QuestionFreeText

    q1 = QuestionMultipleChoice(
        question_name = "student",
        question_text = "Are you a student?",
        question_options = ["yes", "no"]
    )
    q2 = QuestionNumerical(
        question_name = "years",
        question_text = "How many years have you been in school?"
    )
    q3 = QuestionFreeText(
        question_name = "weekends",
        question_text = "What do you do on weekends?"
    )

Adding questions to a survey
^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Questions are added to a Survey object as a list of question ids:

.. code-block:: python

    from edsl.surveys import Survey

    survey = Survey(questions=[q1, q2, q3])

Alternatively, questions can be added to a Survey one at a time:

.. code-block:: python

    survey = Survey().add_question(q1).add_question(q2)
    
Applying survey rules
^^^^^^^^^^^^^^^^^^^^^
Rules are applied to a Survey with the `add_rule` and `add_stop_rule` methods which take a logical expression and the relevant questions.
For example, the following rule specifies that if the response to q1 is "no" then the next question is q3 (a skip rule):

.. code-block:: python
    
    survey = survey.add_rule(q1, "student == 'no'", q3)

Here we apply a stop rule instead of a skip rule. If the response to q1 is "no", the survey will end after q1 is answered:

.. code-block:: python

    survey = survey.add_stop_rule(q1, "student == 'no'"))

Writing conditional expressions
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
The expressions themselves ()"student == 'no'") are written in Python.
An expression is evaluated to True or False, with the answer substituted into the expression. 
The placeholder for this answer is the name of the question itself. 
In the examples, the answer to q1 is substituted into the expression "student == 'no'", 
as the name of q1 is "student".

Memory
^^^^^^
When an agent is taking a survey, they can be prompted to "remember" answers to previous questions.
This can be done in several ways:

* Full memory: The agent is given all of the answers to the questions in the survey.

.. code-block:: python

    s.set_full_memory_mode()

Note that this is slow and token-intensive, as the questions must be answered serially and requires the agent to remember all of the answers to the questions in the survey.
In contrast, if the agent does not need to remember all of the answers to the questions in the survey, execution can proceed in parallel.
    
* Lagged memory: With each question, the agent is given the answers to the specified number of lagged (prior) questions.
In this example, the agent is given the answers to the 2 previous questions in the survey:

.. code-block:: python

    s.set_lagged_memory(2)

* Targeted memory: The agent is given the answers to specific targeted prior questions.
In this example, the agent is given the answer to q1 when prompted to to answer q2:

.. code-block:: python

    survey.add_targeted_memory(q2, q1)

We can also use question names instead of question ids. The following example is equivalent to the previous one:

.. code-block:: python

    survey.add_targeted_memory("years", "student")

This method can be applied multiple times to add prior answers to a given question.
For example, we can add answers to both q1 and q2 when answering q3:

.. code-block:: python

    survey.add_memory_collection(q3, q1)
    survey.add_memory_collection(q3, q2)

    
Running a survey
^^^^^^^^^^^^^^^^
Once constructed, a Survey can be `run`, creating a `Results` object:

.. code-block:: python

    results = survey.run()

If question scenarios, agents or language models have been specified, they are added to the survey with the `by` method when running it:

.. code-block:: python

    results = survey.by(scenarios).by(agents).by(models).run()

Note that these survey components can be chained in any order, so long as each type of component is chained at once (e.g., if adding multiple agents, use `by.(agents)` once where agents is a list of all Agent objects).

Learn more about specifying question scenarios, agents and language models in their respective modules:

* :ref:`scenarios`
* :ref:`agents`
* :ref:`language_models`

Survey class methods
--------------------
"""
from __future__ import annotations
import re
from rich import print
from rich.table import Table
from rich.console import Console
import io

from dataclasses import dataclass
from collections import UserDict

from typing import Any, Generator, Optional, Union, List
from edsl.exceptions import SurveyCreationError, SurveyHasNoRulesError
from edsl.questions.Question import Question
from edsl.surveys.base import RulePriority, EndOfSurvey
from edsl.surveys.Rule import Rule
from edsl.surveys.RuleCollection import RuleCollection

from edsl.Base import Base
from edsl.surveys.SurveyExportMixin import SurveyExportMixin
from edsl.surveys.descriptors import QuestionsDescriptor
from edsl.surveys.MemoryPlan import MemoryPlan

from edsl.surveys.DAG import DAG


@dataclass
class SurveyMetaData:
    """Metadata for a survey. This is a dataclass that holds the name, description, and version of a survey."""

    name: str = None
    description: str = None
    version: str = None


from edsl.surveys.SurveyFlowVisualizationMixin import SurveyFlowVisualizationMixin


class Survey(SurveyExportMixin, SurveyFlowVisualizationMixin, Base):
    """A collection of questions that supports skip logic."""

    questions = QuestionsDescriptor()
    """
    A collection of questions that supports skip logic.

    Initalization:
    - `questions`: the questions in the survey (optional)
    - `question_names`: the names of the questions (optional)
    - `name`: the name of the survey (optional)

    Methods:
    -

    Notes:
    - The presumed order of the survey is the order in which questions are added.
    """

    def __init__(
        self,
        questions: list[Question] = None,
        memory_plan: MemoryPlan = None,
        name: str = None,
        description: str = None,
        version: str = None,
    ):
        """Create a new survey."""
        self.rule_collection = RuleCollection(
            num_questions=len(questions) if questions else None
        )
        self.meta_data = SurveyMetaData(
            name=name, description=description, version=version
        )
        self.questions = questions or []
        self.memory_plan = memory_plan or MemoryPlan(self)

    @property
    def name(self):
        """Return the name of the survey."""
        # print("WARNING: name is deprecated. Please use meta_data.name instead.")
        return self.meta_data.name

    def get_question(self, question_name) -> Question:
        """Return the question object given the question name."""
        if question_name not in self.question_name_to_index:
            raise KeyError(f"Question name {question_name} not found in survey.")
        index = self.question_name_to_index[question_name]
        return self._questions[index]

    @property
    def question_names(self) -> list[str]:
        """Return a list of question names in the survey.

        Example:
        >>> s = Survey.example()
        >>> s.question_names
        ['q0', 'q1', 'q2']
        """
        # return list(self.question_name_to_index.keys())
        return [q.question_name for q in self.questions]

    @property
    def question_name_to_index(self) -> dict[str, int]:
        """Return a dictionary mapping question names to question indices.

        Example:
        >>> s = Survey.example()
        >>> s.question_name_to_index
        {'q0': 0, 'q1': 1, 'q2': 2}
        """
        return {q.question_name: i for i, q in enumerate(self.questions)}

    def add_question(
        self, question: Question, question_name: Optional[str] = None
    ) -> Survey:
        """
        Add a question to survey.

        - The question is appended at the end of the self.questions list
        - A default rule is created that the next index is the next question.
        """
        if question_name is not None:
            print(
                "Warning: question_name is deprecated. Please use question.question_name instead."
            )

        if question.question_name in self.question_names:
            raise SurveyCreationError(
                f"""Question name already exists in survey. Please use a different name for the offensing question.
                The problemetic question name is {question_name}.
                """
            )
        index = len(self.questions)
        # TODO: This is a bit ugly because the user
        # doesn't "know" about _questions - it's generated by the
        # descriptor.
        self._questions.append(question)

        # using index + 1 presumes there is a next question
        self.rule_collection.add_rule(
            Rule(
                current_q=index,
                expression="True",
                next_q=index + 1,
                question_name_to_index=self.question_name_to_index,
                priority=RulePriority.DEFAULT.value,
            )
        )

        # a question might be added before the memory plan is created
        # it's ok because the memory plan will be updated when it is created
        if hasattr(self, "memory_plan"):
            self.memory_plan.add_question(question)

        return self

    def set_full_memory_mode(self) -> None:
        """Add instructions to a survey that the agent should remember all of the answers to the questions in the survey."""
        self._set_memory_plan(lambda i: self.question_names[:i])

    def set_lagged_memory(self, lags: int):
        """Add instructions to a survey that the agent should remember the answers to the questions in the survey.
        
        The agent should remember the answers to the questions in the survey from the previous lags.
        """
        self._set_memory_plan(lambda i: self.question_names[max(0, i - lags) : i])

    def _set_memory_plan(self, prior_questions_func):
        """Set memory plan based on a provided function determining prior questions."""
        for i, question_name in enumerate(self.question_names):
            self.memory_plan.add_memory_collection(
                focal_question=question_name,
                prior_questions=prior_questions_func(i),
            )

    def add_targeted_memory(
        self, focal_question: Union[Question, str], prior_question: Union[Question, str]
    ) -> None:
        """Add instructions to a survey than when answering focal_question.
        
        The agent should also remember the answers to prior_questions listed in prior_questions.
        """
        focal_question_name = self.question_names[
            self._get_question_index(focal_question)
        ]
        prior_question_name = self.question_names[
            self._get_question_index(prior_question)
        ]

        self.memory_plan.add_single_memory(
            focal_question=focal_question_name,
            prior_question=prior_question_name,
        )

    def add_memory_collection(
        self,
        focal_question: Union[Question, str],
        prior_questions: List[Union[Question, str]],
    ):
        """Add prior questions and responses so the agent has them when answering.

        This adds instructions to a survey than when answering focal_question, the agent should also remember the answers to prior_questions listed in prior_questions.

        :param focal_question: The question that the agent is answering.
        :param prior_questions: The questions that the agent should remember when answering the focal question.

        Example:
        >>> s = Survey.example()
        >>> s.add_memory_collection("q2", ["q0", "q1"])
        """
        focal_question_name = self.question_names[
            self._get_question_index(focal_question)
        ]

        prior_question_names = [
            self.question_names[self._get_question_index(prior_question)]
            for prior_question in prior_questions
        ]

        self.memory_plan.add_memory_collection(
            focal_question=focal_question_name, prior_questions=prior_question_names
        )

    def add_stop_rule(self, question: Question, expression: str) -> Survey:
        """Add a rule that stops the survey."""
        self.add_rule(question, expression, EndOfSurvey)
        return self

    def _get_question_index(self, q):
        """Return the index of the question or EndOfSurvey object.
        
        It can handle it if the user passes in the question name, the question object, or the EndOfSurvey object.
        """
        if q == EndOfSurvey:
            return EndOfSurvey
        else:
            question_name = q if isinstance(q, str) else q.question_name
            if question_name not in self.question_name_to_index:
                raise ValueError(
                    f"""Question name {question_name} not found in survey. The current question names are {self.question_name_to_index}."""
                )
            return self.question_name_to_index[question_name]

    def add_rule(
        self, question: Question, expression: str, next_question: Question
    ) -> Survey:
        """
        Add a rule to a Question of the Survey with the appropriate priority.

        - The last rule added for the question will have the highest priority.
        - If there are no rules, the rule added gets priority -1.
        """
        question_index = self._get_question_index(question)
        next_question_index = self._get_question_index(next_question)

        def get_new_rule_priority(question_index):
            """Return the priority for the new rule."""
            current_priorities = [
                rule.priority
                for rule in self.rule_collection.applicable_rules(question_index)
            ]
            max_priority = max(current_priorities)
            # newer rules take priority over older rules
            new_priority = (
                RulePriority.DEFAULT.value
                if len(current_priorities) == 0
                else max_priority + 1
            )
            return new_priority

        self.rule_collection.add_rule(
            Rule(
                current_q=question_index,
                expression=expression,
                next_q=next_question_index,
                question_name_to_index=self.question_name_to_index,
                priority=get_new_rule_priority(question_index),
            )
        )

        return self

    ###################
    # FORWARD METHODS
    ###################
    def by(self, *args: Union[Agent, Scenario, LanguageModel]) -> Jobs:
        """Add Agents, Scenarios, and LanguageModels to a survey and returns a runnable Jobs object."""
        from edsl.jobs.Jobs import Jobs

        job = Jobs(survey=self)
        return job.by(*args)

    def run(self, *args, **kwargs) -> Jobs:
        """Turn the survey into a Job and runs it."""
        from edsl.jobs.Jobs import Jobs

        return Jobs(survey=self).run(*args, **kwargs)

    ########################
    ## Survey-Taking Methods
    ########################

    def first_question(self) -> Question:
        """Return the first question in the survey."""
        return self.questions[0]

    def next_question(
        self, current_question: "Question", answers: dict
    ) -> Union[Question, EndOfSurvey.__class__]:
        """
        Return the next question in a survey.

        - If called with no arguments, it returns the first question in the survey.
        - If no answers are provided for a question with a rule, the next question is returned. If answers are provided, the next question is determined by the rules and the answers.
        - If the next question is the last question in the survey, an EndOfSurvey object is returned.
        """
        if isinstance(current_question, str):
            print(
                "WARNING: current_question by string is deprecated. Please use a Question object."
            )
            current_question = self.get_question(current_question)

        question_index = self.question_name_to_index[current_question.question_name]
        next_question_object = self.rule_collection.next_question(
            question_index, answers
        )

        if next_question_object.num_rules_found == 0:
            raise SurveyHasNoRulesError

        if next_question_object.next_q == EndOfSurvey:
            return EndOfSurvey
        else:
            if next_question_object.next_q >= len(self.questions):
                return EndOfSurvey
            else:
                return self.questions[next_question_object.next_q]

    def gen_path_through_survey(self) -> Generator[Question, dict, None]:
        """
        Generate a coroutine that can be used to conduct an Interview.

        - The coroutine is a generator that yields a question and receives answers.
        - The coroutine starts with the first question in the survey.
        - The coroutine ends when an EndOfSurvey object is returned.

        E.g., in Interview.py

        path_through_survey = self.survey.gen_path_through_survey()
        question = path_through_survey.send({question.question_name: answer})
        """
        question = self.first_question()
        while not question == EndOfSurvey:
            self.answers = yield question
            question = self.next_question(question, self.answers)

    @property
    def scenario_attributes(self) -> list[str]:
        """Return a list of attributes that admissible Scenarios should have."""
        temp = []
        for question in self.questions:
            question_text = question.question_text
            # extract the contents of all {{ }} in the question text using regex
            matches = re.findall(r"\{\{(.+?)\}\}", question_text)
            # remove whitespace
            matches = [match.strip() for match in matches]
            # add them to the temp list
            temp.extend(matches)
        return temp

    def textify(self, index_dag: DAG) -> DAG:
        """Convert the DAG of question indices to a DAG of question names.

        Example:
        >>> s = Survey.example()
        >>> d = s.dag()
        >>> d
        {1: {0}, 2: {0}}
        >>> s.textify(d)
        {'q1': {'q0'}, 'q2': {'q0'}}
        """

        def get_name(index):
            """Return the name of the question given the index."""
            return self.questions[index].question_name

        try:
            text_dag = {}
            for child_index, parent_indices in index_dag.items():
                parent_names = {get_name(index) for index in parent_indices}
                child_name = get_name(child_index)
                text_dag[child_name] = parent_names
            return text_dag
        except IndexError:
            breakpoint()

    def dag(self, textify=False) -> DAG:
        """Return the DAG of the survey, which reflects both skip-logic and memory."""
        memory_dag = self.memory_plan.dag
        rule_dag = self.rule_collection.dag
        if textify:
            memory_dag = DAG(self.textify(memory_dag))
            rule_dag = DAG(self.textify(rule_dag))
        return memory_dag + rule_dag

    ###################
    # DUNDER METHODS
    ###################
    def __len__(self) -> int:
        """Return the number of questions in the survey."""
        return len(self._questions)

    def __getitem__(self, index) -> Question:
        """Return the question object given the question index."""
        return self._questions[index]

    def __eq__(self, other):
        """Return True if the two surveys have the same to_dict."""
        if not isinstance(other, Survey):
            return False
        return self.to_dict() == other.to_dict()

    ###################
    # SERIALIZATION METHODS
    ###################
    def to_dict(self) -> dict[str, Any]:
        """Serialize the Survey object to a dictionary."""
        return {
            "questions": [q.to_dict() for q in self._questions],
            "name": self.name,
            "memory_plan": self.memory_plan.to_dict(),
            "rule_collection": self.rule_collection.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> Survey:
        """Deserialize the dictionary back to a Survey object."""
        questions = [Question.from_dict(q_dict) for q_dict in data["questions"]]
        memory_plan = MemoryPlan.from_dict(data["memory_plan"])
        survey = cls(questions=questions, name=data["name"], memory_plan=memory_plan)
        survey.rule_collection = RuleCollection.from_dict(data["rule_collection"])
        return survey

    ###################
    # DISPLAY METHODS
    ###################
    def __repr__(self) -> str:
        """Return a string representation of the survey."""
        questions_string = ", ".join([repr(q) for q in self._questions])
        question_names_string = ", ".join([repr(name) for name in self.question_names])
        return f"Survey(questions=[{questions_string}], name={repr(self.name)})"

    def show_rules(self) -> None:
        """Print out the rules in the survey."""
        self.rule_collection.show_rules()

    def rich_print(self):
        """Print the survey in a rich format."""
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Questions", style="dim")

        for question in self._questions:
            table.add_row(question.rich_print())

        return table

    def show_questions(self):
        """Print out the questions in the survey."""
        for name, question in zip(self.question_names, self._questions):
            print(f"Question:{name},{question}")

    def codebook(self) -> dict[str, str]:
        """Create a codebook for the survey, mapping question names to question text."""
        codebook = {}
        for question in self._questions:
            codebook[question.question_name] = question.question_text
        return codebook

    @classmethod
    def example(cls) -> Survey:
        """Return an example survey."""
        from edsl.questions.QuestionMultipleChoice import QuestionMultipleChoice
        # from edsl.surveys.Survey import Survey

        q0 = QuestionMultipleChoice(
            question_text="Do you like school?",
            question_options=["yes", "no"],
            question_name="q0",
        )
        q1 = QuestionMultipleChoice(
            question_text="Why not?",
            question_options=["killer bees in cafeteria", "other"],
            question_name="q1",
        )
        q2 = QuestionMultipleChoice(
            question_text="Why?",
            question_options=["**lack*** of killer bees in cafeteria", "other"],
            question_name="q2",
        )
        s = cls(questions=[q0, q1, q2])
        s = s.add_rule(q0, "q0 == 'yes'", q2)
        return s


def main():
    """Run the example survey."""
    def example_survey():
        """Return an example survey."""
        from edsl.questions.QuestionMultipleChoice import QuestionMultipleChoice
        from edsl.surveys.Survey import Survey

        q0 = QuestionMultipleChoice(
            question_text="Do you like school?",
            question_options=["yes", "no"],
            question_name="q0",
        )
        q1 = QuestionMultipleChoice(
            question_text="Why not?",
            question_options=["killer bees in cafeteria", "other"],
            question_name="q1",
        )
        q2 = QuestionMultipleChoice(
            question_text="Why?",
            question_options=["**lack*** of killer bees in cafeteria", "other"],
            question_name="q2",
        )
        s = Survey(questions=[q0, q1, q2])
        s = s.add_rule(q0, "q0 == 'yes'", q2)
        return s

    s = example_survey()
    survey_dict = s.to_dict()
    s2 = Survey.from_dict(survey_dict)
    results = s2.run()
    print(results)


if __name__ == "__main__":

    def example_survey():
        """Return an example survey."""
        from edsl.questions.QuestionMultipleChoice import QuestionMultipleChoice
        from edsl.surveys.Survey import Survey

        q0 = QuestionMultipleChoice(
            question_text="Do you like school?",
            question_options=["yes", "no"],
            question_name="like_school",
        )
        q1 = QuestionMultipleChoice(
            question_text="Why not?",
            question_options=["killer bees in cafeteria", "other"],
            question_name="why_not",
        )
        q2 = QuestionMultipleChoice(
            question_text="Why?",
            question_options=["**lack*** of killer bees in cafeteria", "other"],
            question_name="why",
        )
        s = Survey(questions=[q0, q1, q2])
        s = s.add_rule(q0, "like_school == 'yes'", q2).add_stop_rule(
            q1, "why_not == 'other'"
        )
        return s

    # s = example_survey()
    # survey_dict = s.to_dict()
    # s2 = Survey.from_dict(survey_dict)
    # results = s2.run()
    # print(results)

    import doctest

    doctest.testmod()

    s = example_survey()
    s.show_flow()
