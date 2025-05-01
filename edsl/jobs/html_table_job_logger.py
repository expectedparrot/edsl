import re
import uuid
from datetime import datetime
from typing import Union

from IPython.display import display, HTML

from .jobs_remote_inference_logger import JobLogger
from .jobs_status_enums import JobsStatus


class HTMLTableJobLogger(JobLogger):
    def __init__(self, verbose=True, **kwargs):
        super().__init__(verbose=verbose)
        self.display_handle = display(HTML(""), display_id=True)
        self.current_message = None
        self.log_id = str(uuid.uuid4())
        self.is_expanded = True
        self.spinner_chars = ["◐", "◓", "◑", "◒"]
        self.spinner_idx = 0
        self.messages = []  # Store message history
        self.external_link_icon = """
            <svg
                xmlns="http://www.w3.org/2000/svg"
                width="24"
                height="24"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="2"
                stroke-linecap="round"
                stroke-linejoin="round"
                class="external-link-icon"
            >
                <path d="M15 3h6v6" />
                <path d="M10 14 21 3" />
                <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
            </svg>
        """

    def _get_status_icon(self, status: JobsStatus) -> str:
        """Return appropriate icon for job status"""
        if status == JobsStatus.RUNNING:
            spinner = self.spinner_chars[self.spinner_idx]
            self.spinner_idx = (self.spinner_idx + 1) % len(self.spinner_chars)
            return f'<span class="status-icon status-running">{spinner}</span>'
        elif status == JobsStatus.COMPLETED:
            return '<span class="status-icon status-completed">✓</span>'
        elif status == JobsStatus.PARTIALLY_FAILED:
            return '<span class="status-icon status-partially-failed">✗</span>'
        elif status == JobsStatus.FAILED:
            return '<span class="status-icon status-failed">✗</span>'
        else:
            return '<span class="status-icon status-unknown">•</span>'

    def _linkify(self, text: str) -> str:
        """Convert markdown-style links to HTML links"""
        markdown_pattern = r"\[(.*?)\]\((.*?)\)"
        return re.sub(
            markdown_pattern,
            r'<a href="\2" target="_blank" class="link">\1</a>',
            text,
        )

    def _create_uuid_copy_button(
        self, uuid_value: str, helper_text: Union[str, None] = None
    ) -> str:
        """Create a UUID display with click-to-copy functionality"""
        short_uuid = uuid_value
        if len(uuid_value) > 12:
            short_uuid = f"{uuid_value[:8]}...{uuid_value[-4:]}"

        return f"""
        <div class="uuid-container-wrapper">
            <div class="uuid-container" title="{uuid_value}">
                <span class="uuid-code">{short_uuid}</span>
                {self._create_copy_button(uuid_value)}
            </div>
            {f'<div class="helper-text">{helper_text}</div>' if helper_text else ''}
        </div>
        """

    def _create_copy_button(self, value: str) -> str:
        """Create a button with click-to-copy functionality"""
        return f"""
            <button class="copy-btn" onclick="navigator.clipboard.writeText('{value}').then(() => {{
                const btn = this;
                btn.querySelector('.copy-icon').style.display = 'none';
                btn.querySelector('.check-icon').style.display = 'block';
                setTimeout(() => {{
                    btn.querySelector('.check-icon').style.display = 'none';
                    btn.querySelector('.copy-icon').style.display = 'block';
                }}, 1000);
            }})" title="Copy to clipboard">
                <svg class="copy-icon" xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
                    <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
                </svg>
                <svg class="check-icon" style="display: none" xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <polyline points="20 6 9 17 4 12"></polyline>
                </svg>
            </button>
        """

    def update(self, message: str, status: JobsStatus = JobsStatus.RUNNING):
        """Update the display with new message and current JobsInfo state"""
        self.current_message = message
        # Add to message history with timestamp
        self.messages.append(
            {
                "text": message,
                "status": status,
                "timestamp": datetime.now().strftime("%H:%M:%S"),
            }
        )

        if self.verbose:
            self.display_handle.update(HTML(self._get_html(status)))
        else:
            return None

    def _collapse(self, content_id: str, arrow_id: str) -> str:
        """Generate the onclick JavaScript for collapsible sections"""
        return f"""
            const content = document.getElementById('{content_id}');
            const arrow = document.getElementById('{arrow_id}');
            if (content.style.display === 'none') {{
                content.style.display = 'block';
                arrow.innerHTML = '&#8963;';
            }} else {{
                content.style.display = 'none';
                arrow.innerHTML = '&#8964;';
            }}
        """

    def _build_exceptions_table(self) -> str:
        """Generate HTML for the exceptions summary table section."""
        if not self.jobs_info.exception_summary:
            return ""

        total_exceptions = sum(
            exc.exception_count for exc in self.jobs_info.exception_summary
        )

        # Generate exception rows HTML before the return
        exception_rows = "".join(
            f"""
            <tr>
                <td>{exc.exception_type or '-'}</td>
                <td>{exc.inference_service or '-'}</td>
                <td>{exc.model or '-'}</td>
                <td>{exc.question_name or '-'}</td>
                <td class='exception-count'>{exc.exception_count:,}</td>
            </tr>
        """
            for exc in self.jobs_info.exception_summary
        )

        # Get the error report URL if it exists
        error_report_url = getattr(self.jobs_info, "error_report_url", None)
        error_report_link = (
            f"""
            <div style="margin-bottom: 12px; font-size: 0.85em;">
                <a href="{error_report_url}" target="_blank" class="pill-link">
                    View full exceptions report{self.external_link_icon}
                </a>
            </div>
            """
            if error_report_url
            else ""
        )

        return f"""
        <div class="exception-section">
            <div class="exception-header" onclick="{self._collapse(f'exception-content-{self.log_id}', f'exception-arrow-{self.log_id}')}">
                <span id="exception-arrow-{self.log_id}" class="expand-toggle">&#8963;</span>
                <span>Exception Summary ({total_exceptions:,} total)</span>
                <span style="flex-grow: 1;"></span>
            </div>
            <div id="exception-content-{self.log_id}" class="exception-content">
                {error_report_link}
                <table class='exception-table'>
                    <thead>
                        <tr>
                            <th>Exception Type</th>
                            <th>Service</th>
                            <th>Model</th>
                            <th>Question</th>
                            <th>Count</th>
                        </tr>
                    </thead>
                    <tbody>
                        {exception_rows}
                    </tbody>
                </table>
            </div>
        </div>
        """

    def _build_model_costs_table(self) -> str:
        """Generate HTML for the model costs summary table section."""
        if not hasattr(self.jobs_info, "model_costs") or not self.jobs_info.model_costs:
            return ""

        # Calculate totals
        total_input_tokens = sum(
            cost.input_tokens or 0 for cost in self.jobs_info.model_costs
        )
        total_output_tokens = sum(
            cost.output_tokens or 0 for cost in self.jobs_info.model_costs
        )
        total_input_cost = sum(
            cost.input_cost_usd or 0 for cost in self.jobs_info.model_costs
        )
        total_output_cost = sum(
            cost.output_cost_usd or 0 for cost in self.jobs_info.model_costs
        )
        total_cost = total_input_cost + total_output_cost

        # Generate cost rows HTML with class names for right alignment
        cost_rows = "".join(
            f"""
            <tr>
                <td>{cost.service or '-'}</td>
                <td>{cost.model or '-'}</td>
                <td class='token-count'>{cost.input_tokens:,}</td>
                <td class='cost-value'>${cost.input_cost_usd:.4f}</td>
                <td class='token-count'>{cost.output_tokens:,}</td>
                <td class='cost-value'>${cost.output_cost_usd:.4f}</td>
                <td class='cost-value'>${(cost.input_cost_usd or 0) + (cost.output_cost_usd or 0):.4f}</td>
            </tr>
            """
            for cost in self.jobs_info.model_costs
        )

        # Add total row with the same alignment classes
        total_row = f"""
            <tr class='totals-row'>
                <td colspan='2'><strong>Totals</strong></td>
                <td class='token-count'>{total_input_tokens:,}</td>
                <td class='cost-value'>${total_input_cost:.4f}</td>
                <td class='token-count'>{total_output_tokens:,}</td>
                <td class='cost-value'>${total_output_cost:.4f}</td>
                <td class='cost-value'>${total_cost:.4f}</td>
            </tr>
        """

        return f"""
        <div class="model-costs-section">
            <div class="model-costs-header" onclick="{self._collapse(f'model-costs-content-{self.log_id}', f'model-costs-arrow-{self.log_id}')}">
                <span id="model-costs-arrow-{self.log_id}" class="expand-toggle">&#8963;</span>
                <span>Model Costs (${total_cost:.4f} total)</span>
                <span style="flex-grow: 1;"></span>
            </div>
            <div id="model-costs-content-{self.log_id}" class="model-costs-content">
                <table class='model-costs-table'>
                    <thead>
                        <tr>
                            <th>Service</th>
                            <th>Model</th>
                            <th class="cost-header">Input Tokens</th>
                            <th class="cost-header">Input Cost</th>
                            <th class="cost-header">Output Tokens</th>
                            <th class="cost-header">Output Cost</th>
                            <th class="cost-header">Total Cost</th>
                        </tr>
                    </thead>
                    <tbody>
                        {cost_rows}
                        {total_row}
                    </tbody>
                </table>
            </div>
        </div>
        """

    def _get_html(self, current_status: JobsStatus = JobsStatus.RUNNING) -> str:
        """Generate the complete HTML display with modern design"""
        css = """
        <style>
            .jobs-container {
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Oxygen, Ubuntu, Cantarell, "Open Sans", "Helvetica Neue", sans-serif;
                max-width: 800px;
                margin: 16px 0;
                border-radius: 8px;
                overflow: hidden;
                box-shadow: 0 1px 3px rgba(0,0,0,0.12), 0 1px 2px rgba(0,0,0,0.24);
                color: #1a1a1a;
            }
            .jobs-header {
                padding: 8px 12px;
                background: linear-gradient(to right, #f7f9fc, #edf2f7);
                border-bottom: 1px solid #e2e8f0;
                cursor: pointer;
                display: flex;
                align-items: center;
                justify-content: space-between;
                font-weight: 500;
                font-size: 0.9em;
                flex-wrap: wrap;
                gap: 8px;
            }
            .jobs-content {
                background: white;
            }
            .jobs-table {
                width: 100%;
                border-collapse: collapse;
            }
            .jobs-table th, .jobs-table td {
                padding: 12px 16px;
                text-align: left;
                border-bottom: 1px solid #edf2f7;
            }
            .jobs-table th {
                width: 25%;
                max-width: 140px;
                background-color: #f7fafc;
                font-weight: 500;
                color: #4a5568;
            }
            .jobs-table td {
                width: 75%;
            }
            .section-header {
                padding: 5px 12px;
                font-weight: 600;
                color: #1f2937;
                background-color: #f7fafc;
                border-bottom: 1px solid #cbd5e1;
                font-size: 0.85em;
            }
            .three-column-grid {
                display: flex;
                flex-wrap: wrap;
                gap: 1px;
                background-color: #e2e8f0;
            }
            .column {
                background-color: white;
            }
            .column:nth-child(1) {  /* Job Links */
                flex: 1;
                min-width: 150px;
            }
            .column:nth-child(2) {  /* Content */
                flex: 1;
                min-width: 150px;
            }
            .column:nth-child(3) {  /* Identifiers */
                flex: 2;
                min-width: 300px;
            }
            .content-box {
                padding: 5px 12px;
            }
            .link-item {
                padding: 3px 0;
                border-bottom: 1px solid #f1f5f9;
                font-size: 0.9em;
            }
            .link-item:last-child {
                border-bottom: none;
            }
            .results-link .pill-link {
                color: #059669;
                font-weight: 500;
            }
            .results-link .pill-link:hover {
                border-bottom-color: #059669;
            }
            .progress-link .pill-link {
                color: #3b82f6;
                font-weight: 500;
            }
            .progress-link .pill-link:hover {
                border-bottom-color: #3b82f6;
            }
            .remote-link .pill-link {
                color: #4b5563;
                font-weight: 500;
            }
            .remote-link .pill-link:hover {
                border-bottom-color: #4b5563;
            }
            .uuid-item {
                padding: 3px 0;
                border-bottom: 1px solid #f1f5f9;
                display: flex;
                align-items: flex-start;
            }
            .uuid-item:last-child {
                border-bottom: none;
            }
            .uuid-label {
                font-weight: 500;
                color: #4b5563;
                font-size: 0.75em;
                margin-right: 6px;
                min-width: 80px;
            }
            .compact-links {
                padding: 8px 16px;
                line-height: 1.5;
            }
            .pill-link {
                font-weight: 500;
                text-decoration: none;
                border-bottom: 1px dotted #bfdbfe;
                transition: border-color 0.2s;
                display: inline-flex;
                align-items: center;
                gap: 4px;
            }
            .pill-link:hover {
                border-bottom: 1px solid #3b82f6;
            }
            .external-link-icon {
                width: 12px;
                height: 12px;
                opacity: 0.7;
            }
            .status-banner {
                display: flex;
                align-items: center;
                flex-wrap: wrap;
                gap: 8px;
                padding: 5px 12px;
                background-color: #f7fafc;
                border-top: 1px solid #edf2f7;
                font-size: 0.85em;
                cursor: pointer;
            }
            .status-running { color: #3b82f6; }
            .status-completed { color: #059669; }
            .status-partially-failed { color: #d97706; }
            .status-failed { color: #ef4444; }
            .status-unknown { color: #6b7280; }
            .status-icon {
                display: inline-flex;
                align-items: center;
                justify-content: center;
                width: 18px;
                height: 18px;
                margin-right: 6px;
                font-weight: bold;
            }
            .link {
                color: #3b82f6;
                text-decoration: none;
                border-bottom: 1px dotted #bfdbfe;
                transition: border-color 0.2s;
            }
            .link:hover {
                border-bottom: 1px solid #3b82f6;
            }
            .uuid-container-wrapper {
                display: flex;
                flex-direction: column;
                align-items: stretch;
                gap: 4px;
                flex: 1;
                padding-bottom: 4px;
            }            
            .uuid-container {
                display: flex;
                align-items: center;
                background-color: #f8fafc;
                border-radius: 3px;
                padding: 2px 6px;
                font-family: monospace;
                font-size: 0.75em;
                width: 100%;  /* Make sure it fills the width */
            }
            .uuid-code {
                color: #4b5563;
                overflow: hidden;
                text-overflow: ellipsis;
                flex: 1;
            }
            .copy-btn {
                background-color: #e2e8f0;
                border: none;
                cursor: pointer;
                margin-left: 4px;
                padding: 4px;
                border-radius: 3px;
                transition: all 0.2s ease;
                color: #4b5563;
                display: flex;
                align-items: center;
                justify-content: center;
                width: 22px;
                height: 22px;
            }
            .copy-btn:hover {
                background-color: #cbd5e1;
                color: #1f2937;
            }
            .copy-icon, .check-icon {
                display: block;
            }
            .message-log {
                max-height: 120px;
                overflow-y: auto;
                border-top: 1px solid #edf2f7;
                padding: 3px 0;
                font-size: 0.85em;
            }
            .message-item {
                display: flex;
                padding: 2px 12px;
            }
            .message-timestamp {
                color: #9ca3af;
                font-size: 0.85em;
                margin-right: 8px;
                white-space: nowrap;
            }
            .status-indicator {
                display: inline-block;
                width: 8px;
                height: 8px;
                border-radius: 50%;
                margin-right: 8px;
            }
            .expand-toggle {
                display: inline-block;
                width: 16px;
                text-align: center;
                margin-right: 6px;
                font-size: 12px;
            }
            .badge {
                display: inline-block;
                padding: 2px 6px;
                border-radius: 3px;
                font-size: 0.8em;
                font-weight: 500;
            }
            .status-running.badge { background-color: #dbeafe; }
            .status-completed.badge { background-color: #d1fae5; }
            .status-partially-failed.badge { background-color: #fef3c7; }
            .status-failed.badge { background-color: #fee2e2; }
            .helper-text {
                color: #4b5563;
                font-size: 0.75em;
                text-align: left;
            }
            /* Exception table styles */
            .exception-section {
                border-top: 1px solid #edf2f7;
            }
            .exception-header {
                padding: 8px 12px;
                background-color: #f7fafc;
                display: flex;
                align-items: center;
                cursor: pointer;
                font-size: 0.85em;
                font-weight: 500;
                user-select: none;  /* Prevent text selection */
            }
            .exception-content {
                padding: 12px;
            }
            .exception-table {
                width: 100%;
                border-collapse: collapse;
                margin: 0;
                font-size: 0.85em;
            }
            .exception-table th {
                background-color: #f1f5f9;
                color: #475569;
                font-weight: 500;
                text-align: left;
                padding: 8px 12px;
                border-bottom: 2px solid #e2e8f0;
            }
            .exception-table td {
                padding: 6px 12px;
                border-bottom: 1px solid #e2e8f0;
                color: #1f2937;
                text-align: left;  /* Ensure left alignment */
            }
            .exception-table tr:last-child td {
                border-bottom: none;
            }
            .exception-count {
                font-weight: 500;
                color: #ef4444;
            }
            /* Model costs table styles */
            .model-costs-section {
                border-top: 1px solid #edf2f7;
            }
            .model-costs-header {
                padding: 8px 12px;
                background-color: #f7fafc;
                display: flex;
                align-items: center;
                cursor: pointer;
                font-size: 0.85em;
                font-weight: 500;
                user-select: none;
            }
            .model-costs-content {
                padding: 12px;
            }
            .model-costs-table {
                width: 100%;
                border-collapse: collapse;
                margin: 0;
                font-size: 0.85em;
            }
            .model-costs-table th {
                background-color: #f1f5f9;
                color: #475569;
                font-weight: 500;
                text-align: left;  /* Default left alignment */
                padding: 8px 12px;
                border-bottom: 2px solid #e2e8f0;
            }
            .model-costs-table th.cost-header {  /* New class for cost headers */
                text-align: right;
            }
            .model-costs-table td {
                padding: 6px 12px;
                border-bottom: 1px solid #e2e8f0;
                color: #1f2937;
                text-align: left;  /* Ensure left alignment for all cells by default */
            }
            .model-costs-table tr:last-child td {
                border-bottom: none;
            }
            .token-count td, .cost-value td {  /* Override for specific columns that need right alignment */
                text-align: right;
            }
            .totals-row {
                background-color: #f8fafc;
            }
            .totals-row td {
                border-top: 2px solid #e2e8f0;
            }
            /* Model costs table styles */
            .model-costs-table td.token-count,
            .model-costs-table td.cost-value {
                text-align: right;  /* Right align the token counts and cost values */
            }
        </style>
        """

        # Group JobsInfo fields into categories
        url_fields = []
        uuid_fields = []
        other_fields = []

        for field, _ in self.jobs_info.__annotations__.items():
            if field not in [
                "pretty_names",
                "completed_interviews",
                "failed_interviews",
                "exception_summary",
                "model_costs",
            ]:
                value = getattr(self.jobs_info, field)
                if not value:
                    continue

                pretty_name = self.jobs_info.pretty_names.get(
                    field, field.replace("_", " ").title()
                )

                if "url" in field.lower():
                    url_fields.append((field, pretty_name, value))
                elif "uuid" in field.lower():
                    uuid_fields.append((field, pretty_name, value))
                else:
                    other_fields.append((field, pretty_name, value))

        # Build a three-column layout
        content_html = """
        <div class="three-column-grid">
            <div class="column">
                <div class="section-header">Job Links</div>
                <div class="content-box">
        """

        # Sort URLs to prioritize Results first, then Progress
        results_links = []
        progress_links = []
        remote_links = []
        other_links = []

        for field, pretty_name, value in url_fields:
            # Replace "Progress Bar" with "Progress Report"
            if "progress_bar" in field.lower():
                pretty_name = "Progress Report URL"

            label = pretty_name.replace(" URL", "")

            if "result" in field.lower():
                results_links.append((field, pretty_name, value, label))
            elif "progress" in field.lower() or "error_report" in field.lower():
                progress_links.append((field, pretty_name, value, label))
            elif "remote_cache" in field.lower() or "remote_inference" in field.lower():
                remote_links.append((field, pretty_name, value, label))
            else:
                other_links.append((field, pretty_name, value, label))

        # Add results and progress links to first column
        for field, pretty_name, value, label in results_links:
            content_html += f"""
            <div class="link-item results-link" style="display: flex; align-items: center; justify-content: space-between;">
                <a href="{value}" target="_blank" class="pill-link">{label}{self.external_link_icon}</a>
                {self._create_copy_button(value)}
            </div>
            """

        # Then add progress links with different special styling
        for field, pretty_name, value, label in progress_links:
            content_html += f"""
            <div class="link-item progress-link" style="display: flex; align-items: center; justify-content: space-between;">
                <a href="{value}" target="_blank" class="pill-link">{label}{self.external_link_icon}</a>
                {self._create_copy_button(value)}
            </div>
            """

        # Close first column and start second column
        content_html += """
                </div>
            </div>
            <div class="column">
                <div class="section-header">Content</div>
                <div class="content-box">
        """

        # Add remote links to middle column
        for field, pretty_name, value, label in remote_links + other_links:
            content_html += f"""
            <div class="link-item remote-link" style="display: flex; align-items: center; justify-content: space-between;">
                <a href="{value}" target="_blank" class="pill-link">{label}{self.external_link_icon}</a>
                {self._create_copy_button(value)}
            </div>
            """

        content_html += """
                </div>
            </div>
            <div class="column">
                <div class="section-header">Identifiers</div>
                <div class="content-box">
        """

        # Sort UUIDs to prioritize Result UUID first
        uuid_fields.sort(key=lambda x: 0 if "result" in x[0].lower() else 1)
        for field, pretty_name, value in uuid_fields:
            if "result" in field.lower():
                helper_text = "Use Results.pull(uuid) to fetch results."
            elif "job" in field.lower():
                helper_text = "Use Jobs.pull(uuid) to fetch job."
            else:
                helper_text = ""

            content_html += f"""
            <div class="uuid-item">
                <span class="uuid-label">{pretty_name}:</span>{self._create_uuid_copy_button(value, helper_text)}
            </div>
            """

        content_html += """
                </div>
            </div>
        </div>
        """

        # Add other fields in full width if any
        if other_fields:
            content_html += "<div class='section-header'>Additional Information</div>"
            content_html += "<table class='jobs-table'>"
            for field, pretty_name, value in other_fields:
                content_html += f"""
                <tr>
                    <th>{pretty_name}</th>
                    <td>{value}</td>
                </tr>
                """
            content_html += "</table>"

        # Status banner and message log
        status_class = {
            JobsStatus.RUNNING: "status-running",
            JobsStatus.COMPLETED: "status-completed",
            JobsStatus.PARTIALLY_FAILED: "status-partially-failed",
            JobsStatus.FAILED: "status-failed",
        }.get(current_status, "status-unknown")

        status_icon = self._get_status_icon(current_status)
        status_text = current_status.name.capitalize()
        if current_status == JobsStatus.PARTIALLY_FAILED:
            status_text = "Partially failed"
        elif hasattr(current_status, "name"):
            status_text = current_status.name.capitalize()
        else:
            status_text = str(current_status).capitalize()

        status_banner = f"""
        <div class="status-banner" onclick="{self._collapse(f'message-log-{self.log_id}', f'message-arrow-{self.log_id}')}">
            <div style="display: flex; align-items: center; gap: 8px;">
                <span id="message-arrow-{self.log_id}" class="expand-toggle">&#8963;</span>
                <div style="display: flex; align-items: center;">
                    {status_icon}
                    <strong>Status:</strong>&nbsp;<span class="badge {status_class}">{status_text}</span>
                </div>
            </div>
            <span style="flex-grow: 1;"></span>
            <span>Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</span>
        </div>
        """

        # Message history
        message_log = ""
        if self.messages:
            message_items = []
            for msg in self.messages:
                status_color = {
                    JobsStatus.RUNNING: "#3b82f6",
                    JobsStatus.COMPLETED: "#10b981",
                    JobsStatus.PARTIALLY_FAILED: "#f59e0b",
                    JobsStatus.FAILED: "#ef4444",
                }.get(msg["status"], "#6b7280")

                message_items.append(
                    f"""
                <div class="message-item">
                    <span class="message-timestamp">{msg["timestamp"]}</span>
                    <span class="status-indicator" style="background-color: {status_color};"></span>
                    <div>{self._linkify(msg["text"])}</div>
                </div>
                """
                )

            message_log = f"""
            <div id="message-log-{self.log_id}" class="message-log">
                {''.join(reversed(message_items))}
            </div>
            """

        display_style = "block" if self.is_expanded else "none"

        header_status_text = status_text
        if (
            self.jobs_info.completed_interviews is not None
            and self.jobs_info.failed_interviews is not None
        ):
            header_status_text += f" ({self.jobs_info.completed_interviews:,} completed, {self.jobs_info.failed_interviews:,} failed)"

        # Add model costs table before exceptions table
        main_content = f"""
            {content_html}
            {status_banner}
            {message_log}
            {self._build_model_costs_table()}
            {self._build_exceptions_table()}
        """

        # Return the complete HTML
        return f"""
        {css}
        <div class="jobs-container">
            <div class="jobs-header" onclick="{self._collapse(f'content-{self.log_id}', f'arrow-{self.log_id}')}">
                <div>
                    <span id="arrow-{self.log_id}" class="expand-toggle">{'&#8963;' if self.is_expanded else '&#8964;'}</span>
                    Job Status 🦜
                </div>
                <div class="{status_class}">{header_status_text}</div>
            </div>
            <div id="content-{self.log_id}" class="jobs-content" style="display: {display_style};">
                {main_content}
            </div>
        </div>
        """
