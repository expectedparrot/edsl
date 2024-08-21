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
        self.raw_model_response = raw_model_response
        self.exception = exception
        self.prompts = prompts

    def __repr__(self):
        return f"{self.__class__.__name__}(question={repr(self.question)}, scenario={repr(self.scenario)}, model={repr(self.model)}, agent={repr(self.agent)}, raw_model_response={repr(self.raw_model_response)}, exception={repr(self.exception)})"

    def jobs(self):
        return self.question.by(self.scenario).by(self.agent).by(self.model)

    def rerun(self):
        results = self.jobs.run()
        return results

    def help(self):
        pass
