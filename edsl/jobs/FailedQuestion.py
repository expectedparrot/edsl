from edsl.questions import QuestionBase
from edsl import Question, Scenario, Model, Agent

from edsl.language_models.LanguageModel import LanguageModel


class FailedQuestion:
    # tests/jobs/test_Interview.py::test_handle_model_exceptions

    # (Pdb) dir(self.exception.__traceback__)
    # ['tb_frame', 'tb_lasti', 'tb_lineno', 'tb_next']

    def __init__(
        self, question, scenario, model, agent, raw_model_response, exception, prompts
    ):
        self.question = question
        self.scenario = scenario
        self.model = model
        self.agent = agent
        self.raw_model_response = raw_model_response  # JSON
        self.exception = exception
        self.prompts = prompts

    def to_dict(self):
        return {
            "question": self.question._to_dict(),
            "scenario": self.scenario._to_dict(),
            "model": self.model._to_dict(),
            "agent": self.agent._to_dict(),
            "raw_model_response": self.raw_model_response,
            "exception": self.exception.__class__.__name__,  # self.exception,
            "prompts": self.prompts,
        }

    @classmethod
    def from_dict(cls, data):
        question = QuestionBase.from_dict(data["question"])
        scenario = Scenario.from_dict(data["scenario"])
        model = LanguageModel.from_dict(data["model"])
        agent = Agent.from_dict(data["agent"])
        raw_model_response = data["raw_model_response"]
        exception = data["exception"]
        prompts = data["prompts"]
        return cls(
            question, scenario, model, agent, raw_model_response, exception, prompts
        )

    def __repr__(self):
        return f"{self.__class__.__name__}(question={repr(self.question)}, scenario={repr(self.scenario)}, model={repr(self.model)}, agent={repr(self.agent)}, raw_model_response={repr(self.raw_model_response)}, exception={repr(self.exception)})"

    @property
    def jobs(self):
        return self.question.by(self.scenario).by(self.agent).by(self.model)

    def rerun(self):
        results = self.jobs.run()
        return results

    def help(self):
        pass

    @classmethod
    def example(cls):
        from edsl.language_models.utilities import create_language_model
        from edsl.language_models.utilities import create_survey

        survey = create_survey(2, chained=False, take_scenario=False)
        fail_at_number = 1
        model = create_language_model(ValueError, fail_at_number)()
        from edsl import Survey

        results = survey.by(model).run()
        return results.failed_questions[0][0]


if __name__ == "__main__":
    fq = FailedQuestion.example()
    new_fq = FailedQuestion.from_dict(fq.to_dict())
