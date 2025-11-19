import pandas as pd
import altair as alt

from .base import ChartOutput


class ScatterPlotOutput(ChartOutput):
    """A scatter plot comparing answers from two questions."""

    def __init__(self, results, *question_names):
        if len(question_names) != 2:
            raise ValueError("ScatterPlotOutput requires exactly two question names")
        super().__init__(results, *question_names)

        # Get questions and their options
        self.x_question = self.questions[0]
        self.y_question = self.questions[1]

        # Get answers for both questions
        self.x_answers = self.results.select(
            self.get_data_column(self.questions[0])
        ).to_list()
        self.y_answers = self.results.select(
            self.get_data_column(self.questions[1])
        ).to_list()

    @property
    def narrative(self):
        return f"A scatter plot comparing responses between two numerical questions: '{self.x_question.question_text}' and '{self.y_question.question_text}'. Each point represents one respondent's answers to both questions."

    @classmethod
    def can_handle(cls, *question_objs):
        """
        Check if this chart type can handle the given questions.
        Returns True if there are exactly two questions and both are numerical or linear_scale.
        """
        return len(question_objs) == 2 and all(
            q.question_type in ["numerical", "linear_scale"] for q in question_objs
        )

    def output(self):
        """
        Generate a scatter plot comparing two sets of answers.

        Returns:
            An Altair chart object showing the scatter plot
        """
        # Create DataFrame with both sets of answers
        df = pd.DataFrame({"x_values": self.x_answers, "y_values": self.y_answers})

        # Count frequency of each x,y combination
        df_counts = (
            df.groupby(["x_values", "y_values"]).size().reset_index(name="count")
        )

        # Create the scatter plot
        chart = (
            alt.Chart(df_counts)
            .mark_circle()
            .encode(
                x=alt.X("x_values:Q", title=self.x_question.question_text),
                y=alt.Y("y_values:Q", title=self.y_question.question_text),
                size=alt.Size(
                    "count:Q",
                    title="Number of Responses",
                    scale=alt.Scale(range=[100, 1000]),
                ),
                tooltip=["x_values", "y_values", "count"],
            )
            .properties(
                title=f"Comparison of {self.question_names[0]} vs {self.question_names[1]}",
                width=600,
                height=400,
            )
        )

        return chart
