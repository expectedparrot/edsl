"""
Analyzer module for Reports.

This module contains classes for analyzing survey questions and generating
visualizations, tables, and written analyses. It handles different types of questions
(multiple choice, free text, linear scale, checkbox) with appropriate analysis methods.

The module provides a factory function to create the appropriate analyzer for a given
question type and methods to generate HTML reports with interactive charts.
"""

from __future__ import annotations

import os
import tempfile
import traceback
from abc import ABC, abstractmethod
from typing import Any, List, Optional

import altair as alt
import pandas as pd
from edsl import FileStore, QuestionFreeText, Scenario, Question
from .warning_utils import print_error


def create_survey_bar_chart(
    responses: List[Any],
    all_options: List[Any],
    title: str = "Survey Response Distribution",
    width: int = 500,
    height: int = 300,
    color_scheme: str = "category10",
) -> alt.Chart:
    """
    Create a bar chart for survey response data using Altair.

    This function generates a bar chart visualization showing the frequency distribution
    of responses across different options in a survey question.

    Args:
        responses: List of responses collected from the survey
        all_options: List of all possible options that were available to respondents
        title: Title of the chart
        width: Width of the chart in pixels
        height: Height of the chart in pixels
        color_scheme: Color scheme to use for the bars

    Returns:
        Altair chart object that can be displayed or saved
    """
    # Count occurrences of each option
    option_counts = {}
    for option in all_options:
        option_counts[option] = sum(1 for response in responses if response == option)

    # Create DataFrame from the counts
    df = pd.DataFrame(
        {"Option": list(option_counts.keys()), "Count": list(option_counts.values())}
    )

    # Create the bar chart
    chart = (
        alt.Chart(df)
        .mark_bar()
        .encode(
            x=alt.X("Option:N", sort=all_options, title="Response Option"),
            y=alt.Y("Count:Q", title="Number of Responses"),
            color=alt.Color(
                "Option:N", scale=alt.Scale(scheme=color_scheme), legend=None
            ),
            tooltip=["Option", "Count"],
        )
        .properties(title=title, width=width, height=height)
    )

    return chart


class AnalyzeQuestion(ABC):
    """
    Abstract base class for analyzing survey questions.

    This class provides a common interface and shared functionality
    for analyzing different types of survey questions and generating
    visualizations, tables, and written analyses for them.

    Attributes:
        question (Question): The question object to analyze
        answers (List[Any]): The list of responses to analyze
        question_type (str): The type of question (e.g., 'multiple_choice', 'free_text')
        test_mode (bool): If True, use placeholder data and analyses
        _chart_file_store (Optional[FileStore]): Cached FileStore object for the chart
        _chart (Optional[alt.Chart]): Cached chart object
        _analyses (List): List of Analysis objects for this question
    """

    _question_type = None

    def __init__(
        self,
        question_text: str,
        answers: List[Any],
        question_options: Optional[List[str]] = None,
        test_mode: bool = False,
    ) -> None:
        """
        Initialize a question analyzer.

        Args:
            question: The question object to analyze
            answers: The list of responses to analyze
            test_mode: If True, use placeholder data and analyses instead of LLM-generated content
        """
        self.question_text = question_text
        self.question_options = question_options
        self.answers = answers
        self.question_options = [
            str(option) for option in question_options if option is not None
        ]
        self.test_mode = test_mode

        self._chart_file_store: Optional[FileStore] = None
        self._chart: Optional[alt.Chart] = None
        self._analyses: List[Any] = []

    @property
    def question_type(self) -> str:
        """
        Get the type of question.
        """
        return self._question_type

    def get_analyses(self) -> List[Any]:
        """
        Get the list of analyses for this question.

        Lazy-loads the analyses if they haven't been generated yet.

        Returns:
            List of Analysis objects for this question
        """
        if not self._analyses:
            self._generate_analyses()
        return self._analyses

    @abstractmethod
    def _generate_analyses(self) -> None:
        """
        Generate analyses for this question.

        Each question type should implement this to create its specific analyses.
        This method populates the self._analyses list.
        """
        pass

    def html_table(self) -> str:
        """
        Generate an HTML table of the responses.

        Creates a styled HTML table showing the raw responses to the question,
        with sensible pagination and truncation for large datasets.

        Returns:
            HTML string representing the table
        """
        # Remove None values
        answers = [a for a in self.answers if a is not None]

        # Create a DataFrame with an index column for row numbering
        df = (
            pd.DataFrame({"Response": answers})
            .reset_index()
            .rename(columns={"index": "Response #"})
        )

        # Add 1 to response numbers to start from 1 instead of 0
        df["Response #"] = df["Response #"] + 1

        # For large datasets, limit to a reasonable number of rows to display
        max_rows = 30
        if len(df) > max_rows:
            df = df.iloc[:max_rows].copy()
            show_more_message = f"<div class='table-note'>Showing {max_rows} of {len(answers)} responses</div>"
        else:
            show_more_message = ""

        # Clean and truncate long responses for display
        max_length = 300
        df["Response"] = df["Response"].apply(
            lambda x: (
                (str(x)[:max_length] + "...")
                if x and len(str(x)) > max_length
                else str(x)
            )
        )

        # Add styling to the DataFrame
        styled_df = df.style.set_table_attributes('class="data-table"')

        # Apply custom styling
        styled_df = styled_df.set_properties(
            **{
                "text-align": "left",
                "border-bottom": "1px solid #e1e1e1",
                "padding": "8px",
            }
        )

        # Apply alternating row colors and header styling
        styled_df = styled_df.set_table_styles(
            [
                {
                    "selector": "th",
                    "props": [
                        ("background-color", "#f2f2f2"),
                        ("color", "#333"),
                        ("font-weight", "bold"),
                        ("text-align", "left"),
                        ("padding", "10px"),
                        ("border-bottom", "2px solid #ccc"),
                    ],
                },
                {
                    "selector": "tr:nth-child(even)",
                    "props": [("background-color", "#f9f9f9")],
                },
                {"selector": "tr:hover", "props": [("background-color", "#f0f7fb")]},
            ]
        )

        # Generate HTML for the table
        html_table = styled_df.to_html()

        # Wrap in a container with scrolling capability
        table_html = f"""
        <div class="custom-table-wrapper">
            {html_table}
            {show_more_message}
        </div>
        """

        return table_html

    def chart_file_store(self, existing_path: Optional[str] = None) -> FileStore:
        """
        Get a FileStore object for the chart.

        Creates a FileStore containing the chart image, either by using
        an existing path or by saving the chart to a new file.

        Args:
            existing_path: Optional path to an existing chart image file

        Returns:
            FileStore object containing the chart image
        """
        if self._chart_file_store is None:
            if existing_path:
                self._chart_file_store = FileStore(existing_path)
            else:
                self._chart_file_store = FileStore(self.save_chart_as_png())

        return self._chart_file_store

    def visualize(self) -> None:
        """
        Display the chart in a browser.

        Opens the chart in a web browser using Altair's built-in serve method.
        """
        self.chart.serve()

    def save_chart_as_png(self) -> str:
        """
        Save the chart as a PNG file in a temporary directory.

        Configures the chart for PNG export and saves it to a temporary file.

        Returns:
            Path to the saved PNG file
        """
        # Configure for PNG export
        configured_chart = self.chart.configure_view(
            continuousHeight=300,
            continuousWidth=400,
        )

        # Create temp file with .png extension
        temp_dir = tempfile.gettempdir()
        temp_path = os.path.join(temp_dir, f"chart_{hash(str(self.answers))}.png")

        # Save as PNG
        configured_chart.save(temp_path, scale_factor=2.0)

        return temp_path

    def save_chart_as_html(self) -> str:
        """
        Save the chart as HTML.

        Converts the chart to HTML for embedding in web pages.

        Returns:
            HTML string representation of the chart
        """
        return self.chart.to_html()

    @property
    @abstractmethod
    def chart(self) -> alt.Chart:
        """
        Get the visualization chart for this question.

        Each question type should implement this to return the appropriate
        chart type for that question.

        Returns:
            Altair chart object
        """
        pass

    def written_analysis(self) -> str:
        """
        Generate a written analysis of the survey results.

        In test mode, returns placeholder text.
        In normal mode, uses LLM to generate an analysis based on the chart.

        Returns:
            String containing the written analysis
        """
        if self.test_mode:
            return """Lorem ipsum dolor sit amet, consectetur adipiscing elit. Nulla facilisi. 
            Sed convallis libero in tortor fringilla, at dictum sem ultricies. 
            Data shows interesting patterns that would require further analysis in a 
            production environment. The visualization highlights key trends that 
            would typically be elaborated upon using actual LLM analysis."""

        try:
            q_analysis = QuestionFreeText(
                question_name="written_analysis",
                question_text="""Please provide a written analysis of the survey results.
                Survey respondents were asked the question: 
                <question>
                {{ scenario.question_text }}
                </question>

                <question_type>
                {{ scenario.question_type }}
                </question_type>

                The results have been analyzed and this is the visualization of the results:
                <chart>
                {{ scenario.chart }}
                </chart>
                Please write a short, 1 paragraph analysis of the results as plain text.
                """,
            )
            scenario = Scenario(
                {
                    "question_text": self.question_text,
                    "question_type": self.question_type,
                    "chart": self.chart_file_store(),
                }
            )

            results = q_analysis.by(scenario).run(stop_on_exception=True)
            return results.select("answer.written_analysis").first()
        except Exception as e:
            print_error(f"Error generating written analysis: {e}")
            print_error(traceback.format_exc())
            return "*Analysis generation failed or timed out*"

    # Note: HTML generation is now handled by the Report class


class AnalyzeQuestionMultipleChoice(AnalyzeQuestion):
    """
    Analyzer for multiple choice questions.

    This class specializes the general question analyzer for multiple choice questions,
    where respondents select one option from a predefined set of options.
    It provides visualizations showing the distribution of responses across options.

    Attributes:
        Inherits all attributes from AnalyzeQuestion
    """

    _question_type = "multiple_choice"

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        if self.question_options is None:
            raise ValueError(
                "Question options must be provided for a multiple choice question"
            )

    def _generate_analyses(self) -> None:
        """
        Generate analyses for multiple choice questions.

        This method creates and adds the following analysis objects:
        1. Frequency Distribution Analysis - shows distribution of responses across options
        2. Response Overview Analysis - provides a general overview of the responses
        """

        from .analysis import FrequencyAnalysis, ResponseAnalysis

        # Add frequency analysis
        frequency_analysis = FrequencyAnalysis(
            question_text=self.question_text,
            question_options=self.question_options,
            answers=self.answers,
            test_mode=self.test_mode,
        )
        self._analyses.append(frequency_analysis)

        # Add response overview
        response_analysis = ResponseAnalysis(
            question=self.question_text, answers=self.answers, test_mode=self.test_mode
        )
        self._analyses.append(response_analysis)

    @property
    def chart(self) -> alt.Chart:
        """
        Get a bar chart visualizing response distribution.

        This property lazily creates a bar chart showing the frequency
        distribution of responses across the available options.

        Returns:
            Altair chart object showing response distribution
        """
        if self._chart is None:
            self._chart = create_survey_bar_chart(self.answers, self.question_options)
        return self._chart

    def html_table(self) -> str:
        """
        Generate an HTML table showing response distribution.

        Creates a styled HTML table specifically for multiple choice questions,
        showing counts, percentages, and visual distribution of responses.

        Returns:
            HTML string representing the distribution table
        """
        # Count occurrences of each option
        option_counts = {}
        for option in self.question.question_options:
            count = sum(1 for answer in self.answers if answer == option)
            option_counts[option] = count

        # Calculate percentages
        total_responses = len(self.answers)
        option_percentages = {
            option: (count / total_responses * 100)
            for option, count in option_counts.items()
        }

        # Create DataFrame with counts and percentages
        df = pd.DataFrame(
            {
                "Option": list(option_counts.keys()),
                "Count": list(option_counts.values()),
                "Percentage": [
                    f"{option_percentages[option]:.1f}%"
                    for option in option_counts.keys()
                ],
            }
        )

        # Sort by count in descending order
        df = df.sort_values("Count", ascending=False)

        # Create a progress bar visualization for each option
        def create_progress_bar(percentage: str) -> str:
            """Create an HTML progress bar for a percentage value."""
            actual_percentage = float(percentage.strip("%"))
            bar_width = min(100, max(0, actual_percentage))
            return f"""
            <div style="display: flex; align-items: center; margin: 5px 0;">
                <div style="background-color: #3498db; height: 20px; width: {bar_width}%; border-radius: 2px;"></div>
                <span style="margin-left: 8px; color: #333;">{percentage}</span>
            </div>
            """

        df["Distribution"] = df["Percentage"].apply(create_progress_bar)

        # Style the DataFrame
        styled_df = df.style.hide(axis="index").set_table_attributes(
            'class="data-table"'
        )

        # Apply custom styling
        styled_df = styled_df.set_properties(
            **{
                "text-align": "left",
                "border-bottom": "1px solid #e1e1e1",
                "padding": "8px",
            }
        )

        # Apply header styling
        styled_df = styled_df.set_table_styles(
            [
                {
                    "selector": "th",
                    "props": [
                        ("background-color", "#f2f2f2"),
                        ("color", "#333"),
                        ("font-weight", "bold"),
                        ("text-align", "left"),
                        ("padding", "10px"),
                        ("border-bottom", "2px solid #ccc"),
                    ],
                },
                {
                    "selector": "tr:nth-child(even)",
                    "props": [("background-color", "#f9f9f9")],
                },
                {"selector": "tr:hover", "props": [("background-color", "#f0f7fb")]},
            ]
        )

        # Generate summary statistics
        total_responses = len(self.answers)
        most_common = df.iloc[0]["Option"]
        most_common_count = df.iloc[0]["Count"]
        most_common_pct = float(df.iloc[0]["Percentage"].strip("%"))

        # Create overall summary
        summary_html = f"""
        <div class="response-summary">
            <p><strong>Total Responses:</strong> {total_responses}</p>
            <p><strong>Most Common Response:</strong> '{most_common}' ({most_common_count} responses, {most_common_pct:.1f}%)</p>
        </div>
        """

        # Generate HTML for the table
        html_table = styled_df.to_html(escape=False)

        # Wrap in a container
        table_html = f"""
        <div class="custom-table-wrapper">
            {summary_html}
            {html_table}
        </div>
        """

        return table_html


class AnalyzeQuestionFreeText(AnalyzeQuestion):
    """
    Analyzer for free text questions.

    This class specializes the general question analyzer for free text questions,
    where respondents provide open-ended text responses. It uses ThemeFinder to
    identify common themes and analyze sentiment in the responses.

    Attributes:
        Inherits all attributes from AnalyzeQuestion
    """

    _question_type = "free_text"

    def _generate_analyses(self) -> None:
        """
        Generate analyses for free text questions.

        This method creates and adds the following analysis objects:
        1. Theme Analysis - identifies and analyzes common themes in responses
        2. Sentiment Analysis - analyzes sentiment in responses by theme
        3. Response Overview Analysis - provides a general overview of the responses
        """
        from .analysis import ThemeAnalysis, SentimentAnalysis, ResponseAnalysis

        # Add theme analysis
        theme_analysis = ThemeAnalysis(
            question=self.question, answers=self.answers, test_mode=self.test_mode
        )
        self._analyses.append(theme_analysis)

        # Add sentiment analysis
        sentiment_analysis = SentimentAnalysis(
            question=self.question, answers=self.answers, test_mode=self.test_mode
        )
        self._analyses.append(sentiment_analysis)

        # Add response overview
        response_analysis = ResponseAnalysis(
            question=self.question, answers=self.answers, test_mode=self.test_mode
        )
        self._analyses.append(response_analysis)

    @property
    def chart(self) -> alt.Chart:
        """
        Get a chart visualizing themes in free text responses.

        In test mode, returns a mock chart with sample theme data.
        In normal mode, uses ThemeFinder to identify themes and create a
        visualization of theme frequency.

        Returns:
            Altair chart object showing theme distribution
        """
        # In test mode, return a mock chart for free text questions
        if self.test_mode:
            import random

            # Create sample theme data for visualization
            sample_themes = ["Theme 1", "Theme 2", "Theme 3", "Theme 4", "Theme 5"]
            sample_counts = [random.randint(5, 20) for _ in range(len(sample_themes))]

            # Create a DataFrame
            df = pd.DataFrame({"theme": sample_themes, "count": sample_counts})

            # Create a simple bar chart
            chart = (
                alt.Chart(df)
                .mark_bar()
                .encode(
                    x=alt.X("theme:N", title="Themes"),
                    y=alt.Y("count:Q", title="Count"),
                    color=alt.Color("theme:N", legend=None),
                )
                .properties(
                    width=600,
                    height=300,
                    title=f"Test Mode: Theme Analysis for {self.question.question_name}",
                )
            )

            return chart
        else:
            # In normal mode, use the actual ThemeFinder
            try:
                from .themes import ThemeFinder
            except ImportError:
                from themes import ThemeFinder
            tf = ThemeFinder(
                question=self.question.question_text,
                answers=self.answers,
                context="Survey results",
            )
            return tf.create_theme_counts_chart()


class AnalyzeQuestionLinearScale(AnalyzeQuestion):
    """
    Analyzer for linear scale questions.

    This class specializes the general question analyzer for linear scale questions,
    where respondents select a value on a numerical scale. It provides visualizations
    showing the distribution of responses across the scale.

    Attributes:
        Inherits all attributes from AnalyzeQuestion
    """

    _question_type = "linear_scale"

    def _generate_analyses(self) -> None:
        """
        Generate analyses for linear scale questions.

        This method creates and adds the following analysis objects:
        1. Frequency Distribution Analysis - shows distribution of responses across scale values
        2. Response Overview Analysis - provides a general overview of the responses
        """
        from .analysis import FrequencyAnalysis, ResponseAnalysis

        # Add frequency analysis
        frequency_analysis = FrequencyAnalysis(
            question=self.question, answers=self.answers, test_mode=self.test_mode
        )
        self._analyses.append(frequency_analysis)

        # Add response overview
        response_analysis = ResponseAnalysis(
            question=self.question, answers=self.answers, test_mode=self.test_mode
        )
        self._analyses.append(response_analysis)

    @property
    def chart(self) -> alt.Chart:
        """
        Get a bar chart visualizing linear scale responses.

        This property lazily creates a bar chart showing the frequency
        distribution of responses across the scale values.

        Returns:
            Altair chart object showing response distribution
        """
        if self._chart is None:
            # Create bar chart of response distribution
            self._chart = create_survey_bar_chart(
                self.answers, self.question.question_options
            )
        return self._chart


class AnalyzeQuestionCheckBox(AnalyzeQuestion):
    """
    Analyzer for checkbox questions.

    This class specializes the general question analyzer for checkbox questions,
    where respondents can select multiple options from a set. It provides visualizations
    showing the distribution of selections across options.

    Attributes:
        Inherits all attributes from AnalyzeQuestion
    """

    _question_type = "checkbox"

    def _generate_analyses(self) -> None:
        """
        Generate analyses for checkbox questions.

        This method creates and adds the following analysis objects:
        1. Frequency Distribution Analysis - shows distribution of selections across options
        2. Response Overview Analysis - provides a general overview of the responses
        """
        from .analysis import FrequencyAnalysis, ResponseAnalysis

        # Add frequency analysis (using same approach as multiple choice)
        frequency_analysis = FrequencyAnalysis(
            question=self.question, answers=self.answers, test_mode=self.test_mode
        )
        self._analyses.append(frequency_analysis)

        # Add response overview
        response_analysis = ResponseAnalysis(
            question=self.question, answers=self.answers, test_mode=self.test_mode
        )
        self._analyses.append(response_analysis)

    @property
    def chart(self) -> alt.Chart:
        """
        Get a bar chart visualizing checkbox responses.

        This property lazily creates a bar chart showing the frequency
        distribution of selections across options. For checkbox questions,
        it first flattens the responses since each response can contain
        multiple selections.

        Returns:
            Altair chart object showing selection distribution
        """
        if self._chart is None:
            # For checkbox, answers may contain multiple selected items
            # Flatten all answers into a single list
            flattened_answers = []
            for answer in self.answers:
                if isinstance(answer, list):
                    flattened_answers.extend(answer)
                else:
                    flattened_answers.append(answer)

            # Create bar chart of response distribution
            self._chart = create_survey_bar_chart(
                flattened_answers, self.question.question_options
            )
        return self._chart


def create_analyzer(
    question: Question, answers: List[Any], test_mode: bool = False
) -> AnalyzeQuestion:
    """
    Factory function to create the appropriate analyzer for a given question type.

    This function examines the question type and returns an instance of the
    appropriate analyzer subclass tailored to that type of question.

    Args:
        question: The question object to analyze
        answers: The list of responses to analyze
        test_mode: If True, uses placeholder data instead of LLM-generated analysis

    Returns:
        An instance of the appropriate analyzer subclass for the question type

    Raises:
        ValueError: If the question type is not supported
    """
    handlers = {
        "multiple_choice": AnalyzeQuestionMultipleChoice,
        "free_text": AnalyzeQuestionFreeText,
        "linear_scale": AnalyzeQuestionLinearScale,
        "checkbox": AnalyzeQuestionCheckBox,
    }
    f = handlers[question.question_type]
    return f(
        question_text=question.question_text,
        answers=answers,
        question_options=getattr(question, "question_options"),
        test_mode=test_mode,
    )


# class Analyis:
#     def __init__(self, results: Results) -> None:
#         self.results = results
#         self.analyses = {}

#     @property
#     def questions(self) -> List[Question]:
#         return self.results.survey.questions

#     def run_analysis(self) -> None:
#         for question in self.questions:
#             print("Now analyzing question: ", question.question_name)
#             answers = self.results.select(question.question_name).to_list()
#             analyzer = create_analyzer(question, answers, test_mode=True)
#             self.analyses[question.question_name] = analyzer.get_analyses()


if __name__ == "__main__":
    from edsl.results import Results

    r = Results.example()
    # a = Analyis(r)
    # a.run_analysis()
