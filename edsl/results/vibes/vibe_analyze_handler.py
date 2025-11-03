"""Handler for analyzing results using LLM-powered insights."""

from typing import TYPE_CHECKING, Dict, List, Any, Optional
from dataclasses import dataclass, field

if TYPE_CHECKING:
    from ..results import Results
    from edsl.reports.report import QuestionAnalysis


@dataclass
class QuestionVibeAnalysis:
    """Container for a single question's analysis with LLM insights.

    Attributes:
        question_name: Name of the question
        question_text: Text of the question
        question_type: Type of question
        analysis: QuestionAnalysis object from results.analyze()
        llm_insights: LLM-generated insights about the data
        visualization_analysis: Optional LLM analysis of the visualization
        chart_png: PNG bytes of the chart for serialization
    """
    question_name: str
    question_text: str
    question_type: str
    analysis: "QuestionAnalysis"
    llm_insights: Optional[str] = None
    visualization_analysis: Optional[str] = None
    chart_png: Optional[bytes] = None

    def __repr__(self):
        """String representation showing question details."""
        return (
            f"QuestionVibeAnalysis(question='{self.question_name}', "
            f"type='{self.question_type}')"
        )

    def get_chart_as_image(self):
        """Get the chart as a displayable image object.

        Returns PNG bytes if available, otherwise tries to get from analysis.
        """
        if self.chart_png:
            return self.chart_png

        # Try to get from analysis
        try:
            if hasattr(self.analysis, 'bar_chart'):
                return _capture_chart_as_png(self.analysis.bar_chart)
        except Exception:
            pass

        return None


@dataclass
class ResultsVibeAnalysis:
    """Container for all question analyses with LLM insights.

    This object holds the analysis results for all questions in the survey,
    with optional LLM-generated insights and commentary.

    Attributes:
        question_analyses: Dictionary mapping question names to their analyses
        summary_report: Optional overall summary report across all questions
    """
    question_analyses: Dict[str, QuestionVibeAnalysis] = field(default_factory=dict)
    summary_report: Optional[str] = None

    def __getitem__(self, question_name: str) -> QuestionVibeAnalysis:
        """Access a specific question's analysis by name."""
        return self.question_analyses[question_name]

    def __iter__(self):
        """Iterate through question analyses in order."""
        return iter(self.question_analyses.values())

    def __len__(self):
        """Return number of questions analyzed."""
        return len(self.question_analyses)

    def list_questions(self) -> List[str]:
        """Return list of all question names that were analyzed."""
        return list(self.question_analyses.keys())

    def to_dict(self) -> Dict[str, Any]:
        """Export to a dictionary with serializable data only.

        This method extracts only the serializable parts (PNG bytes, text insights)
        and excludes the non-serializable analysis objects. Useful for saving to
        notebooks or other serialization formats.

        Returns:
            Dictionary with question analyses as serializable data
        """
        import base64

        result = {
            "questions": {},
            "summary_report": self.summary_report,
        }

        for q_name, q_analysis in self.question_analyses.items():
            result["questions"][q_name] = {
                "question_name": q_analysis.question_name,
                "question_text": q_analysis.question_text,
                "question_type": q_analysis.question_type,
                "llm_insights": q_analysis.llm_insights,
                "visualization_analysis": q_analysis.visualization_analysis,
                # Store PNG as base64 string for JSON compatibility
                "chart_png_base64": (
                    base64.b64encode(q_analysis.chart_png).decode('utf-8')
                    if q_analysis.chart_png
                    else None
                ),
            }

        return result

    def print_insights(self):
        """Print all LLM insights in a readable format."""
        for q_name, q_analysis in self.question_analyses.items():
            print(f"\n{'=' * 80}")
            print(f"Question: {q_analysis.question_text}")
            print(f"Type: {q_analysis.question_type}")
            print(f"{'=' * 80}")

            if q_analysis.llm_insights:
                print("\nInsights:")
                print(q_analysis.llm_insights)

            if q_analysis.visualization_analysis:
                print("\nVisualization Analysis:")
                print(q_analysis.visualization_analysis)

        if self.summary_report:
            print(f"\n{'=' * 80}")
            print("OVERALL SUMMARY")
            print(f"{'=' * 80}")
            print(self.summary_report)

    def display(self):
        """Display the analysis with plots and insights in a notebook."""
        try:
            from IPython.display import display, HTML, Markdown
        except ImportError:
            print("IPython not available. Using print_insights() instead.")
            self.print_insights()
            return

        # Display each question's analysis
        for q_name, q_analysis in self.question_analyses.items():
            # Question header
            display(HTML(f"""
                <div style="margin-top: 30px; margin-bottom: 20px; padding: 15px;
                     background-color: #f0f7ff; border-left: 4px solid #0066cc; border-radius: 4px;">
                    <h2 style="margin: 0; color: #0066cc; font-size: 20px;">
                        {q_analysis.question_text}
                    </h2>
                    <p style="margin: 5px 0 0 0; color: #666; font-size: 14px;">
                        Question: <code>{q_name}</code> | Type: <code>{q_analysis.question_type}</code>
                    </p>
                </div>
            """))

            # Display the chart/visualization
            try:
                # First try to use the stored PNG
                if q_analysis.chart_png:
                    from IPython.display import Image
                    display(Image(q_analysis.chart_png))
                # Otherwise try to display the interactive chart
                elif hasattr(q_analysis.analysis, 'bar_chart'):
                    chart = q_analysis.analysis.bar_chart
                    display(chart)
            except Exception as e:
                print(f"Could not display chart: {e}")

            # Display LLM insights
            if q_analysis.llm_insights:
                display(HTML(f"""
                    <div style="margin: 20px 0; padding: 15px;
                         background-color: #f9f9f9; border-radius: 4px; border: 1px solid #ddd;">
                        <h3 style="margin-top: 0; color: #333; font-size: 16px;">
                            💡 AI Insights
                        </h3>
                        <div style="line-height: 1.6; color: #444;">
                            {q_analysis.llm_insights.replace(chr(10), '<br>')}
                        </div>
                    </div>
                """))

            # Display visualization analysis if available
            if q_analysis.visualization_analysis:
                display(HTML(f"""
                    <div style="margin: 20px 0; padding: 15px;
                         background-color: #fff8e6; border-radius: 4px; border: 1px solid #ffd700;">
                        <h3 style="margin-top: 0; color: #333; font-size: 16px;">
                            📊 Visualization Analysis
                        </h3>
                        <div style="line-height: 1.6; color: #444;">
                            {q_analysis.visualization_analysis.replace(chr(10), '<br>')}
                        </div>
                    </div>
                """))

        # Display overall summary
        if self.summary_report:
            display(HTML(f"""
                <div style="margin-top: 40px; padding: 20px;
                     background-color: #e8f5e9; border-radius: 4px; border: 2px solid #4caf50;">
                    <h2 style="margin-top: 0; color: #2e7d32; font-size: 20px;">
                        📋 Overall Summary
                    </h2>
                    <div style="line-height: 1.8; color: #333; font-size: 15px;">
                        {self.summary_report.replace(chr(10) + chr(10), '</p><p style="margin: 15px 0;">').replace(chr(10), '<br>')}
                    </div>
                </div>
            """))

    def _repr_html_(self):
        """Return HTML representation for automatic display in Jupyter notebooks."""
        html_parts = []

        # Overall header
        html_parts.append("""
            <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 1000px;">
                <h1 style="color: #0066cc; border-bottom: 3px solid #0066cc; padding-bottom: 10px; margin-bottom: 30px;">
                    📊 Results Analysis with AI Insights
                </h1>
        """)

        # Each question's analysis
        for q_name, q_analysis in self.question_analyses.items():
            # Question header
            html_parts.append(f"""
                <div style="margin-top: 30px; margin-bottom: 20px; padding: 15px;
                     background-color: #f0f7ff; border-left: 4px solid #0066cc; border-radius: 4px;">
                    <h2 style="margin: 0; color: #0066cc; font-size: 20px;">
                        {q_analysis.question_text}
                    </h2>
                    <p style="margin: 5px 0 0 0; color: #666; font-size: 14px;">
                        Question: <code>{q_name}</code> | Type: <code>{q_analysis.question_type}</code>
                    </p>
                </div>
            """)

            # Try to get chart HTML or PNG
            try:
                # First try to use the stored PNG
                if q_analysis.chart_png:
                    import base64
                    img_base64 = base64.b64encode(q_analysis.chart_png).decode('utf-8')
                    html_parts.append(f"""
                        <div style="margin: 20px 0;">
                            <img src="data:image/png;base64,{img_base64}"
                                 style="max-width: 100%; height: auto; border: 1px solid #ddd; border-radius: 4px;"/>
                        </div>
                    """)
                # Otherwise try to get HTML representation
                elif hasattr(q_analysis.analysis, 'bar_chart'):
                    chart = q_analysis.analysis.bar_chart
                    if hasattr(chart, '_repr_html_'):
                        html_parts.append(f"""
                            <div style="margin: 20px 0;">
                                {chart._repr_html_()}
                            </div>
                        """)
                    elif hasattr(chart, 'to_html'):
                        html_parts.append(f"""
                            <div style="margin: 20px 0;">
                                {chart.to_html()}
                            </div>
                        """)
            except Exception:
                html_parts.append("""
                    <div style="margin: 20px 0; padding: 10px; background-color: #f9f9f9; border-radius: 4px;">
                        <em>Chart available via .bar_chart property</em>
                    </div>
                """)

            # LLM insights
            if q_analysis.llm_insights:
                insights_html = q_analysis.llm_insights.replace('\n', '<br>')
                html_parts.append(f"""
                    <div style="margin: 20px 0; padding: 15px;
                         background-color: #f9f9f9; border-radius: 4px; border: 1px solid #ddd;">
                        <h3 style="margin-top: 0; color: #333; font-size: 16px;">
                            💡 AI Insights
                        </h3>
                        <div style="line-height: 1.6; color: #444;">
                            {insights_html}
                        </div>
                    </div>
                """)

            # Visualization analysis if available
            if q_analysis.visualization_analysis:
                viz_html = q_analysis.visualization_analysis.replace('\n', '<br>')
                html_parts.append(f"""
                    <div style="margin: 20px 0; padding: 15px;
                         background-color: #fff8e6; border-radius: 4px; border: 1px solid #ffd700;">
                        <h3 style="margin-top: 0; color: #333; font-size: 16px;">
                            📊 Visualization Analysis
                        </h3>
                        <div style="line-height: 1.6; color: #444;">
                            {viz_html}
                        </div>
                    </div>
                """)

        # Overall summary
        if self.summary_report:
            summary_html = self.summary_report.replace('\n\n', '</p><p style="margin: 15px 0;">').replace('\n', '<br>')
            html_parts.append(f"""
                <div style="margin-top: 40px; padding: 20px;
                     background-color: #e8f5e9; border-radius: 4px; border: 2px solid #4caf50;">
                    <h2 style="margin-top: 0; color: #2e7d32; font-size: 20px;">
                        📋 Overall Summary
                    </h2>
                    <div style="line-height: 1.8; color: #333; font-size: 15px;">
                        <p style="margin: 15px 0;">{summary_html}</p>
                    </div>
                </div>
            """)

        html_parts.append("</div>")
        return ''.join(html_parts)


def analyze_with_vibes(
    results: "Results",
    *,
    model: str = "gpt-4o",
    temperature: float = 0.7,
    include_visualizations: bool = False,
    generate_summary: bool = True,
) -> ResultsVibeAnalysis:
    """Analyze all questions in results with LLM-powered insights.

    This function iterates through each question in the survey, generates
    analysis using the existing analyze() method, and optionally uses an LLM
    to provide insights about the data patterns and visualizations.

    Args:
        results: The Results instance to analyze
        model: OpenAI model to use for generating insights (default: "gpt-4o")
        temperature: Temperature for LLM generation (default: 0.7)
        include_visualizations: Whether to send visualizations to OpenAI for analysis
            (default: False). Note: This can increase API costs significantly.
        generate_summary: Whether to generate an overall summary report (default: True)

    Returns:
        ResultsVibeAnalysis: Container object with analyses for all questions
            and optional LLM insights

    Raises:
        ValueError: If no survey is available in the results
        ImportError: If required visualization dependencies are not installed

    Examples:
        >>> results = Results.example()  # doctest: +SKIP
        >>> vibe_analysis = analyze_with_vibes(results)  # doctest: +SKIP
        >>> vibe_analysis.print_insights()  # doctest: +SKIP

        >>> # Access specific question
        >>> q_analysis = vibe_analysis["how_feeling"]  # doctest: +SKIP
        >>> q_analysis.analysis.bar_chart  # doctest: +SKIP
        >>> print(q_analysis.llm_insights)  # doctest: +SKIP
    """
    from .vibe_analyzer import VibeAnalyzer

    # Validate that we have a survey to work with
    if results.survey is None:
        raise ValueError(
            "Cannot analyze results without a survey. "
            "Results must have an associated survey to use vibe_analyze."
        )

    # Create the analyzer
    analyzer = VibeAnalyzer(model=model, temperature=temperature)

    # Create container for all analyses
    results_analysis = ResultsVibeAnalysis()

    # Iterate through each question in the survey
    for question in results.survey.questions:
        question_name = question.question_name
        question_text = question.question_text
        question_type = question.question_type

        # Get the standard analysis using existing analyze() method
        try:
            analysis = results.analyze(question_name)
        except Exception as e:
            print(f"Warning: Could not analyze question '{question_name}': {e}")
            continue

        # Extract actual response data from results
        data_summary = _extract_data_summary(analysis, question_type, results, question_name)

        # Generate LLM insights about the data
        llm_insights = analyzer.analyze_question_data(
            question_name=question_name,
            question_text=question_text,
            question_type=question_type,
            data_summary=data_summary,
            response_distribution=data_summary.get("distribution", {}),
        )

        # Capture chart as PNG for serialization
        chart_png = None
        try:
            if hasattr(analysis, 'bar_chart'):
                chart_png = _capture_chart_as_png(analysis.bar_chart)
        except Exception as e:
            print(f"Warning: Could not capture chart for '{question_name}': {e}")

        # Optionally analyze visualizations
        visualization_analysis = None
        if include_visualizations:
            # Use the captured PNG or try to get image data
            image_data = chart_png or _get_visualization_image(analysis)
            if image_data:
                visualization_analysis = analyzer.analyze_visualization(
                    question_name=question_name,
                    question_text=question_text,
                    question_type=question_type,
                    image_data=image_data,
                    visualization_type="bar_chart",  # Could be made dynamic
                )

        # Store the analysis with insights
        results_analysis.question_analyses[question_name] = QuestionVibeAnalysis(
            question_name=question_name,
            question_text=question_text,
            question_type=question_type,
            analysis=analysis,
            llm_insights=llm_insights,
            visualization_analysis=visualization_analysis,
            chart_png=chart_png,
        )

    # Generate overall summary if requested
    if generate_summary and results_analysis.question_analyses:
        summary_data = {
            q_name: {
                "question": q_analysis.question_text,
                "type": q_analysis.question_type,
                "insights": q_analysis.llm_insights,
            }
            for q_name, q_analysis in results_analysis.question_analyses.items()
        }
        results_analysis.summary_report = analyzer.generate_summary_report(summary_data)

    return results_analysis


def _extract_data_summary(
    analysis: "QuestionAnalysis",
    question_type: str,
    results: "Results",
    question_name: str,
) -> Dict[str, Any]:
    """Extract summary statistics and actual response data.

    Args:
        analysis: QuestionAnalysis object from results.analyze()
        question_type: Type of the question
        results: Results object containing the actual response data
        question_name: Name of the question

    Returns:
        Dictionary with summary statistics, distributions, and actual responses
    """
    summary = {}

    # Extract actual response values from results
    try:
        responses = results.select(f"answer.{question_name}").to_list()
        summary["responses"] = responses
        summary["response_count"] = len(responses)

        # Get unique values and their counts for categorical data
        if question_type in ["multiple_choice", "checkbox", "yes_no"]:
            from collections import Counter
            response_counts = Counter(str(r) for r in responses if r is not None)
            summary["distribution"] = dict(response_counts)
            summary["unique_values"] = list(response_counts.keys())

        # Get statistics for numerical data
        elif question_type in ["numerical", "linear_scale"]:
            numeric_responses = [r for r in responses if r is not None and isinstance(r, (int, float))]
            if numeric_responses:
                summary["statistics"] = {
                    "count": len(numeric_responses),
                    "mean": sum(numeric_responses) / len(numeric_responses),
                    "min": min(numeric_responses),
                    "max": max(numeric_responses),
                }
                # Also get distribution for discrete scales
                from collections import Counter
                response_counts = Counter(numeric_responses)
                summary["distribution"] = {str(k): v for k, v in response_counts.items()}

        # For free text, provide samples
        elif question_type in ["free_text", "text"]:
            summary["sample_responses"] = responses[:10]  # First 10 responses
            summary["total_responses"] = len(responses)

    except Exception as e:
        summary["extraction_error"] = str(e)

    # Also try to get frequency table data from analysis if available
    try:
        if hasattr(analysis, 'frequency_table'):
            freq_table = analysis.frequency_table
            if hasattr(freq_table, '_data'):
                summary["frequency_table"] = freq_table._data
    except Exception:
        pass

    return summary


def _capture_chart_as_png(chart_wrapper) -> Optional[bytes]:
    """Capture a chart/visualization as PNG bytes.

    Args:
        chart_wrapper: Chart object (may be OutputWrapper or raw chart)

    Returns:
        PNG image bytes or None if capture fails
    """
    try:
        # If it's an OutputWrapper, get the actual chart
        if hasattr(chart_wrapper, 'chart'):
            actual_chart = chart_wrapper.chart
        else:
            actual_chart = chart_wrapper

        # For Altair charts (most common in edsl)
        if hasattr(actual_chart, 'save'):
            import tempfile
            import os

            # Create temp file
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
                temp_path = f.name

            try:
                # Save chart as PNG
                actual_chart.save(temp_path, format='png')

                # Read the PNG bytes
                with open(temp_path, 'rb') as f:
                    png_bytes = f.read()

                return png_bytes

            finally:
                # Clean up temp file
                try:
                    os.unlink(temp_path)
                except Exception:
                    pass

        # For Plotly figures
        elif hasattr(actual_chart, 'to_image'):
            return actual_chart.to_image(format="png")

        # For matplotlib figures
        elif hasattr(actual_chart, 'savefig'):
            import io
            buf = io.BytesIO()
            actual_chart.savefig(buf, format='png')
            buf.seek(0)
            return buf.read()

    except Exception as e:
        # Silently fail if we can't capture the image
        pass

    return None


def _get_visualization_image(analysis: "QuestionAnalysis") -> Optional[bytes]:
    """Try to capture a visualization as PNG image data.

    Args:
        analysis: QuestionAnalysis object

    Returns:
        PNG image bytes or None if capture fails
    """
    try:
        # Try to get bar chart as the default visualization
        if hasattr(analysis, 'bar_chart'):
            return _capture_chart_as_png(analysis.bar_chart)
    except Exception:
        pass

    return None
