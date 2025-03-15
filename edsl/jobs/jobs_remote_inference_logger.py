import re
import sys
import uuid
from abc import ABC, abstractmethod
from typing import Literal, TYPE_CHECKING, List
from datetime import datetime
from dataclasses import dataclass

from .exceptions import JobsValueError


from .jobs_status_enums import JobsStatus

if TYPE_CHECKING:
    pass


@dataclass
class LogMessage:
    text: str
    status: str
    timestamp: datetime
    status: JobsStatus


@dataclass
class JobsInfo:
    job_uuid: str = None
    progress_bar_url: str = None
    error_report_url: str = None
    results_uuid: str = None
    results_url: str = None

    pretty_names = {
        "job_uuid": "Job UUID",
        "progress_bar_url": "Progress Bar URL",
        "error_report_url": "Exceptions Report URL",
        "results_uuid": "Results UUID",
        "results_url": "Results URL",
    }


class JobLogger(ABC):
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.jobs_info = JobsInfo()

    def add_info(
        self,
        information_type: Literal[
            "job_uuid",
            "progress_bar_url",
            "error_report_url",
            "results_uuid",
            "results_url",
        ],
        value: str,
    ):
        """Add information to the logger

        >>> j = StdOutJobLogger()
        >>> j.add_info("job_uuid", "1234")
        >>> j.jobs_info.job_uuid
        '1234'
        """
        if information_type not in self.jobs_info.__annotations__:
            raise JobsValueError(f"Information type {information_type} not supported")
        setattr(self.jobs_info, information_type, value)

    @abstractmethod
    def update(self, message: str, status: str = "running"):
        pass


class HTMLTableJobLogger(JobLogger):
    def __init__(self, verbose=True, **kwargs):
        from IPython.display import display, HTML

        super().__init__(verbose=verbose)
        self.display_handle = display(HTML(""), display_id=True)
        self.current_message = None
        self.log_id = str(uuid.uuid4())
        self.is_expanded = True
        self.spinner_chars = ["◐", "◓", "◑", "◒"]  # Rotating spinner characters
        self.spinner_idx = 0

    def _get_table_row(self, key: str, value: str) -> str:
        """Generate a table row with key-value pair"""
        return f"""
            <tr>
                <td style="padding: 8px; border: 1px solid #ddd; font-weight: bold;">{key}</td>
                <td style="padding: 8px; border: 1px solid #ddd;">{value if value else 'None'}</td>
            </tr>
        """

    def _linkify(self, text: str) -> str:
        """Convert URLs in text to clickable links"""
        url_pattern = r'(https?://[^\s<>"]+|www\.[^\s<>"]+)'
        return re.sub(
            url_pattern,
            r'<a href="\1" target="_blank" style="color: #3b82f6; text-decoration: underline;">\1</a>',
            text,
        )

    def _get_spinner(self, status: JobsStatus) -> str:
        """Get the current spinner frame if status is running"""
        if status == JobsStatus.RUNNING:
            spinner = self.spinner_chars[self.spinner_idx]
            self.spinner_idx = (self.spinner_idx + 1) % len(self.spinner_chars)
            return f'<span style="margin-right: 8px;">{spinner}</span>'
        elif status == JobsStatus.COMPLETED:
            return '<span style="margin-right: 8px; color: #22c55e;">✓</span>'
        elif status == JobsStatus.FAILED:
            return '<span style="margin-right: 8px; color: #ef4444;">✗</span>'
        return ""

    def _get_html(self, status: JobsStatus = JobsStatus.RUNNING) -> str:
        """Generate the complete HTML display"""
        # Generate table rows for each JobsInfo field
        info_rows = ""
        for field, _ in self.jobs_info.__annotations__.items():
            if field != "pretty_names":  # Skip the pretty_names dictionary
                value = getattr(self.jobs_info, field)
                value = self._linkify(str(value)) if value else None
                pretty_name = self.jobs_info.pretty_names.get(
                    field, field.replace("_", " ").title()
                )
                info_rows += self._get_table_row(pretty_name, value)

        # Add current message section with spinner
        message_html = ""
        if self.current_message:
            spinner = self._get_spinner(status)
            message_html = f"""
                <div style="margin-top: 10px; padding: 8px; background-color: #f8f9fa; border: 1px solid #ddd; border-radius: 4px;">
                    {spinner}<strong>Current Status:</strong> {self._linkify(self.current_message)}
                </div>
            """

        display_style = "block" if self.is_expanded else "none"
        arrow = "▼" if self.is_expanded else "▶"

        return f"""
            <div style="font-family: system-ui; max-width: 800px; margin: 10px 0;">
                <div onclick="document.getElementById('content-{self.log_id}').style.display = document.getElementById('content-{self.log_id}').style.display === 'none' ? 'block' : 'none';
                             document.getElementById('arrow-{self.log_id}').innerHTML = document.getElementById('content-{self.log_id}').style.display === 'none' ? '▶' : '▼';"
                     style="padding: 10px; background: #f5f5f5; border: 1px solid #ddd; border-radius: 4px; cursor: pointer;">
                    <span id="arrow-{self.log_id}">{arrow}</span> Job Status ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')})
                </div>
                <div id="content-{self.log_id}" style="display: {display_style};">
                    <table style="width: 100%; border-collapse: collapse; background: white; border: 1px solid #ddd;">
                        {info_rows}
                    </table>
                    {message_html}
                </div>
            </div>
        """

    def update(self, message: str, status: JobsStatus = JobsStatus.RUNNING):
        """Update the display with new message and current JobsInfo state"""
        from IPython.display import HTML

        self.current_message = message
        if self.verbose:
            self.display_handle.update(HTML(self._get_html(status)))
        else:
            return None


class StdOutJobLogger(JobLogger):
    def __init__(self, verbose=True, **kwargs):
        super().__init__(verbose=verbose)  # Properly call parent's __init__
        self.messages: List[LogMessage] = []

    def update(self, message: str, status: JobsStatus = JobsStatus.RUNNING):
        log_msg = LogMessage(text=message, status=status, timestamp=datetime.now())
        self.messages.append(log_msg)
        if self.verbose:
            sys.stdout.write(f"│ {message}\n")
            sys.stdout.flush()
        else:
            return None


class JupyterJobLogger(JobLogger):
    def __init__(self, verbose=True, **kwargs):
        from IPython.display import display, HTML

        super().__init__(verbose=verbose)
        self.messages = []
        self.log_id = str(uuid.uuid4())
        self.is_expanded = True
        self.display_handle = display(HTML(""), display_id=True)

    def _linkify(self, text):
        url_pattern = r'(https?://[^\s<>"]+|www\.[^\s<>"]+)'
        return re.sub(
            url_pattern,
            r'<a href="\1" target="_blank" style="color: #3b82f6; text-decoration: underline;">\1</a>',
            text,
        )

    def _get_html(self):
        messages_html = "\n".join(
            [
                f'<div style="border-left: 3px solid {msg["color"]}; padding: 5px 10px; margin: 5px 0;">{self._linkify(msg["text"])}</div>'
                for msg in self.messages
            ]
        )

        display_style = "block" if self.is_expanded else "none"
        arrow = "▼" if self.is_expanded else "▶"

        return f"""
            <div style="border: 1px solid #ccc; margin: 10px 0; max-width: 800px;">
                <div onclick="document.getElementById('content-{self.log_id}').style.display = document.getElementById('content-{self.log_id}').style.display === 'none' ? 'block' : 'none';
                             document.getElementById('arrow-{self.log_id}').innerHTML = document.getElementById('content-{self.log_id}').style.display === 'none' ? '▶' : '▼';"
                     style="padding: 10px; background: #f5f5f5; cursor: pointer;">
                    <span id="arrow-{self.log_id}">{arrow}</span> Remote Job Log ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')})
                </div>
                <div id="content-{self.log_id}" style="padding: 10px; display: {display_style};">
                    {messages_html}
                </div>
            </div>
        """

    def update(self, message, status: JobsStatus = JobsStatus.RUNNING):
        from IPython.display import HTML

        colors = {"running": "#3b82f6", "completed": "#22c55e", "failed": "#ef4444"}
        self.messages.append({"text": message, "color": colors.get(status, "#666")})
        if self.verbose:
            self.display_handle.update(HTML(self._get_html()))
        else:
            return None


if __name__ == "__main__":
    import doctest

    doctest.testmod()
