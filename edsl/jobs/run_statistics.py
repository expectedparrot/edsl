import asyncio
from enum import Enum
from typing import Literal, List, Type, DefaultDict
from collections import UserDict, defaultdict

from edsl.jobs.tasks.task_management import InterviewStatusDictionary
from edsl.jobs.token_tracking import InterviewTokenUsage
from edsl.jobs.pricing import pricing, TokenPricing
from edsl.jobs.tasks.task_status_enum import TaskStatus

InterviewTokenUsageMapping = DefaultDict[str, InterviewTokenUsage]

class InterviewStatistic(UserDict):

    @staticmethod
    def _format_number(number, digits=0, units=""):
        """Format a number.

        :param number: the number to format
        :param digits: the number of digits to display
        :param units: the units to display
        
        Example usage: 

        >>> InterviewStatistic._format_number(1000, 1, "sec.")
        '1,000.0 sec.'
        """
        if type(number) == str:
            return number
        else:
            return f"{number:,.{digits}f}" + " " + units

    @property
    def _pretty_name(self):
        """Return a pretty name for the statistic.
        
        Example usage:

        >>> InterviewStatistic("elapsed_time", value=100, digits=1, units="sec.").pretty_name
        'Elapsed time'
        """
        return self.name.replace("_", " ").capitalize()

    def __init__(self, 
                 name: str, 
                 value: float, 
                 digits:int =0, 
                 units: str="", 
                 pretty_name: str = None):
        """Create a new InterviewStatistic object."""
        self.name = name
        self.value = value
        self.digits = digits
        self.units = units
        self.pretty_name = pretty_name or self._pretty_name

        super().__init__(
            {self.pretty_name: self._format_number(self.value, self.digits, self.units)}
        )

        self.raw: dict = {self.name: self.value}


class InterviewStatisticsCollection(UserDict):
    """A collection of interview statistics."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.raw: dict = {}

    def add_stat(self, statistic: InterviewStatistic):
        """Add a statistic to the collection.

        Each statistic is a dictionary with a single key-value pair.
    
        Example usage:

        >>> isc = InterviewStatisticsCollection()
        >>> isc.add_stat(InterviewStatistic("elapsed_time", value=100, digits=1, units="sec."))
        >>> isc.raw
        {'elapsed_time': 100}
        """
        self.update(statistic)
        self.raw.update(statistic.raw)

class JobsRunnerStatusData:
    pricing = pricing

    def status_dict(self, interviews):
 
        status = []
        for interview in interviews:
            #model = interview.model
            status.append(interview.interview_status)

        return status
        #return model_to_status

    def status_counts(self, interviews):

        model_to_status = defaultdict(InterviewStatusDictionary)

        for interview in interviews:
            model = interview.model
            model_to_status[model] += interview.interview_status

        #breakpoint()
        return model_to_status.values()

    def generate_status_summary(
        self,
        completed_tasks: List[Type[asyncio.Task]],
        elapsed_time: float,
        interviews: List[Type["Interview"]],
    ) -> InterviewStatisticsCollection:
        """Generate a summary of the status of the job runner.

        :param completed_tasks: list of completed tasks
        :param elapsed_time: time elapsed since the start of the job
        :param interviews: list of interviews to be conducted
        """

        models_to_tokens = defaultdict(InterviewTokenUsage)
        model_to_status = defaultdict(InterviewStatusDictionary)

        waiting_dict = defaultdict(int)

        interview_statistics = InterviewStatisticsCollection()

        for interview in interviews:
            model = interview.model
            models_to_tokens[model] += interview.token_usage
            model_to_status[model] += interview.interview_status
            waiting_dict[model] += interview.interview_status.waiting

        interview_statistics.add_stat(
            InterviewStatistic("elapsed_time", value=elapsed_time, digits=1, units="sec.")
        )
        interview_statistics.add_stat(
            InterviewStatistic("total_interviews_requested", value=len(interviews), units="")
        )
        interview_statistics.add_stat(
            InterviewStatistic("completed_interviews", value=len(completed_tasks), units="")
        )
        interview_statistics.add_stat(
            InterviewStatistic(
                "percent_complete",
                value = len(completed_tasks) / len(interviews) * 100
                if len(interviews) > 0
                else "NA",
                digits=0,
                units="%",
            )
        )
        interview_statistics.add_stat(
            InterviewStatistic(
                "average_time_per_interview",
                value = elapsed_time / len(completed_tasks) if completed_tasks else "NA",
                digits=1,
                units="sec.",
            )
        )
        interview_statistics.add_stat(
            InterviewStatistic(
                "task_remaining", value=len(interviews) - len(completed_tasks), units=""
            )
        )
        interview_statistics.add_stat(
            InterviewStatistic(
                "estimated_time_remaining",
                value = (len(interviews) - len(completed_tasks))
                * (elapsed_time / len(completed_tasks) if len(completed_tasks) > 0 else "NA"),
                digits=1,
                units="sec.",
            )
        )
        model_queues_info = []
        for model, num_waiting in waiting_dict.items():
            model_info = self._get_model_info(model, num_waiting, models_to_tokens)
            model_queues_info.append(model_info)

        interview_statistics["model_queues"] = model_queues_info

        return interview_statistics

    def _get_model_info(
        self,
        model: str,
        num_waiting: int,
        models_to_tokens: InterviewTokenUsageMapping,
    ):
        """Get the status of a model."""
        if model.model not in self.pricing:
            raise ValueError(f"Model {model.model} not found in pricing")

        prices = self.pricing[model.model]

        model_info = {
            "model_name": model.model,
            "TPM_limit_k": model.TPM / 1000,
            "RPM_limit_k": model.RPM / 1000,
            "num_tasks_waiting": num_waiting,
            "token_usage_info": [],
        }

        token_usage_types = ["new_token_usage", "cached_token_usage"]
        for token_usage_type in token_usage_types:
            cache_info = self._get_token_usage_info(
                token_usage_type, models_to_tokens, model, prices
            )
            model_info["token_usage_info"].append(cache_info)

        return model_info

    def _get_token_usage_info(
        self,
        cache_status: Literal["new_token_usage", "cached_token_usage"],
        models_to_tokens: InterviewTokenUsageMapping,
        model: str,
        prices: TokenPricing,
    ):
        cache_info = {"cache_status": cache_status, "details": []}
        token_usage = getattr(models_to_tokens[model], cache_status)
        for token_type in ["prompt_tokens", "completion_tokens"]:
            tokens = getattr(token_usage, token_type)
            cache_info["details"].append(
                {
                    "type": token_type,
                    "tokens": tokens,
                    "cost": f"${token_usage.cost(prices):.5f}",
                }
            )
        return cache_info


def enum_converter(obj):
    if isinstance(obj, Enum):
        return obj.name  # or obj.value if you prefer the enum's value
    raise TypeError(f"Object of type {obj.__class__.__name__} is not JSON serializable")


if __name__ == "__main__":
    #pass
    import doctest
    doctest.testmod()
    # Create a JobsRunHistory object
    # jrh = JobsRunHistory()

    # # Add some data to it
    # jrh.append({"elapsed_time": 0, "completed_interviews": 0})
    # jrh.append({"elapsed_time": 1, "completed_interviews": 1})
    # jrh.append({"elapsed_time": 2, "completed_interviews": 2})

    # # Save the data to a file
    # jrh.to_json("jobs_run_history.json")

    # # Read the data from the file
    # jrh2 = JobsRunHistory.from_json("jobs_run_history.json")

    # # Plot the data
    # jrh2.plot_completion_times()