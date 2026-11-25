"""Hugging Face Hub source (optional edsl[hf] dependencies)."""

from .base import Source


class HuggingFaceSource(Source):
    """Read an EDSL config or the train rows of an ordinary HF dataset."""

    source_type = "huggingface"

    def __init__(self, repo_id, *, config_name=None, revision=None, token=None):
        self.repo_id = repo_id
        self.config_name = config_name
        self.revision = revision
        self.token = token

    def to_scenario_list(self):
        from ..scenario_list import ScenarioList

        return ScenarioList.from_hf(
            self.repo_id,
            config_name=self.config_name,
            revision=self.revision,
            token=self.token,
        )

    @classmethod
    def example(cls):
        # Keep the source registry's example suite offline and dependency-free.
        from ..scenario import Scenario
        from ..scenario_list import ScenarioList

        source = cls("edsl/example")
        source.to_scenario_list = lambda: ScenarioList(
            [Scenario({"text": "Example HF row"})]
        )
        return source
