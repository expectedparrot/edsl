from typing import List

import nbformat
from nbclient import NotebookClient  # For executing notebooks
import yaml

from edsl import Results, QuestionFreeText, Scenario

from .research import Research

# from reports.quatro import NotebookRenderer # TODO: Re-add when module exists

from collections import UserDict, defaultdict
import os
import uuid
import subprocess
import tempfile
import re
from .warning_utils import print_info, print_success, print_error


class WriteupResult:
    """
    Container for a chart and its written analysis.

    When displayed in Jupyter, shows the chart followed by the analysis text.
    """

    def __init__(
        self, chart, analysis_text, question_names=None, report=None, output_obj=None
    ):
        """
        Initialize a WriteupResult.

        Args:
            chart: The chart/visualization object
            analysis_text: The written analysis text
            question_names: Optional tuple of question names
            report: Optional reference to Report object for question info
            output_obj: Optional output object for pretty name
        """
        self.chart = chart
        self.analysis_text = analysis_text
        self._question_names = question_names
        self._report = report
        self._output_obj = output_obj

    def _get_question_or_comment_field(self, name):
        """Get a question or comment field object by name.

        Args:
            name: Question name or comment field name

        Returns:
            Question object or CommentField object
        """
        from edsl.reports.comment_field import is_comment_field, create_comment_field

        if is_comment_field(name):
            return create_comment_field(name, self._report.results)
        else:
            return self._report.results.survey.get(name)

    def _repr_mimebundle_(self, include=None, exclude=None):
        """
        Return a MIME bundle with multiple representations.

        This allows Jupyter and other platforms to choose the best representation.
        For Altair charts, this includes the Vega-Lite spec.
        """
        bundle = {}

        # Try to get the Vega-Lite spec if this is an Altair chart
        if hasattr(self.chart, "to_dict"):
            try:
                vega_spec = self.chart.to_dict()
                # Determine the schema version
                schema = vega_spec.get("$schema", "")
                if "v5" in schema:
                    mime_type = "application/vnd.vegalite.v5+json"
                elif "v4" in schema:
                    mime_type = "application/vnd.vegalite.v4+json"
                elif "v3" in schema:
                    mime_type = "application/vnd.vegalite.v3+json"
                else:
                    mime_type = "application/vnd.vegalite.v2+json"

                bundle[mime_type] = vega_spec
            except:
                pass

        # Always include HTML as fallback
        bundle["text/html"] = self._repr_html_()

        # Include plain text representation
        bundle["text/plain"] = repr(self)

        return bundle

    def _repr_html_(self):
        """Return HTML representation showing chart and analysis."""
        html_parts = []
        html_parts.append(
            """
        <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">
        """
        )

        # Add question information header if available
        if self._question_names and self._report:
            try:
                questions = [
                    self._get_question_or_comment_field(qname)
                    for qname in self._question_names
                ]

                for i, (qname, question) in enumerate(
                    zip(self._question_names, questions)
                ):
                    html_parts.append(
                        f"""
                    <div style="background-color: #f8f9fa; padding: 15px; border-radius: 5px; margin-bottom: 15px; border-left: 4px solid #007bff;">
                        <h4 style="margin: 0 0 8px 0; color: #495057; font-size: 16px;">
                            {qname} <span style="color: #6c757d; font-weight: normal; font-size: 13px;">({question.question_type})</span>
                        </h4>
                        <p style="margin: 0; color: #212529; font-size: 14px;">{question.question_text}</p>
                    </div>
                    """
                    )

                # Add the output name/title
                if self._output_obj:
                    pretty_name = getattr(self._output_obj, "pretty_name", "Analysis")
                    html_parts.append(
                        f"""
                        <div style="margin-bottom: 10px;">
                            <h4 style="color: #007bff; margin: 0; font-size: 15px;">{pretty_name}</h4>
                        </div>
                    """
                    )
            except Exception as e:
                # If we can't get question info, show error in output for debugging
                html_parts.append(
                    f"""
                    <div style="background-color: #fff3cd; padding: 10px; border-radius: 5px; margin-bottom: 15px; border-left: 4px solid #ffc107;">
                        <p style="margin: 0; color: #856404; font-size: 13px;">
                            <strong>Debug:</strong> Could not load question information: {str(e)}
                        </p>
                    </div>
                """
                )

        # Get chart HTML
        if hasattr(self.chart, "to_html"):
            # Generate unique ID to prevent div collisions in Jupyter notebooks
            unique_id = f"vis_{uuid.uuid4().hex[:12]}"
            chart_html = self.chart.to_html()
            # Replace all occurrences of 'vis' with our unique ID in both HTML and JavaScript
            chart_html = chart_html.replace('id="vis"', f'id="{unique_id}"')
            chart_html = chart_html.replace('"#vis"', f'"#{unique_id}"')
            chart_html = chart_html.replace("'#vis'", f"'#{unique_id}'")
            html_parts.append(chart_html)
        elif hasattr(self.chart, "_repr_html_"):
            html_parts.append(self.chart._repr_html_())
        else:
            html_parts.append(f"<div>{str(self.chart)}</div>")

        # Format analysis text as markdown-style HTML
        html_parts.append(
            f"""
        <div style="margin-top: 20px; padding: 20px; background-color: #f8f9fa; border-left: 4px solid #007bff; border-radius: 4px;">
            <h3 style="margin-top: 0; color: #007bff; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">
                Analysis
            </h3>
            <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 14px; line-height: 1.6; color: #212529;">
                {self._format_as_markdown_html(self.analysis_text)}
            </div>
        </div>
        </div>
        """
        )

        return "".join(html_parts)

    def _format_as_markdown_html(self, text):
        """Convert simple markdown-like formatting to HTML."""
        # Replace newlines with <br> for paragraphs
        paragraphs = text.strip().split("\n\n")
        formatted_paragraphs = []

        for para in paragraphs:
            # Replace single newlines with spaces within paragraphs
            para = para.replace("\n", " ")
            # Wrap in paragraph tags
            formatted_paragraphs.append(f"<p>{para}</p>")

        return "".join(formatted_paragraphs)

    def _ipython_display_(self):
        """
        IPython display hook for Jupyter notebooks.
        This method is called automatically by IPython/Jupyter when displaying the object.
        Forces the use of rich HTML/Vega-Lite representation instead of plain text __repr__.
        """
        from edsl.utilities.is_notebook import is_notebook

        if is_notebook():
            try:
                from IPython.display import display, HTML

                # Force display using the HTML representation
                display(HTML(self._repr_html_()))
            except ImportError:
                # Fallback if IPython is somehow not available
                print(repr(self))
        else:
            print(repr(self))

    def __repr__(self):
        """Return string representation."""
        return f"WriteupResult(chart={type(self.chart).__name__}, analysis_length={len(self.analysis_text)})"

    def __str__(self):
        """Return the analysis text."""
        return self.analysis_text


class OutputWrapper:
    """
    Wrapper for an analysis output that provides convenient access to the chart,
    saving functionality, and writeup generation.

    Example:
        output = analysis.bar_chart
        output  # Shows the chart in Jupyter
        output.save('chart.png')
        output.writeup()  # Get LLM-generated analysis
    """

    def __init__(self, output_obj, question_names, output_name, report):
        """
        Initialize an OutputWrapper.

        Args:
            output_obj: The underlying output object
            question_names: Tuple of question names
            output_name: Name of this output type
            report: Reference to the parent Report object
        """
        self._output_obj = output_obj
        self._question_names = question_names
        self._output_name = output_name
        self._report = report
        self._chart = None

    def _get_question_or_comment_field(self, name):
        """Get a question or comment field object by name.

        Args:
            name: Question name or comment field name

        Returns:
            Question object or CommentField object
        """
        from edsl.reports.comment_field import is_comment_field, create_comment_field

        if is_comment_field(name):
            return create_comment_field(name, self._report.results)
        else:
            return self._report.results.survey.get(name)

    @property
    def chart(self):
        """Get the chart/output, caching it."""
        if self._chart is None:
            self._chart = self._output_obj.output()
        return self._chart

    def _ipython_display_(self):
        """
        IPython display hook for Jupyter notebooks.
        This method is called automatically by IPython/Jupyter when displaying the object.
        Forces the use of rich HTML/Vega-Lite representation instead of plain text __repr__.
        """
        from edsl.utilities.is_notebook import is_notebook

        if is_notebook():
            try:
                from IPython.display import display, HTML

                # Display the full HTML which includes header and chart
                # This ensures both the question info and chart render properly
                display(HTML(self._repr_html_()))
            except ImportError:
                # Fallback if IPython is somehow not available
                print(repr(self))
        else:
            print(repr(self))

    def _repr_html_(self):
        """Return HTML representation for Jupyter display."""
        # Get question information
        questions = [
            self._get_question_or_comment_field(qname) for qname in self._question_names
        ]

        # Build header with question information
        html_parts = []
        html_parts.append(
            """
        <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">
        """
        )

        # Question details section
        for i, (qname, question) in enumerate(zip(self._question_names, questions)):
            html_parts.append(
                f"""
            <div style="background-color: #f8f9fa; padding: 15px; border-radius: 5px; margin-bottom: 15px; border-left: 4px solid #007bff;">
                <h4 style="margin: 0 0 8px 0; color: #495057; font-size: 16px;">
                    {qname} <span style="color: #6c757d; font-weight: normal; font-size: 13px;">({question.question_type})</span>
                </h4>
                <p style="margin: 0; color: #212529; font-size: 14px;">{question.question_text}</p>
            </div>
            """
            )

        # Add the output name/title
        pretty_name = getattr(self._output_obj, "pretty_name", self._output_name)
        html_parts.append(
            f"""
            <div style="margin-bottom: 10px;">
                <h4 style="color: #007bff; margin: 0; font-size: 15px;">{pretty_name}</h4>
            </div>
        """
        )

        # Get the chart HTML
        chart = self.chart
        chart_html = ""

        if hasattr(chart, "to_html"):
            # Generate unique ID to prevent div collisions in Jupyter notebooks
            unique_id = f"vis_{uuid.uuid4().hex[:12]}"
            chart_html = chart.to_html()
            # Replace all occurrences of 'vis' with our unique ID in both HTML and JavaScript
            chart_html = chart_html.replace('id="vis"', f'id="{unique_id}"')
            chart_html = chart_html.replace('"#vis"', f'"#{unique_id}"')
            chart_html = chart_html.replace("'#vis'", f"'#{unique_id}'")
        elif hasattr(chart, "_repr_html_"):
            chart_html = chart._repr_html_()
        else:
            # Fallback for other types (like pandas DataFrames)
            chart_html = f"<div>{str(chart)}</div>"

        html_parts.append(chart_html)
        html_parts.append("</div>")

        return "".join(html_parts)

    def _ipython_display_(self):
        """
        IPython display hook for Jupyter notebooks.
        This method is called automatically by IPython/Jupyter when displaying the object.
        Forces the use of rich HTML/Vega-Lite representation instead of plain text __repr__.
        """
        from edsl.utilities.is_notebook import is_notebook

        if is_notebook():
            try:
                from IPython.display import display, HTML

                # Get question information
                questions = [
                    self._get_question_or_comment_field(qname)
                    for qname in self._question_names
                ]

                # Build header HTML
                html_parts = []
                html_parts.append(
                    "<div style=\"font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;\">"
                )

                # Question details section
                for i, (qname, question) in enumerate(
                    zip(self._question_names, questions)
                ):
                    html_parts.append(
                        f"""
                    <div style="background-color: #f8f9fa; padding: 15px; border-radius: 5px; margin-bottom: 15px; border-left: 4px solid #007bff;">
                        <h4 style="margin: 0 0 8px 0; color: #495057; font-size: 16px;">
                            {qname} <span style="color: #6c757d; font-weight: normal; font-size: 13px;">({question.question_type})</span>
                        </h4>
                        <p style="margin: 0; color: #212529; font-size: 14px;">{question.question_text}</p>
                    </div>
                    """
                    )

                # Add the output name/title
                pretty_name = getattr(
                    self._output_obj, "pretty_name", self._output_name
                )
                html_parts.append(
                    f"""
                    <div style="margin-bottom: 10px;">
                        <h4 style="color: #007bff; margin: 0; font-size: 15px;">{pretty_name}</h4>
                    </div>
                    """
                )
                html_parts.append("</div>")

                # Display the header
                display(HTML("".join(html_parts)))

                # Display the chart separately so it renders properly
                chart = self.chart
                display(chart)

            except ImportError:
                # Fallback if IPython is somehow not available
                print(repr(self))
        else:
            print(repr(self))

    def __repr__(self):
        """Return string representation."""
        pretty_name = getattr(self._output_obj, "pretty_name", self._output_name)
        return f"OutputWrapper({pretty_name} for {self._question_names})"

    def save(self, filename, **kwargs):
        """
        Save the chart/output to a file.

        Args:
            filename: Path to save the file
            **kwargs: Additional arguments passed to the save method

        Example:
            output.save('chart.png')
            output.save('chart.svg', scale_factor=2.0)
        """
        chart = self.chart

        # Handle Altair charts
        if hasattr(chart, "save"):
            chart.save(filename, **kwargs)
        # Handle pandas DataFrames
        elif hasattr(chart, "to_csv") and filename.endswith(".csv"):
            chart.to_csv(filename, **kwargs)
        elif hasattr(chart, "to_html") and filename.endswith(".html"):
            with open(filename, "w") as f:
                f.write(chart.to_html(**kwargs))
        else:
            raise ValueError(f"Don't know how to save {type(chart)} to {filename}")

        print_success(f"Saved to {filename}")

    def writeup(self):
        """
        Generate a written analysis of this specific chart/output.

        This always generates a fresh LLM-based analysis of the chart that was created.
        Returns a WriteupResult that displays both the chart and analysis in Jupyter.

        Returns:
            WriteupResult object that displays chart + analysis, or just the analysis text

        Example:
            chart = analysis.bar_chart
            result = chart.writeup()  # Displays chart + analysis in Jupyter
            print(result)  # Prints just the analysis text
            print(result.analysis_text)  # Access the text directly
        """
        analysis_text = self._generate_writeup()
        return WriteupResult(
            self.chart,
            analysis_text,
            question_names=self._question_names,
            report=self._report,
            output_obj=self._output_obj,
        )

    def _generate_writeup(self):
        """
        Generate a fresh LLM-based analysis of this chart.

        Returns:
            String containing the written analysis
        """
        from edsl import QuestionFreeText, Scenario
        import tempfile
        import os

        # Get the chart
        chart = self.chart

        # Get question information
        questions = [
            self._report.results.survey.get(qname) for qname in self._question_names
        ]
        question_texts = [q.question_text for q in questions]
        question_types = [q.question_type for q in questions]

        # Get the narrative from the output object
        narrative = getattr(
            self._output_obj, "narrative", f"Analysis of {self._output_name}"
        )

        # Save chart as PNG for LLM to analyze
        try:
            temp_file = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
            temp_path = temp_file.name
            temp_file.close()

            # Save the chart
            if hasattr(chart, "save"):
                chart.save(temp_path, scale_factor=2.0)
            else:
                # If it's not a chart (e.g., a table), just use the narrative
                return f"Analysis of {self._output_name}: {narrative}"

            from edsl import FileStore

            file_store = FileStore(temp_path)

            # Create the analysis question
            q_analysis = QuestionFreeText(
                question_name="written_analysis",
                question_text="""
                A survey was conducted and the following question(s) were asked:
                <questions>
                {{ scenario.question_texts }}
                </questions>

                The results have been analyzed and this is the visualization of the results:
                <chart>
                {{ scenario.chart }}
                </chart>
                
                <context>
                {{ scenario.narrative }}
                </context>
                
                Please write a short, 1 paragraph analysis of the results as plain text.
                Focus on the key patterns, trends, and insights visible in the visualization.
                """,
            )

            scenario = Scenario(
                {
                    "question_texts": question_texts,
                    "question_types": question_types,
                    "narrative": narrative,
                    "chart": file_store,
                }
            )

            results = q_analysis.by(scenario).run(stop_on_exception=True, verbose=False)
            analysis_text = results[0]["answer"]["written_analysis"]

            # Clean up temp file
            try:
                os.unlink(temp_path)
            except:
                pass

            return analysis_text

        except Exception as e:
            return f"Error generating writeup: {str(e)}\n\nNarrative: {narrative}"

    def show(self):
        """Display the chart (useful in scripts, automatically done in Jupyter)."""
        chart = self.chart
        if hasattr(chart, "show"):
            chart.show()
        else:
            from IPython.display import display

            display(chart)

    def terminal_chart(self):
        """
        Generate and display a terminal-based visualization using termplotlib.

        This method creates ASCII-based visualizations suitable for display in a terminal,
        which is useful for scripts, SSH sessions, or environments without graphical display.

        Returns:
            str: The terminal visualization as a string (also prints it)

        Example:
            >>> from edsl import Results
            >>> results = Results.example()
            >>> analysis = results.analyze('how_feeling')
            >>> analysis.bar_chart_output.terminal_chart()

        Note:
            Requires termplotlib to be installed: pip install termplotlib
        """
        try:
            import termplotlib as tpl
            from collections import Counter
            import numpy as np
        except ImportError:
            error_msg = (
                "termplotlib is required for terminal charts.\n"
                "Install it with: pip install termplotlib"
            )
            print(error_msg)
            return error_msg

        # Get question information
        questions = [
            self._report.results.survey.get(qname) for qname in self._question_names
        ]

        # Print header
        output_lines = []
        output_lines.append("=" * 70)
        for qname, question in zip(self._question_names, questions):
            output_lines.append(f"Question: {question.question_text}")
            output_lines.append(f"Type: {question.question_type}")
            output_lines.append(f"Name: {qname}")

        pretty_name = getattr(self._output_obj, "pretty_name", self._output_name)
        output_lines.append(f"\nVisualization: {pretty_name}")
        output_lines.append("=" * 70)
        output_lines.append("")

        # Get the answers for this question
        results = self._report.results

        # Handle single vs multiple questions
        if len(self._question_names) == 1:
            question_name = self._question_names[0]
            question = questions[0]
            question_type = question.question_type

            # Get answers
            answers = results.get_answers(question_name)
            # Filter out None values
            valid_answers = [a for a in answers if a is not None]

            if not valid_answers:
                msg = "No valid responses to visualize"
                output_lines.append(msg)
                result = "\n".join(output_lines)
                print(result)
                return result

            # Generate appropriate visualization based on question type
            if question_type in [
                "multiple_choice",
                "yes_no",
                "linear_scale",
                "likert_five",
            ]:
                # Bar chart for categorical/scale data
                counts = Counter(valid_answers)

                # Get options from question if available
                if hasattr(question, "question_options"):
                    options = question.question_options
                    labels = [str(opt) for opt in options]
                    values = [counts.get(opt, 0) for opt in options]
                else:
                    sorted_items = counts.most_common()
                    labels = [str(item[0]) for item in sorted_items]
                    values = [item[1] for item in sorted_items]

                # Add summary statistics
                total = len(valid_answers)
                output_lines.append(f"Total responses: {total}")
                output_lines.append("")

                # Create bar chart
                fig = tpl.figure()
                fig.barh(values, labels, force_ascii=False)

                # Capture output
                import io
                import sys

                old_stdout = sys.stdout
                sys.stdout = buffer = io.StringIO()
                fig.show()
                viz_output = buffer.getvalue()
                sys.stdout = old_stdout

                output_lines.append(viz_output)

            elif question_type in ["numerical"]:
                # Histogram for numerical data
                values = np.array(valid_answers, dtype=float)

                output_lines.append(f"Total responses: {len(values)}")
                output_lines.append(f"Mean: {np.mean(values):.2f}")
                output_lines.append(f"Median: {np.median(values):.2f}")
                output_lines.append(f"Std Dev: {np.std(values):.2f}")
                output_lines.append(
                    f"Min: {np.min(values):.2f}, Max: {np.max(values):.2f}"
                )
                output_lines.append("")

                counts, bin_edges = np.histogram(values)
                fig = tpl.figure()
                fig.hist(counts, bin_edges, orientation="horizontal", force_ascii=False)

                import io
                import sys

                old_stdout = sys.stdout
                sys.stdout = buffer = io.StringIO()
                fig.show()
                viz_output = buffer.getvalue()
                sys.stdout = old_stdout

                output_lines.append(viz_output)

            elif question_type in ["checkbox"]:
                # Bar chart for checkbox (multiple selections)
                all_selections = []
                for answer in valid_answers:
                    if isinstance(answer, list):
                        all_selections.extend(answer)
                    else:
                        all_selections.append(answer)

                counts = Counter(all_selections)
                sorted_items = counts.most_common()

                output_lines.append(f"Total respondents: {len(valid_answers)}")
                output_lines.append(f"Total selections: {len(all_selections)}")
                output_lines.append(
                    f"Avg selections per respondent: {len(all_selections)/len(valid_answers):.1f}"
                )
                output_lines.append("")

                labels = [str(item[0]) for item in sorted_items]
                values = [item[1] for item in sorted_items]

                fig = tpl.figure()
                fig.barh(values, labels, force_ascii=False)

                import io
                import sys

                old_stdout = sys.stdout
                sys.stdout = buffer = io.StringIO()
                fig.show()
                viz_output = buffer.getvalue()
                sys.stdout = old_stdout

                output_lines.append(viz_output)

            elif question_type in ["free_text"]:
                # Text length distribution
                lengths = np.array([len(str(answer)) for answer in valid_answers])

                output_lines.append(f"Total responses: {len(valid_answers)}")
                output_lines.append(f"Avg characters: {np.mean(lengths):.1f}")
                output_lines.append(
                    f"Shortest: {np.min(lengths)}, Longest: {np.max(lengths)}"
                )
                output_lines.append("")
                output_lines.append("Response Length Distribution:")
                output_lines.append("")

                counts, bin_edges = np.histogram(lengths)
                fig = tpl.figure()
                fig.hist(counts, bin_edges, orientation="horizontal", force_ascii=False)

                import io
                import sys

                old_stdout = sys.stdout
                sys.stdout = buffer = io.StringIO()
                fig.show()
                viz_output = buffer.getvalue()
                sys.stdout = old_stdout

                output_lines.append(viz_output)

            else:
                # Default: frequency bar chart
                counts = Counter(valid_answers)
                sorted_items = counts.most_common(10)  # Top 10

                output_lines.append(f"Total responses: {len(valid_answers)}")
                output_lines.append(f"Unique values: {len(counts)}")
                output_lines.append(f"Showing top {min(10, len(counts))} values")
                output_lines.append("")

                labels = [str(item[0])[:30] for item in sorted_items]  # Truncate labels
                values = [item[1] for item in sorted_items]

                fig = tpl.figure()
                fig.barh(values, labels, force_ascii=False)

                import io
                import sys

                old_stdout = sys.stdout
                sys.stdout = buffer = io.StringIO()
                fig.show()
                viz_output = buffer.getvalue()
                sys.stdout = old_stdout

                output_lines.append(viz_output)

        else:
            # Multiple questions - show a note
            output_lines.append(
                "Multi-question terminal visualizations not yet supported."
            )
            output_lines.append(f"Questions: {', '.join(self._question_names)}")
            output_lines.append("\nFor now, analyze each question individually:")
            for qname in self._question_names:
                output_lines.append(
                    f"  results.analyze('{qname}').bar_chart_output.terminal_chart()"
                )

        output_lines.append("")
        output_lines.append("=" * 70)

        result = "\n".join(output_lines)
        print(result)
        return result


class QuestionAnalysis:
    """
    A convenience wrapper for accessing analysis outputs for a specific question or question combination.

    Provides dot notation access to outputs using snake_case names.

    Example:
        analysis = report.analyze('gender')
        analysis.bar_chart  # Returns the bar chart
        analysis.frequency_table  # Returns the frequency table

        # For interactions
        analysis = report.analyze('gender', 'employment')
        analysis.heatmap
        analysis.cross_tabulation
    """

    def __init__(self, question_names, outputs_dict, report):
        """
        Initialize a QuestionAnalysis wrapper.

        Args:
            question_names: Tuple of question names
            outputs_dict: Dictionary of output_name -> output_object
            report: Reference to the parent Report object
        """
        self._question_names = question_names
        self._outputs = outputs_dict
        self._report = report
        self._name_mapping = {}  # Maps snake_case to original output_name

        # Create snake_case mappings for all outputs
        for output_name in outputs_dict.keys():
            snake_name = self._camel_to_snake(output_name)
            self._name_mapping[snake_name] = output_name

    def _get_question_or_comment_field(self, name):
        """Get a question or comment field object by name.

        Args:
            name: Question name or comment field name

        Returns:
            Question object or CommentField object
        """
        from .comment_field import is_comment_field, create_comment_field

        if is_comment_field(name):
            return create_comment_field(name, self._report.results)
        else:
            return self._report.results.survey.get(name)

    @staticmethod
    def _camel_to_snake(name):
        """Convert CamelCase or camelCase to snake_case."""
        # Insert underscore before uppercase letters that follow lowercase letters
        s1 = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", name)
        # Insert underscore before uppercase letters that follow lowercase or uppercase letters
        s2 = re.sub("([a-z0-9])([A-Z])", r"\1_\2", s1)
        return s2.lower()

    def __getattr__(self, name):
        """
        Get an output using dot notation with snake_case names.

        Supports shortened names if they uniquely identify an output.
        For example, if 'cross_tabulation' is the only output starting with 'c',
        then analysis.c will work.

        Args:
            name: Snake case name or prefix of the output (e.g., 'bar_chart', 'b', 'bar')

        Returns:
            OutputWrapper object with the chart, save(), and writeup() methods
        """
        # Check if this is an exact match
        if name in self._name_mapping:
            output_name = self._name_mapping[name]
            output_obj = self._outputs[output_name]
            return OutputWrapper(
                output_obj, self._question_names, output_name, self._report
            )

        # Check for prefix matches
        matches = [key for key in self._name_mapping.keys() if key.startswith(name)]

        if len(matches) == 1:
            # Unique prefix match found
            output_name = self._name_mapping[matches[0]]
            output_obj = self._outputs[output_name]
            return OutputWrapper(
                output_obj, self._question_names, output_name, self._report
            )
        elif len(matches) > 1:
            # Ambiguous prefix
            raise AttributeError(
                f"Ambiguous output name '{name}'. Could be: {', '.join(matches)}. "
                f"Please be more specific."
            )

        # If not found, provide helpful error
        available = ", ".join(sorted(self._name_mapping.keys()))
        raise AttributeError(
            f"'{self.__class__.__name__}' has no output matching '{name}'. "
            f"Available outputs: {available}"
        )

    def __dir__(self):
        """Return list of available attributes for tab completion."""
        # Include both the mapped names and standard object attributes
        standard_attrs = ["list_outputs", "question_names", "outputs"]
        return list(self._name_mapping.keys()) + standard_attrs

    @property
    def question_names(self):
        """Return the question names for this analysis."""
        return self._question_names

    @property
    def outputs(self):
        """Return the raw outputs dictionary."""
        return self._outputs

    def list_outputs(self):
        """List all available outputs with their names."""
        print(f"Available outputs for {self._question_names}:")
        for snake_name, output_name in sorted(self._name_mapping.items()):
            output_obj = self._outputs[output_name]
            pretty_name = getattr(output_obj, "pretty_name", output_name)
            print(f"  .{snake_name:<30} ({pretty_name})")

    def __repr__(self):
        """Return a rich-formatted string representation with question details, statistics, and terminal plot."""
        try:
            from rich.console import Console
            from rich.table import Table
            from rich import box
            from collections import Counter
            import numpy as np
            import io

            console = Console(file=io.StringIO(), force_terminal=True, width=100)

            # Get question information
            questions = [
                self._get_question_or_comment_field(qname)
                for qname in self._question_names
            ]

            # Question Details Section (compact)
            for i, (qname, question) in enumerate(zip(self._question_names, questions)):
                # Question info table
                q_table = Table(
                    show_header=False,
                    box=box.SIMPLE,
                    border_style="blue",
                    padding=(0, 1),
                    collapse_padding=True,
                )
                q_table.add_column("Field", style="cyan bold", width=15)
                q_table.add_column("Value", style="white")

                q_table.add_row("Question", f"[bold yellow]{qname}[/bold yellow]")
                q_table.add_row("Type", f"[green]{question.question_type}[/green]")
                q_table.add_row("Text", question.question_text)

                # Add options if available
                if hasattr(question, "question_options") and question.question_options:
                    options_str = ", ".join(
                        [str(opt) for opt in question.question_options[:10]]
                    )
                    if len(question.question_options) > 10:
                        options_str += f" ... ({len(question.question_options)} total)"
                    q_table.add_row("Options", options_str)

                console.print(q_table)

            # Answer Statistics Section (only for single questions)
            if len(self._question_names) == 1:
                question_name = self._question_names[0]
                question = questions[0]
                # Get answers using the correct column (answer.* or comment.*)
                from .comment_field import get_data_column_name

                column_name = get_data_column_name(question)
                answers = self._report.results.select(column_name).to_list()
                valid_answers = [a for a in answers if a is not None]

                if valid_answers:
                    # Statistics table (compact)
                    stats_table = Table(
                        title="[bold cyan]Statistics[/bold cyan]",
                        box=box.SIMPLE,
                        border_style="cyan",
                        padding=(0, 1),
                        collapse_padding=True,
                    )
                    stats_table.add_column("Metric", style="cyan", width=22)
                    stats_table.add_column("Value", style="yellow", width=28)

                    stats_table.add_row("Total Responses", str(len(answers)))
                    stats_table.add_row("Valid Responses", str(len(valid_answers)))

                    if len(answers) > len(valid_answers):
                        stats_table.add_row(
                            "Missing/None", str(len(answers) - len(valid_answers))
                        )

                    # Type-specific statistics
                    question_type = question.question_type

                    if question_type in ["numerical"]:
                        values = np.array(valid_answers, dtype=float)
                        stats_table.add_row("Mean", f"{np.mean(values):.2f}")
                        stats_table.add_row("Median", f"{np.median(values):.2f}")
                        stats_table.add_row("Std Dev", f"{np.std(values):.2f}")
                        stats_table.add_row(
                            "Range", f"{np.min(values):.2f} - {np.max(values):.2f}"
                        )

                    elif question_type in [
                        "multiple_choice",
                        "yes_no",
                        "linear_scale",
                        "likert_five",
                    ]:
                        counts = Counter(valid_answers)
                        stats_table.add_row("Unique Values", str(len(counts)))
                        most_common = counts.most_common(1)[0]
                        stats_table.add_row(
                            "Most Common", f"{most_common[0]} ({most_common[1]} times)"
                        )

                    elif question_type in ["checkbox"]:
                        all_selections = []
                        for answer in valid_answers:
                            if isinstance(answer, list):
                                all_selections.extend(answer)
                        stats_table.add_row(
                            "Total Selections", str(len(all_selections))
                        )
                        stats_table.add_row(
                            "Avg per Respondent",
                            f"{len(all_selections)/len(valid_answers):.1f}",
                        )

                    elif question_type in ["free_text"]:
                        lengths = [len(str(a)) for a in valid_answers]
                        stats_table.add_row(
                            "Avg Length", f"{np.mean(lengths):.1f} chars"
                        )
                        stats_table.add_row(
                            "Length Range", f"{min(lengths)} - {max(lengths)} chars"
                        )

                    console.print(stats_table)

                    # Terminal Plot Section
                    try:
                        import termplotlib as tpl

                        console.print("[bold cyan]Distribution[/bold cyan]")

                        # Generate appropriate plot based on question type
                        if question_type in [
                            "multiple_choice",
                            "yes_no",
                            "linear_scale",
                            "likert_five",
                        ]:
                            counts = Counter(valid_answers)

                            # Get options from question if available
                            if hasattr(question, "question_options"):
                                options = question.question_options
                                labels = [str(opt) for opt in options]
                                values = [counts.get(opt, 0) for opt in options]
                            else:
                                sorted_items = counts.most_common()
                                labels = [str(item[0]) for item in sorted_items]
                                values = [item[1] for item in sorted_items]

                            fig = tpl.figure()
                            fig.barh(values, labels, force_ascii=False)

                            # Capture plot output
                            old_stdout = console.file
                            plot_buffer = io.StringIO()
                            import sys

                            sys.stdout = plot_buffer
                            fig.show()
                            plot_output = plot_buffer.getvalue()
                            sys.stdout = old_stdout

                            console.print(plot_output)

                        elif question_type in ["numerical"]:
                            values = np.array(valid_answers, dtype=float)
                            counts, bin_edges = np.histogram(values)

                            fig = tpl.figure()
                            fig.hist(
                                counts,
                                bin_edges,
                                orientation="horizontal",
                                force_ascii=False,
                            )

                            old_stdout = console.file
                            plot_buffer = io.StringIO()
                            import sys

                            sys.stdout = plot_buffer
                            fig.show()
                            plot_output = plot_buffer.getvalue()
                            sys.stdout = old_stdout

                            console.print(plot_output)

                    except ImportError:
                        console.print(
                            "[dim italic]Install termplotlib for visualizations: pip install termplotlib[/dim italic]"
                        )

            else:
                # Multi-question analysis
                console.print("[yellow]Multi-question analysis[/yellow]")
                console.print(
                    f"Analyzing {len(self._question_names)} questions together"
                )

            # Available Outputs Section (compact)
            outputs_table = Table(
                title="[bold cyan]Available Methods[/bold cyan]",
                box=box.SIMPLE,
                border_style="cyan",
                padding=(0, 1),
                collapse_padding=True,
            )
            outputs_table.add_column("Method/Attribute", style="green", width=35)
            outputs_table.add_column("Description", style="white", width=55)

            # Add output methods
            for snake_name, output_name in sorted(self._name_mapping.items()):
                output_obj = self._outputs[output_name]
                pretty_name = getattr(output_obj, "pretty_name", output_name)
                outputs_table.add_row(f".{snake_name}", pretty_name)

            # Add utility methods
            outputs_table.add_section()
            outputs_table.add_row(".list_outputs()", "List all available outputs")
            outputs_table.add_row(".question_names", "Get question names tuple")
            outputs_table.add_row(".outputs", "Access raw outputs dictionary")

            # Add terminal_chart method if single question
            if len(self._question_names) == 1:
                outputs_table.add_section()
                outputs_table.add_row(
                    ".bar_chart_output.terminal_chart()",
                    "Show full terminal visualization",
                )

            console.print(outputs_table)

            return console.file.getvalue()

        except Exception as e:
            # Fallback to simple repr if rich formatting fails
            return f"QuestionAnalysis({self._question_names}) with {len(self._outputs)} outputs\n(Error in rich formatting: {e})"

    def _repr_html_(self):
        """Return an HTML representation of the QuestionAnalysis."""
        # Get question information
        questions = [
            self._get_question_or_comment_field(qname) for qname in self._question_names
        ]

        # Build HTML
        html_parts = []

        # Header
        html_parts.append(
            """
        <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 900px;">
            <h3 style="color: #007bff; margin-bottom: 20px;">Question Analysis</h3>
        """
        )

        # Question details section
        for i, (qname, question) in enumerate(zip(self._question_names, questions)):
            html_parts.append(
                f"""
            <div style="background-color: #f8f9fa; padding: 15px; border-radius: 5px; margin-bottom: 20px; border-left: 4px solid #007bff;">
                <h4 style="margin-top: 0; color: #495057;">
                    Question {i+1 if len(questions) > 1 else ''}: {qname}
                </h4>
                <p style="margin: 10px 0;"><strong>Type:</strong> {question.question_type}</p>
                <p style="margin: 10px 0;"><strong>Text:</strong> {question.question_text}</p>
            </div>
            """
            )

        # Get responses for display
        html_parts.append(
            """
            <div style="margin-bottom: 20px;">
                <h4 style="color: #495057;">Sample Responses</h4>
        """
        )

        for qname, question in zip(self._question_names, questions):
            # Get responses using the correct column (answer.* or comment.*)
            from .comment_field import get_data_column_name

            column_name = get_data_column_name(question)
            responses = self._report.results.select(column_name).to_list()

            # Get first 5 and last 5
            total = len(responses)
            if total <= 10:
                sample = responses
                show_ellipsis = False
            else:
                sample = responses[:5] + responses[-5:]
                show_ellipsis = True

            html_parts.append(
                f"""
                <table style="border-collapse: collapse; width: 100%; margin-bottom: 15px; font-size: 13px;">
                    <thead>
                        <tr style="background-color: #e9ecef;">
                            <th style="padding: 8px; text-align: left; border: 1px solid #dee2e6; width: 60px;">#</th>
                            <th style="padding: 8px; text-align: left; border: 1px solid #dee2e6;">Response{' for ' + qname if len(self._question_names) > 1 else ''}</th>
                        </tr>
                    </thead>
                    <tbody>
            """
            )

            # First 5 responses
            for idx, resp in enumerate(sample[:5]):
                resp_str = str(resp) if resp is not None else "<em>None</em>"
                # Truncate long responses
                if len(resp_str) > 100:
                    resp_str = resp_str[:100] + "..."
                html_parts.append(
                    f"""
                        <tr>
                            <td style="padding: 8px; border: 1px solid #dee2e6; color: #6c757d;">{idx + 1}</td>
                            <td style="padding: 8px; border: 1px solid #dee2e6;">{resp_str}</td>
                        </tr>
                """
                )

            # Ellipsis row if needed
            if show_ellipsis:
                html_parts.append(
                    f"""
                        <tr>
                            <td style="padding: 8px; border: 1px solid #dee2e6; text-align: center; color: #6c757d;" colspan="2">
                                ... ({total - 10} more responses) ...
                            </td>
                        </tr>
                """
                )

                # Last 5 responses
                for idx, resp in enumerate(sample[5:], start=total - 4):
                    resp_str = str(resp) if resp is not None else "<em>None</em>"
                    if len(resp_str) > 100:
                        resp_str = resp_str[:100] + "..."
                    html_parts.append(
                        f"""
                        <tr>
                            <td style="padding: 8px; border: 1px solid #dee2e6; color: #6c757d;">{idx}</td>
                            <td style="padding: 8px; border: 1px solid #dee2e6;">{resp_str}</td>
                        </tr>
                    """
                    )

            html_parts.append(
                """
                    </tbody>
                </table>
            """
            )

        html_parts.append(
            f"""
                <p style="color: #6c757d; font-size: 12px; margin-top: 5px;">
                    Total responses: {total}
                </p>
            </div>
        """
        )

        # Available outputs section
        html_parts.append(
            """
            <div style="margin-top: 20px;">
                <h4 style="color: #495057;">Available Outputs</h4>
                <p style="color: #6c757d; font-size: 13px; margin-bottom: 10px;">
                    Access outputs using dot notation with snake_case names:
                </p>
                <ul style="list-style: none; padding: 0; margin: 0;">
        """
        )

        for snake_name, output_name in sorted(self._name_mapping.items()):
            output_obj = self._outputs[output_name]
            pretty_name = getattr(output_obj, "pretty_name", output_name)
            html_parts.append(
                f"""
                    <li style="padding: 8px; margin: 5px 0; background-color: #f8f9fa; border-radius: 3px; font-family: monospace;">
                        <span style="color: #007bff; font-weight: bold;">.{snake_name}</span>
                        <span style="color: #6c757d; margin-left: 10px;">→ {pretty_name}</span>
                    </li>
            """
            )

        html_parts.append(
            """
                </ul>
            </div>
        </div>
        """
        )

        return "".join(html_parts)


class Report(UserDict):
    def __init__(
        self,
        results: Results,
        *,
        include_questions: List[str] | None = None,
        exclude_questions: List[str] | None = None,
        exclude_question_types: List[str] | None = None,
        include_interactions: List[List[str]] | None = None,
        exclude_interactions: List[List[str]] | None = None,
        analyses: List[List[str]] | None = None,
        analysis_output_filters: dict[tuple[str, ...], List[str]] | None = None,
        analysis_writeup_filters: dict[tuple[str, ...], bool] | None = None,
        question_header_max_length: int = 80,
        lorem_ipsum: bool = False,
        include_questions_table: bool = True,
        include_respondents_section: bool = True,
        include_scenario_section: bool = True,
        include_overview: bool = True,
        free_text_sample_config: dict[str, int] | None = None,
    ):
        """Create a Report.

        Args:
            results (Results): The EDSL Results object upon which this report is built.
            include_questions (List[str] | None, optional): Explicit list of question names
                to include in the analysis. If *None* (default) all questions from the
                survey are considered.  All names provided must match the question names
                contained in *results.survey.questions*.
            exclude_questions (List[str] | None, optional): List of question names to
                exclude from the analysis.  Applied after *include_questions* filtering.
                All names provided must also exist in the survey.  Defaults to *None*.
            exclude_question_types (List[str] | None, optional): List of question types to
                exclude from the analysis. Supported types: 'free_text', 'multiple_choice',
                'linear_scale', 'checkbox', 'numerical'. Applied after question name filtering.
                Defaults to *None*.
            include_interactions (List[List[str]] | None, optional): Explicit list of 2-way
                interactions (question pairs) to include in the analysis. Each element should
                be a list of exactly 2 question names. If *None* (default), all possible
                2-way interactions are considered based on filtered questions.
            exclude_interactions (List[List[str]] | None, optional): List of 2-way interactions
                to exclude from the analysis. Applied after *include_interactions* filtering.
                Each element should be a list of exactly 2 question names. Defaults to *None*.
            analyses (List[List[str]] | None, optional): List of pre-defined analyses to use.
                If *None* (default), analyses are generated based on the filtered questions.
            analysis_output_filters (dict[tuple[str, ...], List[str]] | None, optional): Filters for allowed output types for each analysis.
            analysis_writeup_filters (dict[tuple[str, ...], bool] | None, optional): Control writeup generation for each analysis.
            question_header_max_length (int, optional): Maximum length for question text in headers. Defaults to 80.
            lorem_ipsum (bool, optional): Use lorem ipsum text instead of LLM-generated analysis writeups. Defaults to False.
            include_questions_table (bool, optional): Include the questions summary table in the report. Defaults to True.
            include_respondents_section (bool, optional): Include the respondents overview section in the report. Defaults to True.
            include_scenario_section (bool, optional): Include the scenario overview section in the report. Defaults to True.
            include_overview (bool, optional): Include the survey overview section in the report. Defaults to True.
            free_text_sample_config (dict[str, int] | None, optional): Configuration for sampling free text questions.
                Keys are question names or '_global' for global setting. Values are sample sizes. Defaults to None.
        """

        self.results = results
        self._analysis_output_filters = {
            tuple(k): v for k, v in (analysis_output_filters or {}).items()
        }
        self._analysis_writeup_filters = {
            tuple(k): v for k, v in (analysis_writeup_filters or {}).items()
        }
        self.question_header_max_length = question_header_max_length
        self.lorem_ipsum = lorem_ipsum
        self.include_questions_table = include_questions_table
        self.include_respondents_section = include_respondents_section
        self.include_scenario_section = include_scenario_section
        self.include_overview = include_overview
        self.free_text_sample_config = free_text_sample_config or {}
        self.exclude_question_types = exclude_question_types or []

        # ---------------------------------------------------------------------
        # Determine which questions to analyse based on include/exclude filters
        # ---------------------------------------------------------------------
        from .comment_field import (
            get_available_comment_fields,
            is_comment_field,
            normalize_comment_field,
        )

        all_question_names: list[str] = [
            q.question_name for q in results.survey.questions
        ]
        all_comment_fields: list[str] = get_available_comment_fields(results)
        all_analyzable_fields: list[str] = all_question_names + all_comment_fields

        # Normalise None to empty list for easier handling later on
        include_questions = (
            list(include_questions)
            if include_questions is not None
            else all_question_names  # By default, only include questions, not comments
        )
        exclude_questions = (
            list(exclude_questions) if exclude_questions is not None else []
        )

        # Normalize comment field names in the include/exclude lists
        include_questions = [
            normalize_comment_field(q) if is_comment_field(q) else q
            for q in include_questions
        ]
        exclude_questions = [
            normalize_comment_field(q) if is_comment_field(q) else q
            for q in exclude_questions
        ]

        # Validate provided question names and comment fields
        invalid_includes = [
            q for q in include_questions if q not in all_analyzable_fields
        ]
        if invalid_includes:
            raise ValueError(
                f"Unknown question names or comment fields in include_questions: {invalid_includes}. "
                f"Available fields: {all_analyzable_fields}"
            )

        invalid_excludes = [
            q for q in exclude_questions if q not in all_analyzable_fields
        ]
        if invalid_excludes:
            raise ValueError(
                f"Unknown question names or comment fields in exclude_questions: {invalid_excludes}. "
                f"Available fields: {all_analyzable_fields}"
            )

        # Apply exclusion
        filtered_questions: list[str] = [
            q for q in include_questions if q not in exclude_questions
        ]

        # Apply question type exclusion
        if self.exclude_question_types:
            question_type_map = {
                q.question_name: q.question_type for q in results.survey.questions
            }
            # Add comment fields to the type map (they're always free_text)
            for comment_field in all_comment_fields:
                question_type_map[comment_field] = "free_text"

            filtered_questions = [
                q
                for q in filtered_questions
                if question_type_map[q] not in self.exclude_question_types
            ]

        if not filtered_questions:
            raise ValueError(
                "No questions remain after applying include/exclude filters."
            )

        # Generate analyses based on the filtered set of questions (or use provided list)
        self.analyses = (
            analyses
            if analyses is not None
            else self._get_analyses(
                filtered_questions, include_interactions, exclude_interactions
            )
        )

        self.research_items = []

        for analysis in self.analyses:
            allowed = (
                self._analysis_output_filters.get(tuple(analysis))
                if analysis_output_filters is not None
                else None
            )
            self.research_items.append(
                Research(
                    self.results,
                    analysis,
                    allowed_output_names=allowed,
                    free_text_sample_config=self.free_text_sample_config,
                )
            )

        self._scenario_list_cache = None  # Lazy initialization

        d = {}
        self._writeups = None  # Initialize writeups cache

        for research_item in self.research_items:
            d[research_item.question_names] = research_item.generated_outputs
        super().__init__(d)
        self.data = d  # Ensure data attribute is set for UserDict compatibility
        self._survey_overview = None
        self._respondent_overview = None  # Add initialization
        self._scenario_overview = None  # Add initialization

    @classmethod
    def from_yaml(cls, results: Results, yaml_config_path: str):
        """Create a Report from a YAML configuration file.

        Args:
            results (Results): The EDSL Results object upon which this report is built.
            yaml_config_path (str): Path to the YAML configuration file.

        Returns:
            Report: A new Report instance configured according to the YAML file.
        """
        with open(yaml_config_path, "r") as f:
            config = yaml.safe_load(f)

        # Extract report settings
        report_settings = config.get("report_settings", {})
        lorem_ipsum = report_settings.get("lorem_ipsum", False)
        include_questions_table = report_settings.get("include_questions_table", True)
        include_respondents_section = report_settings.get(
            "include_respondents_section", True
        )
        include_scenario_section = report_settings.get("include_scenario_section", True)
        include_overview = report_settings.get("include_overview", True)

        # Extract question filters
        question_filters = config.get("question_filters", {})
        include_questions = question_filters.get("include_questions")
        exclude_questions = question_filters.get("exclude_questions")

        # Extract interaction filters
        interaction_filters = config.get("interaction_filters", {})
        include_interactions = interaction_filters.get("include_interactions")
        exclude_interactions = interaction_filters.get("exclude_interactions")

        # Extract analyses configuration
        analyses_config = config.get("analyses", [])

        # Convert analyses configuration to the format expected by Report
        analyses: List[List[str]] = []
        analysis_output_filters: dict[tuple[str, ...], List[str]] = {}

        for analysis_config in analyses_config:
            questions = analysis_config.get("questions", [])
            outputs = analysis_config.get("outputs", [])

            # Add this analysis to the analyses list
            analyses.append(questions)

            # Process outputs - only include enabled ones
            enabled_outputs = [
                output["name"] for output in outputs if output.get("enabled", True)
            ]

            # If there are specific outputs defined, use them as a filter
            if enabled_outputs and len(enabled_outputs) < len(outputs):
                analysis_output_filters[tuple(questions)] = enabled_outputs

        # Create and return the Report instance
        return cls(
            results,
            include_questions=include_questions,
            exclude_questions=exclude_questions,
            include_interactions=include_interactions,
            exclude_interactions=exclude_interactions,
            analyses=analyses if analyses else None,
            analysis_output_filters=(
                analysis_output_filters if analysis_output_filters else None
            ),
            lorem_ipsum=lorem_ipsum,
            include_questions_table=include_questions_table,
            include_respondents_section=include_respondents_section,
            include_scenario_section=include_scenario_section,
            include_overview=include_overview,
        )

    @property
    def scenario_list(self):
        """Lazily generate the scenario list only when needed."""
        if self._scenario_list_cache is None:
            self._scenario_list_cache = list(self._scenario_list())
        return self._scenario_list_cache

    @property
    def survey_overview(self):
        if not hasattr(self, "_survey_overview") or self._survey_overview is None:
            """Generates and returns the survey overview."""
            if self.lorem_ipsum:
                self._survey_overview = "Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat."
            else:
                q = QuestionFreeText(
                    question_name="survey_overview",
                    question_text="""
                    A survey was conducted. This is the survey itself:
                    <survey>
                    {{ scenario.survey }}
                    </survey>
                    Please write a short overview of the survey as plain text.
                    """,
                )
                results = q.by(Scenario({"survey": str(self.results.survey)})).run(
                    stop_on_exception=True
                )
                self._survey_overview = results[0]["answer"]["survey_overview"]
        return self._survey_overview

    def _generate_overview(
        self,
        data_source: str,
        question_name: str,
        prompt_text: str,
        data: object,
        max_length: int = 100,
    ) -> str:
        """Helper function to generate overviews with max length enforcement."""
        if self.lorem_ipsum:
            return "Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua."
        else:
            q = QuestionFreeText(question_name=question_name, question_text=prompt_text)
            # Pass the already-processed (potentially truncated) data string directly
            results = q.by(Scenario({data_source: data})).run(stop_on_exception=True)
            overview = results[0]["answer"][question_name]
            return overview

    @property
    def respondent_overview(self):
        if (
            not hasattr(self, "_respondent_overview")
            or self._respondent_overview is None
        ):
            max_length = 100
            agents_str = str(self.results.agents)
            if len(agents_str) > max_length:
                agents_str = agents_str[:max_length] + "... (truncated)"

            prompt = """
            These are the respondents (represented by Agents) who participated in the survey:
            <agents>
            {{ scenario.agents }}
            </agents>
            The list above may be truncated if it was too long.
            Please write a short overview of the respondents as plain text.
            """
            self._respondent_overview = self._generate_overview(
                data_source="agents",
                question_name="respondent_overview",
                prompt_text=prompt,
                data=agents_str,  # Pass truncated string
                max_length=max_length,  # Keep for reference if needed, but not used for output check
            )
        return self._respondent_overview

    @property
    def scenario_overview(self):
        if not hasattr(self, "_scenario_overview") or self._scenario_overview is None:
            max_length = 100
            scenarios_str = str(self.results.scenarios)
            if len(scenarios_str) > max_length:
                scenarios_str = scenarios_str[:max_length] + "... (truncated)"

            prompt = """
            These are the scenarios under which the survey questions were asked:
            <scenarios>
            {{ scenario.scenarios }}
            </scenarios>
            The list above may be truncated if it was too long.
            Please write a short overview of the scenarios as plain text.
            """
            self._scenario_overview = self._generate_overview(
                data_source="scenarios",
                question_name="scenario_overview",
                prompt_text=prompt,
                data=scenarios_str,  # Pass truncated string
                max_length=max_length,  # Keep for reference
            )
        return self._scenario_overview

    @property
    def writeups(self):
        """Generates and returns the textual write-ups for each analysis."""
        from .warning_utils import progress_status

        if not hasattr(self, "_writeups") or self._writeups is None:
            with progress_status("Generating write-ups..."):
                writeup_results = self.gen_writeup()

            d = defaultdict(dict)
            # Iterate directly, assuming keys and valid structure exist
            for result in writeup_results:
                key1 = tuple(result["scenario"]["question_names"])
                key2 = result["scenario"]["output_name"]
                writeup_text = result["answer"]["written_analysis"]
                d[key1][key2] = writeup_text

            self._writeups = dict(d)  # Convert back to regular dict if preferred
            print_success("Write-ups generated.")
        return self._writeups

    def _scenario_list(self):
        for research_item in self.research_items:
            # Check if writeup is enabled for this analysis
            analysis_key = tuple(research_item.question_names)
            writeup_enabled = self._analysis_writeup_filters.get(
                analysis_key, True
            )  # Default to True
            if not writeup_enabled:
                continue  # Skip scenarios for this analysis

            question_texts = [q.question_text for q in research_item.questions]
            question_types = [q.question_type for q in research_item.questions]
            for output_name, output_object in research_item.generated_outputs.items():
                yield Scenario(
                    {
                        "question_names": research_item.question_names,
                        "output_name": output_name,
                        "question_texts": question_texts,
                        "question_types": question_types,
                        "narrative": output_object.narrative,
                        "analysis": output_object.scenario_output,
                    }
                )

    def analyze(self, *question_names):
        """
        Get a QuestionAnalysis object for convenient access to all outputs for specific question(s) or comment fields.

        Args:
            *question_names: One or more question names or comment field names. Can be passed as:
                - Single string: analyze('gender') or analyze('gender_comment')
                - Multiple strings: analyze('gender', 'employment')
                - Comma-separated string: analyze('gender,employment')
                - Mixed questions and comments: analyze('gender', 'gender_comment')

        Returns:
            QuestionAnalysis object with dot notation access to outputs

        Example:
            # Single question
            analysis = report.analyze('gender')
            analysis.bar_chart  # Get the bar chart
            analysis.frequency_table  # Get the frequency table
            analysis.list_outputs()  # See all available outputs

            # Single comment field (always treated as free text)
            analysis = report.analyze('gender_comment')
            analysis.word_cloud  # Get word cloud of comments
            analysis.frequency_table  # Get frequency table of comments

            # Multiple questions (interaction)
            analysis = report.analyze('gender', 'employment')
            analysis.heatmap
            analysis.cross_tabulation

            # Comma-separated
            analysis = report.analyze('gender,employment')
            analysis.heatmap

        Note:
            - For pairwise analyses, order matters! analyze('q1', 'q2') and analyze('q2', 'q1')
              will produce different visualizations (e.g., different axes in charts).
            - Comment fields are always treated as free_text question types.
            - Comment field names can be specified as 'question_name_comment' or 'comment.question_name_comment'.
        """
        # Parse the question names
        if len(question_names) == 1 and "," in question_names[0]:
            # Handle comma-separated string
            parsed_names = [name.strip() for name in question_names[0].split(",")]
        else:
            # Handle multiple arguments
            parsed_names = list(question_names)

        # Normalize to tuple format used internally
        if len(parsed_names) == 1:
            key = (parsed_names[0],)
        else:
            key = tuple(parsed_names)

        # Check if this analysis exists in the report
        if key not in self:
            # Try to create the analysis on-demand
            from .comment_field import (
                get_available_comment_fields,
                is_comment_field,
                normalize_comment_field,
            )

            all_question_names = [
                q.question_name for q in self.results.survey.questions
            ]
            all_comment_fields = get_available_comment_fields(self.results)
            all_analyzable_fields = all_question_names + all_comment_fields

            # Normalize comment field names
            normalized_names = [
                normalize_comment_field(name) if is_comment_field(name) else name
                for name in parsed_names
            ]

            # Validate that all fields exist
            invalid_fields = [
                name for name in normalized_names if name not in all_analyzable_fields
            ]
            if invalid_fields:
                print_error(
                    f"Analysis for {parsed_names} not found in report and fields are invalid."
                )
                print_error(f"Invalid fields: {invalid_fields}")
                print_info(f"Available fields: {all_analyzable_fields}")
                return None

            # Create the analysis on-demand
            try:
                research_item = Research(
                    self.results,
                    normalized_names,
                    free_text_sample_config=self.free_text_sample_config,
                )
                # Add to the report's dictionary
                normalized_key = tuple(normalized_names)
                self[normalized_key] = research_item.generated_outputs
                key = normalized_key  # Use the normalized key
            except Exception as e:
                print_error(
                    f"Failed to create analysis for {parsed_names} on-demand: {e}"
                )
                import traceback

                traceback.print_exc()
                return None

        # Get the output dictionary for these questions
        output_dict = self[key]

        # Return a QuestionAnalysis wrapper with reference to this report
        return QuestionAnalysis(key, output_dict, self)

    def get_plot(self, question_names, output_name):
        """
        Get a specific plot/output from the report.

        Args:
            question_names: Either a single question name (str) or a list of question names (for interactions)
            output_name: Name of the output type (e.g., 'bar_chart', 'heatmap', 'theme_analysis')

        Returns:
            The chart/output object, or None if not found

        Example:
            # Get a bar chart for a single question
            chart = report.get_plot('gender', 'bar_chart')
            chart.show()

            # Get a heatmap for two questions
            chart = report.get_plot(['gender', 'employment'], 'heatmap')
            chart.show()
        """
        # Normalize to tuple format used internally
        if isinstance(question_names, str):
            key = (question_names,)
        elif isinstance(question_names, list):
            key = tuple(question_names)
        else:
            key = question_names

        # Check if this analysis exists in the report
        if key not in self:
            print_error(f"Analysis for {question_names} not found in report.")
            print_info(f"Available analyses: {list(self.keys())}")
            return None

        # Get the output dictionary for these questions
        output_dict = self[key]

        # Check if the requested output exists
        if output_name not in output_dict:
            print_error(f"Output '{output_name}' not found for {question_names}.")
            print_info(f"Available outputs: {list(output_dict.keys())}")
            return None

        # Return the output object's chart/visualization
        output_obj = output_dict[output_name]
        return output_obj.output()

    def list_outputs(self, question_names=None):
        """
        List available outputs in the report.

        Args:
            question_names: Optional. If provided, lists outputs for specific question(s).
                           If None, lists all analyses and their outputs.

        Example:
            # List all analyses
            report.list_outputs()

            # List outputs for a specific question
            report.list_outputs('gender')
        """
        if question_names is None:
            # List all analyses
            print("Available analyses in report:")
            for key, outputs in self.items():
                print(f"\n  {key}:")
                for output_name in outputs.keys():
                    output_obj = outputs[output_name]
                    pretty_name = getattr(output_obj, "pretty_name", output_name)
                    print(f"    - {output_name} ({pretty_name})")
        else:
            # List outputs for specific question(s)
            if isinstance(question_names, str):
                key = (question_names,)
            elif isinstance(question_names, list):
                key = tuple(question_names)
            else:
                key = question_names

            if key not in self:
                print_error(f"Analysis for {question_names} not found in report.")
                print_info(f"Available analyses: {list(self.keys())}")
                return

            print(f"Available outputs for {question_names}:")
            for output_name, output_obj in self[key].items():
                pretty_name = getattr(output_obj, "pretty_name", output_name)
                print(f"  - {output_name} ({pretty_name})")

    def _get_analyses(
        self,
        questions: List[str],
        include_interactions: List[List[str]] | None = None,
        exclude_interactions: List[List[str]] | None = None,
    ):
        """Return combinations of questions to analyse.

        Args:
            questions (List[str]): The list of question names to consider.
            include_interactions (List[List[str]] | None, optional): Explicit list of 2-way
                interactions to include. If None, all possible pairs are considered.
            exclude_interactions (List[List[str]] | None, optional): List of 2-way interactions
                to exclude. Applied after include_interactions filtering.

        Returns:
            List[List[str]]: A list where each element is either a single-element list
                (individual question) or a two-element list (pairwise combination).
        """
        from itertools import combinations

        # Single-question analyses
        singles = [[q] for q in questions]

        # Generate pairwise analyses with include/exclude filtering
        if include_interactions is not None:
            # Validate and use explicitly provided interactions
            all_question_names = [
                q.question_name for q in self.results.survey.questions
            ]
            filtered_pairs = []

            for interaction in include_interactions:
                if len(interaction) != 2:
                    raise ValueError(
                        f"Interaction must contain exactly 2 questions, got {len(interaction)}: {interaction}"
                    )

                # Validate question names exist
                invalid_questions = [
                    q for q in interaction if q not in all_question_names
                ]
                if invalid_questions:
                    raise ValueError(
                        f"Unknown question names in include_interactions: {invalid_questions}"
                    )

                # Check if both questions are in our filtered question list
                if all(q in questions for q in interaction):
                    # Add both orderings since order matters for visualizations
                    filtered_pairs.append(list(interaction))
                    # Add reverse order if not already present
                    reversed_pair = list(reversed(interaction))
                    if reversed_pair != list(interaction):
                        filtered_pairs.append(reversed_pair)

            pairs = filtered_pairs
        else:
            # Generate all possible pairwise combinations in BOTH orderings
            # Order matters for visualizations (e.g., which axis each question is on)
            pairs = []
            for combo in combinations(questions, 2):
                # Add both (q1, q2) and (q2, q1)
                pairs.append([combo[0], combo[1]])
                pairs.append([combo[1], combo[0]])

        # Apply exclusions
        if exclude_interactions is not None:
            # Validate exclusion interactions
            all_question_names = [
                q.question_name for q in self.results.survey.questions
            ]

            for interaction in exclude_interactions:
                if len(interaction) != 2:
                    raise ValueError(
                        f"Interaction must contain exactly 2 questions, got {len(interaction)}: {interaction}"
                    )

                # Validate question names exist
                invalid_questions = [
                    q for q in interaction if q not in all_question_names
                ]
                if invalid_questions:
                    raise ValueError(
                        f"Unknown question names in exclude_interactions: {invalid_questions}"
                    )

            # Remove excluded interactions (check both the pair and its reverse)
            pairs_to_exclude = []
            for interaction in exclude_interactions:
                pairs_to_exclude.append(list(interaction))
                pairs_to_exclude.append(list(reversed(interaction)))

            pairs = [pair for pair in pairs if pair not in pairs_to_exclude]

        return singles + pairs

    def _format_question_header(self, question_names: List[str]) -> str:
        """Format question header using question text with question name in small font in parentheses."""
        if len(question_names) == 1:
            question_name = question_names[0]
            question = next(
                (
                    q
                    for q in self.results.survey.questions
                    if q.question_name == question_name
                ),
                None,
            )
            if question:
                question_text = question.question_text
                if len(question_text) > self.question_header_max_length:
                    question_text = (
                        question_text[: self.question_header_max_length] + "..."
                    )
                return f"'{question_text}' <small>({question_name})</small>"
            else:
                return f"{question_name}"
        else:
            # For multiple questions, show truncated text for each
            formatted_questions = []
            for question_name in question_names:
                question = next(
                    (
                        q
                        for q in self.results.survey.questions
                        if q.question_name == question_name
                    ),
                    None,
                )
                if question:
                    question_text = question.question_text
                    if (
                        len(question_text) > self.question_header_max_length // 2
                    ):  # Shorter for multiple questions
                        question_text = (
                            question_text[: self.question_header_max_length // 2]
                            + "..."
                        )
                    formatted_questions.append(
                        f"'{question_text}' <small>({question_name})</small>"
                    )
                else:
                    formatted_questions.append(question_name)
            return f"{' and '.join(formatted_questions)}"

    def _create_question_metadata_table(self, question_names: List[str]) -> str:
        """Create HTML table with question metadata."""
        html_parts = []
        html_parts.append(
            "<table style='margin-bottom: 20px; border-collapse: collapse; width: 100%;'>"
        )

        total_respondents = len(self.results)

        for question_name in question_names:
            question = next(
                (
                    q
                    for q in self.results.survey.questions
                    if q.question_name == question_name
                ),
                None,
            )
            if question:
                question_type = question.question_type
                question_options = ""
                if hasattr(question, "question_options") and question.question_options:
                    question_options = ", ".join(
                        str(opt) for opt in question.question_options
                    )
                elif hasattr(question, "option_labels") and question.option_labels:
                    question_options = ", ".join(
                        str(opt) for opt in question.option_labels
                    )

                html_parts.append(
                    "<tr><th style='border: 1px solid #ddd; padding: 8px; background: #f5f5f5; width: 30%;'>Question Name</th>"
                )
                html_parts.append(
                    f"<td style='border: 1px solid #ddd; padding: 8px;'>{question_name}</td></tr>"
                )
                html_parts.append(
                    "<tr><th style='border: 1px solid #ddd; padding: 8px; background: #f5f5f5; width: 30%;'>Question Text</th>"
                )
                html_parts.append(
                    f"<td style='border: 1px solid #ddd; padding: 8px;'>{question.question_text}</td></tr>"
                )
                html_parts.append(
                    "<tr><th style='border: 1px solid #ddd; padding: 8px; background: #f5f5f5; width: 30%;'>Question Type</th>"
                )
                html_parts.append(
                    f"<td style='border: 1px solid #ddd; padding: 8px;'>{question_type}</td></tr>"
                )
                html_parts.append(
                    "<tr><th style='border: 1px solid #ddd; padding: 8px; background: #f5f5f5; width: 30%;'>Question Options</th>"
                )
                html_parts.append(
                    f"<td style='border: 1px solid #ddd; padding: 8px;'>{question_options}</td></tr>"
                )
                html_parts.append(
                    "<tr><th style='border: 1px solid #ddd; padding: 8px; background: #f5f5f5; width: 30%;'>Total Respondents</th>"
                )
                html_parts.append(
                    f"<td style='border: 1px solid #ddd; padding: 8px;'>{total_respondents}</td></tr>"
                )

                # Add separator between questions if there are multiple
                if len(question_names) > 1 and question_name != question_names[-1]:
                    html_parts.append(
                        "<tr><td colspan='2' style='border: none; padding: 10px;'></td></tr>"
                    )

        html_parts.append("</table>")
        return "".join(html_parts)

    def _create_question_summary_table(self) -> str:
        """Create HTML table summarizing all questions and their inclusion in the report."""
        html_parts = []
        html_parts.append(
            "<table style='margin-bottom: 20px; border-collapse: collapse; width: 100%;'>"
        )
        html_parts.append("<thead>")
        html_parts.append("<tr>")
        html_parts.append(
            "<th style='border: 1px solid #ddd; padding: 8px; background: #f5f5f5;'>Question Name</th>"
        )
        html_parts.append(
            "<th style='border: 1px solid #ddd; padding: 8px; background: #f5f5f5;'>Question Type</th>"
        )
        html_parts.append(
            "<th style='border: 1px solid #ddd; padding: 8px; background: #f5f5f5;'>Included in Report</th>"
        )
        html_parts.append("</tr>")
        html_parts.append("</thead>")
        html_parts.append("<tbody>")

        # Get all questions that are included in the report
        included_questions = set()
        for analysis in self.analyses:
            for question_name in analysis:
                included_questions.add(question_name)

        # Iterate through all questions in the survey
        for question in self.results.survey.questions:
            question_name = question.question_name
            question_type = question.question_type
            is_included = question_name in included_questions

            html_parts.append("<tr>")
            html_parts.append(
                f"<td style='border: 1px solid #ddd; padding: 8px;'>{question_name}</td>"
            )
            html_parts.append(
                f"<td style='border: 1px solid #ddd; padding: 8px;'>{question_type}</td>"
            )

            if is_included:
                html_parts.append(
                    "<td style='border: 1px solid #ddd; padding: 8px; text-align: center;'>✓</td>"
                )
            else:
                html_parts.append(
                    "<td style='border: 1px solid #ddd; padding: 8px; text-align: center;'>-</td>"
                )

            html_parts.append("</tr>")

        html_parts.append("</tbody>")
        html_parts.append("</table>")

        return "".join(html_parts)

    def gen_writeup(self):
        """Generate a writeup of the report."""
        if self.lorem_ipsum:
            # Generate lorem ipsum text instead of LLM analysis
            lorem_text = "Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat. Duis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla pariatur. Excepteur sint occaecat cupidatat non proident, sunt in culpa qui officia deserunt mollit anim id est laborum."

            # Create mock results that match the expected structure
            mock_results = []
            for scenario in self.scenario_list:
                mock_result = {
                    "scenario": scenario.data,
                    "answer": {"written_analysis": lorem_text},
                }
                mock_results.append(mock_result)
            return mock_results
        else:
            q_analysis = QuestionFreeText(
                question_name="written_analysis",
                question_text="""
                A survey was conducted and the following questions were asked:
                <questions>
                {{ scenario.question_texts }}
                </questions>

                The results have been analyzed and this is the visualization/table of the results:
                <analysis>
                {{ scenario.analysis }}
                </analysis>
                Please write a short, 1 paragraph analysis of the results as plain text.
                """,
            )
            results = q_analysis.by(self.scenario_list).run(stop_on_exception=True)
            return results

    def generate_notebook(self, filename: str, execute: bool = True):
        """Generate a Jupyternotebook, optionally execute it.

        Args:
            filename (str): The name of the notebook file to create (e.g., "report.ipynb").
            execute (bool, optional): Whether to execute the notebook after creating it. Defaults to False.
        """
        nb = nbformat.v4.new_notebook()

        # Add title
        nb.cells.append(nbformat.v4.new_markdown_cell("# Survey Report"))

        # Add question summary table
        if self.include_questions_table:
            nb.cells.append(nbformat.v4.new_markdown_cell("## Question Summary"))
            question_summary_table = self._create_question_summary_table()
            nb.cells.append(nbformat.v4.new_markdown_cell(question_summary_table))

        # Add survey overview
        if self.include_overview:
            nb.cells.append(nbformat.v4.new_markdown_cell("## Survey Overview"))
            nb.cells.append(nbformat.v4.new_markdown_cell(self.survey_overview))

        # Add respondent overview
        if self.include_respondents_section:
            nb.cells.append(nbformat.v4.new_markdown_cell("## Respondent Overview"))
            nb.cells.append(nbformat.v4.new_markdown_cell(self.respondent_overview))

        # Add scenario overview
        if self.include_scenario_section:
            nb.cells.append(nbformat.v4.new_markdown_cell("## Scenario Overview"))
            nb.cells.append(nbformat.v4.new_markdown_cell(self.scenario_overview))

        # Need code to recreate the results object used to initialize this report
        # For now, adding placeholder code
        recreate_code = (
            "import altair as alt\n"
            # Using 'png' renderer for execution might embed static images.
            # Consider 'default' or 'mimetype' if you want interactive charts in the saved .ipynb.
            "alt.renderers.enable('svg')\n\n"
            "from edsl import Results\n"
            "results = Results.example() # Replace with actual results loading code\n"
            "from reports.report import Report\n"
            "report = Report(results)"
        )
        nb.cells.append(nbformat.v4.new_code_cell(recreate_code))

        for key, ouput_dict in self.items():
            section_title = self._format_question_header(key)
            nb.cells.append(nbformat.v4.new_markdown_cell(f"## {section_title}"))

            # Add question metadata table as markdown
            metadata_table = self._create_question_metadata_table(key)
            nb.cells.append(nbformat.v4.new_markdown_cell(metadata_table))

            for output_name, output_object in ouput_dict.items():
                display_name = getattr(output_object, "pretty_short_name", output_name)
                nb.cells.append(nbformat.v4.new_markdown_cell(f"### {display_name}"))

                # Add the write-up as a markdown cell if keys exist
                if key in self.writeups and output_name in self.writeups[key]:
                    # Check if writeup is enabled for this analysis
                    analysis_key = (
                        tuple(key) if isinstance(key, (list, tuple)) else (key,)
                    )
                    writeup_enabled = self._analysis_writeup_filters.get(
                        analysis_key, True
                    )
                    if writeup_enabled:
                        writeup_text = self.writeups[key][output_name]
                        nb.cells.append(nbformat.v4.new_markdown_cell(writeup_text))
                # If keys don't exist, skip adding the write-up cell

                # Add the code cell for the output visualization/table
                code_cell = f"report[{key!r}]['{output_name}'].output()"
                nb.cells.append(nbformat.v4.new_code_cell(code_cell))

        notebook_saved = False
        if execute:
            print_info("Executing notebook...")
            # Execute the notebook in memory
            # Ensure the kernel matches your environment if not default python3
            client = NotebookClient(nb, timeout=600, kernel_name="python3")
            try:
                client.execute()
                print_success("Execution complete. Saving executed notebook...")
            except Exception as e:
                print_error(f"Error executing notebook: {e}")
                # Decide if you still want to save the partially executed notebook

            # Save the executed notebook (overwrites the original file)
            with open(filename, "w") as f:
                nbformat.write(nb, f)
            print_success(f"Executed notebook saved to {filename}")
            notebook_saved = True
        else:
            # Save the notebook without execution
            with open(filename, "w") as f:
                nbformat.write(nb, f)
            print_success(f"Notebook saved to {filename}")
            notebook_saved = True

    ##############################
    # New export helpers
    ##############################

    def generate_html(self, filename: str, css: str = None):
        """Generate a standalone HTML report.

        Args:
            filename (str): Destination HTML file path (e.g. "report.html").
            css (str, optional): Custom CSS styling to include in the report.
        """
        from .report_html import ReportHTML

        html_generator = ReportHTML(self)
        html_generator.generate(filename, css)

    def generate_docx(self, filename: str):
        """Generate a Word (.docx) report.

        Charts will be embedded as PNGs, tables converted to Word tables when possible.

        Args:
            filename (str): Destination docx file path (e.g. "report.docx").
        """
        from .report_docx import ReportDOCX

        docx_generator = ReportDOCX(self)
        docx_generator.generate(filename)

    def generate_pptx(self, filename: str):
        """Generate a PowerPoint (.pptx) presentation.

        Each question analysis gets its own slide with visualizations and writeups.

        Args:
            filename (str): Destination pptx file path (e.g. "report.pptx").
        """
        from .report_pptx import ReportPPTX

        pptx_generator = ReportPPTX(self)
        pptx_generator.generate(filename)

    def generate_pdf(self, filename: str):
        """Generate a PDF report using pandoc.

        This method first generates an HTML report and then converts it to PDF using pandoc.
        Requires pandoc to be installed on the system.

        Args:
            filename (str): Destination PDF file path (e.g. "report.pdf").
        """
        print_info("Generating PDF report...")

        # Check if pandoc is available
        try:
            subprocess.run(["pandoc", "--version"], capture_output=True, check=True)
        except (FileNotFoundError, subprocess.CalledProcessError):
            print_error("pandoc is not available.")
            print_error("Please install pandoc: https://pandoc.org/installing.html")
            raise RuntimeError("pandoc is required for PDF generation")

        # Create a temporary HTML file
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".html", delete=False
        ) as tmp_html:
            tmp_html_path = tmp_html.name

        try:
            # Generate HTML report to temporary file
            self.generate_html(tmp_html_path)

            # Convert HTML to PDF using pandoc
            cmd = [
                "pandoc",
                tmp_html_path,
                "-o",
                filename,
                "--pdf-engine=xelatex",  # Use xelatex for better Unicode support
                "--variable",
                "geometry:margin=0.75in",
                "--variable",
                "fontsize=11pt",
                "--variable",
                "papersize=a4",
                "--standalone",
            ]

            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode != 0:
                # Try with different PDF engine as fallback
                print_info("Trying alternative PDF engine...")
                cmd_fallback = [
                    "pandoc",
                    tmp_html_path,
                    "-o",
                    filename,
                    "--pdf-engine=pdflatex",
                    "--variable",
                    "geometry:margin=0.75in",
                    "--variable",
                    "fontsize=11pt",
                    "--variable",
                    "papersize=a4",
                    "--standalone",
                ]

                result_fallback = subprocess.run(
                    cmd_fallback, capture_output=True, text=True
                )

                if result_fallback.returncode != 0:
                    print_error(f"pandoc failed: {result_fallback.stderr}")
                    raise RuntimeError(f"pandoc failed: {result_fallback.stderr}")
                else:
                    print_success(f"PDF report saved to {filename}")
            else:
                print_success(f"PDF report saved to {filename}")

        finally:
            # Clean up temporary HTML file
            try:
                os.unlink(tmp_html_path)
            except OSError:
                pass


if __name__ == "__main__":
    # This should be updated to load actual results instead of using example
    # Use the CLI tool instead: python -m reports generate --json-gz-file your_results.json.gz
    print_error("This script should not be run directly.")
    print_info("Use the CLI tool instead:")
    print_info("  python -m reports generate --json-gz-file your_results.json.gz")
    print_info("  python -m reports generate --coop-uuid your-uuid")
    print_info("  cat your_results.json | python -m reports generate")

    # For testing purposes only - generate example reports
    results = Results.example()
    report = Report(results)

    # Generate HTML, DOCX, PPTX, and PDF versions
    html_filename = "report.html"
    report.generate_html(html_filename)
    print(f"HTML report generated: {html_filename}")

    docx_filename = "report.docx"
    report.generate_docx(docx_filename)
    print(f"DOCX report generated: {docx_filename}")

    pptx_filename = "report.pptx"
    try:
        report.generate_pptx(pptx_filename)
        print(f"PPTX presentation generated: {pptx_filename}")
    except Exception as e:
        print_error(f"Failed to generate PPTX: {e}")
        print_info("PPTX generation requires python-pptx")

    pdf_filename = "report.pdf"
    try:
        report.generate_pdf(pdf_filename)
        print(f"PDF report generated: {pdf_filename}")
    except Exception as e:
        print_error(f"Failed to generate PDF: {e}")
        print_info("PDF generation requires pandoc")
