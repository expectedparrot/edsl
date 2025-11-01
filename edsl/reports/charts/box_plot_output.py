from .chart_output import ChartOutput
import pandas as pd
import altair as alt


class BoxPlotOutput(ChartOutput):
    """A box plot showing distribution of numerical data across categories."""

    pretty_name = "Box Plot"
    pretty_short_name = "Box plot"
    methodology = "Creates box plots to show the distribution of numerical responses across different categories"

    def __init__(self, results, *question_names):
        if len(question_names) != 2:
            raise ValueError("BoxPlotOutput requires exactly two question names")
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
        return f"A box plot showing the distribution of the numerical question '{self.num_question.question_text}' across categories of '{self.cat_question.question_text}'. Each box shows the median, quartiles, and range of responses for that category."

    @classmethod
    def can_handle(cls, *question_objs):
        """
        Check if this chart type can handle the given questions.
        Returns True if there is exactly one numerical/linear_scale and one multiple choice question.
        """
        if len(question_objs) != 2:
            return False

        types = [q.question_type for q in question_objs]
        return (
            any(t in ["numerical", "linear_scale"] for t in types)
            and "multiple_choice" in types
            and any(hasattr(q, "question_options") for q in question_objs)
        )

    def output(self):
        """
        Generate a box plot showing distribution by category.

        Returns:
            An Altair chart object showing the box plot
        """
        # Create DataFrame with both answers
        df = pd.DataFrame({"Value": self.num_answers, "Category": self.cat_answers})

        # Calculate summary statistics for tooltips
        stats = (
            df.groupby("Category")["Value"]
            .agg(
                [
                    ("Count", "count"),
                    ("Mean", "mean"),
                    ("Median", "median"),
                    ("Q1", lambda x: x.quantile(0.25)),
                    ("Q3", lambda x: x.quantile(0.75)),
                    ("Min", "min"),
                    ("Max", "max"),
                ]
            )
            .reset_index()
        )

        # Create the box plot
        chart = (
            alt.Chart(df)
            .mark_boxplot(
                size=50,
                extent="min-max",  # Show whiskers to min/max
                outliers=True,  # Show outlier points
                median=alt.MarkConfig(color="white"),  # Make median line stand out
                ticks=True,
            )
            .encode(
                x=alt.X(
                    "Category:N",
                    title=self.cat_question.question_text,
                    sort=list(self.cat_question.question_options),
                ),  # Preserve original order
                y=alt.Y("Value:Q", title=self.num_question.question_text),
                color=alt.Color(
                    "Category:N", legend=None, scale=alt.Scale(scheme="category10")
                ),
            )
        )

        # Add jittered points
        points = (
            alt.Chart(df)
            .mark_circle(size=40, opacity=0.3)
            .encode(
                x=alt.X("Category:N"),
                y=alt.Y("Value:Q"),
                color=alt.Color(
                    "Category:N", legend=None, scale=alt.Scale(scheme="category10")
                ),
                tooltip=[
                    alt.Tooltip("Category:N", title=self.cat_question.question_text),
                    alt.Tooltip(
                        "Value:Q", title=self.num_question.question_text, format=".2f"
                    ),
                ],
            )
        )

        # Combine box plot with points
        combined = (
            (chart + points)
            .properties(
                title=f"Distribution of {self.num_question.question_text} by {self.cat_question.question_text}",
                width=600,
                height=400,
            )
            .configure_axis(labelFontSize=12, titleFontSize=14)
            .configure_title(fontSize=16, anchor="middle")
        )

        return combined
