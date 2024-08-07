from edsl.jobs.tasks.task_status_enum import TaskStatus
from typing import List, Optional
from io import BytesIO
import base64


class TaskHistory:
    def __init__(self, interviews: List["Interview"], include_traceback=False):
        """
        The structure of a TaskHistory exception

        [Interview.exceptions, Interview.exceptions, Interview.exceptions, ...]

        """

        self.total_interviews = interviews
        self.include_traceback = include_traceback

        self._interviews = {index: i for index, i in enumerate(self.total_interviews)}

    @property
    def exceptions(self):
        return [i.exceptions for k, i in self._interviews.items() if i.exceptions != {}]

    @property
    def indices(self):
        return [k for k, i in self._interviews.items() if i.exceptions != {}]

    def __repr__(self):
        """Return a string representation of the TaskHistory."""
        return f"TaskHistory(interviews={self.total_interviews})."

    def to_dict(self):
        """Return the TaskHistory as a dictionary."""
        return {
            "exceptions": [
                e.to_dict(include_traceback=self.include_traceback)
                for e in self.exceptions
            ],
            "indices": self.indices,
        }

    @property
    def has_exceptions(self) -> bool:
        """Return True if there are any exceptions."""
        return len(self.exceptions) > 0

    def _repr_html_(self):
        """Return an HTML representation of the TaskHistory."""
        from edsl.utilities.utilities import data_to_html

        newdata = self.to_dict()["exceptions"]
        return data_to_html(newdata, replace_new_lines=True)

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
        return """
        body {
        font-family: Arial, sans-serif;
        line-height: 1.6;
        background-color: #f9f9f9;
        color: #333;
        margin: 20px;
        }

        .interview {
        font-size: 1.5em;
        margin-bottom: 10px;
        padding: 10px;
        background-color: #e3f2fd;
        border-left: 5px solid #2196f3;
        }

        .question {
        font-size: 1.2em;
        margin-bottom: 10px;
        padding: 10px;
        background-color: #fff9c4;
        border-left: 5px solid #ffeb3b;
        }

        .exception-detail {
        margin-bottom: 10px;
        padding: 10px;
        background-color: #ffebee;
        border-left: 5px solid #f44336;
        }

        .question-detail {
           border: 3px solid black; /* Adjust the thickness by changing the number */
            padding: 10px; /* Optional: Adds some padding inside the border */
        }

        .exception-detail div {
        margin-bottom: 5px;
        }

        .exception-exception {
        font-weight: bold;
        color: #d32f2f;
        }

        .exception-time,
        .exception-traceback {
        font-style: italic;
        color: #555;
        }
        """

    def html(
        self,
        filename: Optional[str] = None,
        return_link=False,
        css=None,
        cta="Open Report in New Tab",
    ):
        """Return an HTML report."""

        from IPython.display import display, HTML
        import tempfile
        import os
        from edsl.utilities.utilities import is_notebook
        from jinja2 import Template

        performance_plot_html = self.plot(num_periods=100, get_embedded_html=True)

        if css is None:
            css = self.css()

        template = Template(
            """
        <!DOCTYPE html>
        <html lang="en">
        <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Exception Details</title>
        <style>
        {{ css }}
        </style>
        </head>
        <body>
            {% for index, interview in interviews.items() %}
                {% if interview.exceptions != {} %}
                   <div class="interview">Interview: {{ index }} </div>
                    <h1>Failing questions</h1>
                {% endif %}
                {% for question, exceptions in interview.exceptions.items() %}
                    <div class="question">question_name: {{ question }}</div>

                    <h2>Question</h2>
                    <div class="question-detail"> 
                            {{ interview.survey.get_question(question).html() }}
                    </div>        

                    <h2>Scenario</h2>                            
                    <div class="scenario"> 
                            {{ interview.scenario._repr_html_() }}
                    </div>        

                    <h2>Agent</h2>
                    <div class="agent">
                            {{ interview.agent._repr_html_() }}
                    </div>

                    <h2>Model</h2>
                    <div class="model">
                            {{ interview.model._repr_html_() }}
                    </div>
                            
                    <h2>Exception details</h2>

                    {% for exception_message in exceptions %}
                        <div class="exception-detail">
                            <div class="exception-exception">Exception: {{ exception_message.exception }}</div>
                            <div class="exception-time">Time: {{ exception_message.time }}</div>
                            <div class="exception-traceback">Traceback: <pre>{{ exception_message.traceback }} </pre></div>
                        </div>
                    {% endfor %}            
                {% endfor %}            
            {% endfor %}
                            
        <h1>Performance Plot</h1>
        {{ performance_plot_html }}
        </body>
        </html>
        """
        )

        # Render the template with data
        output = template.render(
            interviews=self._interviews,
            css=css,
            performance_plot_html=performance_plot_html,
        )

        # Save the rendered output to a file
        with open("output.html", "w") as f:
            f.write(output)

        if css is None:
            css = self.css()

        if filename is None:
            current_directory = os.getcwd()
            filename = tempfile.NamedTemporaryFile(
                "w", delete=False, suffix=".html", dir=current_directory
            ).name

        with open(filename, "w") as f:
            with open(filename, "w") as f:
                # f.write(html_header)
                # f.write(self._repr_html_())
                f.write(output)
                # f.write(html_footer)

        if is_notebook():
            import html

            html_url = f"/files/{filename}"
            html_link = f'<a href="{html_url}" target="_blank">{cta}</a>'
            display(HTML(html_link))
            escaped_output = html.escape(output)
            iframe = f""""
            <iframe srcdoc="{ escaped_output }" style="width: 800px; height: 600px;"></iframe>
            """
            display(HTML(iframe))
            # display(HTML(output))
        else:
            print(f"Exception report saved to {filename}")
            import webbrowser
            import os

            webbrowser.open(f"file://{os.path.abspath(filename)}")

        if return_link:
            return filename
