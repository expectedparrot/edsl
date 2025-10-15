import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# from output import Output  # TODO: Fix this import
from abc import ABC, abstractmethod
import pandas as pd
import tempfile
import uuid
import base64
import io

class TableOutput:  # TODO: Should inherit from Output when available
    """Base class for table outputs"""
    pretty_name = "Table"
    pretty_short_name = "Table"
    methodology = "Base class for table-based analysis outputs"
    
    # Registry to store all table output types
    _registry = {}
    
    def __init__(self, results, *question_names):
        """Initialize table output with results and question names"""
        self.results = results
        self.question_names = question_names
        self.questions = [self.results.survey.get(name) for name in self.question_names]
    
    def __init_subclass__(cls, **kwargs):
        """Automatically register all subclasses"""
        super().__init_subclass__(**kwargs)
        cls._registry[cls.__name__] = cls
    
    @property
    def scenario_output(self):
        """Returns the table as HTML."""
        df = self.output()
        if not isinstance(df, pd.DataFrame):
            raise ValueError("output() must return a pandas DataFrame")
        
        # Start with basic table HTML
        html_parts = ['<table class="styled-table">']
        
        # Add header
        html_parts.append('<thead>')
        html_parts.append('<tr>')
        for col in df.columns:
            html_parts.append(f'<th>{col}</th>')
        html_parts.append('</tr>')
        html_parts.append('</thead>')
        
        # Add body
        html_parts.append('<tbody>')
        for _, row in df.iterrows():
            html_parts.append('<tr>')
            for val in row:
                html_parts.append(f'<td>{val}</td>')
            html_parts.append('</tr>')
        html_parts.append('</tbody>')
        html_parts.append('</table>')
        
        # Add CSS styling
        style = """
        <style>
        .styled-table {
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
            font-family: Arial, sans-serif;
            font-size: 14px;
            box-shadow: 0 0 20px rgba(0, 0, 0, 0.1);
        }
        .styled-table thead tr {
            background-color: #f5f5f5;
            color: #333;
            text-align: left;
        }
        .styled-table th,
        .styled-table td {
            padding: 12px 15px;
            border: 1px solid #ddd;
        }
        .styled-table tbody tr {
            border-bottom: 1px solid #ddd;
        }
        .styled-table tbody tr:nth-of-type(even) {
            background-color: #f9f9f9;
        }
        .styled-table tbody tr:last-of-type {
            border-bottom: 2px solid #f5f5f5;
        }
        </style>
        """
        
        return style + '\n'.join(html_parts)

    @property
    @abstractmethod
    def narrative(self):
        """Returns a description of what this table shows. Must be implemented by subclasses."""
        pass
    
    @property
    def html(self):
        """Returns the HTML representation of the table"""
        df = self.output()
        if not isinstance(df, pd.DataFrame):
            raise ValueError("output() must return a pandas DataFrame")
        
        # Generate unique ID for this table
        table_id = f"table_{uuid.uuid4().hex[:8]}"
        filename_base = self.get_download_filename_base()
        
        # Start with download buttons
        html_parts = [f'<div class="table-with-downloads" id="{table_id}">']
        html_parts.append('<div class="table-download-buttons">')
        html_parts.append(f'<button class="table-download-btn" onclick="downloadTableAsCSV(\'{table_id}\', \'{filename_base}\')">📊 Download CSV</button>')
        html_parts.append(f'<button class="table-download-btn" onclick="downloadTableAsExcel(\'{table_id}\', \'{filename_base}\')">📈 Download Excel</button>')
        html_parts.append('</div>')
        
        # Add table HTML
        html_parts.append('<table class="styled-table">')
        
        # Add header
        html_parts.append('<thead>')
        html_parts.append('<tr>')
        for col in df.columns:
            html_parts.append(f'<th>{col}</th>')
        html_parts.append('</tr>')
        html_parts.append('</thead>')
        
        # Add body
        html_parts.append('<tbody>')
        for _, row in df.iterrows():
            html_parts.append('<tr>')
            for val in row:
                html_parts.append(f'<td>{val}</td>')
            html_parts.append('</tr>')
        html_parts.append('</tbody>')
        html_parts.append('</table>')
        html_parts.append('</div>')
        
        # Add CSS styling
        style = """
        <style>
        .table-with-downloads {
            margin: 20px 0;
        }
        .table-download-buttons {
            margin-bottom: 10px;
            text-align: right;
        }
        .table-download-btn {
            background-color: #2563eb;
            color: white;
            border: none;
            padding: 8px 16px;
            margin-left: 8px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 12px;
            transition: background-color 0.2s;
        }
        .table-download-btn:hover {
            background-color: #3b82f6;
        }
        .styled-table {
            width: 100%;
            border-collapse: collapse;
            font-family: Arial, sans-serif;
            font-size: 14px;
            box-shadow: 0 0 20px rgba(0, 0, 0, 0.1);
        }
        .styled-table thead tr {
            background-color: #f5f5f5;
            color: #333;
            text-align: left;
        }
        .styled-table th,
        .styled-table td {
            padding: 12px 15px;
            border: 1px solid #ddd;
        }
        .styled-table tbody tr {
            border-bottom: 1px solid #ddd;
        }
        .styled-table tbody tr:nth-of-type(even) {
            background-color: #f9f9f9;
        }
        .styled-table tbody tr:last-of-type {
            border-bottom: 2px solid #f5f5f5;
        }
        </style>
        """
        
        return style + '\n'.join(html_parts)
    
    @classmethod
    def get_available_outputs(cls):
        """Returns a dictionary of all registered table types"""
        return cls._registry
    
    @classmethod
    def create(cls, table_type, *args, **kwargs):
        """Factory method to create a table by name"""
        if table_type not in cls._registry:
            raise ValueError(f"Unknown table type: {table_type}. Available types: {list(cls._registry.keys())}")
        return cls._registry[table_type](*args, **kwargs)

    @classmethod
    @abstractmethod
    def can_handle(cls, *question_objs) -> bool:
        """
        Abstract method that determines if this table type can handle the given questions.
        Must be implemented by all child classes.
        
        Args:
            *question_objs: Variable number of question objects to check
            
        Returns:
            bool: True if this table type can handle these questions, False otherwise
        """
        pass

    def output(self):
        """Must return a pandas DataFrame"""
        pass
        
    def _get_container_class(self):
        """Return the appropriate container class for table outputs."""
        return "table-container"
    
    def _get_content_html(self):
        """Generate HTML specifically for table output."""
        try:
            # Use the existing html property
            return self.html
        except Exception as e:
            return f'<div class="error-message">Error generating table: {str(e)}</div>'
    
    def get_csv_download_url(self):
        """Generate a data URL for CSV download."""
        df = self.output()
        if not isinstance(df, pd.DataFrame):
            raise ValueError("output() must return a pandas DataFrame")
        
        # Convert DataFrame to CSV
        csv_buffer = io.StringIO()
        df.to_csv(csv_buffer, index=True)
        csv_content = csv_buffer.getvalue()
        
        # Encode as base64 for data URL
        csv_base64 = base64.b64encode(csv_content.encode('utf-8')).decode('utf-8')
        
        return f"data:text/csv;base64,{csv_base64}"
    
    def get_excel_download_url(self):
        """Generate a data URL for Excel download."""
        df = self.output()
        if not isinstance(df, pd.DataFrame):
            raise ValueError("output() must return a pandas DataFrame")
        
        # Convert DataFrame to Excel
        excel_buffer = io.BytesIO()
        df.to_excel(excel_buffer, index=True, engine='xlsxwriter')
        excel_content = excel_buffer.getvalue()
        
        # Encode as base64 for data URL
        excel_base64 = base64.b64encode(excel_content).decode('utf-8')
        
        return f"data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,{excel_base64}"
    
    def get_download_filename_base(self):
        """Generate a base filename for downloads based on question names."""
        if len(self.question_names) == 1:
            return f"table_{self.question_names[0]}"
        else:
            return f"table_{'_'.join(self.question_names)}"