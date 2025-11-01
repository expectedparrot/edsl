from .table_output import TableOutput
import pandas as pd


class CrossTabulationTable(TableOutput):
    """A cross-tabulation table showing counts and percentages between two multiple choice questions."""

    pretty_name = "Cross Tabulation"
    pretty_short_name = "Cross tabulation"
    methodology = "Creates a cross-tabulation table showing the joint distribution of responses between two categorical variables"

    def __init__(self, results, *question_names):
        if len(question_names) != 2:
            raise ValueError("CrossTabulationTable requires exactly two question names")
        super().__init__(results, *question_names)

        # Get questions
        self.q1 = self.results.survey.get(self.question_names[0])
        self.q2 = self.results.survey.get(self.question_names[1])

        # Get answers
        self.answers1 = self.results.select(
            f"answer.{self.question_names[0]}"
        ).to_list()
        self.answers2 = self.results.select(
            f"answer.{self.question_names[1]}"
        ).to_list()

    @property
    def narrative(self):
        return f"A cross-tabulation table showing the relationship between two multiple choice questions: '{self.q1.question_text}' and '{self.q2.question_text}'. Each cell shows counts and percentages of respondents selecting each combination of answers."

    @classmethod
    def can_handle(cls, *question_objs):
        """Check if this table type can handle the given questions."""
        if len(question_objs) != 2:
            return False
        return all(q.question_type == "multiple_choice" for q in question_objs) and all(
            hasattr(q, "question_options") for q in question_objs
        )

    def output(self):
        """
        Generate a cross-tabulation table showing counts and percentages.

        Returns:
            A pandas DataFrame containing the cross-tabulation
        """
        # Create DataFrame with both answers
        df = pd.DataFrame({"Question1": self.answers1, "Question2": self.answers2})

        # Calculate counts
        counts = pd.crosstab(
            df["Question1"], df["Question2"], margins=True, margins_name="Total"
        )

        # Calculate percentages of total
        total = len(df)
        percentages = counts.copy() / total * 100

        # Create multi-level columns for counts and percentages
        result = pd.DataFrame()

        # Add count and percentage for each column
        for col in counts.columns:
            if col != "Total":
                result[f"{col} (Count)"] = counts[col]
                result[f"{col} (%)"] = percentages[col].round(1).astype(str) + "%"

        # Add row totals
        result["Total (Count)"] = counts["Total"]
        result["Total (%)"] = percentages["Total"].round(1).astype(str) + "%"

        # Format counts with commas
        count_cols = [col for col in result.columns if "(Count)" in col]
        for col in count_cols:
            result[col] = result[col].apply(lambda x: f"{x:,}")

        # Add column totals
        totals_row = result.iloc[-1]
        result = result.drop("Total")
        result.loc["Total"] = totals_row

        # Add question text as index and column names
        result.index.name = self.q1.question_text

        return result
