import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# from output import Output  # TODO: Fix this import
from abc import abstractmethod
import subprocess
import tempfile
import webbrowser
import altair as alt
import uuid

from edsl import FileStore


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


class ChartOutput:  # TODO: Should inherit from Output when available
    """Base class for chart-based visualizations.

    Supports both regular questions and comment fields.
    """

    pretty_name = "Chart"
    pretty_short_name = "Chart"
    methodology = "Base class for chart-based visualizations"

    # Registry to store all chart output types
    _registry = {}

    def __init__(self, results, *question_names):
        """Initialize the chart output with results and question names.

        Supports both regular question names and comment field names.
        """
        from edsl.reports.comment_field import (
            is_comment_field,
            create_comment_field,
        )

        self.results = results
        self.question_names = question_names

        # Handle both regular questions and comment fields
        self.questions = []
        for name in self.question_names:
            if is_comment_field(name):
                self.questions.append(create_comment_field(name, results))
            else:
                self.questions.append(self.results.survey.get(name))

    def get_data_column(self, question_or_field):
        """Get the correct column name for accessing data.

        Args:
            question_or_field: Either a Question object or a CommentField object

        Returns:
            The full column name (e.g., "answer.how_feeling" or "comment.how_feeling_comment")
        """
        from edsl.reports.comment_field import get_data_column_name

        return get_data_column_name(question_or_field)

    @staticmethod
    def sanitize_text_for_chart(text):
        """Sanitize text for use in chart specifications.

        Removes or escapes template variables and other characters that could
        break Altair/Vega-Lite JavaScript expressions.

        Args:
            text: The text to sanitize (e.g., question text)

        Returns:
            Sanitized text safe for use in chart titles, tooltips, etc.
        """
        import re

        # Remove Jinja2 template variables like {{ variable }} or {% if %}
        text = re.sub(r"\{\{[^}]+\}\}", "[template]", text)
        text = re.sub(r"\{%[^%]+%\}", "", text)
        # Remove any remaining curly braces that could break JS
        text = text.replace("{", "").replace("}", "")
        # Replace colons which have special meaning in Altair field specs
        text = text.replace(":", " -")
        return text.strip()

    def __init_subclass__(cls, **kwargs):
        """Automatically register all subclasses"""
        super().__init_subclass__(**kwargs)
        cls._registry[cls.__name__] = cls

    @property
    def scenario_output(self):
        """Returns the chart as a PNG file."""
        chart = self.output()
        # Create a temporary file with .png extension
        temp_file = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
        temp_path = temp_file.name
        temp_file.close()

        # Save the chart as PNG
        chart.save(temp_path)

        return FileStore(path=temp_path)

    @property
    @abstractmethod
    def narrative(self):
        """Returns a description of what this chart shows. Must be implemented by subclasses."""
        pass

    @property
    def html(self):
        """Returns the HTML snippet representation of the chart for embedding."""
        return self._get_content_html()

    @property
    def png(self):
        """Returns a PNGLocation object for the chart"""
        chart = self.output()
        if not isinstance(chart, (alt.Chart, alt.LayerChart, alt.FacetChart)):
            raise ValueError("output() must return an Altair Chart object")

        # Create a temporary file with .png extension
        temp_file = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
        temp_path = temp_file.name
        temp_file.close()

        # Save the chart as PNG
        chart.save(temp_path)

        return PNGLocation(temp_path)

    @classmethod
    def get_available_outputs(cls):
        """Returns a dictionary of all registered chart types"""
        return cls._registry

    @classmethod
    def create(cls, chart_type, *args, **kwargs):
        """Factory method to create a chart by name"""
        if chart_type not in cls._registry:
            raise ValueError(
                f"Unknown chart type: {chart_type}. Available types: {list(cls._registry.keys())}"
            )
        return cls._registry[chart_type](*args, **kwargs)

    @classmethod
    @abstractmethod
    def can_handle(cls, *question_objs) -> bool:
        """
        Abstract method that determines if this chart type can handle the given questions.
        Must be implemented by all child classes.

        Args:
            *question_objs: Variable number of question objects to check

        Returns:
            bool: True if this chart type can handle these questions, False otherwise
        """
        pass

    def output(self):
        pass

    def show(self):
        """Opens the chart in the default web browser for interactive viewing."""
        chart = self.output()
        if not isinstance(chart, (alt.Chart, alt.LayerChart, alt.FacetChart)):
            raise ValueError("output() must return an Altair Chart object")

        # Create a temporary HTML file
        temp_dir = tempfile.gettempdir()
        temp_path = os.path.join(temp_dir, "chart.html")

        # Save the chart to the temporary file using Altair's default full HTML
        chart.save(temp_path, format="html")

        # Open the chart in the default browser
        webbrowser.open("file://" + temp_path)

    def _get_container_class(self):
        """Return the appropriate container class for chart outputs."""
        return "chart-container"

    def _get_content_html(self):
        """Generate full HTML document for the chart (e.g., for saving or direct viewing)."""
        chart = self.output()
        # No type check here; assuming self.output() returns a valid object
        # with a to_html() method. Errors will propagate.

        # Generate unique ID to prevent div collisions in Jupyter notebooks
        unique_id = f"vis_{uuid.uuid4().hex[:12]}"
        chart_html = chart.to_html()
        # Replace all occurrences of 'vis' with our unique ID in both HTML and JavaScript
        chart_html = chart_html.replace('id="vis"', f'id="{unique_id}"')
        chart_html = chart_html.replace('"#vis"', f'"#{unique_id}"')
        chart_html = chart_html.replace("'#vis'", f"'#{unique_id}'")
        return chart_html
