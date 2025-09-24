"""
DataFrameGridChartsEnterpriseWidget - AG-Grid Enterprise + AG-Charts Enterprise widget

Provides the full enterprise experience for pandas DataFrame exploration including:
- Integrated Charts: Create charts directly from grid selections
- Pivot Tables: Drag columns to create dynamic pivot tables  
- Tool Panel: Column management with drag & drop
- Advanced Filtering: Set filters and date ranges
- Range Selection: Select cell ranges for analysis
- Row Grouping: Group and aggregate data
- Status Bar: Show aggregations and counts
- Excel Export: Export data to Excel format
"""

import traitlets
import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional, Union
import logging

try:
    from .base_widget import EDSLBaseWidget
except ImportError:
    from base_widget import EDSLBaseWidget

logger = logging.getLogger(__name__)


class DataFrameGridChartsEnterpriseWidget(EDSLBaseWidget):
    """Full-featured Enterprise data grid and charts widget for pandas DataFrames."""
    
    widget_short_name = "dataframe_grid_charts_enterprise"
    
    # Core traitlets for data
    dataframe = traitlets.Any(allow_none=True).tag(sync=False)
    data = traitlets.List().tag(sync=True)
    columns = traitlets.List().tag(sync=True)
    
    # Basic grid configuration
    page_size = traitlets.Int(50).tag(sync=True)
    enable_sorting = traitlets.Bool(True).tag(sync=True)
    enable_filtering = traitlets.Bool(True).tag(sync=True)
    enable_selection = traitlets.Bool(True).tag(sync=True)
    selection_mode = traitlets.Unicode("multiple").tag(sync=True)
    
    # Enterprise features
    enable_charts = traitlets.Bool(True).tag(sync=True)
    enable_pivot = traitlets.Bool(True).tag(sync=True)
    pivot_mode = traitlets.Bool(False).tag(sync=True)
    show_tool_panel = traitlets.Bool(True).tag(sync=True)
    enable_range_selection = traitlets.Bool(True).tag(sync=True)
    enable_status_bar = traitlets.Bool(True).tag(sync=True)
    enable_context_menu = traitlets.Bool(True).tag(sync=True)
    
    # Chart themes and options
    chart_themes = traitlets.List(default_value=['ag-default', 'ag-material', 'ag-solar']).tag(sync=True)
    default_chart_type = traitlets.Unicode("column").tag(sync=True)
    
    # Available columns for analysis
    numeric_columns = traitlets.List().tag(sync=True)
    categorical_columns = traitlets.List().tag(sync=True)
    datetime_columns = traitlets.List().tag(sync=True)
    
    # Status and error handling  
    status = traitlets.Unicode("ready").tag(sync=True)
    error_message = traitlets.Unicode("").tag(sync=True)
    
    # Selected rows and ranges
    selected_rows = traitlets.List().tag(sync=True)
    selected_indices = traitlets.List().tag(sync=True)
    selected_ranges = traitlets.List().tag(sync=True)
    
    # Grouping and aggregation
    row_group_columns = traitlets.List().tag(sync=True)
    value_columns = traitlets.List().tag(sync=True)
    pivot_columns = traitlets.List().tag(sync=True)

    def __init__(self, dataframe: Optional[pd.DataFrame] = None, **kwargs):
        """
        Initialize the DataFrameGridChartsEnterpriseWidget.
        
        Args:
            dataframe: pandas DataFrame to display
            **kwargs: Additional keyword arguments
        """
        super().__init__(**kwargs)
        if dataframe is not None:
            self.dataframe = dataframe

    @traitlets.observe("dataframe")
    def _on_dataframe_change(self, change):
        """Update widget data when dataframe changes."""
        if change["new"] is not None:
            self._process_dataframe()

    def _process_dataframe(self):
        """Process the pandas DataFrame for Enterprise features."""
        if self.dataframe is None:
            self._clear_data()
            return

        try:
            self.status = "processing"
            self.error_message = ""
            
            if not isinstance(self.dataframe, pd.DataFrame):
                raise ValueError("Input must be a pandas DataFrame")
            
            if self.dataframe.empty:
                self._clear_data()
                self.error_message = "DataFrame is empty"
                self.status = "error"
                return
            
            # Prepare data for AG-Grid Enterprise
            processed_data = self._prepare_data(self.dataframe)
            column_defs = self._prepare_enterprise_columns(self.dataframe)
            
            # Analyze columns for Enterprise features
            self._analyze_columns(self.dataframe)
            
            # Update traitlets
            self.data = processed_data
            self.columns = column_defs
            
            self.status = "ready"
            logger.info(f"Processed DataFrame for Enterprise features: {len(self.dataframe)} rows, {len(self.dataframe.columns)} columns")
            
        except Exception as e:
            logger.error(f"Error processing DataFrame: {e}")
            self.error_message = str(e)
            self.status = "error"
            self._clear_data()

    def _prepare_data(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """
        Prepare DataFrame data for AG-Grid Enterprise features.
        
        Args:
            df: pandas DataFrame
            
        Returns:
            List of dictionaries representing rows
        """
        # Handle missing values and data types
        df_clean = df.copy()
        
        # Convert data types for Enterprise features
        for col in df_clean.columns:
            if df_clean[col].dtype == 'object':
                # Keep strings as strings for grouping
                df_clean[col] = df_clean[col].astype(str)
                df_clean[col] = df_clean[col].replace(['nan', 'None'], '')
            elif pd.api.types.is_datetime64_any_dtype(df_clean[col]):
                # Keep datetime format for Enterprise date handling
                df_clean[col] = df_clean[col].dt.strftime('%Y-%m-%d %H:%M:%S')
                df_clean[col] = df_clean[col].fillna('')
            elif pd.api.types.is_numeric_dtype(df_clean[col]):
                # Handle numeric values properly for aggregations
                df_clean[col] = df_clean[col].fillna(0)
        
        # Add row index for tracking
        df_clean.reset_index(inplace=True)
        if 'index' in df_clean.columns:
            df_clean.rename(columns={'index': '_row_index'}, inplace=True)
        
        return df_clean.to_dict('records')

    def _prepare_enterprise_columns(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """
        Prepare column definitions with Enterprise features.
        
        Args:
            df: pandas DataFrame
            
        Returns:
            List of AG-Grid Enterprise column definitions
        """
        column_defs = []
        
        # Hidden row index column
        column_defs.append({
            "field": "_row_index",
            "headerName": "Index",
            "hide": True,
            "suppressMenu": True,
            "suppressSorting": True,
            "suppressColumnsToolPanel": True
        })
        
        for col in df.columns:
            dtype = df[col].dtype
            
            col_def = {
                "field": str(col),
                "headerName": str(col),
                "sortable": self.enable_sorting,
                "filter": self.enable_filtering,
                "resizable": True,
                "enableRowGroup": True,  # Enterprise: enable row grouping
                "enablePivot": self.enable_pivot,  # Enterprise: enable pivoting
                "enableValue": False,  # Will be set based on data type
                "menuTabs": ["generalMenuTab", "filterMenuTab", "columnsMenuTab"],
            }
            
            # Configure based on data type
            if pd.api.types.is_integer_dtype(dtype) or pd.api.types.is_float_dtype(dtype):
                col_def.update({
                    "type": "numericColumn",
                    "filter": "agNumberColumnFilter" if self.enable_filtering else False,
                    "enableValue": True,  # Enable aggregation for numeric columns
                    "aggFunc": "sum",  # Default aggregation
                    "allowedAggFuncs": ["sum", "avg", "count", "min", "max"],
                })
                if pd.api.types.is_float_dtype(dtype):
                    col_def["cellRenderer"] = "agAnimateShowChangeCellRenderer"
                    col_def["valueFormatter"] = "value ? value.toFixed(2) : ''"
                    
            elif pd.api.types.is_datetime64_any_dtype(dtype):
                col_def.update({
                    "filter": "agDateColumnFilter" if self.enable_filtering else False,
                    "enableValue": False,  # Dates typically used for grouping, not values
                })
                
            elif pd.api.types.is_bool_dtype(dtype):
                col_def.update({
                    "cellRenderer": "agCheckboxCellRenderer",
                    "enableValue": False,
                })
                
            else:  # String/categorical columns
                col_def.update({
                    "filter": "agTextColumnFilter" if self.enable_filtering else False,
                    "enableValue": False,  # Text columns used for grouping
                })
                
                # If categorical with reasonable cardinality, enhance for grouping
                if df[col].nunique() <= min(20, len(df) // 10):
                    col_def["enableRowGroup"] = True
                    col_def["enablePivot"] = self.enable_pivot
            
            column_defs.append(col_def)
        
        return column_defs

    def _analyze_columns(self, df: pd.DataFrame):
        """
        Analyze DataFrame columns for Enterprise features.
        
        Args:
            df: pandas DataFrame
        """
        numeric_cols = []
        categorical_cols = []
        datetime_cols = []
        
        for col in df.columns:
            if pd.api.types.is_numeric_dtype(df[col]):
                numeric_cols.append(str(col))
            elif pd.api.types.is_datetime64_any_dtype(df[col]):
                datetime_cols.append(str(col))
            else:
                # Consider categorical if reasonable cardinality
                if df[col].nunique() <= min(50, len(df) // 2):
                    categorical_cols.append(str(col))
        
        self.numeric_columns = numeric_cols
        self.categorical_columns = categorical_cols
        self.datetime_columns = datetime_cols

    def _clear_data(self):
        """Clear all data from the widget."""
        self.data = []
        self.columns = []
        self.selected_rows = []
        self.selected_indices = []
        self.selected_ranges = []
        self.numeric_columns = []
        self.categorical_columns = []
        self.datetime_columns = []
        self.row_group_columns = []
        self.value_columns = []
        self.pivot_columns = []

    def set_dataframe(self, dataframe: pd.DataFrame):
        """
        Set a new DataFrame to display.
        
        Args:
            dataframe: pandas DataFrame to display
        """
        self.dataframe = dataframe

    def get_selected_dataframe(self) -> Optional[pd.DataFrame]:
        """
        Get a DataFrame containing only the selected rows.
        
        Returns:
            pandas DataFrame with selected rows, or None if no selection
        """
        if not self.selected_indices or self.dataframe is None:
            return None
        
        try:
            return self.dataframe.iloc[self.selected_indices]
        except IndexError:
            logger.warning("Selected indices are out of range")
            return None

    def clear_selection(self):
        """Clear the current selection."""
        self.selected_rows = []
        self.selected_indices = []
        self.selected_ranges = []

    def configure_enterprise_features(self,
                                    enable_charts: Optional[bool] = None,
                                    enable_pivot: Optional[bool] = None,
                                    show_tool_panel: Optional[bool] = None,
                                    enable_range_selection: Optional[bool] = None,
                                    chart_themes: Optional[List[str]] = None):
        """
        Configure Enterprise-specific features.
        
        Args:
            enable_charts: Enable integrated charting
            enable_pivot: Enable pivot mode and functionality
            show_tool_panel: Show the column tool panel
            enable_range_selection: Enable range selection
            chart_themes: Available chart themes
        """
        if enable_charts is not None:
            self.enable_charts = enable_charts
        if enable_pivot is not None:
            self.enable_pivot = enable_pivot
        if show_tool_panel is not None:
            self.show_tool_panel = show_tool_panel
        if enable_range_selection is not None:
            self.enable_range_selection = enable_range_selection
        if chart_themes is not None:
            self.chart_themes = chart_themes

    def toggle_pivot_mode(self):
        """Toggle pivot mode on/off."""
        self.pivot_mode = not self.pivot_mode
        logger.info(f"Pivot mode {'enabled' if self.pivot_mode else 'disabled'}")

    def create_chart_from_selection(self, chart_type: str = "column"):
        """
        Trigger chart creation from selected data (Enterprise feature).
        
        Args:
            chart_type: Type of chart to create
        """
        if not self.enable_charts:
            logger.warning("Charts not enabled")
            return
            
        self.default_chart_type = chart_type
        logger.info(f"Chart creation triggered: {chart_type}")

    def export_to_excel(self, filename: Optional[str] = None) -> str:
        """
        Export data to Excel (Enterprise feature placeholder).
        
        Args:
            filename: Optional filename for export
            
        Returns:
            Success message
        """
        if self.dataframe is None:
            raise ValueError("No data to export")
            
        if filename is None:
            filename = "dataframe_export.xlsx"
            
        # In a real implementation, this would trigger the Enterprise export
        logger.info(f"Excel export would be triggered to {filename}")
        return f"Export to {filename} triggered"

    def get_aggregation_summary(self) -> Dict[str, Any]:
        """
        Get summary of current aggregations and groupings.
        
        Returns:
            Dictionary with aggregation information
        """
        return {
            "row_groups": self.row_group_columns,
            "value_columns": self.value_columns,
            "pivot_columns": self.pivot_columns,
            "pivot_mode": self.pivot_mode,
            "numeric_columns": self.numeric_columns,
            "categorical_columns": self.categorical_columns,
            "total_rows": len(self.data)
        }