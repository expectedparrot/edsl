from .table_output import TableOutput
import pandas as pd
from ..themes import ThemeFinder


class ResponsesWithThemesTable(TableOutput):
    """A table showing all responses with their assigned theme labels."""

    pretty_name = "Responses with Theme Labels"
    pretty_short_name = "Responses with themes"
    methodology = "Shows all raw responses alongside the themes that were identified for each response using natural language processing"

    def __init__(self, results, *question_names, free_text_sample_config=None):
        if len(question_names) != 1:
            raise ValueError(
                "ResponsesWithThemesTable requires exactly one question name"
            )
        super().__init__(results, *question_names)

        # Get the question and answers
        self.question = self.questions[0]
        self.answers = self.results.select(self.get_data_column(self.questions[0])).to_list()
        self.free_text_sample_config = free_text_sample_config or {}

        # Get question text and survey context if available
        self.question_text = self.question.question_text
        self.context = None

        # Try to get survey context if it exists
        if hasattr(self.results, "metadata") and self.results.metadata:
            if "context" in self.results.metadata:
                self.context = self.results.metadata["context"]

        # Apply sampling if configured
        sampled_answers = self._apply_sampling(self.answers, self.question_names[0])

        # Initialize ThemeFinder
        self.theme_finder = ThemeFinder(
            answers=sampled_answers, question=self.question_text, context=self.context
        )

    def _apply_sampling(self, answers, question_name):
        """Apply sampling configuration to the answers for this question."""
        if not self.free_text_sample_config:
            return answers

        # Check for question-specific configuration first
        if question_name in self.free_text_sample_config:
            sample_size = self.free_text_sample_config[question_name]
        elif "_global" in self.free_text_sample_config:
            sample_size = self.free_text_sample_config["_global"]
        else:
            return answers

        # Filter out None values before sampling
        valid_answers = [a for a in answers if a is not None]

        if not valid_answers or len(valid_answers) <= sample_size:
            return answers  # Return original if no valid answers or sample size >= valid answers

        # Sample without replacement using random.sample
        import random

        random.seed("reports_sampling")  # Use consistent seed for reproducibility
        sampled_answers = random.sample(valid_answers, sample_size)

        # Add back None values to maintain original structure if needed
        # For theme analysis, we usually just want the valid answers
        return sampled_answers

    @property
    def can_be_analyzed(self):
        """ResponsesWithThemesTable should not be included in written analysis."""
        return False

    @property
    def scenario_output(self):
        """Returns the table as HTML with scrollable styling."""
        df = self.output()
        if not isinstance(df, pd.DataFrame):
            raise ValueError("output() must return a pandas DataFrame")

        # Convert DataFrame to styled HTML with scrollable container
        styled_df = df.style.set_properties(
            **{
                "text-align": "left",
                "padding": "8px",
                "border": "1px solid #ddd",
                "word-wrap": "break-word",
            }
        ).set_table_styles(
            [
                # Table container with scroll
                {
                    "selector": "",
                    "props": [
                        ("max-height", "400px"),  # Fixed height for scroll
                        ("overflow-y", "auto"),  # Vertical scroll
                        ("display", "block"),
                        ("font-family", "Arial, sans-serif"),
                        ("font-size", "14px"),
                        ("border-collapse", "collapse"),
                        ("width", "100%"),
                        ("margin", "20px 0"),
                    ],
                },
                # Header row styling
                {
                    "selector": "thead",
                    "props": [
                        ("background-color", "#f5f5f5"),
                        ("position", "sticky"),  # Sticky header
                        ("top", "0"),  # Stick to top
                        ("z-index", "1"),
                    ],
                },
                {
                    "selector": "thead th",
                    "props": [
                        ("background-color", "#f5f5f5"),
                        ("font-weight", "bold"),
                        ("text-align", "left"),
                        ("padding", "8px"),
                        ("border", "1px solid #ddd"),
                    ],
                },
                # Row styling
                {
                    "selector": "tbody tr:nth-of-type(odd)",
                    "props": [("background-color", "#f9f9f9")],
                },
                {
                    "selector": "td",
                    "props": [
                        ("border", "1px solid #ddd"),
                        ("padding", "8px"),
                        ("vertical-align", "top"),
                    ],
                },
            ]
        )

        return styled_df.to_html()

    @property
    def narrative(self):
        return f"A detailed table showing all individual responses for the question '{self.question_text}' with their assigned theme labels. Each row represents one respondent's answer and the themes identified in that response."

    @classmethod
    def can_handle(cls, *question_objs):
        """Check if this table type can handle the given questions."""
        # Only handle single free text questions
        return len(question_objs) == 1 and question_objs[0].question_type == "free_text"

    def output(self):
        """
        Generate a table containing all responses with their assigned themes.

        Returns:
            A pandas DataFrame containing all responses and their themes
        """
        # Get the all responses table from theme finder
        responses_df = self.theme_finder.create_all_responses_table(
            max_response_length=500
        )

        # Add row numbers as index
        responses_df.index = responses_df.index + 1  # Make it 1-based
        responses_df.index.name = "Response #"

        return responses_df

    @property
    def html(self):
        """Returns the HTML representation of the table with scrollable content"""
        df = self.output()
        if not isinstance(df, pd.DataFrame):
            raise ValueError("output() must return a pandas DataFrame")

        # Import at function level to avoid circular imports
        import uuid

        # Generate unique ID for this table
        table_id = f"table_{uuid.uuid4().hex[:8]}"
        filename_base = self.get_download_filename_base()

        # Start with download buttons
        html_parts = [f'<div class="table-with-downloads" id="{table_id}">']
        html_parts.append('<div class="table-download-buttons">')
        html_parts.append(
            f"<button class=\"table-download-btn\" onclick=\"downloadTableAsCSV('{table_id}', '{filename_base}')\">📊 Download CSV</button>"
        )
        html_parts.append(
            f"<button class=\"table-download-btn\" onclick=\"downloadTableAsExcel('{table_id}', '{filename_base}')\">📈 Download Excel</button>"
        )
        html_parts.append("</div>")

        # Add summary information
        total_responses = len(df)
        themes_count = len(self.theme_finder.themes)

        summary_html = f"""
        <div class="response-summary" style="margin-bottom: 15px; padding: 10px; background-color: #f8f9fa; border: 1px solid #e9ecef; border-radius: 4px;">
            <p><strong>Total Responses:</strong> {total_responses}</p>
            <p><strong>Total Themes:</strong> {themes_count}</p>
            <p><strong>Themes:</strong> {', '.join(self.theme_finder.themes)}</p>
        </div>
        """
        html_parts.append(summary_html)

        # Create HTML with scrollable container
        html_parts.append(
            '<div class="table-container" style="max-height: 400px; overflow-y: auto;">'
        )
        html_parts.append('<table class="styled-table">')
        html_parts.append("<thead>")
        html_parts.append("<tr>")

        # Add index name if it exists
        if df.index.name:
            html_parts.append(f"<th>{df.index.name}</th>")

        # Add column headers
        for col in df.columns:
            html_parts.append(f"<th>{col}</th>")
        html_parts.append("</tr>")
        html_parts.append("</thead>")

        # Add body
        html_parts.append("<tbody>")
        for idx, row in df.iterrows():
            html_parts.append("<tr>")
            # Add index
            html_parts.append(f"<td>{idx}</td>")
            # Add row data
            for val in row:
                html_parts.append(f"<td>{val}</td>")
            html_parts.append("</tr>")
        html_parts.append("</tbody>")
        html_parts.append("</table>")
        html_parts.append("</div>")
        html_parts.append("</div>")

        # Add CSS for download buttons
        css_style = """
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
        </style>
        """

        return css_style + "\n".join(html_parts)
