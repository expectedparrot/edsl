import json
import uuid
import os
from .warning_utils import print_info, print_success


class ReportHTML:
    """Helper class for generating HTML reports from Report objects."""
    
    def __init__(self, report):
        """Initialize with a Report instance.
        
        Args:
            report: The Report instance to generate HTML for.
        """
        self.report = report
    
    def generate(self, filename: str, css: str = None):
        """Generate a standalone HTML report.

        Args:
            filename (str): Destination HTML file path (e.g. "report.html").
            css (str, optional): Custom CSS styling to include in the report.
        """
        print_info("Generating HTML report…")

        html_parts: list[str] = []
        
        # Generate HTML structure
        self._add_html_header(html_parts, css)
        self._add_title_and_sections(html_parts, filename)
        self._add_table_of_contents(html_parts)
        self._add_analysis_sections(html_parts)
        self._add_javascript(html_parts, filename)
        
        html_parts.append("</body></html>")

        # Write to file
        with open(filename, "w", encoding="utf-8") as f:
            f.write("\n".join(html_parts))

        print_success(f"HTML report saved to {filename}")
    
    def _add_html_header(self, html_parts: list[str], css: str = None):
        """Add HTML document header with CSS and JavaScript imports."""
        html_parts.extend([
            "<!DOCTYPE html>",
            "<html lang='en'>",
            "<head>",
            "  <meta charset='utf-8'>",
            "  <title>Survey Report</title>",
            "  <meta name='viewport' content='width=device-width, initial-scale=1'>"
        ])
        
        # Add CSS
        css_content = css if css is not None else self._get_default_css()
        html_parts.append(f"  <style>{css_content}</style>")
        
        # Add JavaScript libraries
        html_parts.extend([
            "  <script src='https://cdn.jsdelivr.net/npm/vega@5'></script>",
            "  <script src='https://cdn.jsdelivr.net/npm/vega-lite@5'></script>",
            "  <script src='https://cdn.jsdelivr.net/npm/vega-embed@6'></script>",
            "  <script src='https://cdnjs.cloudflare.com/ajax/libs/xlsx/0.18.5/xlsx.full.min.js'></script>",
            "</head>",
            "<body>"
        ])
    
    def _add_title_and_sections(self, html_parts: list[str], filename: str):
        """Add title and main overview sections."""
        html_parts.append("<h1>Survey Report</h1>")

        # Add question summary table
        if self.report.include_questions_table:
            html_parts.extend([
                "<div class='overview-section'>",
                "<h2>Question Summary</h2>"
            ])
            question_summary_table = self.report._create_question_summary_table()
            html_parts.append(question_summary_table)
            html_parts.append("</div>")

        # Add download links section
        self._add_download_links_section(html_parts, filename)

        # Add overview sections
        if self.report.include_overview:
            html_parts.extend([
                "<div class='overview-section'>",
                "<h2>Survey Overview</h2>",
                f"<p>{self.report.survey_overview}</p>",
                "</div>"
            ])

        if self.report.include_respondents_section:
            html_parts.extend([
                "<div class='overview-section'>",
                "<h2>Respondent Overview</h2>",
                f"<p>{self.report.respondent_overview}</p>",
                "</div>"
            ])

        if self.report.include_scenario_section:
            html_parts.extend([
                "<div class='overview-section'>",
                "<h2>Scenario Overview</h2>",
                f"<p>{self.report.scenario_overview}</p>",
                "</div>"
            ])
    
    def _add_download_links_section(self, html_parts: list[str], filename: str):
        """Add download links and survey link section."""
        html_parts.extend([
            "<div class='download-links-section'>",
            "<h3>Downloads & Links</h3>",
            "<div class='download-links'>"
        ])
        
        # Generate filenames based on input filename
        base_filename = filename.replace('.html', '') if filename.endswith('.html') else filename
        docx_filename = f"{base_filename}.docx"
        pdf_filename = f"{base_filename}.pdf"
        notebook_filename = f"{base_filename}.ipynb"
        
        # Check if files exist before adding download links
        if os.path.exists(docx_filename):
            html_parts.extend([
                f"<a href='{os.path.basename(docx_filename)}' class='download-link' download>",
                "📄 Download DOCX",
                "</a>"
            ])
        
        if os.path.exists(pdf_filename):
            html_parts.extend([
                f"<a href='{os.path.basename(pdf_filename)}' class='download-link' download>",
                "📋 Download PDF",
                "</a>"
            ])
        
        if os.path.exists(notebook_filename):
            html_parts.extend([
                f"<a href='#' class='download-link' onclick='downloadNotebook()'>",
                "📓 Download Jupyter Notebook",
                "</a>"
            ])
        
        # Add "View original survey" link
        try:
            survey_humanized = self.report.results.survey.humanize()
            respondent_url = survey_humanized.get('respondent_url', None)
            if respondent_url:
                html_parts.extend([
                    f"<a href='{respondent_url}' class='download-link' target='_blank'>",
                    "🔗 View original survey on E[🦜]",
                    "</a>"
                ])
        except Exception:
            # If humanize() fails or respondent_url doesn't exist, skip this link
            pass
        
        html_parts.extend([
            "</div>",
            "</div>"
        ])
    
    def _add_table_of_contents(self, html_parts: list[str]):
        """Add table of contents section."""
        html_parts.extend([
            "<div class='overview-section'>",
            "<h2>Table of Contents</h2>",
            "<ul style='list-style-type: none; padding-left: 0;'>"
        ])
        
        for question_names, _ in self.report.items():
            section_title = self.report._format_question_header(question_names)
            anchor_id = self._create_anchor_id(question_names)
            
            html_parts.extend([
                f"<li style='margin-bottom: 8px;'>",
                f"<a href='#{anchor_id}' style='color: var(--primary-color); text-decoration: none; font-weight: 500;'>{section_title}</a>",
                "</li>"
            ])
        
        html_parts.extend([
            "</ul>",
            "</div>"
        ])
    
    def _add_analysis_sections(self, html_parts: list[str]):
        """Add individual analysis sections (collapsible)."""
        for question_names, output_dict in self.report.items():
            section_title = self.report._format_question_header(question_names)
            anchor_id = self._create_anchor_id(question_names)
            
            html_parts.extend([
                f"<div class='section' id='{anchor_id}'>",
                f"<div class='section-header' onclick='toggleSection(\"{anchor_id}\")'>",
                f"<h2 class='section-title'>{section_title}</h2>",
                "<span class='toggle-icon'>▼</span>",
                "</div>",
                "<div class='section-content'>"
            ])
            
            # Add question metadata table
            metadata_table = self.report._create_question_metadata_table(question_names)
            html_parts.append(metadata_table)

            # Add output subsections
            self._add_output_subsections(html_parts, question_names, output_dict)
            
            html_parts.extend([
                "</div>",  # Close section-content
                "</div>"   # Close section
            ])
    
    def _add_output_subsections(self, html_parts: list[str], question_names, output_dict):
        """Add output subsections for a question analysis."""
        for output_name, output_obj in output_dict.items():
            display_name = getattr(output_obj, 'pretty_short_name', output_name)
            html_parts.extend([
                "<div class='subsection'>",
                f"<h3>{display_name}</h3>"
            ])

            # Add writeup paragraph
            self._add_writeup(html_parts, question_names, output_name)
            
            # Add visualization/table
            self._embed_output(html_parts, output_obj, output_name, question_names)
            
            html_parts.append("</div>")  # Close subsection
    
    def _add_writeup(self, html_parts: list[str], question_names, output_name):
        """Add writeup text for an output if available and enabled."""
        if question_names in self.report.writeups and output_name in self.report.writeups[question_names]:
            # Check if writeup is enabled for this analysis
            analysis_key = tuple(question_names) if isinstance(question_names, (list, tuple)) else (question_names,)
            writeup_enabled = self.report._analysis_writeup_filters.get(analysis_key, True)
            if writeup_enabled:
                writeup_text = self.report.writeups[question_names][output_name]
                html_parts.append(f"<p>{writeup_text}</p>")
    
    def _embed_output(self, html_parts: list[str], output_obj, output_name: str, question_names):
        """Embed visualization or table output in HTML."""
        embedded = False

        # Check for specialized theme finder output with multiple charts
        from reports.charts.theme_finder_output import ThemeFinderOutput
        if isinstance(output_obj, ThemeFinderOutput):
            try:
                section_id = f"theme-{uuid.uuid4().hex}"
                theme_html = output_obj.generate_html(section_id, collapsed=False)
                html_parts.append(theme_html)
                embedded = True
            except Exception:
                embedded = False

        # Prefer embedding as SVG (robust for Altair charts)
        if not embedded:
            embedded = self._try_embed_svg(html_parts, output_obj)

        # Attempt interactive Vega/Vega-Lite embed for Altair charts
        if not embedded:
            embedded = self._try_embed_altair_chart(html_parts, output_obj)

        # Fallback: use .html property directly (tables, pre-built snippets)
        if not embedded:
            embedded = self._try_embed_html_property(html_parts, output_obj)

        # Fallback: if object returns a DataFrame, convert to HTML table
        if not embedded:
            embedded = self._try_embed_dataframe(html_parts, output_obj)

        if not embedded:
            raise RuntimeError(f"Failed to embed output '{output_name}' for questions {question_names} in HTML report.")
    
    def _try_embed_svg(self, html_parts: list[str], output_obj) -> bool:
        """Try to embed output as SVG."""
        try:
            svg_location = getattr(output_obj, "svg", None)
            if svg_location is not None:
                html_parts.append(f"<div class='chart-container'>{svg_location.html}</div>")
                return True
        except Exception:
            pass
        return False
    
    def _try_embed_altair_chart(self, html_parts: list[str], output_obj) -> bool:
        """Try to embed Altair chart with Vega/Vega-Lite."""
        try:
            if hasattr(output_obj, "output"):
                alt_output = output_obj.output()
                import altair as alt
                if isinstance(alt_output, (alt.Chart, alt.LayerChart, alt.FacetChart)) or isinstance(alt_output, alt.TopLevelMixin):
                    spec_json = json.dumps(alt_output.to_dict())
                    unique_id = f"chart-{uuid.uuid4().hex}"
                    html_parts.extend([
                        f"<div class='chart-container'><div id=\"{unique_id}\"></div></div>",
                        f"<script type=\"text/javascript\">vegaEmbed('#{unique_id}', {spec_json}, {{'renderer': 'svg'}});</script>"
                    ])
                    return True
        except Exception:
            pass
        return False
    
    def _try_embed_html_property(self, html_parts: list[str], output_obj) -> bool:
        """Try to embed using .html property."""
        try:
            if hasattr(output_obj, "html"):
                html_parts.append(output_obj.html)
                return True
        except Exception:
            pass
        return False
    
    def _try_embed_dataframe(self, html_parts: list[str], output_obj) -> bool:
        """Try to embed DataFrame as HTML table."""
        try:
            if hasattr(output_obj, "output"):
                generic_output = output_obj.output()
                import pandas as pd
                if isinstance(generic_output, pd.DataFrame):
                    html_parts.append(generic_output.to_html(border=0, classes=["styled-table"]))
                    return True
        except Exception:
            pass
        return False
    
    def _add_javascript(self, html_parts: list[str], filename: str):
        """Add JavaScript for interactivity."""
        base_filename = filename.replace('.html', '') if filename.endswith('.html') else filename
        notebook_filename = f"{base_filename}.ipynb"
        
        javascript = f"""
        <script>
        function toggleSection(sectionId) {{
            const section = document.getElementById(sectionId);
            const content = section.querySelector('.section-content');
            const icon = section.querySelector('.toggle-icon');
            
            if (content.classList.contains('show')) {{
                content.classList.remove('show');
                section.classList.remove('expanded');
                icon.textContent = '▼';
            }} else {{
                content.classList.add('show');
                section.classList.add('expanded');
                icon.textContent = '▲';
            }}
        }}
        
        function downloadTableAsCSV(tableId, filename) {{
            const tableContainer = document.getElementById(tableId);
            const table = tableContainer.querySelector('table');
            
            let csvContent = '';
            
            // Get headers
            const headers = table.querySelectorAll('thead th');
            const headerRow = Array.from(headers).map(th => '"' + th.textContent.replace(/"/g, '""') + '"').join(',');
            csvContent += headerRow + '\\n';
            
            // Get data rows
            const rows = table.querySelectorAll('tbody tr');
            rows.forEach(row => {{
                const cells = row.querySelectorAll('td');
                const rowData = Array.from(cells).map(td => '"' + td.textContent.replace(/"/g, '""') + '"').join(',');
                csvContent += rowData + '\\n';
            }});
            
            // Create blob and download
            const blob = new Blob([csvContent], {{ type: 'text/csv' }});
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = filename + '.csv';
            a.click();
            window.URL.revokeObjectURL(url);
        }}
        
        function downloadTableAsExcel(tableId, filename) {{
            const tableContainer = document.getElementById(tableId);
            const table = tableContainer.querySelector('table');
            
            // Create workbook
            const wb = XLSX.utils.book_new();
            const ws = XLSX.utils.table_to_sheet(table);
            XLSX.utils.book_append_sheet(wb, ws, 'Sheet1');
            
            // Write file
            XLSX.writeFile(wb, filename + '.xlsx');
        }}
        
        function downloadNotebook() {{
            const filename = '{os.path.basename(notebook_filename)}';
            fetch(filename)
                .then(response => response.blob())
                .then(blob => {{
                    const url = window.URL.createObjectURL(new Blob([blob], {{ type: 'application/x-ipynb+json' }}));
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = filename;
                    document.body.appendChild(a);
                    a.click();
                    document.body.removeChild(a);
                    window.URL.revokeObjectURL(url);
                }})
                .catch(error => {{
                    console.error('Error downloading notebook:', error);
                    // Fallback to direct link
                    const a = document.createElement('a');
                    a.href = filename;
                    a.download = filename;
                    a.click();
                }});
        }}
        
        function toggleSubsection(subsectionId) {{
            const subsection = document.getElementById(subsectionId);
            const toggle = subsection.parentElement.querySelector('.subsection-toggle');
            
            if (subsection.classList.contains('open')) {{
                subsection.classList.remove('open');
                subsection.classList.add('closed');
                toggle.textContent = '▶';
            }} else {{
                subsection.classList.remove('closed');
                subsection.classList.add('open');
                toggle.textContent = '▼';
            }}
        }}
        
        // Optional: Expand first section by default
        document.addEventListener('DOMContentLoaded', function() {{
            const firstSection = document.querySelector('.section');
            if (firstSection) {{
                const firstSectionId = firstSection.id;
                toggleSection(firstSectionId);
            }}
        }});
        </script>
        """
        html_parts.append(javascript)
    
    def _create_anchor_id(self, question_names) -> str:
        """Create a safe anchor ID from question names."""
        anchor_id = f"section-{'-'.join(question_names)}"
        return anchor_id.replace(' ', '-').replace("'", "").replace('"', '').replace('(', '').replace(')', '').replace('?', '').replace('!', '').replace('.', '').replace(',', '').replace(':', '').replace(';', '').lower()
    
    def _get_default_css(self) -> str:
        """Return the default CSS styling for HTML reports."""
        return """
        :root {
            --primary-color: #2563eb;
            --secondary-color: #64748b;
            --accent-color: #3b82f6;
            --background-color: #ffffff;
            --surface-color: #f8fafc;
            --text-primary: #1e293b;
            --text-secondary: #64748b;
            --border-color: #e2e8f0;
            --shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.1), 0 1px 2px 0 rgba(0, 0, 0, 0.06);
            --shadow-lg: 0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05);
        }
        
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            line-height: 1.6;
            color: var(--text-primary);
            background: var(--background-color);
            padding: 2rem;
            max-width: 1200px;
            margin: 0 auto;
        }
        
        h1, h2, h3 {
            color: var(--text-primary);
            margin-bottom: 1rem;
            font-weight: 600;
        }
        
        h1 {
            font-size: 2.5rem;
            border-bottom: 3px solid var(--primary-color);
            padding-bottom: 0.5rem;
            margin-bottom: 2rem;
        }
        
        h2 {
            font-size: 1.75rem;
            margin-top: 2rem;
            margin-bottom: 1.5rem;
        }
        
        h3 {
            font-size: 1.25rem;
            margin-top: 1.5rem;
            margin-bottom: 1rem;
            color: var(--secondary-color);
        }
        
        p {
            margin-bottom: 1rem;
            color: var(--text-secondary);
        }
        
        .section {
            background: var(--surface-color);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            margin-bottom: 2rem;
            box-shadow: var(--shadow);
            overflow: hidden;
        }
        
        .section-header {
            background: var(--primary-color);
            color: white;
            padding: 1.5rem;
            cursor: pointer;
            display: flex;
            justify-content: space-between;
            align-items: center;
            transition: background-color 0.2s;
        }
        
        .section-header:hover {
            background: var(--accent-color);
        }
        
        .section-title {
            font-size: 1.5rem;
            font-weight: 600;
            margin: 0;
        }
        
        .toggle-icon {
            font-size: 1.5rem;
            transition: transform 0.3s ease;
        }
        
        .section-content {
            padding: 2rem;
            display: none;
        }
        
        .section-content.show {
            display: block;
        }
        
        .section.expanded .toggle-icon {
            transform: rotate(180deg);
        }
        
        .download-links-section {
            background: linear-gradient(135deg, #f1f5f9 0%, #e2e8f0 100%);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            padding: 1.5rem;
            margin-bottom: 2rem;
            box-shadow: var(--shadow);
        }
        
        .download-links-section h3 {
            color: var(--primary-color);
            margin-top: 0;
            margin-bottom: 1rem;
        }
        
        .download-links {
            display: flex;
            gap: 1rem;
            flex-wrap: wrap;
        }
        
        .download-link {
            display: inline-flex;
            align-items: center;
            gap: 0.5rem;
            padding: 0.75rem 1.5rem;
            background: var(--primary-color);
            color: white;
            text-decoration: none;
            border-radius: 6px;
            font-weight: 500;
            transition: all 0.2s ease;
            box-shadow: var(--shadow);
        }
        
        .download-link:hover {
            background: var(--accent-color);
            transform: translateY(-2px);
            box-shadow: var(--shadow-lg);
            text-decoration: none;
            color: white;
        }
        
        .download-link:active {
            transform: translateY(0);
        }
        
        .overview-section {
            background: linear-gradient(135deg, var(--surface-color) 0%, #e0e7ff 100%);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            padding: 2rem;
            margin-bottom: 2rem;
            box-shadow: var(--shadow);
        }
        
        .overview-section h2 {
            color: var(--primary-color);
            margin-top: 0;
        }
        
        .overview-section ul a:hover {
            text-decoration: underline;
            color: var(--accent-color);
        }
        
        table {
            width: 100%;
            border-collapse: collapse;
            margin: 1rem 0;
            background: white;
            border-radius: 8px;
            overflow: hidden;
            box-shadow: var(--shadow);
        }
        
        th, td {
            padding: 1rem;
            text-align: left;
            border-bottom: 1px solid var(--border-color);
        }
        
        th {
            background: var(--surface-color);
            font-weight: 600;
            color: var(--text-primary);
        }
        
        tr:hover {
            background: var(--surface-color);
        }
        
        img {
            max-width: 100%;
            height: auto;
            border-radius: 8px;
            box-shadow: var(--shadow);
            margin: 1rem 0;
        }
        
        .chart-container {
            background: white;
            border: 1px solid var(--border-color);
            border-radius: 8px;
            padding: 1rem;
            margin: 1rem 0;
            box-shadow: var(--shadow);
        }
        
        .subsection {
            margin-bottom: 2rem;
            padding: 1.5rem;
            background: white;
            border: 1px solid var(--border-color);
            border-radius: 8px;
            box-shadow: var(--shadow);
        }
        
        .subsection h3 {
            color: var(--primary-color);
            margin-top: 0;
            border-bottom: 2px solid var(--border-color);
            padding-bottom: 0.5rem;
        }
        
        .theme-finder-output .subsection-header {
            background: var(--accent-color);
            color: white;
            padding: 1rem;
            cursor: pointer;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-radius: 6px 6px 0 0;
        }
        
        .theme-finder-output .subsection-header:hover {
            background: var(--primary-color);
        }
        
        .theme-finder-output .subsection-content {
            padding: 1.5rem;
            border: 1px solid var(--border-color);
            border-top: none;
            border-radius: 0 0 6px 6px;
            background: white;
        }
        
        .theme-finder-output .subsection-content.closed {
            display: none;
        }
        
        .theme-finder-output .subsection-content.open {
            display: block;
        }
        
        .theme-finder-output .subsection-toggle {
            font-size: 1.2rem;
            transition: transform 0.3s ease;
        }
        
        .theme-finder-output h4 {
            color: var(--primary-color);
            margin-top: 1.5rem;
            margin-bottom: 1rem;
        }
        
        .theme-finder-output h4:first-child {
            margin-top: 0;
        }
        
        .error-message {
            background: #fee;
            border: 1px solid #fcc;
            color: #c33;
            padding: 1rem;
            border-radius: 4px;
            font-style: italic;
        }
        
        @media (max-width: 768px) {
            body {
                padding: 1rem;
            }
            
            h1 {
                font-size: 2rem;
            }
            
            h2 {
                font-size: 1.5rem;
            }
            
            .section-header {
                padding: 1rem;
            }
            
            .section-content {
                padding: 1rem;
            }
            
            .download-links-section {
                padding: 1rem;
            }
            
            .download-links {
                flex-direction: column;
                gap: 0.75rem;
            }
            
            .download-link {
                justify-content: center;
                padding: 0.75rem;
            }
            
            table {
                font-size: 0.9rem;
            }
            
            th, td {
                padding: 0.75rem;
            }
        }
        """ 