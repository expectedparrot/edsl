import tempfile
import altair as alt
from edsl import FileStore

from .chart_output import ChartOutput
from ..themes import ThemeFinder


class ThemeFinderOutput(ChartOutput):
    """A theme analysis visualization for free text responses using ThemeFinder."""

    pretty_name = "Theme Analysis"
    pretty_short_name = "Theme analysis"
    methodology = "Uses natural language processing to identify common themes in free text responses, then analyzes sentiment for each theme"

    def __init__(self, results, *question_names, free_text_sample_config=None):
        if len(question_names) != 1:
            raise ValueError("ThemeFinderOutput requires exactly one question name")
        super().__init__(results, *question_names)
        self.question = self.questions[0]
        self.answers = self.results.select(self.get_data_column(self.questions[0])).to_list()
        self.free_text_sample_config = free_text_sample_config or {}

        # Get question text and survey context if available
        self.question_text = self.question.question_text
        self.context = None

        # Try to get survey context if it exists
        if hasattr(self.results, "metadata") and self.results.metadata:
            if "context" in self.results.metadata:
                self.context = self.results.metadata["context"]

        # Apply sampling if configured
        self._sampled_answers = self._apply_sampling(
            self.answers, self.question_names[0]
        )

        # Lazy initialization - don't create ThemeFinder until actually needed
        self._theme_finder = None
        self._initialization_error = None
        self._initialization_attempted = False

    def _apply_sampling(self, answers, question_name):
        """Apply sampling configuration to the answers for this question."""
        if not self.free_text_sample_config:
            return answers

        # Check for question-specific configuration first
        if question_name in self.free_text_sample_config:
            sample_size = self.free_text_sample_config[question_name]
        elif "_global" in self.free_text_sample_config:
            sample_size = self.free_text_sample_config["_global"]
        else:
            return answers

        # Filter out None values before sampling
        valid_answers = [a for a in answers if a is not None]

        if not valid_answers or len(valid_answers) <= sample_size:
            return answers  # Return original if no valid answers or sample size >= valid answers

        # Sample without replacement using random.sample
        import random

        random.seed("reports_sampling")  # Use consistent seed for reproducibility
        sampled_answers = random.sample(valid_answers, sample_size)

        # Add back None values to maintain original structure if needed
        # For theme analysis, we usually just want the valid answers
        return sampled_answers

    @property
    def theme_finder(self):
        """Lazily initialize ThemeFinder only when first accessed."""
        if not self._initialization_attempted:
            self._initialization_attempted = True
            try:
                self._theme_finder = ThemeFinder(
                    answers=self._sampled_answers,
                    question=self.question_text,
                    context=self.context,
                )
            except Exception as e:
                self._initialization_error = e
                self._theme_finder = None

        return self._theme_finder

    @property
    def narrative(self):
        return f"A theme analysis of responses to the free text question: '{self.question_text}'. The chart shows the frequency distribution of identified themes and sentiment analysis for each theme."

    @classmethod
    def can_handle(cls, *question_objs):
        """
        Check if this chart type can handle the given questions.
        Returns True if there is exactly one question and it is of type 'free_text'.
        """
        return len(question_objs) == 1 and question_objs[0].question_type == "free_text"

    def get_theme_counts_chart(self):
        """
        Get a bar chart showing the distribution of themes.

        Returns:
            An Altair chart object showing theme distribution
        """
        if self.theme_finder is None:
            return self._create_error_chart(
                f"ThemeFinder initialization failed: {self._initialization_error}"
            )

        try:
            return self.theme_finder.create_theme_counts_chart()
        except Exception as e:
            return self._create_error_chart(f"Theme counts chart failed: {str(e)}")

    def get_sentiment_chart(self):
        """
        Get a faceted bar chart showing sentiment distribution for each theme.

        Returns:
            An Altair chart object showing sentiment analysis by theme
        """
        if self.theme_finder is None:
            return self._create_error_chart(
                f"ThemeFinder initialization failed: {self._initialization_error}"
            )

        try:
            return self.theme_finder.create_sentiment_chart()
        except Exception as e:
            return self._create_error_chart(f"Sentiment chart failed: {str(e)}")

    def get_sentiment_dot_chart(self):
        """
        Get a dot chart showing individual responses colored by sentiment.

        Returns:
            An Altair chart object showing individual responses by sentiment
        """
        if self.theme_finder is None:
            return self._create_error_chart(
                f"ThemeFinder initialization failed: {self._initialization_error}"
            )

        try:
            return self.theme_finder.create_sentiment_dot_chart()
        except Exception as e:
            return self._create_error_chart(f"Sentiment dot chart failed: {str(e)}")

    def get_sentiment_examples_chart(self):
        """
        Get a chart showing example answers for each sentiment level within each theme.

        Returns:
            An Altair chart object showing example quotes
        """
        if self.theme_finder is None:
            return self._create_error_chart(
                f"ThemeFinder initialization failed: {self._initialization_error}"
            )

        try:
            return self.theme_finder.create_sentiment_examples_chart()
        except Exception as e:
            return self._create_error_chart(
                f"Sentiment examples chart failed: {str(e)}"
            )

    def output(self):
        """
        Generate the theme counts chart as the default visualization.

        Returns:
            An Altair chart object showing theme distribution
        """
        from ..warning_utils import print_error, print_info, progress_status

        print_info(
            f"ThemeFinderOutput.output() called for question: {self.question_names[0]}"
        )

        if self.theme_finder is None:
            print_error(
                f"ThemeFinder initialization failed: {self._initialization_error}"
            )
            error_chart = self._create_error_chart(
                f"ThemeFinder initialization failed: {self._initialization_error}"
            )
            return error_chart

        try:
            # Use progress indicator for long-running theme analysis
            with progress_status(f"Analyzing themes for '{self.question_names[0]}'..."):
                chart = self.get_theme_counts_chart()

            if chart is None:
                print_error("get_theme_counts_chart() returned None")
                error_chart = self._create_error_chart("No theme data available")
                return error_chart

            # Final validation - ensure it's actually an Altair Chart
            if not isinstance(
                chart, (alt.Chart, alt.LayerChart, alt.FacetChart, alt.TopLevelMixin)
            ):
                print_error(f"Chart is not an Altair Chart, got: {type(chart)}")
                error_chart = self._create_error_chart(
                    f"Invalid chart type: {type(chart)}"
                )
                return error_chart

            return chart
        except Exception as e:
            print_error(f"Theme analysis failed: {str(e)}")
            error_chart = self._create_error_chart(f"Chart generation failed: {str(e)}")

            # Final validation of error chart too
            if not isinstance(
                error_chart,
                (alt.Chart, alt.LayerChart, alt.FacetChart, alt.TopLevelMixin),
            ):
                print_error(f"Error chart is not an Altair Chart: {type(error_chart)}")
                # Create the most basic chart possible as absolute last resort
                import pandas as pd

                basic_chart = (
                    alt.Chart(pd.DataFrame({"x": [1]})).mark_point().encode(x="x:Q")
                )
                return basic_chart

            return error_chart

    def _create_error_chart(self, error_message: str):
        """Create a simple error chart when theme analysis fails."""
        import pandas as pd
        from ..warning_utils import print_info, print_error

        print_info(f"Creating error chart with message: {error_message}")

        try:
            # Create a simple chart with error message
            error_data = pd.DataFrame({"message": [error_message], "x": [1], "y": [1]})

            chart = (
                alt.Chart(error_data)
                .mark_text(align="center", baseline="middle", fontSize=12, color="red")
                .encode(
                    x=alt.X("x:Q", scale=alt.Scale(domain=[0, 2]), axis=None),
                    y=alt.Y("y:Q", scale=alt.Scale(domain=[0, 2]), axis=None),
                    text=alt.Text("message:N"),
                )
                .properties(
                    width=600,
                    height=400,
                    title=f"Theme Analysis Error - {self.question_names[0]}",
                )
                .resolve_scale(x="independent", y="independent")
            )

            print_info(f"Error chart created successfully, type: {type(chart)}")
            print_info(f"Is instance of alt.Chart: {isinstance(chart, alt.Chart)}")

            # Verify it's a valid chart by checking it has the required methods
            if hasattr(chart, "to_dict") and hasattr(chart, "save"):
                print_info("Chart has required methods (to_dict, save)")
                return chart
            else:
                print_error("Chart missing required methods")
                raise ValueError("Created chart is missing required methods")

        except Exception as e:
            print_error(f"Failed to create error chart: {e}")
            import traceback

            print_error(f"Traceback: {traceback.format_exc()}")

            # Create an even simpler fallback chart with minimal dependencies
            try:
                # Most basic possible Altair chart
                fallback_data = pd.DataFrame({"x": [0], "y": [0]})
                simple_chart = (
                    alt.Chart(fallback_data)
                    .mark_circle(size=100, color="red")
                    .encode(
                        x=alt.X("x:Q", axis=alt.Axis(title="Error")),
                        y=alt.Y("y:Q", axis=alt.Axis(title="Chart Creation Failed")),
                    )
                    .properties(
                        width=400,
                        height=300,
                        title="Error Creating Theme Analysis Chart",
                    )
                )
                print_info(f"Fallback chart created, type: {type(simple_chart)}")
                return simple_chart
            except Exception as e2:
                print_error(f"Even fallback chart creation failed: {e2}")

                # Last resort - create the most minimal chart possible
                try:
                    minimal_chart = (
                        alt.Chart(pd.DataFrame({"a": [1]})).mark_point().encode(x="a")
                    )
                    print_info(f"Minimal chart created, type: {type(minimal_chart)}")
                    return minimal_chart
                except Exception as e3:
                    print_error(f"Minimal chart creation also failed: {e3}")
                    raise RuntimeError(
                        f"Unable to create any type of Altair chart: {e3}"
                    )

    @property
    def scenario_output(self):
        """
        Returns the theme analysis as a PNG file.
        """
        chart = self.output()

        # Create a temporary file with .png extension
        temp_file = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
        temp_path = temp_file.name
        temp_file.close()

        # Save the chart as PNG
        chart.save(temp_path, scale_factor=2.0)

        return FileStore(path=temp_path)

    def generate_html(self, section_id, collapsed=False):
        """Generate specialized HTML for theme finder with multiple charts."""
        title = getattr(self, "pretty_name", self.__class__.__name__)
        initial_state = "closed" if collapsed else "open"
        toggle_icon = "▶" if collapsed else "▼"

        if self.theme_finder is None:
            html = f"""
            <div class="subsection theme-finder-output">
                <div class="subsection-header" onclick="toggleSubsection('{section_id}')">
                    <h3>{title}</h3>
                    <span class="subsection-toggle">{toggle_icon}</span>
                </div>
                <div id="{section_id}" class="subsection-content {initial_state}">
                    <div class="error-message">
                        <p style="color: red; font-weight: bold;">Theme Analysis Error</p>
                        <p>ThemeFinder initialization failed: {self._initialization_error}</p>
                        <p>This usually indicates issues with the free text data or missing dependencies.</p>
                    </div>
                </div>
            </div>
            """
            return html

        html = f"""
        <div class="subsection theme-finder-output">
            <div class="subsection-header" onclick="toggleSubsection('{section_id}')">
                <h3>{title}</h3>
                <span class="subsection-toggle">{toggle_icon}</span>
            </div>
            <div id="{section_id}" class="subsection-content {initial_state}">
                <div class="theme-finder-container">
                    <h4>Theme Distribution</h4>
                    <div class="chart-container">
                        {self._get_chart_html(self.get_theme_counts_chart(), "Theme Distribution")}
                    </div>
                    
                    <h4>Sentiment Analysis by Theme</h4>
                    <div class="chart-container">
                        {self._get_chart_html(self.get_sentiment_chart(), "Sentiment Analysis")}
                    </div>
                    
                    <h4>Individual Responses by Sentiment</h4>
                    <p>Each dot represents an individual response, colored by sentiment. Hover over dots to see the actual comment.</p>
                    <div class="chart-container">
                        {self._get_chart_html(self.get_sentiment_dot_chart(), "Individual Responses by Sentiment")}
                    </div>
                    
                    <h4>Example Quotes by Theme and Sentiment</h4>
                    <div class="chart-container">
                        {self._get_chart_html(self.get_sentiment_examples_chart(), "Example Quotes")}
                    </div>
                    
                    <p><em>Note: For a full report with examples, use: theme_output.generate_report()</em></p>
                </div>
            </div>
        </div>
        """
        return html

    def _get_chart_html(self, chart, title):
        """Helper to get HTML for a chart, including error handling"""
        try:
            if chart is None:
                return f'<div class="error-message">No data available for {title}</div>'

            import json
            import uuid

            # Generate Vega-Lite embed code
            spec_json = json.dumps(chart.to_dict())
            unique_id = f"chart-{uuid.uuid4().hex}"

            html = f'<div id="{unique_id}"></div>'
            html += f'<script type="text/javascript">vegaEmbed("#{unique_id}", {spec_json}, {{"renderer": "svg"}});</script>'
            return html
        except Exception as e:
            return (
                f'<div class="error-message">Error displaying {title}: {str(e)}</div>'
            )

    def get_all_charts_for_docx(self):
        """
        Get all charts that should be included in DOCX generation.
        Returns a list of tuples: (chart_title, chart_object, description)
        """
        from ..warning_utils import print_error

        charts = []

        # Theme Distribution
        try:
            chart = self.get_theme_counts_chart()
            charts.append(
                ("Theme Distribution", chart, "Distribution of themes across responses")
            )
        except Exception as e:
            print_error(f"Failed to get theme counts chart: {e}")

        # Sentiment Analysis by Theme
        try:
            chart = self.get_sentiment_chart()
            charts.append(
                (
                    "Sentiment Analysis by Theme",
                    chart,
                    "Sentiment distribution for each identified theme",
                )
            )
        except Exception as e:
            print_error(f"Failed to get sentiment chart: {e}")

        # Individual Responses by Sentiment
        try:
            chart = self.get_sentiment_dot_chart()
            charts.append(
                (
                    "Individual Responses by Sentiment",
                    chart,
                    "Each dot represents an individual response, colored by sentiment",
                )
            )
        except Exception as e:
            print_error(f"Failed to get sentiment dot chart: {e}")

        # Example Quotes by Theme and Sentiment
        try:
            chart = self.get_sentiment_examples_chart()
            charts.append(
                (
                    "Example Quotes by Theme and Sentiment",
                    chart,
                    "Representative quotes for each sentiment level within themes",
                )
            )
        except Exception as e:
            print_error(f"Failed to get sentiment examples chart: {e}")

        return charts

    def generate_report(self):
        """
        Generate a comprehensive HTML report of all ThemeFinder analyses.

        Returns:
            str: HTML string containing the complete report
        """
        if self.theme_finder is None:
            return f"""
            <div class="theme-finder-error-report">
                <h2>Theme Analysis Error Report</h2>
                <p style="color: red; font-weight: bold;">ThemeFinder initialization failed</p>
                <p><strong>Error:</strong> {self._initialization_error}</p>
                <p><strong>Question:</strong> {self.question_text}</p>
                <p><strong>Number of responses:</strong> {len(self.answers) if self.answers else 0}</p>
                <p>This usually indicates issues with the free text data, missing dependencies, or invalid configuration.</p>
                
                <h3>Debugging Tips:</h3>
                <ul>
                    <li>Check that your responses contain valid text data</li>
                    <li>Ensure you have the required LLM dependencies installed</li>
                    <li>Verify your EDSL configuration is set up correctly</li>
                    <li>Check that the question is of type 'free_text'</li>
                </ul>
            </div>
            """

        return self.theme_finder.report()
