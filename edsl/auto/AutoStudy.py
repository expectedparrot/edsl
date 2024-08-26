from typing import Optional

from edsl import Model
from edsl.auto.StageQuestions import StageQuestions
from edsl.auto.StagePersona import StagePersona
from edsl.auto.StagePersonaDimensions import StagePersonaDimensions
from edsl.auto.StagePersonaDimensionValues import StagePersonaDimensionValues
from edsl.auto.StagePersonaDimensionValueRanges import (
    StagePersonaDimensionValueRanges,
)
from edsl.auto.StageLabelQuestions import StageLabelQuestions
from edsl.auto.StageGenerateSurvey import StageGenerateSurvey

# from edsl.auto.StageBase import gen_pipeline

from edsl.auto.utilities import agent_generator, create_agents, gen_pipeline


class AutoStudy:
    def __init__(
        self,
        overall_question: str,
        population: str,
        model: Optional["Model"] = None,
        survey: Optional["Survey"] = None,
        agent_list: Optional["AgentList"] = None,
        default_num_agents=11,
    ):
        self.overall_question = overall_question
        self.population = population
        self._survey = survey
        self._agent_list = agent_list
        self._agent_list_generator = None
        self._persona_mapping = None
        self._results = None
        self.default_num_agents = default_num_agents
        self.model = model or Model()

    @property
    def survey(self):
        if self._survey is None:
            self._survey = self._create_survey()
        return self._survey

    @property
    def persona_mapping(self):
        if self._persona_mapping is None:
            self._persona_mapping = self._create_persona_mapping()
        return self._persona_mapping

    @property
    def agent_list_generator(self):
        if self._agent_list_generator is None:
            self._agent_list_generator = self._create_agent_list_generator()
        return self._agent_list_generator

    @property
    def results(self):
        if self._results is None:
            self._results = self._create_results()
        return self._results

    def _create_survey(self):
        survey_pipline_stages = [
            StageQuestions,
            StageLabelQuestions,
            StageGenerateSurvey,
        ]
        survey_pipeline = gen_pipeline(survey_pipline_stages)
        return survey_pipeline.process(
            data=survey_pipeline.input(
                overall_question=self.overall_question, population=self.population
            )
        ).survey

    def _create_persona_mapping(self):
        persona_pipeline_stages = [
            StageQuestions,
            StagePersona,
            StagePersonaDimensions,
            StagePersonaDimensionValues,
            StagePersonaDimensionValueRanges,
        ]

        persona_pipeline = gen_pipeline(persona_pipeline_stages)
        sample_agent_results = persona_pipeline.process(
            persona_pipeline.input(
                overall_question=overall_question, population=self.population
            )
        )
        return sample_agent_results

    def _create_agent_list_generator(self):
        return agent_generator(
            persona=self.persona_mapping.persona,
            dimension_dict=self.persona_mapping.mapping,
        )

    def agent_list(self, num_agents):
        return create_agents(
            agent_generator=self.agent_list_generator,
            survey=self.survey,
            num_agents=num_agents,
        )

    def _create_results(self, num_agents=None):
        if num_agents is None:
            num_agents = self.default_num_agents
        agent_list = self.agent_list(num_agents)
        return self.survey.by(agent_list).by(self.model).run()


if __name__ == "__main__":
    overall_question = "Should online platforms be regulated with respect to selling electric scooters?"
    auto_study = AutoStudy(overall_question, population="US Adults")

    results = auto_study.results
