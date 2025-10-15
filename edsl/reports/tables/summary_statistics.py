import pandas as pd

from .base import TableOutput

class SummaryStatisticsTable(TableOutput):
    """A table showing summary statistics for a numerical question."""

    def __init__(self, results, *question_names):
        if len(question_names) != 1:
            raise ValueError("SummaryStatisticsTable requires exactly one question name")
        super().__init__(results, *question_names)
        
        self.question = self.results.survey.get(self.question_names[0])
        self.answers = self.results.select(f'answer.{self.question_names[0]}').to_list()

    @property
    def narrative(self):
        return f"A summary statistics table for the numerical question '{self.question.question_text}', showing key metrics including count, mean, median, standard deviation, and quartiles."

    @classmethod
    def can_handle(cls, *question_objs):
        """Check if this table type can handle the given questions."""
        return len(question_objs) == 1 and question_objs[0].question_type in ["numerical", "linear_scale"]

    def output(self):
        """
        Generate summary statistics for the numerical question.
        
        Returns:
            A pandas DataFrame containing the summary statistics
        """
        series = pd.Series(self.answers)
        
        stats = {
            'Statistic': [
                'Count',
                'Mean',
                'Median',
                'Standard Deviation',
                'Minimum',
                '25th Percentile',
                '75th Percentile',
                'Maximum'
            ],
            'Value': [
                len(series),
                series.mean(),
                series.median(),
                series.std(),
                series.min(),
                series.quantile(0.25),
                series.quantile(0.75),
                series.max()
            ]
        }
        
        df = pd.DataFrame(stats)
        
        # Format numerical values
        df['Value'] = df['Value'].apply(lambda x: f"{x:,.2f}" if isinstance(x, float) else f"{x:,}")
        
        return df
