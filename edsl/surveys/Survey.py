"""A Survey is collection of questions that can be administered to an Agent."""
from __future__ import annotations
import re
from rich import print
from rich.table import Table

from dataclasses import dataclass

from typing import Any, Generator, Optional, Union, List, Literal
from edsl.exceptions import SurveyCreationError, SurveyHasNoRulesError
from edsl.questions.QuestionBase import QuestionBase
from edsl.surveys.base import RulePriority, EndOfSurvey
from edsl.surveys.Rule import Rule
from edsl.surveys.RuleCollection import RuleCollection

from edsl.Base import Base
from edsl.surveys.SurveyExportMixin import SurveyExportMixin
from edsl.surveys.descriptors import QuestionsDescriptor
from edsl.surveys.MemoryPlan import MemoryPlan
from edsl.surveys.DAG import DAG
from edsl.utilities import is_notebook
from edsl.utilities.decorators import add_edsl_version, remove_edsl_version
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
        questions: list[QuestionBase] = None,
        memory_plan: MemoryPlan = None,
        rule_collection: RuleCollection = None,
        question_groups: dict[str, tuple[int, int]] = None,
        name: str = None,
    ):
        """Create a new survey."""
        self.rule_collection = RuleCollection(
            num_questions=len(questions) if questions else None
        )
        # the RuleCollection needs to be present while we add the questions; we might override this later
        # if a rule_collection is provided. This allows us to serialize the survey with the rule_collection.
        self.questions = questions or []
        self.memory_plan = memory_plan or MemoryPlan(self)
        if question_groups is not None:
            self.question_groups = question_groups
        else:
            self.question_groups = {}

        # if a rule collection is provided, use it instead
        if rule_collection is not None:
            self.rule_collection = rule_collection

        if name is not None:
            import warnings

            warnings.warn("name is deprecated.")

    def get_question(self, question_name) -> QuestionBase:
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

    def add_question(self, question: QuestionBase) -> Survey:
        """
        Add a question to survey.

        :param question: The question to add to the survey.
        :param question_name: The name of the question. If not provided, the question name is used.

        The question is appended at the end of the self.questions list
        A default rule is created that the next index is the next question.

        >>> from edsl import QuestionMultipleChoice
        >>> q = QuestionMultipleChoice(question_text = "Do you like school?", question_options=["yes", "no"], question_name="q0")
        >>> s = Survey().add_question(q)

        >>> s = Survey().add_question(q).add_question(q)
        Traceback (most recent call last):
        ...
        edsl.exceptions.surveys.SurveyCreationError: Question name already exists in survey. ...
        """
        if question.question_name in self.question_names:
            raise SurveyCreationError(
                f"""Question name already exists in survey. Please use a different name for the offensing question. The problemetic question name is {question.question_name}."""
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

    def set_full_memory_mode(self) -> Survey:
        """Add instructions to a survey that the agent should remember all of the answers to the questions in the survey."""
        self._set_memory_plan(lambda i: self.question_names[:i])
        return self

    def set_lagged_memory(self, lags: int) -> Survey:
        """Add instructions to a survey that the agent should remember the answers to the questions in the survey.

        The agent should remember the answers to the questions in the survey from the previous lags.
        """
        self._set_memory_plan(lambda i: self.question_names[max(0, i - lags) : i])
        return self

    def _set_memory_plan(self, prior_questions_func):
        """Set memory plan based on a provided function determining prior questions."""
        for i, question_name in enumerate(self.question_names):
            self.memory_plan.add_memory_collection(
                focal_question=question_name,
                prior_questions=prior_questions_func(i),
            )

    def add_question_group(
        self,
        start_question: Union[QuestionBase, str],
        end_question: Union[QuestionBase, str],
        group_name: str,
    ) -> None:
        """Add a group of questions to the survey."""

        if not group_name.isidentifier():
            raise ValueError(f"Group name {group_name} is not a valid identifier.")

        if group_name in self.question_groups:
            raise ValueError(f"Group name {group_name} already exists in the survey.")

        if group_name in self.question_name_to_index:
            raise ValueError(
                f"Group name {group_name} already exists as a question name in the survey."
            )

        start_index = self._get_question_index(start_question)
        end_index = self._get_question_index(end_question)

        if start_index > end_index:
            raise ValueError(
                f"Start index {start_index} is greater than end index {end_index}."
            )

        for existing_group_name, (
            existing_start_index,
            existing_end_index,
        ) in self.question_groups.items():
            if start_index < existing_start_index and end_index > existing_end_index:
                raise ValueError(
                    f"Group {group_name} contains the questions in the new group."
                )
            if start_index > existing_start_index and end_index < existing_end_index:
                raise ValueError(f"Group {group_name} is contained in the new group.")
            if start_index < existing_start_index and end_index > existing_start_index:
                raise ValueError(f"Group {group_name} overlaps with the new group.")
            if start_index < existing_end_index and end_index > existing_end_index:
                raise ValueError(f"Group {group_name} overlaps with the new group.")

        self.question_groups[group_name] = (start_index, end_index)
        return self

    def add_targeted_memory(
        self,
        focal_question: Union[QuestionBase, str],
        prior_question: Union[QuestionBase, str],
    ) -> Survey:
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

        return self

    def add_memory_collection(
        self,
        focal_question: Union[QuestionBase, str],
        prior_questions: List[Union[QuestionBase, str]],
    ) -> Survey:
        """Add prior questions and responses so the agent has them when answering.

        This adds instructions to a survey than when answering focal_question, the agent should also remember the answers to prior_questions listed in prior_questions.

        :param focal_question: The question that the agent is answering.
        :param prior_questions: The questions that the agent should remember when answering the focal question.

        Example:

        >>> s = Survey.example().add_memory_collection("q2", ["q0", "q1"])
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
        return self

    def add_stop_rule(
        self, question: Union[QuestionBase, str], expression: str
    ) -> Survey:
        """Add a rule that stops the survey.

        The rule is evaluated *after* the question is answered. If the rule is true, the survey ends.

        >>> s = Survey.example().add_stop_rule("q0", "q0 == 'yes'")
        >>> s.next_question("q0", {"q0": "yes"})
        EndOfSurvey

        >>> s.next_question("q0", {"q0": "no"}).question_name
        'q1'
        """
        self.add_rule(question, expression, EndOfSurvey)
        return self

    def add_skip_rule(
        self, question: Union[QuestionBase, str], expression: str
    ) -> Survey:
        """
        Adds a skip rule to the survey.

        :param question: The question to add the skip rule to.
        :param expression: The expression to evaluate.

        If the expression evaluates to True, the question is skipped. This is evaluated *before* the question is answered.
        """
        question_index = self._get_question_index(question)
        self._add_rule(question, expression, question_index + 1, before_rule=True)
        return self

    def _get_question_index(
        self, q: Union[QuestionBase, str, EndOfSurvey.__class__]
    ) -> Union[int, EndOfSurvey.__class__]:
        """Return the index of the question or EndOfSurvey object.

        :param q: The question or question name to get the index of.

        It can handle it if the user passes in the question name, the question object, or the EndOfSurvey object.

        >>> s = Survey.example()
        >>> s._get_question_index("q0")
        0
        >>> s._get_question_index("poop")
        Traceback (most recent call last):
        ...
        ValueError: Question name poop not found in survey. The current question names are {'q0': 0, 'q1': 1, 'q2': 2}.
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

    def _get_new_rule_priority(
        self, question_index: int, before_rule: bool = False
    ) -> int:
        """Return the priority for the new rule."""
        current_priorities = [
            rule.priority
            for rule in self.rule_collection.applicable_rules(
                question_index, before_rule
            )
        ]
        if len(current_priorities) == 0:
            return RulePriority.DEFAULT.value + 1

        max_priority = max(current_priorities)
        # newer rules take priority over older rules
        new_priority = (
            RulePriority.DEFAULT.value
            if len(current_priorities) == 0
            else max_priority + 1
        )
        return new_priority

    def add_rule(
        self,
        question: Union[QuestionBase, str],
        expression: str,
        next_question: Union[QuestionBase, int],
        before_rule: bool = False,
    ) -> Survey:
        """
        Add a rule to a Question of the Survey with the appropriate priority.

        :param question: The question to add the rule to.
        :param expression: The expression to evaluate.
        :param next_question: The next question to go to if the rule is true.
        :param before_rule: Whether the rule is evaluated before the question is answered.
        """
        return self._add_rule(
            question, expression, next_question, before_rule=before_rule
        )

    def _add_rule(
        self,
        question: Union[QuestionBase, str],
        expression: str,
        next_question: Union[QuestionBase, str, int],
        before_rule: bool = False,
    ) -> Survey:
        """
        Add a rule to a Question of the Survey with the appropriate priority.

        :param question: The question to add the rule to.
        :param expression: The expression to evaluate.
        :param next_question: The next question to go to if the rule is true.
        :param before_rule: Whether the rule is evaluated before the question is answered.


        - The last rule added for the question will have the highest priority.
        - If there are no rules, the rule added gets priority -1.
        """
        question_index = self._get_question_index(question)

        # Might not have the name of the next question yet
        if isinstance(next_question, int):
            next_question_index = next_question
        else:
            next_question_index = self._get_question_index(next_question)

        new_priority = self._get_new_rule_priority(question_index, before_rule)

        self.rule_collection.add_rule(
            Rule(
                current_q=question_index,
                expression=expression,
                next_q=next_question_index,
                question_name_to_index=self.question_name_to_index,
                priority=new_priority,
                before_rule=before_rule,
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

    def first_question(self) -> QuestionBase:
        """Return the first question in the survey."""
        return self.questions[0]

    def next_question(
        self, current_question: Union[str, QuestionBase], answers: dict
    ) -> Union[QuestionBase, EndOfSurvey.__class__]:
        """
        Return the next question in a survey.

        - If called with no arguments, it returns the first question in the survey.
        - If no answers are provided for a question with a rule, the next question is returned. If answers are provided, the next question is determined by the rules and the answers.
        - If the next question is the last question in the survey, an EndOfSurvey object is returned.
        """
        if isinstance(current_question, str):
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

    def gen_path_through_survey(self) -> Generator[QuestionBase, dict, None]:
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
            ## TODO: This should also include survey and agent attributes
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

        def get_name(index: int):
            """Return the name of the question given the index."""
            if index >= len(self.questions):
                return EndOfSurvey
            try:
                return self.questions[index].question_name
            except IndexError:
                print(
                    f"The index is {index} but the length of the questions is {len(self.questions)}"
                )
                raise

        try:
            text_dag = {}
            for child_index, parent_indices in index_dag.items():
                parent_names = {get_name(index) for index in parent_indices}
                child_name = get_name(child_index)
                text_dag[child_name] = parent_names
            return text_dag
        except IndexError:
            raise

    def dag(self, textify=False) -> DAG:
        """Return the DAG of the survey, which reflects both skip-logic and memory.

        >>> s = Survey.example()
        >>> d = s.dag()
        >>> d
        {1: {0}, 2: {0}}

        """
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
        """Return the number of questions in the survey.

        >>> s = Survey.example()
        >>> len(s)
        3
        """
        return len(self._questions)

    def __getitem__(self, index) -> QuestionBase:
        """Return the question object given the question index."""
        if isinstance(index, int):
            return self._questions[index]
        elif isinstance(index, str):
            return getattr(self, index)

    def diff(self, other):
        from rich import print

        for key, value in self.to_dict().items():
            if value != other.to_dict()[key]:
                print(f"Key: {key}")
                print("\n")
                print(f"Self: {value}")
                print("\n")
                print(f"Other: {other.to_dict()[key]}")
                print("\n\n")

    def __eq__(self, other) -> bool:
        """Return True if the two surveys have the same to_dict."""
        if not isinstance(other, Survey):
            return False
        return self.to_dict() == other.to_dict()

    ###################
    # SERIALIZATION METHODS
    ###################
    @add_edsl_version
    def to_dict(self) -> dict[str, Any]:
        """Serialize the Survey object to a dictionary."""
        return {
            "questions": [q.to_dict() for q in self._questions],
            "memory_plan": self.memory_plan.to_dict(),
            "rule_collection": self.rule_collection.to_dict(),
            "question_groups": self.question_groups,
        }

    @classmethod
    @remove_edsl_version
    def from_dict(cls, data: dict) -> Survey:
        """Deserialize the dictionary back to a Survey object."""
        questions = [QuestionBase.from_dict(q_dict) for q_dict in data["questions"]]
        memory_plan = MemoryPlan.from_dict(data["memory_plan"])
        survey = cls(
            questions=questions,
            memory_plan=memory_plan,
            rule_collection=RuleCollection.from_dict(data["rule_collection"]),
            question_groups=data["question_groups"],
        )
        return survey

    ###################
    # DISPLAY METHODS
    ###################
    def print(self):
        from rich import print_json
        import json

        print_json(json.dumps(self.to_dict()))

    def __repr__(self) -> str:
        """Return a string representation of the survey."""

        questions_string = ", ".join([repr(q) for q in self._questions])
        question_names_string = ", ".join([repr(name) for name in self.question_names])
        return f"Survey(questions=[{questions_string}], memory_plan={self.memory_plan}, rule_collection={self.rule_collection}, question_groups={self.question_groups})"

    def _repr_html_(self) -> str:
        from edsl.utilities.utilities import data_to_html

        return data_to_html(self.to_dict())

    def show_rules(self) -> None:
        """Print out the rules in the survey.

        >>> s = Survey.example()
        >>> s.show_rules()
        ┏━━━━━━━━━━━┳━━━━━━━━━━━━━┳━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━━━━┓
        ┃ current_q ┃ expression  ┃ next_q ┃ priority ┃ before_rule ┃
        ┡━━━━━━━━━━━╇━━━━━━━━━━━━━╇━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━━━━┩
        │ 0         │ True        │ 1      │ -1       │ False       │
        │ 0         │ q0 == 'yes' │ 2      │ 0        │ False       │
        │ 1         │ True        │ 2      │ -1       │ False       │
        │ 2         │ True        │ 3      │ -1       │ False       │
        └───────────┴─────────────┴────────┴──────────┴─────────────┘
        """
        self.rule_collection.show_rules()

    def rich_print(self):
        """Print the survey in a rich format."""
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Questions", style="dim")

        for question in self._questions:
            table.add_row(question.rich_print())

        return table

    def codebook(self) -> dict[str, str]:
        """Create a codebook for the survey, mapping question names to question text.

        >>> s = Survey.example()
        >>> s.codebook()
        {'q0': 'Do you like school?', 'q1': 'Why not?', 'q2': 'Why?'}
        """
        codebook = {}
        for question in self._questions:
            codebook[question.question_name] = question.question_text
        return codebook

    def to_csv(self, filename: str = None):
        """Export the survey to a CSV file.

        :param filename: The name of the file to save the CSV to.

        >>> s = Survey.example()
        >>> s.to_csv()
           index question_name        question_text                                question_options    question_type edsl_version edsl_class_name
        0      0            q0  Do you like school?                                       [yes, no]  multiple_choice       0.1.21    QuestionBase
        1      1            q1             Why not?               [killer bees in cafeteria, other]  multiple_choice       0.1.21    QuestionBase
        2      2            q2                 Why?  [**lack*** of killer bees in cafeteria, other]  multiple_choice       0.1.21    QuestionBase
        """
        raw_data = []
        for index, question in enumerate(self._questions):
            d = {"index": index}
            d.update(question.to_dict())
            raw_data.append(d)
        from pandas import DataFrame

        df = DataFrame(raw_data)
        if filename:
            df.to_csv(filename, index=False)
        else:
            return df

    def web(
        self,
        platform: Literal[
            "google_forms", "lime_survey", "survey_monkey"
        ] = "google_forms",
        email=None,
    ):
        from edsl.coop import Coop

        c = Coop()

        res = c.web(self.to_dict(), platform, email)
        return res

    @classmethod
    def example(cls) -> Survey:
        """Return an example survey."""
        from edsl.questions.QuestionMultipleChoice import QuestionMultipleChoice

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
    import doctest

    doctest.testmod(optionflags=doctest.ELLIPSIS)

    # def example_survey():
    #     """Return an example survey."""
    #     from edsl.questions.QuestionMultipleChoice import QuestionMultipleChoice
    #     from edsl.surveys.Survey import Survey

    #     q0 = QuestionMultipleChoice(
    #         question_text="Do you like school?",
    #         question_options=["yes", "no"],
    #         question_name="like_school",
    #     )
    #     q1 = QuestionMultipleChoice(
    #         question_text="Why not?",
    #         question_options=["killer bees in cafeteria", "other"],
    #         question_name="why_not",
    #     )
    #     q2 = QuestionMultipleChoice(
    #         question_text="Why?",
    #         question_options=["**lack*** of killer bees in cafeteria", "other"],
    #         question_name="why",
    #     )
    #     s = Survey(questions=[q0, q1, q2])
    #     s = s.add_rule(q0, "like_school == 'yes'", q2).add_stop_rule(
    #         q1, "why_not == 'other'"
    #     )
    #     return s

    # s = example_survey()
    # s.show_flow()
