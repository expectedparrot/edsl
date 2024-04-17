"""A survey has a memory plan that specifies what the agent should remember when answering a question."""
from collections import UserDict, defaultdict
from edsl.surveys.Memory import Memory

from edsl.prompts.Prompt import Prompt
from edsl.surveys.DAG import DAG


class MemoryPlan(UserDict):
    """A survey has a memory plan that specifies what the agent should remember when answering a question.

    {focal_question: [prior_questions], focal_question: [prior_questions]}
    """

    def __init__(self, survey: "Survey" = None, data=None):
        """Initialize a memory plan."""
        if survey is not None:
            self.survey = survey
            self.survey_question_names = [q.question_name for q in survey.questions]
            self.question_texts = [q.question_text for q in survey.questions]
        super().__init__(data or {})

    @property
    def name_to_text(self):
        """Return a dictionary mapping question names to question texts."""
        return dict(zip(self.survey_question_names, self.question_texts))

    def add_question(self, question: "Question") -> None:
        """Add a question to the survey.

        :param question: A question to add to the survey

        """
        self.survey_question_names.append(question.question_name)
        self.question_texts.append(question.question_text)

    def _check_valid_question_name(self, question_name: str) -> None:
        """Ensure a passed question name is valid.

        :param question_name: The name of the question to check.

        """
        if question_name not in self.survey_question_names:
            raise ValueError(
                f"{question_name} is not in the survey. Current names are {self.survey_question_names}"
            )

    def get_memory_prompt_fragment(
        self, focal_question: str, answers: dict
    ) -> "Prompt":
        """Generate the prompt fragment descripting that past question and answer.

        :param focal_question: The current question being answered.
        :param answers: A dictionary of question names to answers.

        """
        self._check_valid_question_name(focal_question)

        if focal_question not in self:
            return Prompt("")

        q_and_a_pairs = [
            (self.name_to_text[question_name], answers.get(question_name, None))
            for question_name in self[focal_question]
        ]

        base_prompt_text = """
        Before the question you are now answering, you already answered the following question(s):
        """

        def gen_line(question_text, answer):
            """Return a line of memory."""
            return f"\tQuestion: {question_text}\n\tAnswer: {answer}\n"

        lines = [gen_line(*pair) for pair in q_and_a_pairs]
        if lines:
            return Prompt(
                base_prompt_text + "\n Prior questions and answers:".join(lines)
            )
        else:
            return Prompt("")

    def _check_order(self, focal_question: str, prior_question: str) -> None:
        """Ensure the prior question comes before the focal question."""
        focal_index = self.survey_question_names.index(focal_question)
        prior_index = self.survey_question_names.index(prior_question)
        if focal_index <= prior_index:
            raise ValueError(f"{prior_question} must come before {focal_question}.")

    def add_single_memory(self, focal_question: str, prior_question: str) -> None:
        """Add a single memory to the memory plan.

        :param focal_question: The current question being answered.
        :param prior_question: The question that was answered before the focal question that should be remembered.
        """
        self._check_valid_question_name(focal_question)
        self._check_valid_question_name(prior_question)
        self._check_order(focal_question, prior_question)

        if focal_question not in self:
            memory = Memory()
            memory.add_prior_question(prior_question)
            self[focal_question] = memory
        else:
            self[focal_question].add_prior_question(prior_question)

    def add_memory_collection(
        self, focal_question: str, prior_questions: list[str]
    ) -> None:
        """Add a collection of prior questions to the memory plan.

        :param focal_question: The current question being answered.
        :param prior_questions: A list of questions that were answered before the focal question that should be remembered.
        """
        for question in prior_questions:
            self.add_single_memory(focal_question, question)

    def to_dict(self) -> dict:
        """Serialize the memory plan to a dictionary."""
        newdata = {}
        for question_name, memory in self.items():
            newdata[question_name] = memory.to_dict()

        return {
            "survey_question_names": self.survey_question_names,
            "survey_question_texts": self.question_texts,
            "data": newdata,
        }

    @classmethod
    def from_dict(cls, data) -> "MemoryPlan":
        """Deserialize a memory plan from a dictionary."""
        newdata = {}
        for question_name, memory in data["data"].items():
            newdata[question_name] = Memory.from_dict(memory)

        memory_plan = cls(survey=None, data=newdata)
        memory_plan.survey_question_names = data["survey_question_names"]
        memory_plan.question_texts = data["survey_question_texts"]
        return memory_plan

    def _indexify(self, d: dict):
        """Convert a dictionary of question names to a dictionary of question indices.

        :param d: A dictionary of question names to indices.
        """
        new_d = {}
        for k, v in d.items():
            key = self.survey_question_names.index(k)
            new_v = set({self.survey_question_names.index(q) for q in v})
            new_d[key] = new_v
        return new_d

    @property
    def dag(self) -> DAG:
        """Return a directed acyclic graph of the memory plan."""
        d = defaultdict(set)
        for focal_question, memory in self.items():
            for prior_question in memory:
                d[focal_question].add(prior_question)
        return DAG(self._indexify(d))
