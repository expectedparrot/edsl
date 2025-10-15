import pandas as pd
import altair as alt

from .base import ChartOutput

class HeatmapChartOutput(ChartOutput):
    """A heatmap showing the relationship between two multiple choice questions."""

    def __init__(self, results, *question_names):
        if len(question_names) != 2:
            raise ValueError("HeatmapChartOutput requires exactly two question names")
        super().__init__(results, *question_names)
        
        # Get questions
        self.q1 = self.results.survey.get(self.question_names[0])
        self.q2 = self.results.survey.get(self.question_names[1])
        
        # Get answers
        self.answers1 = self.results.select(f'answer.{self.question_names[0]}').to_list()
        self.answers2 = self.results.select(f'answer.{self.question_names[1]}').to_list()

    @property
    def narrative(self):
        return f"A heatmap showing the relationship between two multiple choice questions: '{self.q1.question_text}' and '{self.q2.question_text}'. Darker colors indicate more responses in that combination of answers."

    @classmethod
    def can_handle(cls, *question_objs):
        """
        Check if this chart type can handle the given questions.
        Returns True if there are exactly two multiple choice questions.
        """
        if len(question_objs) != 2:
            return False
            
        return (all(q.question_type == "multiple_choice" for q in question_objs) and
                all(hasattr(q, 'question_options') for q in question_objs))

    def output(self):
        """
        Generate a heatmap showing the relationship between two multiple choice questions.
        
        Returns:
            An Altair chart object showing the heatmap
        """
        # Create DataFrame with both answers
        df = pd.DataFrame({
            'Question1': self.answers1,
            'Question2': self.answers2
        })
        
        # Count combinations
        counts = df.groupby(['Question1', 'Question2']).size().reset_index(name='Count')
        
        # Calculate percentages
        total = len(df)
        counts['Percentage'] = counts['Count'] / total * 100
        
        # Create the heatmap
        base = alt.Chart(counts).encode(
            x=alt.X('Question1:N',
                   title=self.q1.question_text,
                   sort=list(self.q1.question_options)),  # Preserve original order
            y=alt.Y('Question2:N',
                   title=self.q2.question_text,
                   sort=list(self.q2.question_options))   # Preserve original order
        )
        
        # Create heatmap rectangles
        heatmap = base.mark_rect().encode(
            color=alt.Color('Count:Q',
                          scale=alt.Scale(scheme='blues'),
                          legend=alt.Legend(title='Count'))
        )
        
        # Add text labels showing both count and percentage
        text = base.mark_text(baseline='middle', align='center').encode(
            text=alt.Text('Count:Q', format='.0f'),
            color=alt.condition(
                alt.datum.Count > counts['Count'].median(),
                alt.value('white'),
                alt.value('black')
            )
        )
        
        # Combine heatmap and text
        chart = (heatmap + text).properties(
            title=f"Relationship between {self.q1.question_text} and {self.q2.question_text}",
            width=400,
            height=300
        ).configure_axis(
            labelFontSize=12,
            titleFontSize=14
        ).configure_title(
            fontSize=16,
            anchor='middle'
        )
        
        return chart
