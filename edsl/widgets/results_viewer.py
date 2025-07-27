"""
Interactive Results Visualization Widget

An anywidget for visualizing EDSL Results objects with searchable dropdowns
to select questions and display histograms, bar charts, or grouped comparisons.
"""

import traitlets
from typing import Any, Dict, List, Optional
from .base_widget import EDSLBaseWidget


class ResultsViewerWidget(EDSLBaseWidget):
    """Interactive widget for visualizing EDSL Results with histograms, bar charts, and grouped comparisons."""

    # Traitlets for data communication with frontend
    results = traitlets.Any(allow_none=True).tag(sync=False)
    raw_data = traitlets.Dict().tag(sync=True)
    questions_data = traitlets.List().tag(sync=True)
    chart_data = traitlets.Dict().tag(sync=True)
    selected_question = traitlets.Unicode('').tag(sync=True)
    
    def __init__(self, results=None, **kwargs):
        super().__init__(**kwargs)
        if results is not None:
            self.results = results
    
    @traitlets.observe('results')
    def _on_results_change(self, change):
        """Update widget data when results change."""
        if change['new'] is not None:
            self._update_data()
    
    def _update_data(self):
        """Extract questions and data from the Results object."""
        if self.results is None:
            self.questions_data = []
            self.chart_data = {}
            self.raw_data = {}
            return
        
        try:
            # Extract questions from the survey
            questions = []
            chart_data = {}
            raw_data = {}
            
            # Get all questions from the survey
            if hasattr(self.results, 'survey') and hasattr(self.results.survey, 'questions'):
                for question in self.results.survey.questions:
                    question_info = {
                        'question_name': question.question_name,
                        'question_text': question.question_text,
                        'question_type': getattr(question, 'question_type', 'unknown')
                    }
                    questions.append(question_info)
                    
                    # If it's a numerical or multiple choice question, extract the data
                    if question_info['question_type'] in ['numerical', 'multiple_choice']:
                        try:
                            values = self.results.select(question.question_name).to_list()
                            
                            # Store raw data for cross-tabulation
                            raw_data[question.question_name] = [str(val) if val is not None else None for val in values]
                            
                            if question_info['question_type'] == 'numerical':
                                # Convert to numbers and filter out non-numeric values
                                numeric_values = []
                                for val in values:
                                    try:
                                        numeric_values.append(float(val))
                                    except (ValueError, TypeError):
                                        pass  # Skip non-numeric values
                                chart_data[question.question_name] = numeric_values
                            
                            elif question_info['question_type'] == 'multiple_choice':
                                # For multiple choice, keep as strings and count frequencies
                                from collections import Counter
                                value_counts = Counter([str(val) for val in values if val is not None])
                                chart_data[question.question_name] = dict(value_counts)
                                
                        except Exception as e:
                            print(f"Error extracting data for {question.question_name}: {e}")
                            chart_data[question.question_name] = [] if question_info['question_type'] == 'numerical' else {}
                            raw_data[question.question_name] = []
            
            self.questions_data = questions
            self.chart_data = chart_data
            self.raw_data = raw_data
            
        except Exception as e:
            print(f"Error updating widget data: {e}")
            self.questions_data = []
            self.chart_data = {}
            self.raw_data = {}