from .chart_output import ChartOutput
import pandas as pd
import altair as alt
import textwrap


class FacetedBarChartOutput(ChartOutput):
    """A faceted bar chart showing distribution of one multiple choice question across another."""

    pretty_name = "Distribution of responses, by facets"
    pretty_short_name = "Distribution of responses, by facets"
    methodology = "Creates separate bar charts for each category to show how responses to one question vary across another"

    def __init__(self, results, *question_names):
        if len(question_names) != 2:
            raise ValueError(
                "FacetedBarChartOutput requires exactly two question names"
            )
        super().__init__(results, *question_names)

        # Get questions
        self.q1 = self.results.survey.get(
            self.question_names[0]
        )  # This will be the main bars
        self.q2 = self.results.survey.get(
            self.question_names[1]
        )  # This will be the facets

        # Get answers
        self.answers1 = self.results.select(
            f"answer.{self.question_names[0]}"
        ).to_list()
        self.answers2 = self.results.select(
            f"answer.{self.question_names[1]}"
        ).to_list()

    def _format_question_text(self, text, width=30):
        """Format question text with line breaks for better readability."""
        # Use space instead of newlines to avoid Vega-Lite expression parsing issues
        return " ".join(textwrap.wrap(text, width=width))

    @property
    def narrative(self):
        return f"A faceted bar chart comparing responses between '{self.q1.question_text}' and '{self.q2.question_text}'. Each facet shows the distribution of responses for one category of the second question."

    @classmethod
    def can_handle(cls, *question_objs):
        """
        Check if this chart type can handle the given questions.
        Returns True if there are exactly two questions that are either multiple_choice or linear_scale,
        and both have question_options.
        """
        if len(question_objs) != 2:
            return False

        return all(
            q.question_type in ["multiple_choice", "linear_scale"]
            for q in question_objs
        ) and all(hasattr(q, "question_options") for q in question_objs)

    def output(self):
        """
        Generate a faceted bar chart showing distribution of answers.

        Returns:
            An Altair chart object showing the faceted distribution
        """
        # Create DataFrame with both answers
        df = pd.DataFrame(
            {
                "Primary": self.answers1,
                "Facet": self.answers2,
            }
        )

        # Count combinations
        counts = df.groupby(["Primary", "Facet"]).size().reset_index(name="Count")

        # Create the faceted bar chart with simple titles to avoid tooltip issues
        chart = (
            alt.Chart(counts)
            .mark_bar(opacity=0.8, cornerRadius=2)
            .encode(
                x=alt.X(
                    "Primary:N",
                    title="Response",  # Simple generic title
                    sort=list(self.q1.question_options),  # Preserve original order
                    axis=alt.Axis(labelAngle=45),
                ),
                y=alt.Y("Count:Q", title="Count"),  # Simple generic title
                color=alt.Color(
                    "Primary:N", scale=alt.Scale(scheme="category10"), legend=None
                ),  # Remove legend to avoid redundancy
                column=alt.Column(
                    "Facet:N",
                    title="Category",  # Simple generic title
                    sort=list(self.q2.question_options),  # Preserve original order
                    header=alt.Header(labelOrient="bottom", labelAngle=0),
                ),
                tooltip=[
                    alt.Tooltip("Primary:N", title="Response"),
                    alt.Tooltip("Facet:N", title="Category"),
                    alt.Tooltip("Count:Q", title="Count"),
                ],
            )
            .properties(
                title="Distribution by Category",  # Simple generic title
                width=150,  # Width per facet
                height=300,
            )
            .configure_axis(labelFontSize=12, titleFontSize=14)
            .configure_title(fontSize=16, anchor="middle")
            .configure_header(titleFontSize=14, labelFontSize=12)
        )

        return chart
