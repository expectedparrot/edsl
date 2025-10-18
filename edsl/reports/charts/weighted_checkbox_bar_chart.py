from .chart_output import ChartOutput
import pandas as pd
import altair as alt


class WeightedCheckboxBarChart(ChartOutput):
    """A bar chart showing weighted frequency distribution for checkbox questions."""

    pretty_name = "Bar Chart (Weighted)"
    pretty_short_name = "Weighted bar chart"
    methodology = "Creates a bar chart where each respondent's checkbox selections are weighted by the inverse of their total selections"

    def __init__(self, results, *question_names):
        if len(question_names) != 1:
            raise ValueError(
                "WeightedCheckboxBarChart requires exactly one question name"
            )
        super().__init__(results, *question_names)
        self.question = self.results.survey.get(self.question_names[0])
        self.answers = self.results.select(f"answer.{self.question_names[0]}").to_list()

    @property
    def narrative(self):
        return f"A weighted bar chart showing the distribution of responses to the checkbox question: '{self.question.question_text}'. Each respondent's selections are weighted by the inverse of their total number of selections, ensuring equal weight per respondent."

    @classmethod
    def can_handle(cls, *question_objs):
        """
        Check if this chart type can handle the given questions.
        Returns True if there is exactly one question and it is of type 'checkbox'.
        """
        return len(question_objs) == 1 and question_objs[0].question_type == "checkbox"

    def _calculate_weighted_counts(self):
        """
        Calculate weighted counts for each option.
        Each respondent's selections are weighted by 1/n where n is their number of selections.
        """
        option_counts = {opt: 0.0 for opt in self.question.question_options}

        for answer in self.answers:
            if not answer:  # Skip empty answers
                continue

            # For checkbox questions, answer should be a list
            if not isinstance(answer, list):
                continue

            # Calculate weight based on number of selections
            num_selections = len(answer)
            if num_selections == 0:  # Skip if no selections
                continue

            weight = 1.0 / num_selections

            # Add weighted count to each selected option
            for selection in answer:
                if selection in option_counts:
                    option_counts[selection] += weight

        return option_counts

    def output(self):
        """
        Generate a bar chart showing weighted frequency distribution.

        Returns:
            An Altair chart object showing weighted response distribution
        """
        # Calculate weighted counts
        option_counts = self._calculate_weighted_counts()

        # Create DataFrame from the counts
        df = pd.DataFrame(
            {
                "Option": list(option_counts.keys()),
                "Weighted Count": list(option_counts.values()),
            }
        )

        # Sort by weighted count in descending order
        df = df.sort_values("Weighted Count", ascending=False)

        # Create the bar chart with a clean, modern style
        chart = (
            alt.Chart(df)
            .mark_bar(
                cornerRadius=2,  # Slightly rounded corners
                opacity=0.8,  # Slight transparency
            )
            .encode(
                x=alt.X(
                    "Option:N", title="Response Option", sort="-y"
                ),  # Sort by height descending
                y=alt.Y("Weighted Count:Q", title="Weighted Number of Responses"),
                color=alt.value("#4C78A8"),  # Use a single, pleasing color
                tooltip=["Option", alt.Tooltip("Weighted Count:Q", format=".2f")],
            )
            .properties(
                title=alt.TitleParams(
                    text=f"Weighted Distribution of {self.question.question_text}",
                    subtitle="Each respondent's selections weighted by 1/(number of selections)",
                    fontSize=16,
                    subtitleFontSize=12,
                    anchor="middle",
                ),
                width=500,
                height=300,
            )
            .configure_axis(labelFontSize=12, titleFontSize=14)
        )

        return chart
