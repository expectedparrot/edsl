"""
ResultsVisualizeWidget - Client-side visualization widget for EDSL Results

Provides comprehensive chart creation capabilities using pure client-side rendering
with intelligent chart suggestions and interactive controls.
"""

import traitlets
import pandas as pd
from typing import Dict, List, Any, Optional
import logging
from .base_widget import EDSLBaseWidget

logger = logging.getLogger(__name__)


class ResultsVisualizeWidget(EDSLBaseWidget):
    """Advanced visualization widget for EDSL Results with comprehensive chart types."""

    widget_short_name = "results_visualizer"

    # Core traitlets for data and configuration
    results = traitlets.Any(allow_none=True).tag(sync=False)
    data = traitlets.List().tag(sync=True)
    columns = traitlets.List().tag(sync=True)
    numeric_columns = traitlets.List().tag(sync=True)
    categorical_columns = traitlets.List().tag(sync=True)
    
    # Chart configuration
    chart_type = traitlets.Unicode("bar").tag(sync=True)
    x_column = traitlets.Unicode("").tag(sync=True)
    y_column = traitlets.Unicode("").tag(sync=True)
    color_column = traitlets.Unicode("").tag(sync=True)
    title = traitlets.Unicode("").tag(sync=True)
    
    # Chart suggestions and column info (no chart_spec needed for client-side)
    chart_suggestions = traitlets.List().tag(sync=True)
    column_info = traitlets.Dict().tag(sync=True)
    
    # Status and error handling
    status = traitlets.Unicode("ready").tag(sync=True)
    error_message = traitlets.Unicode("").tag(sync=True)

    def __init__(self, results=None, **kwargs):
        super().__init__(**kwargs)
        if results is not None:
            self.results = results

    @traitlets.observe("results")
    def _on_results_change(self, change):
        """Update widget data when results change."""
        if change["new"] is not None:
            self._process_results()

    def _process_results(self):
        """Extract and process data from EDSL Results object."""
        if self.results is None:
            self._clear_data()
            return

        try:
            self.status = "processing"
            self.error_message = ""
            
            # Convert results to DataFrame
            df = self._results_to_dataframe()
            
            if df.empty:
                self._clear_data()
                self.error_message = "No data found in results"
                self.status = "error"
                return
            
            # Process data
            processed_data = self._prepare_data(df)
            column_analysis = self._analyze_columns(df)
            suggestions = self._generate_chart_suggestions(df)
            
            # Update traitlets
            self.data = processed_data
            self.columns = list(df.columns)
            self.numeric_columns = column_analysis["numeric"]
            self.categorical_columns = column_analysis["categorical"]
            self.column_info = column_analysis["info"]
            self.chart_suggestions = suggestions
            
            # Set default chart configuration if not set
            if not self.x_column and self.columns:
                self.x_column = self.columns[0]
            if not self.y_column and len(self.numeric_columns) > 0:
                self.y_column = self.numeric_columns[0]
            
            self.status = "ready"
            logger.info(f"Processed {len(df)} rows with {len(df.columns)} columns")
            
        except Exception as e:
            logger.error(f"Error processing results: {e}")
            self.error_message = str(e)
            self.status = "error"
            self._clear_data()

    def _results_to_dataframe(self) -> pd.DataFrame:
        """Convert EDSL Results to pandas DataFrame."""
        try:
            # Try to use the built-in to_pandas method if available
            if hasattr(self.results, 'to_pandas'):
                return self.results.to_pandas()
            
            # Fallback: extract data manually
            data_rows = []
            if hasattr(self.results, 'survey') and hasattr(self.results.survey, 'questions'):
                for i, result in enumerate(self.results):
                    row = {}
                    for question in self.results.survey.questions:
                        try:
                            value = result.get(question.question_name)
                            row[question.question_name] = value
                        except:
                            row[question.question_name] = None
                    data_rows.append(row)
            
            return pd.DataFrame(data_rows)
            
        except Exception as e:
            logger.error(f"Error converting results to DataFrame: {e}")
            return pd.DataFrame()

    def _prepare_data(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """Prepare data for frontend visualization."""
        # Handle missing values
        df_clean = df.fillna("")
        
        # Sample large datasets for performance
        if len(df_clean) > 10000:
            logger.warning(f"Large dataset ({len(df_clean)} rows), sampling to 10000")
            df_clean = df_clean.sample(n=10000, random_state=42)
        
        # Convert to list of dictionaries
        return df_clean.to_dict('records')

    def _analyze_columns(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Analyze column types and characteristics."""
        numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
        categorical_cols = df.select_dtypes(include=['object', 'category']).columns.tolist()
        
        column_info = {}
        for col in df.columns:
            dtype = str(df[col].dtype)
            unique_count = df[col].nunique()
            null_count = df[col].isnull().sum()
            
            column_info[col] = {
                "type": dtype,
                "unique_values": unique_count,
                "null_count": null_count,
                "sample_values": df[col].dropna().head(5).tolist()
            }
        
        return {
            "numeric": numeric_cols,
            "categorical": categorical_cols,
            "info": column_info
        }

    def _generate_chart_suggestions(self, df: Optional[pd.DataFrame]) -> List[Dict[str, Any]]:
        """Generate intelligent chart suggestions based on data."""
        suggestions = []
        
        if df is None or df.empty:
            return suggestions
        
        numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
        categorical_cols = df.select_dtypes(include=['object', 'category']).columns.tolist()
        
        # Scatter plots for numeric vs numeric
        if len(numeric_cols) >= 2:
            suggestions.append({
                "chart_type": "scatter",
                "x_column": numeric_cols[0],
                "y_column": numeric_cols[1],
                "description": f"Scatter plot of {numeric_cols[0]} vs {numeric_cols[1]}",
                "confidence": 0.9
            })
        
        # Bar charts for categorical vs numeric
        if len(categorical_cols) >= 1 and len(numeric_cols) >= 1:
            suggestions.append({
                "chart_type": "bar",
                "x_column": categorical_cols[0],
                "y_column": numeric_cols[0],
                "description": f"Bar chart of {numeric_cols[0]} by {categorical_cols[0]}",
                "confidence": 0.85
            })
        
        # Histograms for numeric distributions
        if len(numeric_cols) >= 1:
            suggestions.append({
                "chart_type": "histogram",
                "x_column": numeric_cols[0],
                "description": f"Distribution of {numeric_cols[0]}",
                "confidence": 0.8
            })
        
        # Line charts for time series or ordered data
        if len(numeric_cols) >= 2:
            suggestions.append({
                "chart_type": "line",
                "x_column": numeric_cols[0],
                "y_column": numeric_cols[1],
                "description": f"Trend of {numeric_cols[1]} over {numeric_cols[0]}",
                "confidence": 0.7
            })
        
        # Box plots for categorical vs numeric
        if len(categorical_cols) >= 1 and len(numeric_cols) >= 1:
            suggestions.append({
                "chart_type": "box",
                "x_column": categorical_cols[0],
                "y_column": numeric_cols[0],
                "description": f"Box plot of {numeric_cols[0]} by {categorical_cols[0]}",
                "confidence": 0.75
            })
        
        # Sort by confidence and return top 5
        suggestions.sort(key=lambda x: x["confidence"], reverse=True)
        return suggestions[:5]

    def _clear_data(self):
        """Clear all data from the widget."""
        self.data = []
        self.columns = []
        self.numeric_columns = []
        self.categorical_columns = []
        self.column_info = {}
        self.chart_suggestions = []

    def create_chart(self, chart_type: str, x_column: str, y_column: Optional[str] = None, 
                    color_column: Optional[str] = None, title: Optional[str] = None):
        """Programmatically create a chart with specified parameters."""
        self.chart_type = chart_type
        self.x_column = x_column
        if y_column:
            self.y_column = y_column
        if color_column:
            self.color_column = color_column
        if title:
            self.title = title

    def apply_suggestion(self, suggestion_index: int):
        """Apply a chart suggestion by index."""
        if 0 <= suggestion_index < len(self.chart_suggestions):
            suggestion = self.chart_suggestions[suggestion_index]
            self.chart_type = suggestion["chart_type"]
            self.x_column = suggestion["x_column"]
            self.y_column = suggestion.get("y_column", "")
            self.color_column = suggestion.get("color_column", "")
            self.title = suggestion.get("title", "")