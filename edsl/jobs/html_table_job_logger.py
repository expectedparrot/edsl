import re
import uuid
from datetime import datetime

from IPython.display import display, HTML

from .jobs_remote_inference_logger import JobLogger
from .jobs_status_enums import JobsStatus

        
class HTMLTableJobLogger(JobLogger):
    """HTML table-based job logger for displaying job status in Jupyter notebooks.
    
    This logger displays a collapsible table with job information, current status,
    and relevant links. It supports multiple themes and includes an animated spinner
    for running jobs.
    
    To use the more compact SmallHTMLLogger instead, set the environment variable:
    EDSL_USE_SMALL_LOGGER=1
    
    Example:
        import os
        os.environ["EDSL_USE_SMALL_LOGGER"] = "1"
        # Then use Jobs as normal - HTMLTableJobLogger will be replaced with SmallHTMLLogger
    """
    def __new__(cls, verbose=True, theme="auto", **kwargs):
        # Enable to use SmallHTMLLogger instead by using environment variable
        import os
        
        use_small_logger = os.environ.get("EDSL_USE_SMALL_LOGGER", "").lower() in ("1", "true", "yes")
        
        if use_small_logger:
            from .small_html_logger import SmallHTMLLogger
            # Return a SmallHTMLLogger instance instead
            return SmallHTMLLogger(verbose=verbose, theme=theme, **kwargs)
            
        # Otherwise proceed with normal instance creation
        return super(HTMLTableJobLogger, cls).__new__(cls)
        
    def __init__(self, verbose=True, theme="auto", **kwargs):
        super().__init__(verbose=verbose)

        self.display_handle = display(HTML(""), display_id=True) if verbose else None
        #self.display_handle = display(HTML(""), display_id=True)
        self.current_message = None
        self.log_id = str(uuid.uuid4())
        self.is_expanded = True
        self.spinner_chars = ["◐", "◓", "◑", "◒"]
        self.spinner_idx = 0
        self.theme = theme  # Can be "auto", "light", or "dark"

        # Initialize CSS once when the logger is created
        self._init_css()

    def _init_css(self):

        """Initialize the CSS styles with enhanced theme support"""
        if not self.verbose:
            return None
        
        css = """
        <style>
            /* Base theme variables */
            :root {
                --jl-bg-primary: #ffffff;
                --jl-bg-secondary: #f5f5f5;
                --jl-border-color: #e0e0e0;
                --jl-text-primary: #24292e;
                --jl-text-secondary: #586069;
                --jl-link-color: #0366d6;
                --jl-success-color: #28a745;
                --jl-error-color: #d73a49;
                --jl-header-bg: #f1f1f1;
            }
            
            /* Dark theme variables */
            .theme-dark {
                --jl-bg-primary: #1e1e1e;
                --jl-bg-secondary: #252526;
                --jl-border-color: #2d2d2d;
                --jl-text-primary: #cccccc;
                --jl-text-secondary: #999999;
                --jl-link-color: #4e94ce;
                --jl-success-color: #89d185;
                --jl-error-color: #f14c4c;
                --jl-header-bg: #333333;
            }

            /* High contrast theme variables */
            .theme-high-contrast {
                --jl-bg-primary: #000000;
                --jl-bg-secondary: #1a1a1a;
                --jl-border-color: #404040;
                --jl-text-primary: #ffffff;
                --jl-text-secondary: #cccccc;
                --jl-link-color: #66b3ff;
                --jl-success-color: #00ff00;
                --jl-error-color: #ff0000;
                --jl-header-bg: #262626;
            }
            
            .job-logger {
                font-family: system-ui, -apple-system, sans-serif;
                max-width: 800px;
                margin: 10px 0;
                color: var(--jl-text-primary);
                box-shadow: 0 1px 3px rgba(0,0,0,0.12);
                border-radius: 4px;
                overflow: hidden;
            }
            
            .job-logger-header {
                padding: 12px 16px;
                background: var(--jl-header-bg);
                border: none;
                border-radius: 4px 4px 0 0;
                cursor: pointer;
                color: var(--jl-text-primary);
                user-select: none;
                font-weight: 500;
                letter-spacing: 0.3px;
                display: flex;
                justify-content: space-between;
                align-items: center;
            }
            
            .theme-select {
                padding: 4px 8px;
                border-radius: 4px;
                border: 1px solid var(--jl-border-color);
                background: var(--jl-bg-primary);
                color: var(--jl-text-primary);
                font-size: 0.9em;
            }
            
            .job-logger-table {
                width: 100%;
                border-collapse: separate;
                border-spacing: 0;
                background: var(--jl-bg-primary);
                border: 1px solid var(--jl-border-color);
                margin-top: -1px;
            }
            
            .job-logger-cell {
                padding: 12px 16px;
                border-bottom: 1px solid var(--jl-border-color);
                line-height: 1.4;
            }
            
            .job-logger-label {
                font-weight: 500;
                color: var(--jl-text-primary);
                width: 25%;
                background: var(--jl-bg-secondary);
            }
            
            .job-logger-value {
                color: var(--jl-text-secondary);
                word-break: break-word;
            }
            
            .job-logger-status {
                margin: 0;
                padding: 12px 16px;
                background-color: var(--jl-bg-secondary);
                border: 1px solid var(--jl-border-color);
                border-top: none;
                border-radius: 0 0 4px 4px;
                color: var(--jl-text-primary);
                font-size: 0.95em;
            }
        </style>
        
        <script>
            class ThemeManager {
                constructor(logId, initialTheme = 'auto') {
                    this.logId = logId;
                    this.currentTheme = initialTheme;
                    this.darkModeMediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
                    this.init();
                }
                
                init() {
                    this.setupThemeSwitcher();
                    this.updateTheme(this.currentTheme);
                    
                    this.darkModeMediaQuery.addListener(() => {
                        if (this.currentTheme === 'auto') {
                            this.updateTheme('auto');
                        }
                    });
                }
                
                setupThemeSwitcher() {
                    const logger = document.querySelector(`#logger-${this.logId}`);
                    if (!logger) return;
                    
                    const switcher = document.createElement('div');
                    switcher.className = 'theme-switcher';
                    switcher.innerHTML = `
                        <select id="theme-select-${this.logId}" class="theme-select">
                            <option value="auto">Auto</option>
                            <option value="light">Light</option>
                            <option value="dark">Dark</option>
                            <option value="high-contrast">High Contrast</option>
                        </select>
                    `;
                    
                    const header = logger.querySelector('.job-logger-header');
                    header.appendChild(switcher);
                    
                    const select = switcher.querySelector('select');
                    select.value = this.currentTheme;
                    select.addEventListener('change', (e) => {
                        this.updateTheme(e.target.value);
                    });
                }
                
                updateTheme(theme) {
                    const logger = document.querySelector(`#logger-${this.logId}`);
                    if (!logger) return;
                    
                    this.currentTheme = theme;
                    
                    logger.classList.remove('theme-light', 'theme-dark', 'theme-high-contrast');
                    
                    if (theme === 'auto') {
                        const isDark = this.darkModeMediaQuery.matches;
                        logger.classList.add(isDark ? 'theme-dark' : 'theme-light');
                    } else {
                        logger.classList.add(`theme-${theme}`);
                    }
                    
                    try {
                        localStorage.setItem('jobLoggerTheme', theme);
                    } catch (e) {
                        console.warn('Unable to save theme preference:', e);
                    }
                }
            }
            
            window.initThemeManager = (logId, initialTheme) => {
                new ThemeManager(logId, initialTheme);
            };
        </script>
        """

        init_script = f"""
        <script>
            document.addEventListener('DOMContentLoaded', () => {{
                window.initThemeManager('{self.log_id}', '{self.theme}');
            }});
        </script>
        """
        

        display(HTML(css + init_script))

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
        """Generate the complete HTML display with theme support"""
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
            <!-- #region Remove Inference Info -->
            <div id="logger-{self.log_id}" class="job-logger">
                <div class="job-logger-header">
                    <span>
                        <span id="arrow-{self.log_id}">{arrow}</span> 
                        Job Status ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')})
                    </span>
                </div>
                <div id="content-{self.log_id}" style="display: {display_style};">
                    <table class="job-logger-table">
                        {info_rows}
                    </table>
                    {message_html}
                </div>
            </div>
            <!-- # endregion -->
        """

    def update(self, message: str, status: JobsStatus = JobsStatus.RUNNING):
        """Update the display with new message and current JobsInfo state"""
        self.current_message = message
        if self.verbose:
            self.display_handle.update(HTML(self._get_html(status)))
        else:
            return None
