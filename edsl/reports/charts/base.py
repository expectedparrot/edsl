import tempfile
import os
import webbrowser
import uuid
import altair as alt
from abc import abstractmethod
from edsl import FileStore

from ..base import Output, PNGLocation


class ChartOutput(Output):
    """Stuff specifically common to graphics/charts"""

    # Registry to store all chart output types
    _registry = {}

    def __init_subclass__(cls, **kwargs):
        """Automatically register all subclasses"""
        super().__init_subclass__(**kwargs)
        cls._registry[cls.__name__] = cls

    @property
    def scenario_output(self):
        """Returns the chart as a PNG file."""
        chart = self.output()
        if not isinstance(chart, alt.Chart):
            raise ValueError("output() must return an Altair Chart object")

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
        """Returns the HTML representation of the chart"""
        chart = self.output()
        if not isinstance(chart, alt.Chart):
            raise ValueError("output() must return an Altair Chart object")

        # Generate unique ID to prevent div collisions in Jupyter notebooks
        unique_id = f"vis_{uuid.uuid4().hex[:12]}"
        chart_html = chart.to_html()
        # Replace all occurrences of 'vis' with our unique ID in both HTML and JavaScript
        chart_html = chart_html.replace('id="vis"', f'id="{unique_id}"')
        chart_html = chart_html.replace('"#vis"', f'"#{unique_id}"')
        chart_html = chart_html.replace("'#vis'", f"'#{unique_id}'")
        return chart_html

    @property
    def png(self):
        """Returns a PNGLocation object for the chart"""
        chart = self.output()
        if not isinstance(chart, alt.Chart):
            raise ValueError("output() must return an Altair Chart object")

        # Create a temporary file with .png extension
        temp_file = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
        temp_path = temp_file.name
        temp_file.close()

        # Save the chart as PNG
        chart.save(temp_path)

        return PNGLocation(temp_path)

    @classmethod
    def get_available_charts(cls):
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
        if not isinstance(chart, alt.Chart):
            raise ValueError("output() must return an Altair Chart object")

        # Create a temporary HTML file
        temp_dir = tempfile.gettempdir()
        temp_path = os.path.join(temp_dir, "chart.html")

        # Save the chart to the temporary file
        chart.save(temp_path)

        # Open the chart in the default browser
        webbrowser.open("file://" + temp_path)
