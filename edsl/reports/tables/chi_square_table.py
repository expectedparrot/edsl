from .table_output import TableOutput
import pandas as pd

class ChiSquareTable(TableOutput):
    """A table showing cross-tabulation and chi-square test results for two multiple-choice questions."""
    pretty_name = "Chi-Square Test"
    pretty_short_name = "Chi-square test"
    methodology = "Performs chi-square test of independence and creates cross-tabulation table for two categorical variables"

    def __init__(self, results, *question_names):
        if len(question_names) != 2:
            raise ValueError("ChiSquareTable requires exactly two question names")
        super().__init__(results, *question_names)
        
        # Get questions
        self.q1 = self.results.survey.get(self.question_names[0])
        self.q2 = self.results.survey.get(self.question_names[1])
        
        # Get answers
        self.answers1 = self.results.select(f'answer.{self.question_names[0]}').to_list()
        self.answers2 = self.results.select(f'answer.{self.question_names[1]}').to_list()

    @property
    def narrative(self):
        return f"A chi-square analysis table examining the relationship between '{self.q1.question_text}' and '{self.q2.question_text}', including cross-tabulation counts, percentages, and test statistics."

    @classmethod
    def can_handle(cls, *question_objs):
        """Check if this table type can handle the given questions."""
        if len(question_objs) != 2:
            return False
        return (all(q.question_type == "multiple_choice" for q in question_objs) and
                all(hasattr(q, 'question_options') for q in question_objs))

    def output(self):
        """
        Generate cross-tabulation with chi-square test results.
        
        Returns:
            A pandas DataFrame containing the cross-tab and test statistics
        """
        from scipy.stats import chi2_contingency
        
        # Create DataFrame with both answers
        df = pd.DataFrame({
            'Question1': self.answers1,
            'Question2': self.answers2
        })
        
        # Calculate cross-tabulation
        crosstab = pd.crosstab(
            df['Question1'], 
            df['Question2']
        )
        
        # Calculate row percentages
        row_percentages = crosstab.div(crosstab.sum(axis=1), axis=0) * 100
        
        # Add row totals
        crosstab['Total'] = crosstab.sum(axis=1)
        row_percentages['Total'] = 100  # Each row sums to 100%
        
        # Add column totals
        total_row = crosstab.sum()
        total_row_pct = (total_row / len(df)) * 100
        crosstab.loc['Total'] = total_row
        row_percentages.loc['Total'] = total_row_pct
        
        # Perform chi-square test (excluding totals)
        chi2, p_value, dof, expected = chi2_contingency(crosstab.iloc[:-1, :-1])
        
        # Format the table with counts and percentages
        formatted_table = pd.DataFrame(index=crosstab.index)
        
        # Add formatted columns for each category
        for col in crosstab.columns:
            formatted_table[f'{col} (Count)'] = crosstab[col].map(lambda x: f"{x:,}")
            formatted_table[f'{col} (%)'] = row_percentages[col].map(lambda x: f"{x:.1f}%")
        
        # Add test statistics as a separate table
        stats_table = pd.DataFrame({
            'Statistic': [
                'Chi-square value',
                'Degrees of freedom',
                'p-value',
                'Number of observations'
            ],
            'Value': [
                f"{chi2:.3f}",
                str(dof),
                f"{p_value:.3f}",
                f"{len(df):,}"
            ]
        }).set_index('Statistic')
        
        # Store tables separately for HTML formatting
        self.crosstab = formatted_table
        self.stats = stats_table
        
        return formatted_table
        
    @property
    def html(self):
        """Returns the HTML representation of the table with custom styling"""
        if not hasattr(self, 'crosstab') or not hasattr(self, 'stats'):
            self.output()
            
        # Style for cross-tabulation
        crosstab_styled = self.crosstab.style.set_properties(**{
            'text-align': 'left',
            'padding': '8px',
            'border': '1px solid #ddd'
        }).set_table_styles([
            {'selector': '',
             'props': [('font-family', 'Arial, sans-serif'),
                      ('font-size', '14px'),
                      ('border-collapse', 'collapse'),
                      ('width', '100%'),
                      ('margin', '20px 0')]},
            {'selector': 'thead th',
             'props': [('background-color', '#f5f5f5'),
                      ('font-weight', 'bold'),
                      ('text-align', 'left'),
                      ('padding', '8px'),
                      ('border', '1px solid #ddd')]},
            {'selector': 'tbody tr:nth-of-type(odd)',
             'props': [('background-color', '#f9f9f9')]},
            {'selector': 'td',
             'props': [('border', '1px solid #ddd'),
                      ('padding', '8px')]}
        ])
        
        # Style for statistics table
        stats_styled = self.stats.style.set_properties(**{
            'text-align': 'left',
            'padding': '8px',
            'border': '1px solid #ddd'
        }).set_table_styles([
            {'selector': '',
             'props': [('font-family', 'Arial, sans-serif'),
                      ('font-size', '14px'),
                      ('border-collapse', 'collapse'),
                      ('width', '50%'),
                      ('margin', '20px 0')]},
            {'selector': 'thead th',
             'props': [('background-color', '#f5f5f5'),
                      ('font-weight', 'bold'),
                      ('text-align', 'left'),
                      ('padding', '8px'),
                      ('border', '1px solid #ddd')]},
            {'selector': 'tbody tr:nth-of-type(odd)',
             'props': [('background-color', '#f9f9f9')]},
            {'selector': 'td',
             'props': [('border', '1px solid #ddd'),
                      ('padding', '8px')]}
        ])
        
        # Combine both tables with a heading between them
        html = f"""
        <div>
            <h3>Cross-Tabulation: {self.q1.question_text} × {self.q2.question_text}</h3>
            {crosstab_styled.to_html()}
            <h3>Chi-Square Test Results</h3>
            {stats_styled.to_html()}
        </div>
        """
        
        return html