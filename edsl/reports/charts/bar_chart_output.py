from .chart_output import ChartOutput
import pandas as pd
import altair as alt
import math


class BarChartOutput(ChartOutput):
    """A bar chart showing frequency distribution."""

    pretty_name = "Distribution of responses"
    pretty_short_name = "Distribution of responses"
    methodology = "Creates a bar chart showing the frequency distribution of responses to multiple choice or linear scale questions"

    def __init__(self, results, *question_names):
        if len(question_names) != 1:
            raise ValueError("BarChartOutput requires exactly one question name or comment field")
        super().__init__(results, *question_names)
        self.question = self.questions[0]  # Use the question from parent's __init__

        # Convert options to strings if they exist
        if hasattr(self.question, "question_options"):
            self.question_options = [str(opt) for opt in self.question.question_options]
        else:
            self.question_options = None

        # Use get_data_column to get the correct column name
        column_name = self.get_data_column(self.question)
        self.answers = self.results.select(column_name).to_list()

    @property
    def narrative(self):
        return f"A bar chart showing the distribution of responses to the {self.question.question_type} question: '{self.question.question_text}'. Each bar represents the count of responses for each option."

    @classmethod
    def can_handle(cls, *question_objs):
        """
        Check if this chart type can handle the given questions.
        Returns True if there is exactly one question and it is of type 'multiple_choice' or 'linear_scale'.
        """
        if len(question_objs) != 1:
            return False
        try:
            return question_objs[0].question_type in [
                "multiple_choice",
                "linear_scale",
            ] and hasattr(question_objs[0], "question_options")
        except AttributeError:
            return False

    def output(self):
        """
        Generate a bar chart showing frequency distribution.

        Returns:
            An Altair chart object showing response distribution
        """
        # Count occurrences of each option
        option_counts = {}
        if self.question_options:
            for option in self.question_options:
                # Convert both the option and answers to strings for comparison
                count = sum(1 for answer in self.answers if str(answer) == option)
                option_counts[option] = count
        else:
            # If no predefined options (shouldn't happen), count unique answers
            for answer in self.answers:
                str_answer = str(answer)
                option_counts[str_answer] = option_counts.get(str_answer, 0) + 1

        # Calculate total responses
        total_responses = sum(option_counts.values())

        # Create DataFrame from the counts with percentages and standard errors
        data = []
        for option, count in option_counts.items():
            percentage = (count / total_responses) * 100 if total_responses > 0 else 0

            # Calculate standard error using p * (1 - p) / n approximation
            if percentage == 0 or percentage == 100:
                se = 0
            else:
                p = percentage / 100
                se = (
                    math.sqrt(p * (1 - p) / total_responses) * 100
                )  # Convert to percentage

            # Percentage label
            label = f"{percentage:.1f}%"

            data.append(
                {
                    "Option": option,
                    "Count": count,
                    "Percentage": percentage,
                    "SE": se,
                    "Label": label,
                    "Error_Lower": max(0, percentage - se),  # Don't go below 0
                    "Error_Upper": min(100, percentage + se),  # Don't go above 100
                }
            )

        df = pd.DataFrame(data)

        # Create the bar chart with a clean, modern style
        bars = (
            alt.Chart(df)
            .mark_bar(
                cornerRadius=2,  # Slightly rounded corners
                opacity=0.8,  # Slight transparency
            )
            .encode(
                x=alt.X(
                    "Option:N",
                    title="Response Option",
                    sort=list(option_counts.keys()),  # Preserve original order
                    axis=alt.Axis(labelAngle=45),
                ),
                y=alt.Y("Count:Q", title="Count of responses"),
                color=alt.value("#4C78A8"),  # Use a single, pleasing color
                tooltip=["Option", "Count", "Percentage"],
            )
        )

        # Add count labels on top of bars
        text = (
            alt.Chart(df)
            .mark_text(
                align="center",
                baseline="bottom",
                dy=-5,  # Offset above the bar
                fontSize=12,
                fontWeight="bold",
            )
            .encode(
                x=alt.X("Option:N", sort=list(option_counts.keys())),
                y=alt.Y("Count:Q"),
                text=alt.Text("Label:N"),
            )
        )

        # Combine bars and text
        chart = (
            (bars + text)
            .properties(title="Distribution of responses", width=500, height=300)
            .configure_axis(labelFontSize=12, titleFontSize=14)
            .configure_title(fontSize=16, anchor="middle")
        )

        return chart
