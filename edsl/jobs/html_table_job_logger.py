import re
import uuid
from datetime import datetime

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

    def _create_uuid_copy_button(self, uuid_value: str) -> str:
        """Create a UUID display with click-to-copy functionality"""
        short_uuid = uuid_value
        if len(uuid_value) > 12:
            short_uuid = f"{uuid_value[:8]}...{uuid_value[-4:]}"

        return f"""
        <div class="uuid-container" title="{uuid_value}">
            <span class="uuid-code">{short_uuid}</span>
            <button class="copy-btn" onclick="navigator.clipboard.writeText('{uuid_value}').then(() => {{
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
        </div>
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

    def _get_html(self, current_status: JobsStatus = JobsStatus.RUNNING) -> str:
        """Generate the complete HTML display with modern design"""
        # CSS for modern styling
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
            .two-column-grid {
                display: flex;
                flex-wrap: wrap;
                gap: 1px;
                background-color: #e2e8f0;
            }
            .column {
                background-color: white;
            }
            .column:first-child {
                flex: 1;
                min-width: 150px;
            }
            .column:last-child {
                flex: 2;
                min-width: 300px;
            }
            .content-box {
                padding: 5px 12px;
            }
            .link-item {
                padding: 3px 0;
                border-bottom: 1px solid #f1f5f9;
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
            .uuid-item {
                padding: 3px 0;
                border-bottom: 1px solid #f1f5f9;
                display: flex;
                align-items: center;
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
                color: #3b82f6;
                font-weight: 500;
                text-decoration: none;
                border-bottom: 1px dotted #bfdbfe;
                transition: border-color 0.2s;
                font-size: 0.75em;
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
                padding: 5px 12px;
                background-color: #f7fafc;
                border-top: 1px solid #edf2f7;
                font-size: 0.85em;
            }
            .status-running { color: #3b82f6; }
            .status-completed { color: #10b981; }
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
            .uuid-container {
                display: flex;
                align-items: center;
                background-color: #f8fafc;
                border-radius: 3px;
                padding: 2px 6px;
                font-family: monospace;
                font-size: 0.75em;
                flex: 1;
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
        </style>
        """

        # Group JobsInfo fields into categories
        url_fields = []
        uuid_fields = []
        other_fields = []

        for field, _ in self.jobs_info.__annotations__.items():
            if field != "pretty_names":
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

        # Build a two-column layout with links and UUIDs
        content_html = """
        <div class="two-column-grid">
            <div class="column">
                <div class="section-header">Links</div>
                <div class="content-box">
        """

        # Sort URLs to prioritize Results first, then Progress Bar
        results_links = []
        progress_links = []
        other_links = []

        for field, pretty_name, value in url_fields:
            # Replace "Progress Bar" with "Progress Report"
            if "progress_bar" in field.lower():
                pretty_name = "Progress Report URL"

            label = pretty_name.replace(" URL", "")

            if "result" in field.lower():
                results_links.append((field, pretty_name, value, label))
            elif "progress" in field.lower():
                progress_links.append((field, pretty_name, value, label))
            else:
                other_links.append((field, pretty_name, value, label))

        # Add results links first with special styling
        for field, pretty_name, value, label in results_links:
            content_html += f"""
            <div class="link-item results-link">
                <a href="{value}" target="_blank" class="pill-link">{label}{self.external_link_icon}</a>
            </div>
            """

        # Then add progress links with different special styling
        for field, pretty_name, value, label in progress_links:
            content_html += f"""
            <div class="link-item progress-link">
                <a href="{value}" target="_blank" class="pill-link">{label}{self.external_link_icon}</a>
            </div>
            """

        # Then add other links
        for field, pretty_name, value, label in other_links:
            content_html += f"""
            <div class="link-item">
                <a href="{value}" target="_blank" class="pill-link">{label}{self.external_link_icon}</a>
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
            # Create single-line UUID displays
            content_html += f"""
            <div class="uuid-item">
                <span class="uuid-label">{pretty_name}:</span>{self._create_uuid_copy_button(value)}
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

        # Status banner
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
        <div class="status-banner">
            {status_icon}
            <strong>Status:</strong>&nbsp;<span class="badge {status_class}">{status_text}</span>
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
            <div class="message-log">
                {''.join(reversed(message_items))}
            </div>
            """

        display_style = "block" if self.is_expanded else "none"

        return f"""
        {css}
        <div class="jobs-container">
            <div class="jobs-header" onclick="
                const content = document.getElementById('content-{self.log_id}');
                const arrow = document.getElementById('arrow-{self.log_id}');
                if (content.style.display === 'none') {{
                    content.style.display = 'block';
                    arrow.innerHTML = '&#8963;';
                }} else {{
                    content.style.display = 'none';
                    arrow.innerHTML = '&#8964;';
                }}">
                <div>
                    <span id="arrow-{self.log_id}" class="expand-toggle">{'&#8963;' if self.is_expanded else '&#8964;'}</span>
                    Job Status 🦜
                </div>
                <div class="{status_class}">{status_text}</div>
            </div>
            <div id="content-{self.log_id}" class="jobs-content" style="display: {display_style};">
                {content_html}
                {status_banner}
                {message_log}
            </div>
        </div>
        """
