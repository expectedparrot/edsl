from .table_output import TableOutput
import pandas as pd

class FacetedSummaryStatsTable(TableOutput):
    """A table showing summary statistics for a numerical question broken down by categories."""
    pretty_name = "Faceted Summary Statistics"
    pretty_short_name = "Faceted summary statistics"
    methodology = "Calculates summary statistics (mean, median, std dev, etc.) for numerical responses grouped by categories"
    def __init__(self, results, *question_names):
        if len(question_names) != 2:
            raise ValueError("FacetedSummaryStatsTable requires exactly two question names")
        super().__init__(results, *question_names)
        
        # Get questions and determine which is numerical/categorical
        q1, q2 = [self.results.survey.get(name) for name in question_names]
        if q1.question_type in ["numerical", "linear_scale"]:
            self.num_question = q1
            self.cat_question = q2
            self.num_answers = self.results.select(f'answer.{question_names[0]}').to_list()
            self.cat_answers = self.results.select(f'answer.{question_names[1]}').to_list()
        else:
            self.num_question = q2
            self.cat_question = q1
            self.num_answers = self.results.select(f'answer.{question_names[1]}').to_list()
            self.cat_answers = self.results.select(f'answer.{question_names[0]}').to_list()

    @property
    def narrative(self):
        return f"A summary statistics table comparing the {self.num_question.question_type} question '{self.num_question.question_text}' across categories of '{self.cat_question.question_text}'. Each row shows statistics for a different category."

    @classmethod
    def can_handle(cls, *question_objs):
        """Check if this table type can handle the given questions."""
        if len(question_objs) != 2:
            return False
        types = [q.question_type for q in question_objs]
        return (any(t in ["numerical", "linear_scale"] for t in types) and 
                "multiple_choice" in types and
                any(hasattr(q, 'question_options') for q in question_objs))

    def output(self):
        """
        Generate summary statistics for the numerical question broken down by categories.
        
        Returns:
            A pandas DataFrame containing the summary statistics by category
        """
        # Create DataFrame with both answers
        df = pd.DataFrame({
            'Value': self.num_answers,
            'Category': self.cat_answers
        })
        
        # Ensure numeric values for linear_scale or numerical questions
        df['Value'] = pd.to_numeric(df['Value'], errors='coerce')
        
        # Calculate summary statistics for each category
        stats = []
        for category in self.cat_question.question_options:
            category_data = df[df['Category'] == category]['Value']
            valid_data = category_data.dropna()
            
            if len(valid_data) > 0:
                stats.append({
                    'Category': category,
                    'Count': len(category_data),
                    'Mean': valid_data.mean(),
                    'Median': valid_data.median(),
                    'Std Dev': valid_data.std(),
                    'Min': valid_data.min(),
                    'Max': valid_data.max(),
                    '25th %ile': valid_data.quantile(0.25),
                    '75th %ile': valid_data.quantile(0.75)
                })
            else:
                stats.append({
                    'Category': category,
                    'Count': len(category_data),
                    'Mean': 'N/A',
                    'Median': 'N/A',
                    'Std Dev': 'N/A',
                    'Min': 'N/A',
                    'Max': 'N/A',
                    '25th %ile': 'N/A',
                    '75th %ile': 'N/A'
                })
        
        # Create DataFrame
        df_stats = pd.DataFrame(stats)
        
        # Format numerical values where applicable
        numeric_cols = ['Mean', 'Median', 'Std Dev', 'Min', 'Max', '25th %ile', '75th %ile']
        for col in numeric_cols:
            df_stats[col] = df_stats[col].apply(lambda x: f"{x:,.2f}" if isinstance(x, (int, float)) else x)
        
        df_stats['Count'] = df_stats['Count'].apply(lambda x: f"{x:,}")
        
        # Set Category as index but keep it as a column
        df_stats.set_index('Category', inplace=True)
        
        return df_stats