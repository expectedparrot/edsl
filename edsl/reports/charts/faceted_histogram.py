import pandas as pd
import altair as alt

from .base import ChartOutput


class FacetedHistogramOutput(ChartOutput):
    """A faceted histogram showing distribution of a numerical question across categories."""

    def __init__(self, results, *question_names):
        if len(question_names) != 2:
            raise ValueError(
                "FacetedHistogramOutput requires exactly two question names"
            )
        super().__init__(results, *question_names)

        # Get questions and determine which is numerical/categorical
        q1, q2 = [self.results.survey.get(name) for name in question_names]
        if q1.question_type == "numerical":
            self.num_question = q1
            self.cat_question = q2
            self.num_answers = self.results.select(
                f"answer.{question_names[0]}"
            ).to_list()
            self.cat_answers = self.results.select(
                f"answer.{question_names[1]}"
            ).to_list()
        else:
            self.num_question = q2
            self.cat_question = q1
            self.num_answers = self.results.select(
                f"answer.{question_names[1]}"
            ).to_list()
            self.cat_answers = self.results.select(
                f"answer.{question_names[0]}"
            ).to_list()

    @property
    def narrative(self):
        return f"A faceted histogram comparing the numerical question '{self.num_question.question_text}' across categories of '{self.cat_question.question_text}'. Each facet shows the distribution of the numerical responses for one category."

    @classmethod
    def can_handle(cls, *question_objs):
        """
        Check if this chart type can handle the given questions.
        Returns True if there is exactly one numerical and one multiple choice question.
        """
        if len(question_objs) != 2:
            return False

        types = [q.question_type for q in question_objs]
        return (
            "numerical" in types
            and "multiple_choice" in types
            and any(hasattr(q, "question_options") for q in question_objs)
        )

    def output(self):
        """
        Generate faceted histograms showing distribution of numerical values by category.

        Returns:
            An Altair chart object showing the faceted histograms
        """
        # Create DataFrame with both answers
        df = pd.DataFrame({"Value": self.num_answers, "Category": self.cat_answers})

        # Calculate bin parameters based on data
        min_val = min(self.num_answers)
        max_val = max(self.num_answers)
        bin_width = (max_val - min_val) / 20  # Aim for about 20 bins

        # Create the faceted histogram
        chart = (
            alt.Chart(df)
            .mark_bar(opacity=0.8, cornerRadius=2)
            .encode(
                x=alt.X(
                    "Value:Q",
                    title=self.num_question.question_text,
                    bin=alt.Bin(maxbins=20),
                ),
                y=alt.Y("count():Q", title="Count"),
                color=alt.Color(
                    "Category:N",
                    scale=alt.Scale(scheme="category10"),
                    legend=alt.Legend(title=self.cat_question.question_text),
                ),
                column=alt.Column(
                    "Category:N",
                    title=self.cat_question.question_text,
                    sort=list(
                        self.cat_question.question_options
                    ),  # Preserve original order
                    header=alt.Header(labelOrient="bottom", labelAngle=0),
                ),
                tooltip=["Category:N", "Value:Q", "count():Q"],
            )
            .properties(
                title=f"Distribution of {self.num_question.question_text} by {self.cat_question.question_text}",
                width=200,  # Width per facet
                height=300,
            )
            .configure_axis(labelFontSize=12, titleFontSize=14)
            .configure_title(fontSize=16, anchor="middle")
            .configure_header(titleFontSize=14, labelFontSize=12)
        )

        return chart
