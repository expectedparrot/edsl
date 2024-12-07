from abc import ABC, abstractmethod
import uuid

from typing import Optional, Union, Literal
import requests
import sys
from edsl.exceptions.coop import CoopServerResponseError

# from edsl.enums import VisibilityType
from edsl.results import Results

from IPython.display import display, HTML
import uuid

from IPython.display import display, HTML
import uuid
import json
from datetime import datetime
import re


class JobLogger(ABC):
    def __init__(self, verbose: bool = False):
        self.verbose = verbose

    @abstractmethod
    def update(self, message: str, status: str = "running"):
        pass


import sys
from datetime import datetime
from typing import List
from dataclasses import dataclass


@dataclass
class LogMessage:
    text: str
    status: str
    timestamp: datetime


class StdOutJobLogger(JobLogger):

    def __init__(self, verbose=False, **kwargs):
        super().__init__(verbose=verbose)  # Properly call parent's __init__
        self.messages: List[LogMessage] = []

    def update(self, message: str, status: str = "running"):
        log_msg = LogMessage(text=message, status=status, timestamp=datetime.now())
        self.messages.append(log_msg)
        if self.verbose:
            sys.stdout.write(f"│ {message}\n")
            sys.stdout.flush()
        else:
            return None


class JupyterJobLogger(JobLogger):
    def __init__(self, verbose=False, **kwargs):
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

    def update(self, message, status="running"):
        colors = {"running": "#3b82f6", "completed": "#22c55e", "failed": "#ef4444"}
        self.messages.append({"text": message, "color": colors.get(status, "#666")})
        if self.verbose:
            self.display_handle.update(HTML(self._get_html()))
        else:
            return None
