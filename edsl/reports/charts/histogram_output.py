from .chart_output import ChartOutput
import pandas as pd
import altair as alt

class HistogramOutput(ChartOutput):
    """A histogram showing the distribution of a numerical question."""
    pretty_name = "Histogram"
    pretty_short_name = "Histogram"
    methodology = "Creates a histogram showing the frequency distribution of numerical responses with binned data"

    def __init__(self, results, *question_names):
        if len(question_names) != 1:
            raise ValueError("HistogramOutput requires exactly one question name")
        super().__init__(results, *question_names)
        
        # Get question and answers
        self.question = self.results.survey.get(self.question_names[0])
        self.answers = self.results.select(f'answer.{self.question_names[0]}').to_list()

    @property
    def narrative(self):
        return f"A histogram showing the distribution of responses to the numerical question: '{self.question.question_text}'. The bars show how many responses fall into each range of values."

    @classmethod
    def can_handle(cls, *question_objs):
        """
        Check if this chart type can handle the given questions.
        Returns True if there is exactly one question and it is numerical or linear_scale.
        """
        return len(question_objs) == 1 and question_objs[0].question_type in ["numerical", "linear_scale"]

    def output(self):
        """
        Generate a histogram showing the distribution of numerical responses.
        
        Returns:
            An Altair chart object showing the histogram
        """
        # Create DataFrame with answers
        df = pd.DataFrame({
            'value': self.answers
        })
        
        # Create the histogram
        chart = alt.Chart(df).mark_bar().encode(
            x=alt.X('value:Q',
                   title=self.question.question_text,
                   bin=alt.Bin(maxbins=20)),  # Automatically determine bin size with max 20 bins
            y=alt.Y('count()',
                   title='Count'),
            tooltip=['value:Q', 'count()']
        ).properties(
            title=f"Distribution of {self.question_names[0]}",
            width=600,
            height=400
        )
        
        return chart