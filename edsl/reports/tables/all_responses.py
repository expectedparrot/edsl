import pandas as pd

from .base import TableOutput

class AllResponsesTable(TableOutput):
    """A table showing all raw responses for the selected questions."""

    def __init__(self, results, *question_names):
        super().__init__(results, *question_names)
        
    @property
    def can_be_analyzed(self):
        """AllResponsesTable should not be included in written analysis."""
        return False

    @property
    def scenario_output(self):
        """Returns the table as HTML with scrollable styling."""
        df = self.output()
        if not isinstance(df, pd.DataFrame):
            raise ValueError("output() must return a pandas DataFrame")
            
        # Convert DataFrame to styled HTML with scrollable container
        styled_df = df.style.set_properties(**{
            'text-align': 'left',
            'padding': '8px',
            'border': '1px solid #ddd'
        }).set_table_styles([
            # Table container with scroll
            {'selector': '',
             'props': [('max-height', '400px'),  # Fixed height for scroll
                      ('overflow-y', 'auto'),    # Vertical scroll
                      ('display', 'block'),
                      ('font-family', 'Arial, sans-serif'),
                      ('font-size', '14px'),
                      ('border-collapse', 'collapse'),
                      ('width', '100%'),
                      ('margin', '20px 0')]},
            # Header row styling
            {'selector': 'thead',
             'props': [('background-color', '#f5f5f5'),
                      ('position', 'sticky'),     # Sticky header
                      ('top', '0'),              # Stick to top
                      ('z-index', '1')]},
            {'selector': 'thead th',
             'props': [('background-color', '#f5f5f5'),
                      ('font-weight', 'bold'),
                      ('text-align', 'left'),
                      ('padding', '8px'),
                      ('border', '1px solid #ddd')]},
            # Row styling
            {'selector': 'tbody tr:nth-of-type(odd)',
             'props': [('background-color', '#f9f9f9')]},
            {'selector': 'td',
             'props': [('border', '1px solid #ddd'),
                      ('padding', '8px')]}
        ])
        
        return styled_df.to_html()

    @property
    def narrative(self):
        question_texts = [q.question_text for q in self.questions]
        return f"A detailed table showing all individual responses for the questions: {', '.join(question_texts)}. Each row represents one respondent's answers."

    @classmethod
    def can_handle(cls, *question_objs):
        """Check if this table type can handle the given questions."""
        return len(question_objs) >= 1  # Can handle any number of questions

    def output(self):
        """
        Generate a table containing all raw responses for the selected questions.
        
        Returns:
            A pandas DataFrame containing all responses
        """
        # Create a dictionary to store all answers
        data = {}
        for question_name in self.question_names:
            question = self.results.survey.get(question_name)
            answers = self.results.select(f'answer.{question_name}').to_list()
            data[question.question_text] = answers
            
        # Create DataFrame with question texts as column names
        df = pd.DataFrame(data)
        
        # Add row numbers as index
        df.index = df.index + 1  # Make it 1-based
        df.index.name = 'Response #'
        
        return df
        
    @property
    def html(self):
        """Returns the HTML representation of the table with scrollable content"""
        df = self.output()
        if not isinstance(df, pd.DataFrame):
            raise ValueError("output() must return a pandas DataFrame")
            
        # Convert DataFrame to styled HTML
        styled_df = df.style.set_properties(**{
            'text-align': 'left',
            'padding': '8px',
            'border': '1px solid #ddd'
        }).set_table_styles([
            # Table container with scroll
            {'selector': '',
             'props': [('max-height', '400px'),  # Fixed height for scroll
                      ('overflow-y', 'auto'),    # Vertical scroll
                      ('display', 'block'),
                      ('font-family', 'Arial, sans-serif'),
                      ('font-size', '14px'),
                      ('border-collapse', 'collapse'),
                      ('width', '100%'),
                      ('margin', '20px 0')]},
            # Header row styling
            {'selector': 'thead',
             'props': [('background-color', '#f5f5f5'),
                      ('position', 'sticky'),     # Sticky header
                      ('top', '0'),              # Stick to top
                      ('z-index', '1')]},
            {'selector': 'thead th',
             'props': [('background-color', '#f5f5f5'),
                      ('font-weight', 'bold'),
                      ('text-align', 'left'),
                      ('padding', '8px'),
                      ('border', '1px solid #ddd')]},
            # Row styling
            {'selector': 'tbody tr:nth-of-type(odd)',
             'props': [('background-color', '#f9f9f9')]},
            {'selector': 'td',
             'props': [('border', '1px solid #ddd'),
                      ('padding', '8px')]}
        ])
        
        return styled_df.to_html()
