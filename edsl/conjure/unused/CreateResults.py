from edsl.surveys.Survey import Survey
from edsl.agents.AgentList import AgentList


class CreateResults:
    def __init__(self, survey: Survey, agents: AgentList):
        self.survey = survey
        self.agents = agents

    def __call__(self):
        return self.survey.by(self.agents).run()
