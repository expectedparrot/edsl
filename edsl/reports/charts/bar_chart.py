import pandas as pd
import altair as alt

from .base import ChartOutput


class BarChartOutput(ChartOutput):
    """A bar chart showing frequency distribution."""

    def __init__(self, results, *question_names):
        if len(question_names) != 1:
            raise ValueError("BarChartOutput requires exactly one question name")
        super().__init__(results, *question_names)
        self.question = self.questions[0]

        # Handle options based on question type
        if self.question.question_type == "yes_no":
            self.question_options = ["Yes", "No"]
        elif self.question.question_type == "likert_five":
            self.question_options = [
                "Strongly Disagree",
                "Disagree",
                "Neutral",
                "Agree",
                "Strongly Agree",
            ]
        elif hasattr(self.question, "question_options"):
            self.question_options = [str(opt) for opt in self.question.question_options]
        else:
            self.question_options = None

        self.answers = self.results.select(self.get_data_column(self.questions[0])).to_list()

    @property
    def narrative(self):
        if self.question.question_type == "yes_no":
            return f"A bar chart showing the distribution of yes/no responses to the question: '{self.question.question_text}'. Each bar represents the count and percentage of 'Yes' and 'No' responses."
        elif self.question.question_type == "likert_five":
            return f"A bar chart showing the distribution of agreement levels for the statement: '{self.question.question_text}'. Each bar represents the count and percentage of responses from 'Strongly Disagree' to 'Strongly Agree'."
        else:
            return f"A bar chart showing the distribution of responses to the {self.question.question_type} question: '{self.question.question_text}'. Each bar represents the count and percentage of responses for each option."

    @classmethod
    def can_handle(cls, *question_objs):
        """
        Check if this chart type can handle the given questions.
        Returns True if there is exactly one question and it is of type 'multiple_choice', 'linear_scale', 'yes_no', or 'likert_five'.
        """
        if len(question_objs) != 1:
            return False
        try:
            return question_objs[0].question_type in [
                "multiple_choice",
                "linear_scale",
                "yes_no",
                "likert_five",
            ] and (
                hasattr(question_objs[0], "question_options")
                or question_objs[0].question_type in ["yes_no", "likert_five"]
            )
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
                # Handle different question types
                if self.question.question_type == "yes_no":
                    count = sum(
                        1
                        for answer in self.answers
                        if (option == "Yes" and answer is True)
                        or (option == "No" and answer is False)
                    )
                elif self.question.question_type == "likert_five":
                    # Assuming answers are 1-5, map them to the Likert scale options
                    likert_map = {
                        1: "Strongly Disagree",
                        2: "Disagree",
                        3: "Neutral",
                        4: "Agree",
                        5: "Strongly Agree",
                    }
                    count = sum(
                        1 for answer in self.answers if likert_map.get(answer) == option
                    )
                else:
                    # Convert both the option and answers to strings for comparison
                    count = sum(1 for answer in self.answers if str(answer) == option)
                option_counts[option] = count
        else:
            # If no predefined options (shouldn't happen), count unique answers
            for answer in self.answers:
                str_answer = str(answer)
                option_counts[str_answer] = option_counts.get(str_answer, 0) + 1

        # Calculate total responses and percentages
        total_responses = sum(option_counts.values())

        # Create DataFrame from the counts and percentages
        df = pd.DataFrame(
            {
                "Option": list(option_counts.keys()),
                "Count": list(option_counts.values()),
                "Percentage": [
                    count / total_responses * 100 if total_responses > 0 else 0
                    for count in option_counts.values()
                ],
            }
        )

        # For Likert scale, ensure correct order
        if self.question.question_type == "likert_five":
            df["Option"] = pd.Categorical(
                df["Option"], categories=self.question_options, ordered=True
            )
            df = df.sort_values("Option")
        else:
            # Sort by count for other types
            df = df.sort_values("Count", ascending=False)

        # Create the base bar chart
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
                    sort=list(df["Option"]),  # Use the sorted order
                    axis=alt.Axis(
                        labelAngle=45,  # Rotate labels 45 degrees
                        labelAlign="left",  # Align rotated labels to the left
                        labelPadding=10,  # Add some padding for better spacing
                    ),
                ),
                y=alt.Y("Count:Q", title="Number of Responses"),
                color=alt.value("#4C78A8"),  # Use a single, pleasing color
                tooltip=[
                    "Option",
                    "Count",
                    alt.Tooltip("Percentage:Q", format=".1f", title="Percentage"),
                ],
            )
        )

        # Add text labels showing percentages
        text = (
            bars.mark_text(
                align="center",
                baseline="bottom",
                dy=-5,  # Shift label up slightly from top of bar
                fontSize=11,
            )
            .encode(
                text=alt.Text("Percentage:Q", format=".1f", title="Percentage"),
                color=alt.value("black"),
            )
            .transform_calculate(percentage_label=alt.datum.Percentage + "%")
        )

        # Combine bars and text
        chart = (
            (bars + text)
            .properties(
                title=f"Distribution of {self.question.question_text}",
                width=500,
                height=300,
                padding={"bottom": 50},  # Add padding at bottom for rotated labels
            )
            .configure_axis(labelFontSize=12, titleFontSize=14)
            .configure_title(fontSize=16, anchor="middle")
        )

        return chart
