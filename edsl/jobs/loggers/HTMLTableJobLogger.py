import uuid
import re
import datetime
from edsl.jobs.JobsRemoteInferenceLogger import JobLogger
from edsl.jobs.jobs_status_enums import JobsStatus


class HTMLTableJobLogger(JobLogger):
    def __init__(self, verbose=True, **kwargs):
        from IPython.display import display, HTML

        super().__init__(verbose=verbose)
        self.display_handle = display(HTML(""), display_id=True)
        self.current_message = None
        self.log_id = str(uuid.uuid4())
        self.is_expanded = True
        self.spinner_chars = ["◐", "◓", "◑", "◒"]
        self.spinner_idx = 0

        # Initialize CSS once when the logger is created
        self._init_css()

    def _init_css(self):
        """Initialize the CSS styles with theme support"""
        css = """
        <style>
            :root {
                --jl-bg-primary: #ffffff;
                --jl-bg-secondary: #f8f9fa;
                --jl-border-color: #e2e8f0;
                --jl-text-primary: #1a202c;
                --jl-text-secondary: #4a5568;
                --jl-link-color: #3b82f6;
                --jl-success-color: #22c55e;
                --jl-error-color: #ef4444;
            }
            
            [data-theme="dark"] {
                --jl-bg-primary: #1a202c;
                --jl-bg-secondary: #2d3748;
                --jl-border-color: #4a5568;
                --jl-text-primary: #f7fafc;
                --jl-text-secondary: #e2e8f0;
                --jl-link-color: #60a5fa;
                --jl-success-color: #34d399;
                --jl-error-color: #f87171;
            }
            
            .job-logger {
                font-family: system-ui, -apple-system, sans-serif;
                max-width: 800px;
                margin: 10px 0;
                color: var(--jl-text-primary);
            }
            
            .job-logger-header {
                padding: 10px;
                background: var(--jl-bg-secondary);
                border: 1px solid var(--jl-border-color);
                border-radius: 4px;
                cursor: pointer;
                color: var(--jl-text-primary);
                user-select: none;
            }
            
            .job-logger-table {
                width: 100%;
                border-collapse: collapse;
                background: var(--jl-bg-primary);
                border: 1px solid var(--jl-border-color);
            }
            
            .job-logger-cell {
                padding: 8px;
                border: 1px solid var(--jl-border-color);
            }
            
            .job-logger-label {
                font-weight: bold;
                color: var(--jl-text-primary);
            }
            
            .job-logger-value {
                color: var(--jl-text-secondary);
            }
            
            .job-logger-status {
                margin-top: 10px;
                padding: 8px;
                background-color: var(--jl-bg-secondary);
                border: 1px solid var(--jl-border-color);
                border-radius: 4px;
                color: var(--jl-text-primary);
            }
            
            .job-logger-link {
                color: var(--jl-link-color);
                text-decoration: underline;
            }
            
            .job-logger-success {
                color: var(--jl-success-color);
            }
            
            .job-logger-error {
                color: var(--jl-error-color);
            }
        </style>
        
        <script>
            // Auto-detect dark mode
            const darkModeMediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
            const root = document.documentElement;
            
            function updateTheme(e) {
                if (e.matches) {
                    root.setAttribute('data-theme', 'dark');
                } else {
                    root.setAttribute('data-theme', 'light');
                }
            }
            
            darkModeMediaQuery.addListener(updateTheme);
            updateTheme(darkModeMediaQuery);
        </script>
        """
        from IPython.display import HTML, display

        display(HTML(css))

    def _get_table_row(self, key: str, value: str) -> str:
        """Generate a table row with key-value pair"""
        return f"""
            <tr>
                <td class="job-logger-cell job-logger-label">{key}</td>
                <td class="job-logger-cell job-logger-value">{value if value else 'None'}</td>
            </tr>
        """

    def _linkify(self, text: str) -> str:
        """Convert URLs in text to clickable links"""
        url_pattern = r'(https?://[^\s<>"]+|www\.[^\s<>"]+)'
        return re.sub(
            url_pattern,
            r'<a href="\1" target="_blank" class="job-logger-link">\1</a>',
            text,
        )

    def _get_spinner(self, status: JobsStatus) -> str:
        """Get the current spinner frame if status is running"""
        if status == JobsStatus.RUNNING:
            spinner = self.spinner_chars[self.spinner_idx]
            self.spinner_idx = (self.spinner_idx + 1) % len(self.spinner_chars)
            return f'<span style="margin-right: 8px;">{spinner}</span>'
        elif status == JobsStatus.COMPLETED:
            return (
                '<span style="margin-right: 8px;" class="job-logger-success">✓</span>'
            )
        elif status == JobsStatus.FAILED:
            return '<span style="margin-right: 8px;" class="job-logger-error">✗</span>'
        return ""

    def _get_html(self, status: JobsStatus = JobsStatus.RUNNING) -> str:
        """Generate the complete HTML display"""
        info_rows = ""
        for field, _ in self.jobs_info.__annotations__.items():
            if field != "pretty_names":
                value = getattr(self.jobs_info, field)
                value = self._linkify(str(value)) if value else None
                pretty_name = self.jobs_info.pretty_names.get(
                    field, field.replace("_", " ").title()
                )
                info_rows += self._get_table_row(pretty_name, value)

        message_html = ""
        if self.current_message:
            spinner = self._get_spinner(status)
            message_html = f"""
                <div class="job-logger-status">
                    {spinner}<strong>Current Status:</strong> {self._linkify(self.current_message)}
                </div>
            """

        display_style = "block" if self.is_expanded else "none"
        arrow = "▼" if self.is_expanded else "▶"

        return f"""
            <div class="job-logger">
                <div onclick="document.getElementById('content-{self.log_id}').style.display = document.getElementById('content-{self.log_id}').style.display === 'none' ? 'block' : 'none';
                             document.getElementById('arrow-{self.log_id}').innerHTML = document.getElementById('content-{self.log_id}').style.display === 'none' ? '▶' : '▼';"
                     class="job-logger-header">
                    <span id="arrow-{self.log_id}">{arrow}</span> Job Status ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')})
                </div>
                <div id="content-{self.log_id}" style="display: {display_style};">
                    <table class="job-logger-table">
                        {info_rows}
                    </table>
                    {message_html}
                </div>
            </div>
        """

    def update(self, message: str, status: JobsStatus = JobsStatus.RUNNING):
        """Update the display with new message and current JobsInfo state"""
        from IPython.display import HTML

        self.current_message = message
        if self.verbose:
            self.display_handle.update(HTML(self._get_html(status)))
        else:
            return None
