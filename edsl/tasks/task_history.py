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

        self.total_interviews.append(interview)
        self._interviews[len(self._interviews)] = interview

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

    def to_dict(self, add_edsl_version=True):
        """Return the TaskHistory as a dictionary."""
        d = {
            "interviews": [
                i.to_dict(add_edsl_version=add_edsl_version)
                for i in self.total_interviews
            ],
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

        from ..interviews import Interview

        interviews = [Interview.from_dict(i) for i in data["interviews"]]
        return cls(interviews, include_traceback=data["include_traceback"])

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
                        interview.model._inference_service_,     # Service
                        interview.model.model,                   # Model
                        question_name,                           # Question name
                        exception.name,                          # Exception name
                        str(exception.traceback)[:100] if exception.traceback else "",  # Truncated traceback
                    )
                    
                    # Only count if we haven't seen this exact exception before
                    if exception_key not in seen_exceptions:
                        seen_exceptions.add(exception_key)
                        
                        # Add to the summary table
                        table_key = (
                            exception.exception.__class__.__name__,  # Exception type
                            interview.model._inference_service_,     # Service
                            interview.model.model,                   # Model
                            question_name,                           # Question name
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


if __name__ == "__main__":
    import doctest

    doctest.testmod(optionflags=doctest.ELLIPSIS)
