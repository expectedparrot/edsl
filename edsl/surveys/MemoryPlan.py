from collections import UserDict, defaultdict
from edsl.surveys.Memory import Memory

from edsl.prompts.Prompt import Prompt
from edsl.surveys.DAG import DAG


class MemoryPlan(UserDict):
    """A survey has a memory plan that specifies what the agent should remember when answering a question.
    {focal_question: [prior_questions], focal_question: [prior_questions]}
    """

    def __init__(self, survey: "Survey" = None, data=None):
        if survey is not None:
            self.survey = survey
            self.survey_question_names = [q.question_name for q in survey.questions]
            self.question_texts = [q.question_text for q in survey.questions]
        super().__init__(data or {})

    @property
    def name_to_text(self):
        "Returns a dictionary mapping question names to question texts"
        return dict(zip(self.survey_question_names, self.question_texts))

    def add_question(self, question):
        self.survey_question_names.append(question.question_name)
        self.question_texts.append(question.question_text)

    def check_valid_question_name(self, question_name):
        "Make sure a passed question name is valid"
        if question_name not in self.survey_question_names:
            raise ValueError(
                f"{question_name} is not in the survey. Current names are {self.survey_question_names}"
            )

    def get_memory_prompt_fragment(self, focal_question, answers) -> "Prompt":
        "Generates the prompt fragment"
        self.check_valid_question_name(focal_question)

        if focal_question not in self:
            return Prompt("")

        q_and_a_pairs = [
            (self.name_to_text[question_name], answers.get(question_name, None))
            for question_name in self[focal_question]
        ]

        base_prompt_text = """
        Before the question you are now answering, you already answering the following questions:
        """

        def gen_line(question_text, answer):
            "Returns a line of memory"
            return f"\tQuestion: {question_text}\n\tAnswer: {answer}\n"

        lines = [gen_line(*pair) for pair in q_and_a_pairs]
        if lines:
            return Prompt(
                base_prompt_text + "\n Prior questions and answers:".join(lines)
            )
        else:
            return Prompt("")

    def check_order(self, focal_question, prior_question):
        focal_index = self.survey_question_names.index(focal_question)
        prior_index = self.survey_question_names.index(prior_question)
        if focal_index <= prior_index:
            raise ValueError(f"{prior_question} must come before {focal_question}.")

    def add_single_memory(self, focal_question: str, prior_question: str):
        self.check_valid_question_name(focal_question)
        self.check_valid_question_name(prior_question)
        self.check_order(focal_question, prior_question)

        if focal_question not in self:
            memory = Memory()
            memory.add_prior_question(prior_question)
            self[focal_question] = memory
        else:
            self[focal_question].add_prior_question(prior_question)

    def add_memory_collection(self, focal_question, prior_questions: list[str]):
        for question in prior_questions:
            self.add_single_memory(focal_question, question)

    def to_dict(self):
        return {
            "survey_question_names": self.survey_question_names,
            "survey_question_texts": self.question_texts,
            "data": {k: v.to_dict() for k, v in self.items()},
        }

    @classmethod
    def from_dict(cls, data):
        # we avoid serializing the survey
        memory_plan = cls(survey=None, data=data["data"])
        memory_plan.survey_question_names = data["survey_question_names"]
        memory_plan.question_texts = data["survey_question_texts"]
        # memory_plan.data = data
        return memory_plan

    def _indexify(self, d):
        new_d = {}
        for k, v in d.items():
            key = self.survey_question_names.index(k)
            new_v = set({self.survey_question_names.index(q) for q in v})
            new_d[key] = new_v
        return new_d

    @property
    def dag(self):
        d = defaultdict(set)
        "Returns a directed acyclic graph of the memory plan"
        for focal_question, memory in self.items():
            for prior_question in memory:
                d[focal_question].add(prior_question)
                # if focal_question not in d:
                #     d[focal_question] = set({prior_question})
                # else:
                #     d[focal_question].add(prior_question)
        # focal_index = self.survey_question_names.index(focal_question)
        # prior_index = self.survey_question_names.index(prior_question)
        return DAG(self._indexify(d))
