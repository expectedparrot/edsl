"""
This module provides the TaskHistory class for tracking and analyzing task execution history.

The TaskHistory class maintains a record of all interviews conducted by EDSL, including
their task execution histories, exceptions, and performance metrics. It supports rich
visualization and reporting to help users understand task execution patterns and diagnose
issues.
"""

from typing import List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ..interviews import Interview
from io import BytesIO
import base64
import os
import tempfile

from .task_status_enum import TaskStatus
from ..base import RepresentationMixin


class TaskHistory(RepresentationMixin):
    """
    Records and analyzes the execution history of tasks across multiple interviews.

    The TaskHistory class serves as a central repository for tracking task execution
    across multiple interviews. It provides methods for:

    1. Error Analysis - Collecting, categorizing, and reporting exceptions
    2. Execution Visualization - Generating plots of task status over time
    3. Performance Metrics - Calculating timing statistics for tasks
    4. HTML Reports - Creating detailed interactive reports of execution

    This class is particularly useful for debugging complex interview workflows,
    identifying performance bottlenecks, and understanding patterns in task execution.
    It supports both interactive exploration in notebooks and standalone report
    generation.

    Key features:
    - Tracks exceptions with optional traceback storage
    - Provides visualizations of task status transitions
    - Generates interactive HTML reports with filtering and drill-down
    - Computes statistics across interviews (by model, question type, etc.)
    - Exports to various formats (HTML, notebook, etc.)
    - Memory optimization via offloading of large file content
    """

    def __init__(
        self,
        interviews: List["Interview"] = None,
        include_traceback: bool = False,
        max_interviews: int = 10,
        interviews_with_exceptions_only: bool = False,
    ):
        """
        Initialize a TaskHistory to track execution across multiple interviews.

        Parameters:
            interviews: List of Interview objects to track
            include_traceback: Whether to include full exception tracebacks
            max_interviews: Maximum number of interviews to display in reports
            interviews_with_exceptions_only: If True, only track interviews with exceptions

        Example:
            >>> _ = TaskHistory.example()  # Create a sample TaskHistory
        """
        self.interviews_with_exceptions_only = interviews_with_exceptions_only
        self._interviews = {}
        self.total_interviews = []
        if interviews is not None:
            for interview in interviews:
                self.add_interview(interview)

        self.include_traceback = include_traceback
        self._interviews = {
            index: interview for index, interview in enumerate(self.total_interviews)
        }
        self.max_interviews = max_interviews

        self.include_traceback = include_traceback

        self.max_interviews = max_interviews

    def add_interview(self, interview: "Interview"):
        """Add a single interview to the history"""
        if self.interviews_with_exceptions_only and interview.exceptions == {}:
            return

        # Store only essential data from the interview to break strong reference
        # Instead of a deep copy, we create a lightweight reference holder
        class InterviewReference:
            def __init__(self, interview: "Interview"):
                # Store only the data we need for reporting
                self.exceptions = interview.exceptions
                self.task_status_logs = interview.task_status_logs
                self.model = interview.model
                self.survey = interview.survey

                # Store metadata needed for serialization
                self._interview_id = id(interview)

            def to_dict(self, add_edsl_version=True):
                """Create a serializable representation of the interview reference"""
                # Create a simplified dict that has the required fields but doesn't
                # maintain a strong reference to the original interview
                data = {
                    "id": self._interview_id,
                    "type": "InterviewReference",
                    "exceptions": (
                        self.exceptions.to_dict()
                        if hasattr(self.exceptions, "to_dict")
                        else {}
                    ),
                    "task_status_logs": {
                        name: log.to_dict() if hasattr(log, "to_dict") else {}
                        for name, log in self.task_status_logs.items()
                    },
                }

                # Add model and survey info if they have to_dict methods
                if hasattr(self.model, "to_dict"):
                    data["model"] = self.model.to_dict(
                        add_edsl_version=add_edsl_version
                    )

                if hasattr(self.survey, "to_dict"):
                    data["survey"] = self.survey.to_dict(
                        add_edsl_version=add_edsl_version
                    )

                if add_edsl_version:
                    from edsl import __version__

                    data["edsl_version"] = __version__

                return data

            def __getattr__(self, name):
                # Handle any missing attributes by returning None
                # This provides compatibility with code that might access
                # other interview attributes we haven't explicitly stored
                return None

        # Create a reference object instead of keeping the full interview
        interview_ref = InterviewReference(interview)

        self.total_interviews.append(interview_ref)
        self._interviews[len(self._interviews)] = interview_ref

    @classmethod
    def example(cls):
        """ """
        from ..jobs import Jobs

        j = Jobs.example(throw_exception_probability=1, test_model=True)

        results = j.run(
            print_exceptions=False,
            skip_retry=True,
            cache=False,
            raise_validation_errors=True,
            disable_remote_cache=True,
            disable_remote_inference=True,
        )

        return cls(results.task_history.total_interviews)

    @property
    def exceptions(self):
        """
        >>> len(TaskHistory.example().exceptions)
        4
        """
        return [i.exceptions for k, i in self._interviews.items() if i.exceptions != {}]

    @property
    def unfixed_exceptions(self):
        """
        >>> len(TaskHistory.example().unfixed_exceptions)
        4
        """
        return [
            i.exceptions
            for k, i in self._interviews.items()
            if i.exceptions.num_unfixed() > 0
        ]

    @property
    def indices(self):
        return [k for k, i in self._interviews.items() if i.exceptions != {}]

    def __repr__(self):
        """Return a string representation of the TaskHistory."""
        return f"TaskHistory(interviews={self.total_interviews})."

    def to_dict(self, add_edsl_version=True, offload_content=False):
        """
        Return the TaskHistory as a dictionary.

        Parameters:
            add_edsl_version: Whether to include EDSL version in the output
            offload_content: Whether to offload large file content like videos and images
                            to reduce memory usage

        Returns:
            A dictionary representation of this TaskHistory instance
        """
        # Offload large file content if requested
        if offload_content:
            self.offload_files_content()

        # Serialize each interview object
        interview_dicts = []
        for i in self.total_interviews:
            # Use to_dict method if available
            if hasattr(i, "to_dict"):
                try:
                    interview_dicts.append(i.to_dict(add_edsl_version=add_edsl_version))
                except Exception:
                    # Fallback if to_dict fails
                    interview_dicts.append(
                        {
                            "type": "InterviewReference",
                            "exceptions": getattr(i, "exceptions", {}),
                            "task_status_logs": getattr(i, "task_status_logs", {}),
                        }
                    )
            else:
                # Fallback if no to_dict method
                interview_dicts.append(
                    {
                        "type": "InterviewReference",
                        "exceptions": getattr(i, "exceptions", {}),
                        "task_status_logs": getattr(i, "task_status_logs", {}),
                    }
                )

        d = {
            "interviews": interview_dicts,
            "include_traceback": self.include_traceback,
        }

        if add_edsl_version:
            from .. import __version__

            d["edsl_version"] = __version__
            d["edsl_class_name"] = "TaskHistory"
        return d

    @classmethod
    def from_dict(cls, data: dict):
        """Create a TaskHistory from a dictionary."""
        if data is None:
            return cls([], include_traceback=False)

        # Create an instance without interviews
        instance = cls([], include_traceback=data.get("include_traceback", False))

        # Create a custom interview-like object for each serialized interview
        for interview_data in data.get("interviews", []):
            # Check if this is one of our InterviewReference objects
            if (
                isinstance(interview_data, dict)
                and interview_data.get("type") == "InterviewReference"
            ):
                # Create our InterviewReference directly
                class DeserializedInterviewRef:
                    def __init__(self, data):
                        # Convert exceptions dictionary to InterviewExceptionCollection
                        from ..interviews.exception_tracking import (
                            InterviewExceptionCollection,
                        )

                        # Store the original data in full
                        self._original_data = data

                        # Preserve the original interview id
                        self._interview_id = data.get("id", None)

                        # Store exceptions using the original data structure
                        # This ensures when we re-serialize, we keep original data intact
                        self._exceptions_data = data.get("exceptions", {})

                        # Create the InterviewExceptionCollection for runtime use
                        exceptions_data = data.get("exceptions", {})
                        self.exceptions = (
                            InterviewExceptionCollection.from_dict(exceptions_data)
                            if exceptions_data
                            else InterviewExceptionCollection()
                        )

                        # Store other fields
                        self.task_status_logs = data.get("task_status_logs", {})
                        self.model = data.get("model", {})
                        self.survey = data.get("survey", {})

                    def to_dict(self, add_edsl_version=True):
                        # Use the original exceptions data structure when serializing again
                        # This preserves all exception details exactly as they were
                        data = {
                            "type": "InterviewReference",
                            "exceptions": (
                                self._exceptions_data
                                if hasattr(self, "_exceptions_data")
                                else (
                                    self.exceptions.to_dict()
                                    if hasattr(self.exceptions, "to_dict")
                                    else self.exceptions
                                )
                            ),
                            "task_status_logs": self.task_status_logs,
                            "model": self.model,
                            "survey": self.survey,
                        }

                        # Preserve the original interview id if it exists
                        if self._interview_id:
                            data["id"] = self._interview_id

                        # Preserve original version info
                        if (
                            add_edsl_version
                            and hasattr(self, "_original_data")
                            and "edsl_version" in self._original_data
                        ):
                            data["edsl_version"] = self._original_data["edsl_version"]

                        return data

                # Create the reference and add it directly
                ref = DeserializedInterviewRef(interview_data)
                instance.total_interviews.append(ref)
                instance._interviews[len(instance._interviews)] = ref
            else:
                # For backward compatibility, try to use Interview class
                try:
                    from ..interviews import Interview

                    interview = Interview.from_dict(interview_data)
                    # This will make a reference copy through add_interview
                    instance.add_interview(interview)
                except Exception:
                    # If we can't deserialize properly, add a minimal placeholder
                    class MinimalInterviewRef:
                        def __init__(self):
                            from ..interviews.exception_tracking import (
                                InterviewExceptionCollection,
                            )

                            self.exceptions = InterviewExceptionCollection()
                            self.task_status_logs = {}

                        def to_dict(self, add_edsl_version=True):
                            return {"type": "MinimalInterviewRef"}

                    ref = MinimalInterviewRef()
                    instance.total_interviews.append(ref)
                    instance._interviews[len(instance._interviews)] = ref

        return instance

    @property
    def has_exceptions(self) -> bool:
        """Return True if there are any exceptions.

        >>> TaskHistory.example().has_exceptions
        True

        """
        return len(self.exceptions) > 0

    @property
    def has_unfixed_exceptions(self) -> bool:
        """Return True if there are any exceptions."""
        return len(self.unfixed_exceptions) > 0

    def show_exceptions(self, tracebacks=False):
        """Print the exceptions."""
        for index in self.indices:
            self.total_interviews[index].exceptions.print(tracebacks)

    def get_updates(self):
        """Return a list of all the updates."""
        updates = []
        for interview in self.total_interviews:
            # Check if task_status_logs exists and is a dictionary
            if hasattr(interview, "task_status_logs") and isinstance(
                interview.task_status_logs, dict
            ):
                for question_name, logs in interview.task_status_logs.items():
                    updates.append(logs)
        return updates

    def print(self):
        from rich import print

        print(self.get_updates())

    def plot_completion_times(self):
        """Plot the completion times for each task."""
        import matplotlib.pyplot as plt

        updates = self.get_updates()

        elapsed = [update.max_time - update.min_time for update in updates]
        for i, update in enumerate(updates):
            if update[-1]["value"] != TaskStatus.SUCCESS:
                elapsed[i] = 0
        x = range(len(elapsed))
        y = elapsed

        plt.bar(x, y)
        plt.title("Per-interview completion times")
        plt.xlabel("Task")
        plt.ylabel("Time (seconds)")
        plt.show()

    def plotting_data(self, num_periods=100):
        updates = self.get_updates()

        # Handle the case when updates is empty
        if not updates:
            # Return a list of dictionaries with all task statuses set to 0
            return [
                {task_status: 0 for task_status in TaskStatus}
                for _ in range(num_periods)
            ]

        min_t = min([update.min_time for update in updates])
        max_t = max([update.max_time for update in updates])
        delta_t = (max_t - min_t) / (num_periods * 1.0)
        time_periods = [min_t + delta_t * i for i in range(num_periods)]

        def counts(t):
            d = {}
            for update in updates:
                status = update.status_at_time(t)
                if status in d:
                    d[status] += 1
                else:
                    d[status] = 1
            return d

        status_counts = [counts(t) for t in time_periods]

        new_counts = []
        for status_count in status_counts:
            d = {task_status: 0 for task_status in TaskStatus}
            d.update(status_count)
            new_counts.append(d)

        return new_counts

    def plot(self, num_periods=100, get_embedded_html=False):
        """Plot the number of tasks in each state over time."""
        new_counts = self.plotting_data(num_periods)
        max_count = max([max(entry.values()) for entry in new_counts])

        rows = int(len(TaskStatus) ** 0.5) + 1
        cols = (len(TaskStatus) + rows - 1) // rows  # Ensure all plots fit

        import matplotlib.pyplot as plt

        fig, axes = plt.subplots(rows, cols, figsize=(15, 10))
        axes = axes.flatten()  # Flatten in case of a single row/column

        for i, status in enumerate(TaskStatus):
            ax = axes[i]
            x = range(len(new_counts))
            y = [
                item.get(status, 0) for item in new_counts
            ]  # Use .get() to handle missing keys safely
            ax.plot(x, y, marker="o", linestyle="-")
            ax.set_title(status.name)
            ax.set_xlabel("Time Periods")
            ax.set_ylabel("Count")
            ax.grid(True)
            ax.set_ylim(0, max_count)

        # Hide any unused subplots
        for ax in axes[len(TaskStatus) :]:
            ax.axis("off")

        plt.tight_layout()

        if get_embedded_html:
            buffer = BytesIO()
            fig.savefig(buffer, format="png")
            plt.close(fig)
            buffer.seek(0)

            # Encode plot to base64 string
            img_data = base64.b64encode(buffer.getvalue()).decode("utf-8")
            buffer.close()
            return f'<img src="data:image/png;base64,{img_data}" alt="Plot">'
        else:
            plt.show()

    def css(self):
        from importlib import resources

        env = resources.files("edsl").joinpath("templates/error_reporting")
        css = env.joinpath("report.css").read_text()
        return css

    def javascript(self):
        from importlib import resources

        env = resources.files("edsl").joinpath("templates/error_reporting")
        js = env.joinpath("report.js").read_text()
        return js

    # @property
    # def exceptions_table(self) -> dict:
    #     """Return a dictionary of exceptions organized by type, service, model, and question name."""
    #     exceptions_table = {}
    #     for interview in self.total_interviews:
    #         for question_name, exceptions in interview.exceptions.items():
    #             for exception in exceptions:
    #                 key = (
    #                     exception.exception.__class__.__name__,  # Exception type
    #                     interview.model._inference_service_,  # Service
    #                     interview.model.model,  # Model
    #                     question_name,  # Question name
    #                 )
    #                 if key not in exceptions_table:
    #                     exceptions_table[key] = 0
    #                 exceptions_table[key] += 1
    #     return exceptions_table

    @property
    def exceptions_table(self) -> dict:
        """Return a dictionary of unique exceptions organized by type, service, model, and question name."""
        exceptions_table = {}
        seen_exceptions = set()

        for interview in self.total_interviews:
            for question_name, exceptions in interview.exceptions.items():
                for exception in exceptions:
                    # Create a unique identifier for this exception based on its content
                    exception_key = (
                        exception.exception.__class__.__name__,  # Exception type
                        interview.model._inference_service_,  # Service
                        interview.model.model,  # Model
                        question_name,  # Question name
                        exception.name,  # Exception name
                        (
                            str(exception.traceback)[:100]
                            if exception.traceback
                            else ""
                        ),  # Truncated traceback
                    )

                    # Only count if we haven't seen this exact exception before
                    if exception_key not in seen_exceptions:
                        seen_exceptions.add(exception_key)

                        # Add to the summary table
                        table_key = (
                            exception.exception.__class__.__name__,  # Exception type
                            interview.model._inference_service_,  # Service
                            interview.model.model,  # Model
                            question_name,  # Question name
                        )

                        if table_key not in exceptions_table:
                            exceptions_table[table_key] = 0
                        exceptions_table[table_key] += 1

        return exceptions_table

    @property
    def exceptions_by_type(self) -> dict:
        """Return a dictionary of exceptions tallied by type."""
        exceptions_by_type = {}
        for interview in self.total_interviews:
            for question_name, exceptions in interview.exceptions.items():
                for exception in exceptions:
                    exception_type = exception.exception.__class__.__name__
                    if exception_type in exceptions_by_type:
                        exceptions_by_type[exception_type] += 1
                    else:
                        exceptions_by_type[exception_type] = 1
        return exceptions_by_type

    @property
    def exceptions_by_service(self) -> dict:
        """Return a dictionary of exceptions tallied by service."""
        exceptions_by_service = {}
        for interview in self.total_interviews:
            service = interview.model._inference_service_
            if service not in exceptions_by_service:
                exceptions_by_service[service] = 0
            if interview.exceptions != {}:
                exceptions_by_service[service] += len(interview.exceptions)
        return exceptions_by_service

    @property
    def exceptions_by_question_name(self) -> dict:
        """Return a dictionary of exceptions tallied by question name."""
        exceptions_by_question_name = {}
        for interview in self.total_interviews:
            for question_name, exceptions in interview.exceptions.items():
                question_type = interview.survey._get_question_by_name(
                    question_name
                ).question_type
                if (question_name, question_type) not in exceptions_by_question_name:
                    exceptions_by_question_name[(question_name, question_type)] = 0
                exceptions_by_question_name[(question_name, question_type)] += len(
                    exceptions
                )

        for question in self.total_interviews[0].survey.questions:
            if (
                question.question_name,
                question.question_type,
            ) not in exceptions_by_question_name:
                exceptions_by_question_name[
                    (question.question_name, question.question_type)
                ] = 0

        sorted_exceptions_by_question_name = {
            k: v
            for k, v in sorted(
                exceptions_by_question_name.items(),
                key=lambda item: item[1],
                reverse=True,
            )
        }
        return sorted_exceptions_by_question_name

    @property
    def exceptions_by_model(self) -> dict:
        """Return a dictionary of exceptions tallied by model and question name."""
        exceptions_by_model = {}
        for interview in self.total_interviews:
            model = interview.model.model
            service = interview.model._inference_service_
            for question_name, exceptions in interview.exceptions.items():
                key = (service, model, question_name)
                if key not in exceptions_by_model:
                    exceptions_by_model[key] = 0
                exceptions_by_model[key] += len(exceptions)
        return exceptions_by_model

    def generate_html_report(self, css: Optional[str], include_plot=False):
        if include_plot:
            performance_plot_html = self.plot(num_periods=100, get_embedded_html=True)
        else:
            performance_plot_html = ""

        if css is None:
            css = self.css()

        models_used = set([i.model.model for index, i in self._interviews.items()])

        from jinja2 import Environment
        from ..utilities import TemplateLoader

        env = Environment(loader=TemplateLoader("edsl", "templates/error_reporting"))

        # Get current memory usage at this point

        template = env.get_template("base.html")

        # Render the template with data
        output = template.render(
            interviews=self._interviews,
            css=css,
            javascript=self.javascript(),
            num_exceptions=len(self.exceptions),
            performance_plot_html=performance_plot_html,
            exceptions_table=self.exceptions_table,
            exceptions_by_type=self.exceptions_by_type,
            exceptions_by_question_name=self.exceptions_by_question_name,
            exceptions_by_model=self.exceptions_by_model,
            exceptions_by_service=self.exceptions_by_service,
            models_used=models_used,
            max_interviews=self.max_interviews,
        )
        return output

    def html(
        self,
        filename: Optional[str] = None,
        return_link: bool = False,
        css: Optional[str] = None,
        cta: str = "<br><span style='font-size: 18px; font-weight: medium-bold; text-decoration: underline;'>Click to open the report in a new tab</span><br><br>",
        open_in_browser: bool = False,
    ) -> Optional[str]:
        """
        Generate and display an interactive HTML report of task execution.

        This method creates a comprehensive HTML report showing task execution details,
        exceptions, timing information, and statistics across all tracked interviews.
        In notebook environments, it displays an embedded preview with a link to open
        the full report in a new tab.

        Parameters:
            filename: Path to save the HTML report (if None, a temporary file is created)
            return_link: If True, return the path to the saved HTML file
            css: Custom CSS to apply to the report (if None, uses default styling)
            cta: HTML for the "Call to Action" link text
            open_in_browser: If True, automatically open the report in the default browser

        Returns:
            If return_link is True, returns the path to the saved HTML file; otherwise None

        Notes:
            - In Jupyter notebooks, displays an embedded preview with a link
            - In terminal environments, saves the file and prints its location
            - The report includes interactive elements for filtering and drill-down
            - Exception details, status transitions, and timing are all included
        """
        from IPython.display import display, HTML
        import os
        from ..utilities.utilities import is_notebook

        output = self.generate_html_report(css)

        # Save the rendered output to a file
        with open("output.html", "w") as f:
            f.write(output)

        if filename is None:
            current_directory = os.getcwd()
            filename = tempfile.NamedTemporaryFile(
                "w", delete=False, suffix=".html", dir=current_directory
            ).name

        with open(filename, "w") as f:
            with open(filename, "w") as f:
                f.write(output)

        if is_notebook():
            import html

            html_url = f"/files/{filename}"
            html_link = f'<a href="{html_url}" target="_blank">{cta}</a>'
            display(HTML(html_link))
            escaped_output = html.escape(output)
            iframe = f"""
            <iframe srcdoc="{ escaped_output }" style="width: 800px; height: 600px;"></iframe>
            """
            display(HTML(iframe))
        else:
            print(f"Exception report saved to {filename}")

        if open_in_browser:
            import webbrowser

            webbrowser.open(f"file://{os.path.abspath(filename)}")

        if return_link:
            return filename

    def notebook(self):
        """Create a notebook with the HTML content embedded in the first cell, then delete the cell content while keeping the output."""
        from nbformat import v4 as nbf
        from nbconvert.preprocessors import ExecutePreprocessor

        # Use the existing html method to generate the HTML content
        output_html = self.generate_html_report(css=None)
        nb = nbf.new_notebook()

        # Add a code cell that renders the HTML content
        code_cell = nbf.new_code_cell(
            f"""
    from IPython.display import HTML, display
    display(HTML('''{output_html}'''))
            """
        )
        nb.cells.append(code_cell)

        # Execute the notebook
        ep = ExecutePreprocessor(timeout=600, kernel_name="python3")
        ep.preprocess(nb, {"metadata": {"path": os.getcwd()}})

        # After execution, clear the cell's source code
        nb.cells[0].source = ""

        return nb

    def offload_files_content(self):
        """
        Offload large file content from scenarios in interview exceptions.

        This method iterates over all the interview exceptions and calls the offload method
        for any scenario components in the invigilator. This significantly reduces memory usage
        by replacing base64-encoded content with a placeholder string, while preserving the
        structure of the scenarios.

        Returns:
            self: Returns the TaskHistory instance for method chaining

        This is particularly useful for TaskHistory instances containing interviews with
        large file content, such as videos, images, or other binary data.
        """
        for interview in self.total_interviews:
            if not hasattr(interview, "exceptions") or not interview.exceptions:
                continue

            for question_name, exceptions in interview.exceptions.items():
                for exception in exceptions:
                    # Check if exception has an invigilator with scenario
                    if hasattr(exception, "invigilator") and exception.invigilator:
                        if (
                            hasattr(exception.invigilator, "scenario")
                            and exception.invigilator.scenario
                        ):
                            # Call the offload method on the scenario
                            if hasattr(exception.invigilator.scenario, "offload"):
                                try:
                                    # Replace the original scenario with the offloaded version
                                    exception.invigilator.scenario = (
                                        exception.invigilator.scenario.offload()
                                    )
                                except Exception:
                                    # Silently continue if offloading fails for any reason
                                    pass

        return self

    def deduplicate_and_clean_interviews(self):
        """
        Deduplicates exception entries in this task history to reduce memory usage.

        This method removes duplicate error messages across interviews while preserving
        the first occurrence of each unique error. This significantly reduces the size
        of serialized task history data, especially for jobs with many similar errors.

        Returns:
            self: Returns the TaskHistory instance for method chaining.
        """
        seen = set()
        cleaned_interviews = []

        for interview in self.total_interviews:
            # Skip if interview has no exceptions
            if not hasattr(interview, "exceptions") or not interview.exceptions:
                continue

            keep_interview = False
            questions_to_modify = {}
            questions_to_remove = []

            # First pass: Collect all modifications without changing the dictionary
            if hasattr(interview.exceptions, "items"):
                for question_name, exceptions in list(interview.exceptions.items()):
                    filtered_exceptions = []

                    for exception in exceptions:
                        # Get the exception message (may require different access based on structure)
                        if hasattr(exception, "exception") and hasattr(
                            exception.exception, "args"
                        ):
                            message = (
                                str(exception.exception.args[0])
                                if exception.exception.args
                                else ""
                            )
                        else:
                            message = str(exception)

                        # Create a unique key for this exception
                        key = (question_name, message)

                        # Only keep exceptions we haven't seen before
                        if key not in seen:
                            seen.add(key)
                            filtered_exceptions.append(exception)

                    # Track what should happen to this question's exceptions
                    if filtered_exceptions:
                        keep_interview = True
                        questions_to_modify[question_name] = filtered_exceptions
                    else:
                        questions_to_remove.append(question_name)

            # Second pass: Apply all modifications safely
            if hasattr(interview.exceptions, "items"):
                # Add/replace filtered exceptions
                for question_name, filtered_exceptions in questions_to_modify.items():
                    interview.exceptions[question_name] = filtered_exceptions

                # Remove questions with all duplicate exceptions
                for question_name in questions_to_remove:
                    if hasattr(interview.exceptions, "pop"):
                        interview.exceptions.pop(question_name, None)
                    elif (
                        hasattr(interview.exceptions, "__delitem__")
                        and question_name in interview.exceptions
                    ):
                        del interview.exceptions[question_name]

            # Only keep the interview if it still has exceptions after filtering
            if keep_interview:
                cleaned_interviews.append(interview)

        # Replace the total_interviews with our cleaned list
        self.total_interviews = cleaned_interviews

        # Rebuild the _interviews dictionary
        self._interviews = {
            index: interview for index, interview in enumerate(self.total_interviews)
        }

        return self


if __name__ == "__main__":
    import doctest

    doctest.testmod(optionflags=doctest.ELLIPSIS)
