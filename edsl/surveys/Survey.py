"""A Survey is collection of questions that can be administered to an Agent."""

from __future__ import annotations
import re

from typing import Any, Generator, Optional, Union, List, Literal, Callable

from rich import print
from rich.table import Table

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
        questions: Optional[list[QuestionBase]] = None,
        memory_plan: Optional[MemoryPlan] = None,
        rule_collection: Optional[RuleCollection] = None,
        question_groups: Optional[dict[str, tuple[int, int]]] = None,
        name: str = None,
    ):
        """Create a new survey.

        :param questions: The questions in the survey.
        :param memory_plan: The memory plan for the survey.
        :param rule_collection: The rule collection for the survey.
        :param question_groups: The groups of questions in the survey.
        :param name: The name of the survey - DEPRECATED.

        """
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

            warnings.warn("name parameter to a survey is deprecated.")

    def get(self, question_name: str) -> QuestionBase:
        """
        Return the question object given the question name.

        :param question_name: The name of the question to get.

        >>> s = Survey.example()
        >>> s.get_question("q0")
        Question('multiple_choice', question_name = 'q0', question_text = 'Do you like school?', question_options = ['yes', 'no'])
        """
        if question_name not in self.question_name_to_index:
            raise KeyError(f"Question name {question_name} not found in survey.")
        index = self.question_name_to_index[question_name]
        return self._questions[index]

    def get_question(self, question_name: str) -> QuestionBase:
        """Return the question object given the question name."""
        # import warnings
        # warnings.warn("survey.get_question is deprecated. Use subscript operator instead.")
        return self.get(question_name)

    def __hash__(self) -> int:
        """Return a hash of the question."""
        from edsl.utilities.utilities import dict_hash

        return dict_hash(self._to_dict())

    @property
    def parameters(self):
        return set.union(*[q.parameters for q in self.questions])

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
        """Add instructions to a survey that the agent should remember all of the answers to the questions in the survey.

        >>> s = Survey.example().set_full_memory_mode()

        """
        self._set_memory_plan(lambda i: self.question_names[:i])
        return self

    def set_lagged_memory(self, lags: int) -> Survey:
        """Add instructions to a survey that the agent should remember the answers to the questions in the survey.

        The agent should remember the answers to the questions in the survey from the previous lags.
        """
        self._set_memory_plan(lambda i: self.question_names[max(0, i - lags) : i])
        return self

    def _set_memory_plan(self, prior_questions_func: Callable):
        """Set memory plan based on a provided function determining prior questions.

        :param prior_questions_func: A function that takes the index of the current question and returns a list of prior questions to remember.

        >>> s = Survey.example()
        >>> s._set_memory_plan(lambda i: s.question_names[:i])

        """
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
    ) -> Survey:
        """Add a group of questions to the survey.

        :param start_question: The first question in the group.
        :param end_question: The last question in the group.
        :param group_name: The name of the group.

        Example:

        >>> s = Survey.example().add_question_group("q0", "q1", "group1")
        >>> s.question_groups
        {'group1': (0, 1)}

        The name of the group must be a valid identifier:

        >>> s = Survey.example().add_question_group("q0", "q2", "1group1")
        Traceback (most recent call last):
        ...
        ValueError: Group name 1group1 is not a valid identifier.

        The name of the group cannot be the same as an existing question name:

        >>> s = Survey.example().add_question_group("q0", "q1", "q0")
        Traceback (most recent call last):
        ...
        ValueError: Group name q0 already exists as a question name in the survey.

        The start index must be less than the end index:

        >>> s = Survey.example().add_question_group("q1", "q0", "group1")
        Traceback (most recent call last):
        ...
        ValueError: Start index 1 is greater than end index 0.
        """

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

        :param focal_question: The question that the agent is answering.
        :param prior_question: The question that the agent should remember when answering the focal question.

        Here we add instructions to a survey than when answering q2 they should remember q1:

        >>> s = Survey.example().add_targeted_memory("q2", "q0")
        >>> s.memory_plan
        {'q2': Memory(prior_questions=['q0'])}

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

        Here we have it so that when answering q2, the agent should remember answers to q0 and q1:

        >>> s = Survey.example().add_memory_collection("q2", ["q0", "q1"])
        >>> s.memory_plan
        {'q2': Memory(prior_questions=['q0', 'q1'])}
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

        :param question: The question to add the stop rule to.
        :param expression: The expression to evaluate.

        The rule is evaluated *after* the question is answered. If the rule is true, the survey ends.

        Here, answering "yes" to q0 ends the survey:

        >>> s = Survey.example().add_stop_rule("q0", "q0 == 'yes'")
        >>> s.next_question("q0", {"q0": "yes"})
        EndOfSurvey

        By comparison, answering "no" to q0 does not end the survey:

        >>> s.next_question("q0", {"q0": "no"}).question_name
        'q1'
        """
        self.add_rule(question, expression, EndOfSurvey)
        return self

    def add_skip_rule(
        self, question: Union[QuestionBase, str], expression: str
    ) -> Survey:
        """
        Adds a per-question skip rule to the survey.

        :param question: The question to add the skip rule to.
        :param expression: The expression to evaluate.

        This adds a rule that skips 'q0' always, before the question is answered:

        >>> from edsl import QuestionFreeText
        >>> q0 = QuestionFreeText.example()
        >>> q0.question_name = "q0"
        >>> q1 = QuestionFreeText.example()
        >>> q1.question_name = "q1"
        >>> s = Survey([q0, q1]).add_skip_rule("q0", "True")
        >>> s.next_question("q0", {}).question_name
        'q1'

        Note that this is different from a rule that jumps to some other question *after* the question is answered.

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

        This doesnt' work with questions that don't exist:

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
        """Return the priority for the new rule.

        :param question_index: The index of the question to add the rule to.
        :param before_rule: Whether the rule is evaluated before the question is answered.

        >>> s = Survey.example()
        >>> s._get_new_rule_priority(0)
        1
        """
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
        Add a rule to a Question of the Survey.

        :param question: The question to add the rule to.
        :param expression: The expression to evaluate.
        :param next_question: The next question to go to if the rule is true.
        :param before_rule: Whether the rule is evaluated before the question is answered.

        This adds a rule that if the answer to q0 is 'yes', the next question is q2 (as opposed to q1)

        >>> s = Survey.example().add_rule("q0", "{{ q0 }} == 'yes'", "q2")
        >>> s.next_question("q0", {"q0": "yes"}).question_name
        'q2'

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
        """Add Agents, Scenarios, and LanguageModels to a survey and returns a runnable Jobs object.

        :param args: The Agents, Scenarios, and LanguageModels to add to the survey.

        This takes the survey and adds an Agent and a Scenario via 'by' which converts to a Jobs object:

        >>> s = Survey.example(); from edsl import Agent; from edsl import Scenario
        >>> s.by(Agent.example()).by(Scenario.example())
        Jobs(...)
        """
        from edsl.jobs.Jobs import Jobs

        job = Jobs(survey=self)
        return job.by(*args)

    def run(self, *args, **kwargs) -> "Results":
        """Turn the survey into a Job and runs it.

        Here we run a survey but with debug mode on (so LLM calls are not made)

        >>> from edsl import QuestionFreeText
        >>> s = Survey([QuestionFreeText.example()])
        >>> results = s.run(debug = True)
        >>> results
        Results(...)
        >>> results.select('answer.*').print(format = "rich")
        ┏━━━━━━━━━━━━━━┓
        ┃ answer       ┃
        ┃ .how_are_you ┃
        ┡━━━━━━━━━━━━━━┩
        ...
        └──────────────┘
        """
        from edsl.jobs.Jobs import Jobs

        return Jobs(survey=self).run(*args, **kwargs)

    ########################
    ## Survey-Taking Methods
    ########################

    def _first_question(self) -> QuestionBase:
        """Return the first question in the survey."""
        return self.questions[0]

    def next_question(
        self, current_question: Union[str, QuestionBase], answers: dict
    ) -> Union[QuestionBase, EndOfSurvey.__class__]:
        """
        Return the next question in a survey.

        :param current_question: The current question in the survey.
        :param answers: The answers for the survey so far

        - If called with no arguments, it returns the first question in the survey.
        - If no answers are provided for a question with a rule, the next question is returned. If answers are provided, the next question is determined by the rules and the answers.
        - If the next question is the last question in the survey, an EndOfSurvey object is returned.

        >>> s = Survey.example()
        >>> s.next_question("q0", {"q0": "yes"}).question_name
        'q2'
        >>> s.next_question("q0", {"q0": "no"}).question_name
        'q1'

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

        The coroutine is a generator that yields a question and receives answers.
        It starts with the first question in the survey.
        The coroutine ends when an EndOfSurvey object is returned.

        For the example survey, this is the rule table:

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

        Note that q0 has a rule that if the answer is 'yes', the next question is q2. If the answer is 'no', the next question is q1.

        Here is the path through the survey if the answer to q0 is 'yes':

        >>> i = s.gen_path_through_survey()
        >>> next(i)
        Question('multiple_choice', question_name = 'q0', question_text = 'Do you like school?', question_options = ['yes', 'no'])
        >>> i.send({"q0": "yes"})
        Question('multiple_choice', question_name = 'q2', question_text = 'Why?', question_options = ['**lack*** of killer bees in cafeteria', 'other'])

        And here is the path through the survey if the answer to q0 is 'no':

        >>> i2 = s.gen_path_through_survey()
        >>> next(i2)
        Question('multiple_choice', question_name = 'q0', question_text = 'Do you like school?', question_options = ['yes', 'no'])
        >>> i2.send({"q0": "no"})
        Question('multiple_choice', question_name = 'q1', question_text = 'Why not?', question_options = ['killer bees in cafeteria', 'other'])

        """
        question = self._first_question()
        while not question == EndOfSurvey:
            self.answers = yield question
            ## TODO: This should also include survey and agent attributes
            question = self.next_question(question, self.answers)

    @property
    def scenario_attributes(self) -> list[str]:
        """Return a list of attributes that admissible Scenarios should have.

        Here we have a survey with a question that uses a jinja2 style {{ }} template:

        >>> from edsl import QuestionFreeText
        >>> s = Survey().add_question(QuestionFreeText(question_text="{{ greeting }}. What is your name?", question_name="name"))
        >>> s.scenario_attributes
        ['greeting']

        >>> s = Survey().add_question(QuestionFreeText(question_text="{{ greeting }}. What is your {{ attribute }}?", question_name="name"))
        >>> s.scenario_attributes
        ['greeting', 'attribute']


        """
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

        :param index_dag: The DAG of question indices.

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

    def dag(self, textify: bool = False) -> DAG:
        """Return the DAG of the survey, which reflects both skip-logic and memory.

        :param textify: Whether to return the DAG with question names instead of indices.

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
        """Return the question object given the question index.

        :param index: The index of the question to get.

        >>> s = Survey.example()
        >>> s[0]
        Question('multiple_choice', question_name = 'q0', question_text = 'Do you like school?', question_options = ['yes', 'no'])

        """
        if isinstance(index, int):
            return self._questions[index]
        elif isinstance(index, str):
            return getattr(self, index)

    def _diff(self, other):
        """Used for debugging. Print out the differences between two surveys."""
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
        """Return True if the two surveys have the same to_dict.

        :param other: The other survey to compare to.

        >>> s = Survey.example()
        >>> s == s
        True

        >>> s == "poop"
        False

        """
        if not isinstance(other, Survey):
            return False
        return self.to_dict() == other.to_dict()

    ###################
    # SERIALIZATION METHODS
    ###################

    def _to_dict(self) -> dict[str, Any]:
        """Serialize the Survey object to a dictionary.

        >>> s = Survey.example()
        >>> s._to_dict().keys()
        dict_keys(['questions', 'memory_plan', 'rule_collection', 'question_groups'])

        """
        return {
            "questions": [q._to_dict() for q in self._questions],
            "memory_plan": self.memory_plan.to_dict(),
            "rule_collection": self.rule_collection.to_dict(),
            "question_groups": self.question_groups,
        }

    @add_edsl_version
    def to_dict(self) -> dict[str, Any]:
        """Serialize the Survey object to a dictionary.

        >>> s = Survey.example()
        >>> s.to_dict().keys()
        dict_keys(['questions', 'memory_plan', 'rule_collection', 'question_groups', 'edsl_version', 'edsl_class_name'])

        """
        return self._to_dict()

    @classmethod
    @remove_edsl_version
    def from_dict(cls, data: dict) -> Survey:
        """Deserialize the dictionary back to a Survey object.

        :param data: The dictionary to deserialize.

        >>> d = Survey.example().to_dict()
        >>> s = Survey.from_dict(d)
        >>> s == Survey.example()
        True

        """
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
        """Print the survey in a rich format.

        >>> s = Survey.example()
        >>> s.print()
        {
          "questions": [
          ...
        }
        """
        from rich import print_json
        import json

        print_json(json.dumps(self.to_dict()))

    def __repr__(self) -> str:
        """Return a string representation of the survey."""

        questions_string = ", ".join([repr(q) for q in self._questions])
        # question_names_string = ", ".join([repr(name) for name in self.question_names])
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

    def rich_print(self) -> Table:
        """Print the survey in a rich format.

        >>> t = Survey.example().rich_print()
        >>> print(t)
        ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
        ┃ Questions                                                                                          ┃
        ┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
        │ ┏━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━┓                                │
        │ ┃ Question Name ┃ Question Type   ┃ Question Text       ┃ Options ┃                                │
        │ ┡━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━┩                                │
        │ │ q0            │ multiple_choice │ Do you like school? │ yes, no │                                │
        │ └───────────────┴─────────────────┴─────────────────────┴─────────┘                                │
        │ ┏━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓              │
        │ ┃ Question Name ┃ Question Type   ┃ Question Text ┃ Options                         ┃              │
        │ ┡━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩              │
        │ │ q1            │ multiple_choice │ Why not?      │ killer bees in cafeteria, other │              │
        │ └───────────────┴─────────────────┴───────────────┴─────────────────────────────────┘              │
        │ ┏━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓ │
        │ ┃ Question Name ┃ Question Type   ┃ Question Text ┃ Options                                      ┃ │
        │ ┡━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩ │
        │ │ q2            │ multiple_choice │ Why?          │ **lack*** of killer bees in cafeteria, other │ │
        │ └───────────────┴─────────────────┴───────────────┴──────────────────────────────────────────────┘ │
        └────────────────────────────────────────────────────────────────────────────────────────────────────┘
        """
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
           index question_name        question_text                                question_options    question_type
        0      0            q0  Do you like school?                                       [yes, no]  multiple_choice
        1      1            q1             Why not?               [killer bees in cafeteria, other]  multiple_choice
        2      2            q2                 Why?  [**lack*** of killer bees in cafeteria, other]  multiple_choice
        """
        raw_data = []
        for index, question in enumerate(self._questions):
            d = {"index": index}
            question_dict = question.to_dict()
            _ = question_dict.pop("edsl_version")
            _ = question_dict.pop("edsl_class_name")
            d.update(question_dict)
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
        """Return an example survey.

        >>> s = Survey.example()
        >>> [q.question_text for q in s.questions]
        ['Do you like school?', 'Why not?', 'Why?']
        """
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

    def __call__(self, model=None, agent=None, **kwargs):
        """Run the survey with default model, taking the required survey as arguments.

        >>> from edsl.questions import QuestionFunctional
        >>> def f(scenario, agent_traits): return "yes" if scenario["period"] == "morning" else "no"
        >>> q = QuestionFunctional(question_name = "q0", func = f)
        >>> s = Survey([q])
        >>> s(period = "morning").select("answer.q0").first()
        'yes'
        >>> s(period = "evening").select("answer.q0").first()
        'no'
        """
        if not model:
            from edsl import Model

            model = Model()

        from edsl.scenarios.Scenario import Scenario

        s = Scenario(kwargs)

        if not agent:
            from edsl import Agent

            agent = Agent()

        return self.by(s).by(agent).by(model).run()


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
