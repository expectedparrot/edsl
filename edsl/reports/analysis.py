"""
Analysis module for Reports.

This module contains the Analysis class, which represents a single analysis visualization,
table, and written description, as well as specific implementations for different
types of analyses.

The module provides the following analysis types:
- FrequencyAnalysis: For analyzing frequency distributions of multiple choice responses
- ThemeAnalysis: For analyzing themes in free text responses using ThemeFinder
- SentimentAnalysis: For analyzing sentiment in free text responses by theme
- ResponseAnalysis: A general overview analysis of responses for any question type
"""

from __future__ import annotations

import os
import random
import re
import tempfile
import traceback
from abc import ABC, abstractmethod
from typing import Any, List, Optional

import pandas as pd
import numpy as np
import altair as alt

from edsl import FileStore, QuestionFreeText, Scenario, Question

from .themes import ThemeFinder 

class Analysis(ABC):
    """
    Abstract base class representing a single analysis of survey data.
    
    Each Analysis has:
    - A title
    - A visualization (chart)
    - A data table
    - A written analysis text
    
    The class provides methods to generate these components and combine them
    for display in the HTML report.
    
    Attributes:
        title (str): Title of the analysis
        description (str): Description of the analysis
        test_mode (bool): If True, use test mode with placeholder text instead of real analysis
        _chart (Optional[alt.Chart]): The cached chart object
        _chart_file_store (Optional[FileStore]): Cached file store for the chart
    """
    
    def __init__(self, title: str, description: Optional[str] = None, test_mode: bool = False) -> None:
        """
        Initialize a new Analysis.
        
        Args:
            title: Title of the analysis
            description: Description of the analysis
            test_mode: If True, use test mode with lorem ipsum text
        """
        self.title = title
        self.description = description or ""
        self.test_mode = test_mode
        self._chart: Optional[alt.Chart] = None
        self._chart_file_store: Optional[FileStore] = None
        # Default pretty_name - can be overridden by subclasses
        self.pretty_name = self.__class__.__name__
    
    def get_title(self) -> str:
        """Get the title of the analysis."""
        return self.title
    
    def get_description(self) -> str:
        """Get the description of the analysis."""
        return self.description
    
    @abstractmethod
    def generate_chart(self) -> alt.Chart:
        """
        Generate and return a chart for this analysis.
        
        This is an abstract method that must be implemented by subclasses.
        
        Returns:
            A chart object (e.g., Altair chart)
        
        Raises:
            NotImplementedError: If not implemented by subclass
        """
        raise NotImplementedError("Subclasses must implement generate_chart()")
    
    @abstractmethod
    def generate_table(self) -> str:
        """
        Generate and return an HTML table for this analysis.
        
        This is an abstract method that must be implemented by subclasses.
        
        Returns:
            HTML for the table
        
        Raises:
            NotImplementedError: If not implemented by subclass
        """
        raise NotImplementedError("Subclasses must implement generate_table()")
    
    @abstractmethod
    def generate_written_analysis(self) -> str:
        """
        Generate and return a written analysis for this analysis.
        
        This is an abstract method that must be implemented by subclasses.
        
        Returns:
            HTML for the written analysis
        
        Raises:
            NotImplementedError: If not implemented by subclass
        """
        raise NotImplementedError("Subclasses must implement generate_written_analysis()")
    
    @property
    def chart(self) -> alt.Chart:
        """
        Lazy-load the chart.
        
        Returns:
            The chart object (created on first access)
        """
        if self._chart is None:
            self._chart = self.generate_chart()
        return self._chart
    
    def save_chart_as_html(self) -> str:
        """
        Save the chart as HTML with a unique ID to prevent conflicts.
        
        This method creates a custom HTML representation of the chart with a unique ID
        to ensure charts don't conflict with each other on the same page.
        
        Returns:
            HTML representation of the chart
        
        Raises:
            ValueError: If the chart is None
        """
        try:
            # Make sure chart exists and can be converted to HTML
            if self.chart is None:
                raise ValueError("Chart is None")
                
            chart_id = f"vis_{self.__class__.__name__}_{random.randint(10000, 99999)}"
            
            # Complete rewrite of the HTML to ensure it works correctly
            # This approach avoids the problematic regex replacements
            try:
                # First get the JSON specification
                chart_spec = self.chart.to_json()
                
                # Create a custom HTML with the unique ID
                html = f"""
                <div id="{chart_id}"></div>
                <script>
                  (function() {{
                    const spec = {chart_spec};
                    const embedOpt = {{"mode": "vega-lite"}};
                    
                    function showError(el, error) {{
                      el.innerHTML = '<div style="color:red;"><p>Error: ' + error.message + '</p></div>';
                      throw error;
                    }}
                    
                    try {{
                      vegaEmbed("#{chart_id}", spec, embedOpt)
                        .catch(function(error) {{
                          showError(document.getElementById('{chart_id}'), error);
                        }});
                    }} catch (error) {{
                      showError(document.getElementById('{chart_id}'), error);
                    }}
                  }})();
                </script>
                """
                
                print(f"Generated custom chart HTML with id {chart_id}, length: {len(html)} chars")
                return html
            except Exception as e:
                print(f"Error creating custom HTML, falling back to default: {e}")
                
                # Fallback to the original HTML with regex replacements
                html = self.chart.to_html()
                
                # Replace all occurrences of 'vis' with our unique ID
                html = re.sub(r'id="vis"', f'id="{chart_id}"', html)
                html = re.sub(r'getElementById\([\'"]vis[\'"]\)', f'getElementById("{chart_id}")', html)
                html = re.sub(r'vegaEmbed\([\'"]#vis[\'"]\)', f'vegaEmbed("#{chart_id}")', html)
                
                print(f"Generated fallback chart HTML with id {chart_id}, length: {len(html)} chars")
                return html
        except Exception as e:
            print(f"Error converting chart to HTML: {e}")
            print(traceback.format_exc())
            return f"<div class='error'>Error generating chart visualization: {e}</div>"
    
    def to_html(self, index: int) -> str:
        """
        Generate HTML for this analysis, including visualization, table, and written analysis.
        
        This method compiles all components of the analysis (chart, table, written analysis)
        into a single HTML representation for embedding in the report.
        
        Args:
            index: Index of this analysis within its question (for unique IDs)
            
        Returns:
            HTML for the complete analysis section
        """
        try:
            # Get the chart component
            print(f"Generating chart for {self.title}")
            chart_html = self.save_chart_as_html()
            print(f"Successfully generated chart for {self.title}")
        except Exception as e:
            print(f"Error generating chart for {self.title}: {e}")
            print(traceback.format_exc())
            chart_html = f"<div class='error'>Error generating chart: {e}</div>"
            
        try:
            # Get the table component
            print(f"Generating table for {self.title}")
            table_html = self.generate_table()
            print(f"Successfully generated table for {self.title}")
        except Exception as e:
            print(f"Error generating table for {self.title}: {e}")
            print(traceback.format_exc())
            table_html = f"<div class='error'>Error generating table: {e}</div>"
            
        try:
            # Get the analysis component
            print(f"Generating written analysis for {self.title}")
            analysis_html = self.generate_written_analysis()
            print(f"Successfully generated written analysis for {self.title}")
        except Exception as e:
            print(f"Error generating written analysis for {self.title}: {e}")
            print(traceback.format_exc())
            analysis_html = f"<div class='error'>Error generating written analysis: {e}</div>"
        
        # Create HTML
        analysis_id = f"analysis-{index}"
        
        # Get chart type/class name for debugging
        chart_type = self.__class__.__name__
        chart_debug = f"<!-- Chart type: {chart_type} -->"
        
        html = f"""
        <div class="analysis-section" id="{analysis_id}">
            <h3 class="analysis-title">{self.title}</h3>
            
            <!-- Written Analysis -->
            <div class="subsection" id="analysis-text-{analysis_id}">
                <div class="subsection-header" onclick="toggleSubsection('text-{analysis_id}')">
                    <h4>Analysis</h4>
                    <span class="subsection-toggle">▼</span>
                </div>
                <div id="text-{analysis_id}" class="subsection-content open">
                    <div class="analysis">
                        {analysis_html}
                    </div>
                </div>
            </div>
            
            <!-- Chart -->
            <div class="subsection">
                <div class="subsection-header" onclick="toggleSubsection('chart-{analysis_id}')">
                    <h4>{getattr(self, 'pretty_name', 'Visualization')}</h4>
                    <span class="subsection-toggle">▼</span>
                </div>
                <div id="chart-{analysis_id}" class="subsection-content open">
                    <div class="chart-container">
                        {chart_debug}
                        {chart_html}
                    </div>
                </div>
            </div>
            
            <!-- Data Table -->
            <div class="subsection">
                <div class="subsection-header" onclick="toggleSubsection('table-{analysis_id}')">
                    <h4>Data</h4>
                    <span class="subsection-toggle">▼</span>
                </div>
                <div id="table-{analysis_id}" class="subsection-content open">
                    <div class="table-container">
                        {table_html}
                    </div>
                </div>
            </div>
        </div>
        """
        
        return html


class FrequencyAnalysis(Analysis):
    """
    Analysis that shows frequency distribution of responses.
    
    This analysis is commonly used for multiple choice, linear scale,
    and checkbox questions. It displays the distribution of responses
    across the available options.
    
    Attributes:
        question (Question): The survey question being analyzed
        answers (List[Any]): The list of responses to analyze
    """

    @classmethod
    def from_edsl_question(cls, question: Question, answers: List[Any], test_mode: bool = False) -> FrequencyAnalysis:
        """
        Create a FrequencyAnalysis object from an EDSL Question object.
        
        Args:
            question: The EDSL Question object to analyze
        """
        return cls(question.question_text, question.question_options, answers, test_mode)

 
    def __init__(self, question_text: str, question_options: List[str], answers: List[Any], test_mode: bool = False) -> None:
        """
        Initialize a frequency distribution analysis.
        
        Args:
            question: The survey question being analyzed
            answers: The list of responses to analyze
            test_mode: If True, use test mode with placeholder analysis text
        """
        super().__init__(
            title="Frequency Distribution", 
            description="Frequency analysis of responses",
            test_mode=test_mode
        )
        self.pretty_name = "Bar Chart"
        self.question_text = question_text
        self.question_options = [str(option) for option in question_options if option is not None]
        self.answers = answers
    
    def generate_chart(self) -> alt.Chart:
        """
        Generate a bar chart showing frequency distribution.
        
        Returns:
            An Altair chart object showing response distribution
        """
        # Count occurrences of each option
        option_counts = {}
        for option in self.question_options:
            option_counts[option] = sum(1 for answer in self.answers if answer == option)

        # Create DataFrame from the counts
        df = pd.DataFrame({
            'Option': list(option_counts.keys()),
            'Count': list(option_counts.values())
        })
        
        # Create the bar chart
        chart = alt.Chart(df).mark_bar().encode(
            x=alt.X('Option:N', sort=list(self.question_options), title='Response Option'),
            y=alt.Y('Count:Q', title='Number of Responses'),
            color=alt.Color('Option:N', scale=alt.Scale(scheme='category10'), legend=None),
            tooltip=['Option', 'Count']
        ).properties(
            title="Response Distribution",
            width=500,
            height=300
        )
        
        return chart
    
    def generate_table(self) -> str:
        """
        Generate the HTML table for frequency distribution.
        
        Returns:
            HTML representation of the frequency distribution table
        """
        # Count occurrences of each option
        option_counts = {}
        for option in self.question_options:
            count = sum(1 for answer in self.answers if answer == option)
            option_counts[option] = count
            
        # Calculate percentages
        total_responses = len(self.answers)
        option_percentages = {option: (count / total_responses * 100) 
                              for option, count in option_counts.items()}
        
        # Create DataFrame with counts and percentages
        df = pd.DataFrame({
            'Option': list(option_counts.keys()),
            'Count': list(option_counts.values()),
            'Percentage': [f"{option_percentages[option]:.1f}%" for option in option_counts.keys()]
        })
        
        # Sort by count in descending order
        df = df.sort_values('Count', ascending=False)
        
        # Create a progress bar visualization for each option
        def create_progress_bar(percentage: str) -> str:
            """Create an HTML progress bar for a percentage value."""
            actual_percentage = float(percentage.strip('%'))
            bar_width = min(100, max(0, actual_percentage))
            return f"""
            <div style="display: flex; align-items: center; margin: 5px 0;">
                <div style="background-color: #3498db; height: 20px; width: {bar_width}%; border-radius: 2px;"></div>
                <span style="margin-left: 8px; color: #333;">{percentage}</span>
            </div>
            """
        
        df['Distribution'] = df['Percentage'].apply(create_progress_bar)
        
        # Style the DataFrame
        styled_df = df.style.hide(axis='index').set_table_attributes('class="data-table"')
        
        # Apply custom styling
        styled_df = styled_df.set_properties(**{
            'text-align': 'left',
            'border-bottom': '1px solid #e1e1e1',
            'padding': '8px'
        })
        
        # Apply header styling
        styled_df = styled_df.set_table_styles([
            {'selector': 'th', 'props': [
                ('background-color', '#f2f2f2'),
                ('color', '#333'),
                ('font-weight', 'bold'),
                ('text-align', 'left'),
                ('padding', '10px'),
                ('border-bottom', '2px solid #ccc')
            ]},
            {'selector': 'tr:nth-child(even)', 'props': [
                ('background-color', '#f9f9f9')
            ]},
            {'selector': 'tr:hover', 'props': [
                ('background-color', '#f0f7fb')
            ]}
        ])
        
        # Generate summary statistics
        total_responses = len(self.answers)
        most_common = df.iloc[0]['Option']
        most_common_count = df.iloc[0]['Count']
        most_common_pct = float(df.iloc[0]['Percentage'].strip('%'))
        
        # Create overall summary
        summary_html = f"""
        <div class="response-summary">
            <p><strong>Total Responses:</strong> {total_responses}</p>
            <p><strong>Most Common Response:</strong> '{most_common}' ({most_common_count} responses, {most_common_pct:.1f}%)</p>
        </div>
        """
        
        # Generate HTML for the table
        html_table = styled_df.to_html(escape=False)
        
        # Wrap in a container
        table_html = f"""
        <div class="custom-table-wrapper">
            {summary_html}
            {html_table}
        </div>
        """
        
        return table_html
    
    def generate_written_analysis(self) -> str:
        """
        Generate written analysis of the frequency distribution.
        
        In test mode, returns placeholder text. In normal mode,
        uses LLM to generate analysis based on the chart visualization.
        
        Returns:
            HTML string with the written analysis
        """
        if self.test_mode:
            return """Lorem ipsum dolor sit amet, consectetur adipiscing elit. Nulla facilisi. 
            Sed convallis libero in tortor fringilla, at dictum sem ultricies. 
            Data shows interesting patterns that would require further analysis in a 
            production environment. The visualization highlights key trends that 
            would typically be elaborated upon using actual LLM analysis."""
        
        try:
            # Create a file store for the chart
            temp_dir = tempfile.gettempdir()
            temp_path = os.path.join(temp_dir, f'chart_{hash(str(self.answers))}.png')
            self.chart.save(temp_path)
            file_store = FileStore(temp_path)
            
            # Generate analysis using LLM
            q_analysis = QuestionFreeText(
                question_name="written_analysis", 
                question_text="""Please provide a written analysis of the survey results.
                Survey respondents were asked the multiple choice question: 
                <question>
                {{ scenario.question_text }}
                </question>

                The results have been analyzed and this is the visualization of the results:
                <chart>
                {{ scenario.chart }}
                </chart>
                
                Please interpret the frequency distribution shown in the chart. 
                What are the most common responses? Are there any notable patterns or surprises?
                Write a short, 1 paragraph analysis of the results as plain text.
                """
            )
            scenario = Scenario({
                'question_text': self.question.question_text, 
                'chart': file_store
            })
            
            results = q_analysis.by(scenario).run(stop_on_exception=True)
            return results.select('answer.written_analysis').first()
        except Exception as e:
            print(f"Error generating written analysis: {e}")
            return "* Analysis generation failed or timed out *"


class ThemeAnalysis(Analysis):
    """
    Analysis of themes in free text responses.
    
    This analysis uses ThemeFinder to identify common themes in 
    free text responses and displays them in a chart.
    
    Attributes:
        question (Question): The survey question being analyzed
        answers (List[str]): The list of text responses to analyze
        _theme_finder (Optional[ThemeFinder]): Cached ThemeFinder instance
        show_all_output_table (bool): If True, shows a detailed table with responses and their themes
    """
    
    def __init__(self, question: Question, answers: List[Any], test_mode: bool = False, show_all_output_table: bool = True) -> None:
        """
        Initialize a theme analysis.
        
        Args:
            question: The survey question being analyzed
            answers: The list of text responses to analyze
            test_mode: If True, use test mode with sample themes
            show_all_output_table: If True, shows a detailed table with responses and their themes
        """
        super().__init__(
            title="Theme Analysis", 
            description="Analysis of common themes in free text responses",
            test_mode=test_mode
        )
        self.pretty_name = "Theme Analysis"
        self.question = question
        self.answers = answers
        self._theme_finder = None
        self.show_all_output_table = show_all_output_table
    
    @property
    def theme_finder(self) -> Optional[ThemeFinder]:
        """
        Lazy-load the ThemeFinder.
        
        Returns:
            ThemeFinder instance or None if initialization fails
        """
        if self._theme_finder is None and ThemeFinder is not None:
            try:
                self._theme_finder = ThemeFinder(
                    question=self.question.question_text, 
                    answers=self.answers, 
                    context="Survey results"
                )
                print(f"ThemeFinder initialized successfully for {self.question.question_name}")
            except Exception as e:
                print(f"Error initializing ThemeFinder: {e}")
                return None
        return self._theme_finder
    
    def generate_chart(self) -> alt.Chart:
        """
        Generate a chart showing theme counts.
        
        Attempts to use ThemeFinder to generate a chart showing the count
        of responses for each identified theme. Falls back to a sample
        chart if ThemeFinder is not available or encounters an error.
        
        Returns:
            An Altair chart showing theme distribution
        """
        try:
            print(f"Generating theme chart for question: {self.question.question_name}")
            
            # First check if ThemeFinder is available
            if ThemeFinder is None:
                print("ThemeFinder class is not available")
                raise ImportError("ThemeFinder class is not available")
                
            # Create a ThemeFinder instance directly here instead of using property
            theme_finder = ThemeFinder(
                question=self.question.question_text, 
                answers=self.answers, 
                context="Survey results"
            )
            
            # Try to get the chart from ThemeFinder
            try:
                chart = theme_finder.create_theme_counts_chart()
                print(f"Successfully created theme chart for {self.question.question_name}")
                return chart
            except Exception as e:
                print(f"Error creating theme counts chart: {e}")
                print(f"Theme finder: {theme_finder}")
                # Fall back to sample chart
                raise
                
        except Exception as e:
            print(f"ThemeFinder chart generation failed: {e}")
            # Create sample theme data for visualization
            sample_themes = ["Theme 1", "Theme 2", "Theme 3", "Theme 4", "Theme 5"]
            sample_counts = [random.randint(5, 20) for _ in range(len(sample_themes))]
            
            # Create a DataFrame
            df = pd.DataFrame({
                'theme': sample_themes,
                'count': sample_counts
            })
            
            # Create a simple bar chart
            chart = alt.Chart(df).mark_bar().encode(
                x=alt.X('theme:N', title='Themes'),
                y=alt.Y('count:Q', title='Count'),
                color=alt.Color('theme:N', legend=None)
            ).properties(
                width=600,
                height=300,
                title=f"{'Test Mode: ' if self.test_mode else ''}Theme Analysis for {self.question.question_name}"
            )
            
            return chart
    
    def generate_table(self) -> str:
        """
        Generate a table showing theme counts and (optionally) all responses with their themes.
        
        Uses ThemeFinder to get the actual theme data if available,
        otherwise generates sample theme data in test mode.
        
        Returns:
            HTML representation of the theme counts table and optional all-output table
        """
        if self.test_mode or self.theme_finder is None:
            # Generate mock theme data for the table
            sample_themes = ["Theme 1", "Theme 2", "Theme 3", "Theme 4", "Theme 5"]
            sample_counts = [random.randint(5, 20) for _ in range(len(sample_themes))]
            
            # Create DataFrame
            df = pd.DataFrame({
                'Theme': sample_themes,
                'Count': sample_counts,
                'Percentage': [f"{(count / sum(sample_counts) * 100):.1f}%" for count in sample_counts]
            })
            
            # Sort by count
            df = df.sort_values('Count', ascending=False)
            
            # Style the DataFrame
            styled_df = df.style.hide(axis='index').set_table_attributes('class="data-table"')
            
            # Create summary HTML
            summary_html = f"""
            <div class="response-summary">
                <p><strong>Total Themes:</strong> {len(sample_themes)}</p>
                <p><strong>Total Responses:</strong> {len(self.answers)}</p>
                <p><em>Note: Sample themes shown in test mode</em></p>
            </div>
            """
            
            # Generate HTML for the table
            html_table = styled_df.to_html()
            
            # Wrap in a container
            table_html = f"""
            <div class="custom-table-wrapper">
                <h3>Theme Distribution</h3>
                {summary_html}
                {html_table}
            </div>
            """
            
            return table_html
        else:
            # Get the actual theme data from ThemeFinder
            raw_df = self.theme_finder.answer_theme_results.select('answer', 'relevant_theme').remove_prefix().expand('relevant_theme').to_pandas()
            theme_counts = (raw_df
                           .explode('relevant_theme')
                           .groupby('relevant_theme')
                           .size()
                           .reset_index(name='count'))
            
            # Sort by count in descending order
            theme_counts = theme_counts.sort_values('count', ascending=False)
            
            # Calculate percentages
            total_responses = len(self.answers)
            theme_counts['percentage'] = (theme_counts['count'] / total_responses * 100).apply(lambda x: f"{x:.1f}%")
            
            # Style the DataFrame
            styled_df = theme_counts.style.hide(axis='index').set_table_attributes('class="data-table"')
            
            # Create summary HTML
            summary_html = f"""
            <div class="response-summary">
                <p><strong>Total Themes:</strong> {len(theme_counts)}</p>
                <p><strong>Total Responses:</strong> {total_responses}</p>
            </div>
            """
            
            # Generate HTML for the theme counts table
            theme_counts_html = styled_df.to_html()
            
            # Create theme counts container
            theme_counts_container = f"""
            <div class="custom-table-wrapper">
                <h3>Theme Distribution</h3>
                {summary_html}
                {theme_counts_html}
            </div>
            """
            
            # Add all-output table if requested
            if self.show_all_output_table:
                try:
                    # Get all responses with their themes
                    all_output_html = self.theme_finder.create_all_responses_html_table(
                        max_response_length=300
                    )
                    
                    # Create all-output container
                    all_output_container = f"""
                    <div class="custom-table-wrapper" style="margin-top: 30px;">
                        <h3>All Responses with Themes</h3>
                        {all_output_html}
                    </div>
                    """
                    
                    # Combine both tables
                    return theme_counts_container + all_output_container
                except Exception as e:
                    print(f"Error generating all-output table: {e}")
                    return theme_counts_container
            else:
                return theme_counts_container
    
    def generate_written_analysis(self) -> str:
        """
        Generate written analysis of themes.
        
        In test mode, returns placeholder text. In normal mode,
        uses LLM to analyze the themes based on the chart visualization.
        
        Returns:
            HTML string with the written analysis
        """
        if self.test_mode:
            return """Lorem ipsum dolor sit amet, consectetur adipiscing elit. Nulla facilisi. 
            Sed convallis libero in tortor fringilla, at dictum sem ultricies. 
            The theme analysis shows several recurring topics in the free text responses.
            These themes provide insight into the main concerns and interests of the respondents."""
        
        try:
            # Create a file store for the chart
            temp_dir = tempfile.gettempdir()
            temp_path = os.path.join(temp_dir, f'chart_{hash(str(self.answers))}.png')
            self.chart.save(temp_path)
            file_store = FileStore(temp_path)
            
            # Generate analysis using LLM
            q_analysis = QuestionFreeText(
                question_name="written_analysis", 
                question_text="""Please provide a written analysis of the themes found in the free text responses.
                Survey respondents were asked the open-ended question: 
                <question>
                {{ scenario.question_text }}
                </question>

                The responses have been analyzed and the common themes are shown in this visualization:
                <chart>
                {{ scenario.chart }}
                </chart>
                
                Please interpret the themes shown in the chart. 
                What are the most common themes? What insights can we derive from these patterns?
                Write a short, 1 paragraph analysis of the results as plain text.
                """
            )
            scenario = Scenario({
                'question_text': self.question.question_text, 
                'chart': file_store
            })
            
            results = q_analysis.by(scenario).run(stop_on_exception=True)
            return results.select('answer.written_analysis').first()
        except Exception as e:
            print(f"Error generating written analysis: {e}")
            return "* Analysis generation failed or timed out *"


class SentimentAnalysis(Analysis):
    """
    Analysis of sentiment by theme in free text responses.
    
    This analysis uses ThemeFinder to analyze the sentiment associated with
    each identified theme in free text responses.
    
    Attributes:
        question (Question): The survey question being analyzed
        answers (List[str]): The list of text responses to analyze
        _theme_finder (Optional[ThemeFinder]): Cached ThemeFinder instance
    """
    
    def __init__(self, question: Question, answers: List[Any], test_mode: bool = False) -> None:
        """
        Initialize a sentiment analysis.
        
        Args:
            question: The survey question being analyzed
            answers: The list of text responses to analyze
            test_mode: If True, use test mode with sample sentiment data
        """
        super().__init__(
            title="Sentiment Analysis", 
            description="Analysis of sentiment across different themes",
            test_mode=test_mode
        )
        self.question = question
        self.answers = answers
        self._theme_finder = None
    
    @property
    def theme_finder(self) -> Optional[ThemeFinder]:
        """
        Lazy-load the ThemeFinder.
        
        Returns:
            ThemeFinder instance or None if initialization fails
        """
        if self._theme_finder is None and ThemeFinder is not None:
            try:
                self._theme_finder = ThemeFinder(
                    question=self.question.question_text, 
                    answers=self.answers, 
                    context="Survey results"
                )
                print(f"ThemeFinder initialized successfully for {self.question.question_name}")
            except Exception as e:
                print(f"Error initializing ThemeFinder: {e}")
                return None
        return self._theme_finder
    
    def generate_chart(self) -> alt.Chart:
        """
        Generate a chart showing sentiment analysis by theme.
        
        Attempts to use ThemeFinder to generate a chart showing sentiment distribution
        across identified themes. Falls back to a sample chart if ThemeFinder
        is not available or encounters an error.
        
        Returns:
            An Altair chart showing sentiment distribution by theme
        """
        try:
            print(f"Generating sentiment chart for question: {self.question.question_name}")
            
            # First check if ThemeFinder is available
            if ThemeFinder is None:
                print("ThemeFinder class is not available")
                raise ImportError("ThemeFinder class is not available")
                
            # Create a ThemeFinder instance directly here instead of using property
            theme_finder = ThemeFinder(
                question=self.question.question_text, 
                answers=self.answers, 
                context="Survey results"
            )
            
            # Try to get the sentiment chart from ThemeFinder
            try:
                chart = theme_finder.create_sentiment_chart()
                print(f"Successfully created sentiment chart for {self.question.question_name}")
                return chart
            except Exception as e:
                print(f"Error creating sentiment chart: {e}")
                print(traceback.format_exc())
                # Fall back to sample chart
                raise
        
        except Exception as e:
            print(f"Error generating sentiment chart: {e}")
            # Create sample sentiment data as fallback
            themes = ["Theme 1", "Theme 2", "Theme 3"]
            sentiments = ["Very Negative", "Negative", "Neutral/NA", "Positive", "Very Positive"]
        
            # Generate random data for each combination
            data = []
            for theme in themes:
                for sentiment in sentiments:
                    data.append({
                        "Theme": theme,
                        "Sentiment": sentiment,
                        "Count": random.randint(0, 20)
                    })
            
            # Create DataFrame
            df = pd.DataFrame(data)
            
            # Create chart
            chart = alt.Chart(df).mark_bar().encode(
                x=alt.X('Sentiment:N', sort=sentiments),
                y=alt.Y('Count:Q'),
                color=alt.Color('Sentiment:N', 
                                scale=alt.Scale(domain=sentiments, 
                                               range=['#8B0000', '#FF4500', '#FFFFFF', '#90EE90', '#006400'])),
                column=alt.Column('Theme:N')
            ).properties(
                width=150,
                title="Sentiment Analysis (Sample Data)"
            )
            
            return chart
    
    def generate_table(self) -> str:
        """
        Generate a table showing sentiment analysis by theme.
        
        Returns:
            HTML representation of the sentiment analysis table
        """
        # Check if we can get actual sentiment data
        if not self.test_mode and self.theme_finder is not None:
            try:
                # Get sentiment data from ThemeFinder
                raw_df = self.theme_finder.sentiment_by_theme_results.select(
                    'relevant_theme', 'sentiment').to_pandas(remove_prefix=True)
                
                # Process the data
                sentiment_counts = (raw_df
                                   .groupby(['relevant_theme', 'sentiment'])
                                   .size()
                                   .reset_index(name='count'))
                
                # Calculate totals and percentages
                totals = sentiment_counts.groupby('relevant_theme')['count'].sum().reset_index(name='total')
                sentiment_data = pd.merge(sentiment_counts, totals, on='relevant_theme')
                sentiment_data['percentage'] = (sentiment_data['count'] / sentiment_data['total'] * 100).apply(
                    lambda x: f"{x:.1f}%")
                
                # Create DataFrame
                df = sentiment_data[['relevant_theme', 'sentiment', 'count', 'percentage']]
                df.columns = ['Theme', 'Sentiment', 'Count', 'Percentage']
                
                # Style the DataFrame
                styled_df = df.style.hide(axis='index').set_table_attributes('class="data-table"')
                
                # Create summary HTML
                total_themes = len(df['Theme'].unique())
                summary_html = f"""
                <div class="response-summary">
                    <p><strong>Total Themes:</strong> {total_themes}</p>
                    <p><strong>Total Responses:</strong> {len(self.answers)}</p>
                </div>
                """
                
                # Generate HTML for the table
                html_table = styled_df.to_html()
                
                # Wrap in a container
                table_html = f"""
                <div class="custom-table-wrapper">
                    {summary_html}
                    {html_table}
                </div>
                """
                
                return table_html
            
            except Exception as e:
                print(f"Error generating sentiment table from ThemeFinder: {e}")
                print(traceback.format_exc())
                # Fall back to sample data
        
        # Use sample data as fallback
        themes = ["Theme 1", "Theme 2", "Theme 3"]
        sentiments = ["Very Negative", "Negative", "Neutral/NA", "Positive", "Very Positive"]
        
        # Generate random data for each combination
        data = []
        for theme in themes:
            for sentiment in sentiments:
                count = random.randint(0, 20)
                data.append({
                    "Theme": theme,
                    "Sentiment": sentiment,
                    "Count": count,
                    "Percentage": f"{random.randint(5, 30)}.{random.randint(0, 9)}%"
                })
        
        # Create DataFrame
        df = pd.DataFrame(data)
        
        # Style the DataFrame
        styled_df = df.style.hide(axis='index').set_table_attributes('class="data-table"')
        
        # Create summary HTML with appropriate message
        if self.test_mode:
            message = "This is a test mode representation of sentiment analysis."
        else:
            message = "Sentiment analysis representation (actual data would appear in normal mode)."
        
        summary_html = f"""
        <div class="response-summary">
            <p><strong>Total Themes:</strong> {len(themes)}</p>
            <p><strong>Total Responses:</strong> {len(self.answers)}</p>
            <p><em>{message}</em></p>
        </div>
        """
        
        # Generate HTML for the table
        html_table = styled_df.to_html()
        
        # Wrap in a container
        table_html = f"""
        <div class="custom-table-wrapper">
            {summary_html}
            {html_table}
        </div>
        """
        
        return table_html
    
    def generate_written_analysis(self) -> str:
        """
        Generate written analysis of sentiment by theme.
        
        In test mode, returns placeholder text. In normal mode,
        uses LLM to analyze the sentiment patterns across themes.
        
        Returns:
            HTML string with the written analysis
        """
        if self.test_mode:
            return """Lorem ipsum dolor sit amet, consectetur adipiscing elit. Nulla facilisi. 
            The sentiment analysis shows how respondents feel about different themes in their responses.
            Positive sentiments generally dominate for themes related to user experience, while 
            mixed sentiments appear in themes related to technical aspects and performance."""
        
        try:
            # Create a file store for the chart
            temp_dir = tempfile.gettempdir()
            temp_path = os.path.join(temp_dir, f'chart_{hash(str(self.answers))}.png')
            self.chart.save(temp_path)
            file_store = FileStore(temp_path)
            
            # Generate analysis using LLM
            q_analysis = QuestionFreeText(
                question_name="written_analysis", 
                question_text="""Please provide a written analysis of the sentiment across different themes.
                Survey respondents were asked the open-ended question: 
                <question>
                {{ scenario.question_text }}
                </question>

                The sentiments associated with different themes have been analyzed and are shown in this visualization:
                <chart>
                {{ scenario.chart }}
                </chart>
                
                Please interpret the sentiment patterns shown in the chart. 
                Which themes have the most positive/negative sentiment? What might explain these patterns?
                Write a short, 1 paragraph analysis of the results as plain text.
                """
            )
            scenario = Scenario({
                'question_text': self.question.question_text, 
                'chart': file_store
            })
            
            results = q_analysis.by(scenario).run(stop_on_exception=True)
            return results.select('answer.written_analysis').first()
        except Exception as e:
            print(f"Error generating written analysis: {e}")
            return "* Analysis generation failed or timed out *"


class ResponseAnalysis(Analysis):
    """
    Simple analysis showing the raw responses with minimal processing.
    
    This analysis is useful for all question types as a baseline, providing
    a direct view of the raw responses and basic metrics.
    
    Attributes:
        question (Question): The survey question being analyzed
        answers (List[Any]): The list of responses to analyze
    """
    
    def __init__(self, question: Question, answers: List[Any], test_mode: bool = False) -> None:
        """
        Initialize a response overview analysis.
        
        Args:
            question: The survey question being analyzed
            answers: The list of responses to analyze
            test_mode: If True, use test mode with placeholder analysis text
        """
        super().__init__(
            title="Response Overview", 
            description="Overview of all responses",
            test_mode=test_mode
        )
        self.question = question
        self.answers = answers
    
    def generate_chart(self) -> alt.Chart:
        """
        Generate a chart showing response distribution or length statistics.
        
        For multiple choice questions, creates a pie chart showing response distribution.
        For free text questions, creates a bar chart showing the distribution of response lengths.
        
        Returns:
            An Altair chart showing response distribution or length statistics
        """
        try:
            # For multiple choice, return a pie chart
            if hasattr(self.question, 'question_options') and self.question.question_type in [
                'multiple_choice', 'linear_scale', 'checkbox'
            ]:
                # Count occurrences of each option
                option_counts = {}
                for option in self.question.question_options:
                    option_counts[option] = sum(1 for answer in self.answers if answer == option)
    
                # Create DataFrame from the counts
                df = pd.DataFrame({
                    'Option': list(option_counts.keys()),
                    'Count': list(option_counts.values())
                })
                
                # Create a pie chart
                chart = alt.Chart(df).mark_arc().encode(
                    theta=alt.Theta(field="Count", type="quantitative"),
                    color=alt.Color(field="Option", type="nominal"),
                    tooltip=['Option', 'Count']
                ).properties(
                    title="Response Distribution",
                    width=400,
                    height=400
                )
                
                return chart
            
            # For free text, return a bar chart of response lengths
            else:
                # Calculate text lengths
                text_lengths = [len(str(a)) for a in self.answers if a is not None]
                
                # Handle empty responses
                if not text_lengths:
                    # Create a simple placeholder chart
                    df = pd.DataFrame({
                        'Category': ['No data'],
                        'Value': [0]
                    })
                    chart = alt.Chart(df).mark_bar().encode(
                        x='Category:N',
                        y='Value:Q'
                    ).properties(
                        title="No valid responses found",
                        width=500,
                        height=300
                    )
                    return chart
                
                try:
                    # Create bins for length distribution (simple approach not using numpy)
                    max_length = max(text_lengths)
                    bin_size = 50
                    num_bins = max(1, (max_length + bin_size - 1) // bin_size)
                    bins = [(i * bin_size, (i + 1) * bin_size) for i in range(num_bins)]
                    
                    # Manual binning
                    bin_counts = [0] * len(bins)
                    for length in text_lengths:
                        for i, (bin_start, bin_end) in enumerate(bins):
                            if bin_start <= length < bin_end:
                                bin_counts[i] += 1
                                break
                    
                    # Create DataFrame
                    df = pd.DataFrame({
                        'Length': [f"{bin_start}-{bin_end}" for bin_start, bin_end in bins],
                        'Count': bin_counts
                    })
                    
                    # Create bar chart
                    chart = alt.Chart(df).mark_bar().encode(
                        x=alt.X('Length:N', title='Response Length (characters)'),
                        y=alt.Y('Count:Q', title='Number of Responses'),
                        tooltip=['Length', 'Count']
                    ).properties(
                        title="Response Length Distribution",
                        width=500,
                        height=300
                    )
                    
                    return chart
                    
                except Exception as e:
                    print(f"Error generating length distribution chart: {e}")
                    # Fallback to a simpler chart
                    df = pd.DataFrame({
                        'Statistic': ['Responses', 'Avg Length', 'Max Length'],
                        'Value': [len(text_lengths), sum(text_lengths)/len(text_lengths), max(text_lengths)]
                    })
                    
                    chart = alt.Chart(df).mark_bar().encode(
                        x='Statistic:N',
                        y='Value:Q'
                    ).properties(
                        title="Response Statistics",
                        width=500,
                        height=300
                    )
                    
                    return chart
                
        except Exception as e:
            # Create a very simple fallback chart
            print(f"Error in ResponseAnalysis.generate_chart: {e}")
            df = pd.DataFrame({
                'Label': ['Response Count'],
                'Value': [len(self.answers)]
            })
            
            return alt.Chart(df).mark_bar().encode(
                x='Label:N',
                y='Value:Q'
            ).properties(
                title="Response Count",
                width=400,
                height=300
            )
    
    def generate_table(self) -> str:
        """
        Generate an HTML table of the responses.
        
        Returns:
            HTML representation of the response table
        """
        # Remove None values and ensure non-empty list
        answers = [a for a in self.answers if a is not None]
        if not answers:
            return """
            <div class="custom-table-wrapper">
                <div class="response-summary">
                    <p><strong>Total Responses:</strong> 0</p>
                    <p><em>No valid responses to display</em></p>
                </div>
            </div>
            """
        
        # Create a DataFrame with an index column for row numbering
        df = pd.DataFrame({
            'Response': answers
        }).reset_index().rename(columns={'index': 'Response #'})
        
        # Add 1 to response numbers to start from 1 instead of 0
        df['Response #'] = df['Response #'] + 1
        
        # For large datasets, limit to a reasonable number of rows to display
        max_rows = 30
        if len(df) > max_rows:
            df = df.iloc[:max_rows].copy()
            show_more_message = f"<div class='table-note'>Showing {max_rows} of {len(answers)} responses</div>"
        else:
            show_more_message = ""
        
        # Clean and truncate long responses for display
        max_length = 300
        df['Response'] = df['Response'].apply(
            lambda x: (str(x)[:max_length] + '...') if x and len(str(x)) > max_length else str(x)
        )
        
        # Add styling to the DataFrame
        styled_df = df.style.set_table_attributes('class="data-table"')
        
        # Apply custom styling
        styled_df = styled_df.set_properties(**{
            'text-align': 'left',
            'border-bottom': '1px solid #e1e1e1',
            'padding': '8px'
        })
        
        # Apply alternating row colors and header styling
        styled_df = styled_df.set_table_styles([
            {'selector': 'th', 'props': [
                ('background-color', '#f2f2f2'),
                ('color', '#333'),
                ('font-weight', 'bold'),
                ('text-align', 'left'),
                ('padding', '10px'),
                ('border-bottom', '2px solid #ccc')
            ]},
            {'selector': 'tr:nth-child(even)', 'props': [
                ('background-color', '#f9f9f9')
            ]},
            {'selector': 'tr:hover', 'props': [
                ('background-color', '#f0f7fb')
            ]}
        ])
        
        # Calculate average response length safely
        if len(answers) > 0:
            avg_length = sum(len(str(a)) for a in answers) / len(answers)
        else:
            avg_length = 0
            
        # Generate HTML for the table
        html_table = styled_df.to_html()
        
        # Wrap in a container with scrolling capability
        table_html = f"""
        <div class="custom-table-wrapper">
            <div class="response-summary">
                <p><strong>Total Responses:</strong> {len(answers)}</p>
                <p><strong>Average Length:</strong> {avg_length:.1f} characters</p>
            </div>
            {html_table}
            {show_more_message}
        </div>
        """
        
        return table_html
    
    def generate_written_analysis(self) -> str:
        """
        Generate a basic summary of the responses.
        
        In test mode, returns placeholder text. In normal mode,
        uses LLM to generate a summary of the response patterns.
        
        Returns:
            HTML string with the written analysis
        """
        if self.test_mode:
            return """Lorem ipsum dolor sit amet, consectetur adipiscing elit. Nulla facilisi. 
            This overview provides a general summary of all responses received for this question.
            The data shows the distribution of responses and basic metrics about response patterns."""
        
        try:
            # Create a file store for the chart
            temp_dir = tempfile.gettempdir()
            temp_path = os.path.join(temp_dir, f'chart_{hash(str(self.answers))}.png')
            self.chart.save(temp_path)
            file_store = FileStore(temp_path)
            
            # Generate analysis using LLM
            q_analysis = QuestionFreeText(
                question_name="written_analysis", 
                question_text="""Please provide a written overview of the survey responses.
                Survey respondents were asked the question: 
                <question>
                {{ scenario.question_text }}
                </question>

                <question_type>
                {{ scenario.question_type }}
                </question_type>

                The overall response pattern is shown in this visualization:
                <chart>
                {{ scenario.chart }}
                </chart>
                
                Please provide a general overview of the response patterns.
                Write a short, 1 paragraph summary of the results as plain text.
                """
            )
            scenario = Scenario({
                'question_text': self.question.question_text, 
                'question_type': self.question.question_type,
                'chart': file_store
            })
            
            results = q_analysis.by(scenario).run(stop_on_exception=True)
            return results.select('answer.written_analysis').first()
        except Exception as e:
            print(f"Error generating written analysis: {e}")
            return "* Analysis generation failed or timed out *"