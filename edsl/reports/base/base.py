import os
import subprocess
import sys

from abc import ABC, abstractmethod

from edsl import Scenario


class Output(ABC):
    """Has very general methods like saving to file, saving to clipboard, etc., creating markdown, etc."""

    def __init__(self, results, *question_names):
        self.results = results
        self.question_names = list(question_names)
        self.questions = [self.results.survey.get(name) for name in self.question_names]

    @abstractmethod
    def output(self):
        pass

    @property
    @abstractmethod
    def narrative(self):
        """Returns a description of what this output shows. Must be implemented by subclasses."""
        pass

    @property
    def can_be_analyzed(self):
        """Whether this output should be included in written analysis. Default is True."""
        return True

    @property
    def scenario_output(self):
        """Returns the output in a format suitable for a scenario. Must be implemented by subclasses."""
        raise NotImplementedError("Subclasses must implement scenario_output")

    @property
    def scenario(self):
        """Returns the scenario object. Common implementation for all outputs."""
        if not self.can_be_analyzed:
            return None
        return Scenario({"output": self.scenario_output, "context": self.narrative})

    def get_questions_html(self):
        """Returns HTML representation of the questions used in this output."""
        html_parts = []
        for q in self.questions:
            html_parts.append('<div class="question-details">')
            html_parts.append("<h3>Question Details:</h3>")
            html_parts.append('<div class="question-metadata">')
            html_parts.append(f"<p><strong>Name:</strong> {q.question_name}</p>")
            html_parts.append(f"<p><strong>Type:</strong> {q.question_type}</p>")
            if hasattr(q, "question_options"):
                # Convert options to strings before joining
                str_options = [str(opt) for opt in q.question_options]
                html_parts.append(
                    f'<p><strong>Options:</strong> {", ".join(str_options)}</p>'
                )
            html_parts.append("</div>")
            html_parts.append('<div class="question-preview">')
            html_parts.append("<h4>Question Preview:</h4>")
            html_parts.append(q.html())
            html_parts.append("</div>")
            html_parts.append("</div>")
        return "\n".join(html_parts)

    def get_questions_text(self):
        """Returns text representation of the questions used in this output."""
        text_parts = []
        for q in self.questions:
            text_parts.append("Question Details:")
            text_parts.append(f"Name: {q.question_name}")
            text_parts.append(f"Type: {q.question_type}")
            text_parts.append(f"Text: {q.question_text}")
            if hasattr(q, "question_options"):
                text_parts.append("Options:")
                # Convert options to strings
                for opt in q.question_options:
                    text_parts.append(f"  - {str(opt)}")
            text_parts.append("")  # Empty line for spacing
        return "\n".join(text_parts)


class PNGLocation:
    """Helper class for managing PNG files with convenient methods."""

    def __init__(self, path):
        self.path = path

    def show(self):
        """Opens the PNG file using the system's default image viewer."""
        if sys.platform == "darwin":  # macOS
            subprocess.run(["open", self.path])
        elif sys.platform == "win32":  # Windows
            os.startfile(self.path)
        else:  # Linux and other platforms
            subprocess.run(["xdg-open", self.path])

    def cleanup(self):
        """Removes the temporary PNG file."""
        if os.path.exists(self.path):
            os.remove(self.path)

    @property
    def html(self):
        """Returns an HTML img tag with the base64-encoded PNG data."""
        import base64

        # Read the PNG file
        with open(self.path, "rb") as f:
            png_data = f.read()

        # Convert to base64
        b64_data = base64.b64encode(png_data).decode("utf-8")

        # Create HTML img tag
        return f'<img src="data:image/png;base64,{b64_data}" style="max-width: 100%; height: auto;">'

    def __str__(self):
        return self.path

    def __repr__(self):
        return f"PNGLocation('{self.path}')"
