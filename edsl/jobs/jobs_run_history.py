import json
import asyncio
from enum import Enum
from typing import Literal, List, Type, DefaultDict
from collections import UserDict, defaultdict

from edsl.jobs.task_management import InterviewStatusDictionary
from edsl.jobs.token_tracking import InterviewTokenUsage
from edsl.jobs.pricing import pricing, TokenPricing
from edsl.jobs.task_status_enum import TaskStatus

InterviewTokenUsageMapping = DefaultDict[str, InterviewTokenUsage]

class InterviewStatistic(UserDict):

    @staticmethod
    def _format_number(number, digits=0, units=""):
        """Format a number."""
        if type(number) == str:
            return number
        else:
            return f"{number:,.{digits}f}" + " " + units

    @property
    def _pretty_name(self):
        return self.name.replace("_", " ").capitalize()

    def __init__(self, 
                 name: str, 
                 value: float, 
                 digits:int =0, 
                 units: str="", 
                 pretty_name: str = None):
        self.name = name
        self.value = value
        self.digits = digits
        self.units = units
        self.pretty_name = pretty_name or self._pretty_name

        super().__init__(
            {self.pretty_name: self._format_number(self.value, self.digits, self.units)}
        )

        self.raw = {self.name: self.value}


class InterviewStatisticsCollection(UserDict):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.raw = {}

    def add_stat(self, statistic: InterviewStatistic):
        """Add a statistic to the collection.
        
        Each statistic is a dictionary with a single key-value pair.
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


class JobsRunHistory:
    """A class to store the history of jobs run.
    
    -- Task failures and tracebacks
    -- Response headers from API calls
    -- Log each time an Interview is completed 

    Methods: 
    --- Visualization tools

    """

    def __init__(self, data = None):
        self.data = data or {}
        #self.interview_status_updates = interview_status_updates or []
        #self.completed_interview_updates = completed_interview_updates or []    
    
        self.entries = 0 
        self.status_functions = {
            "status_dic": self.status_dict, 
            "status_counts": self.status_counts, 
            "time": self.log_time,
            "exceptions": self.exceptions_dict,
            }

    def log(self, JobRunner, completed_tasks, elapsed_time):
        """Log the status of the job runner."""

        self.entries += 1

        for name, f in self.status_functions.items():
            entry = f(JobRunner, completed_tasks, elapsed_time)
            if name not in self.data:
                self.data[name] = []
            self.data[name].append(entry)

    def log_time(self, JobRunner, completed_tasks, elapsed_time):
        return elapsed_time

    def status_dict(self, JobRunner, completed_tasks, elapsed_time):
        status = []
        for index, interview in enumerate(JobRunner.total_interviews):
            status.append(interview.interview_status)
        return (elapsed_time, index, status)
    
    def exceptions_dict(self, JobRunner, completed_tasks, elapsed_time):
        exceptions = []
        for index, interview in enumerate(JobRunner.total_interviews):
            if interview.has_exceptions:
                exceptions.append(interview.exceptions)
        return (elapsed_time, index, exceptions)

    def status_counts(self, JobRunner, completed_tasks, elapsed_time):
        model_to_status = defaultdict(InterviewStatusDictionary)
        for index, interview in enumerate(JobRunner.total_interviews):
            model = interview.model
            model_to_status[model] += interview.interview_status
        return (elapsed_time, index, model_to_status)
    

    def to_dict(self):
        #breakpoint()
        d = {}
        for key, value in self.data.items():
            d[key] = [t for t in value]
        return d

        # return {"interview_status_updates": [t.to_dict() for t in self.interview_status_updates],
        #         "completed_interview_updates":[t.to_dict() for t in self.completed_interview_updates]}
    
    def to_json(self, json_file):
        with open(json_file, "w") as file:
            #json.dump(self.data, file, default=enum_converter)
            json.dump(obj = self.to_dict(), fp = file)

    @classmethod
    def from_json(cls, json_file):
        with open(json_file, "r") as file:
            data = json.load(file)
        return cls(data = data)

    def plot_completion_times(self):
        """Plot the completion times."""
        from matplotlib import pyplot as plt
        x = [item for item in self.data['time']]

        status_counts = [(time, list(d.values())[0]) for time, d in self.data['status_counts']]
        status_counts.sort(key=lambda x: x[0])
        #breakpoint()
        
        #y = [item[TaskStatus.NOT_STARTED] for item in status_counts]
        #breakpoint()
        #plt.figure(figsize=(10, 6))
        
        rows = int(len(TaskStatus) ** 0.5) + 1
        cols = (len(TaskStatus) + rows - 1) // rows  # Ensure all plots fit

        plt.figure(figsize=(15, 10))  # Adjust the figure size as needed

        for i, status in enumerate(TaskStatus, start=1):
            plt.subplot(rows, cols, i)
            x = [item[0] for item in status_counts]
            y = [item[1].get(status, 0) for item in status_counts]  # Use .get() to handle missing keys safely
            plt.plot(x, y, marker='o', linestyle='-')
            plt.title(status.name)
            plt.xlabel('Elapsed Time')
            plt.ylabel('Count')
            plt.grid(True)
        
        plt.tight_layout()
        plt.show()
        # for status in TaskStatus:
        #     # Generate y-values for the current status
        #     y = [item.get(status, 0) for item in status_counts]
        #     print(status.name)
        #     # Plot the line for the current status
        #     plt.plot(x, y, marker='o', linestyle='-', label=status.name)

        # Creating the plot
        #plt.figure(figsize=(10, 6))
        #plt.plot(x, y, marker='o', linestyle='-', color='blue')
        # plt.title('Completed Interviews Over Time')
        # plt.xlabel('Elapsed Time')
        # plt.ylabel('Completed Interviews')
        # plt.grid(True)
        # plt.legend()
        # plt.show()


if __name__ == "__main__":
    # Create a JobsRunHistory object
    jrh = JobsRunHistory()

    # Add some data to it
    jrh.append({"elapsed_time": 0, "completed_interviews": 0})
    jrh.append({"elapsed_time": 1, "completed_interviews": 1})
    jrh.append({"elapsed_time": 2, "completed_interviews": 2})

    # Save the data to a file
    jrh.to_json("jobs_run_history.json")

    # Read the data from the file
    jrh2 = JobsRunHistory.from_json("jobs_run_history.json")

    # Plot the data
    jrh2.plot_completion_times()