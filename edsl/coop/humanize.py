from dataclasses import dataclass
from typing import Optional


@dataclass
class SurveyItemConfig:
    """
    This is a config class for a survey item (question or instruction).

    Args:
        show_for_scenarios (Optional[list[int]]): A list of scenario indices that the survey item should be shown for.

        If None, the survey item will be shown for all scenarios.

        Note: This parameter is only relevant when you have a sampling config
        where `num_scenarios` >= 1. It is mainly useful for instructions, and for questions that
        should only be shown once, like demographics.

        Say that each user will see 3 scenarios. Show the introduction before the first scenario only:
        >>> SurveyItemConfig(show_for_scenarios=[0])

        Show the conclusion after the last scenario only:
        >>> SurveyItemConfig(show_for_scenarios=[2])
    """

    show_for_scenarios: Optional[list[int]] = None

    def to_dict(self):
        return {
            "show_for_scenarios": self.show_for_scenarios,
        }


@dataclass
class OrderedSamplingConfig:
    """
    This is a config class for ordered sampling.

    Scenarios are drawn in groups of x (where x is `num_scenarios`), following
    the order in which the ScenarioList was initially constructed.

    Args:
        num_scenarios (int): Number of scenarios given to each participant.
        randomize_within_chunk (bool): Whether to randomize the order within each chunk.
        shuffle_on_exhaustion (bool): Whether to shuffle and restart when all scenarios are exhausted.
    """

    num_scenarios: int = 1
    randomize_within_chunk: bool = False
    shuffle_on_exhaustion: bool = False

    def to_dict(self):
        return {
            "sampling_method": "ordered",
            "num_scenarios": self.num_scenarios,
            "randomize_within_chunk": self.randomize_within_chunk,
            "shuffle_on_exhaustion": self.shuffle_on_exhaustion,
        }


@dataclass
class RandomSamplingConfig:
    """
    This is a config class for random sampling.

    Args:
        num_scenarios (int): Number of scenarios given to each participant.
        replace_within_chunk (bool): Whether to allow replacement when sampling within a chunk.
        replace_within_list (bool): Whether to allow replacement when sampling from the entire list.
    """

    num_scenarios: int = 1
    replace_within_chunk: bool = True
    replace_within_list: bool = True

    def to_dict(self):
        return {
            "sampling_method": "random",
            "num_scenarios": self.num_scenarios,
            "replace_within_chunk": self.replace_within_chunk,
            "replace_within_list": self.replace_within_list,
        }
