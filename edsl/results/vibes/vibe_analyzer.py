"""LLM-powered analyzer for generating insights from question analyses."""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional, TYPE_CHECKING
import json

if TYPE_CHECKING:
    from edsl.questions import QuestionBase
    from edsl.reports.report import QuestionAnalysis
    from openai import OpenAI


@dataclass
class VibeAnalyzer:
    """Use LLM to generate insights and commentary on question analyses.

    This class leverages OpenAI's API to provide natural language insights
    about survey question results and their visualizations.

    Args:
        model: OpenAI model to use for generation (default: "gpt-4o")
        temperature: Temperature for generation (default: 0.7)

    Examples:
        >>> analyzer = VibeAnalyzer()  # doctest: +SKIP
        >>> insights = analyzer.analyze_question_data(  # doctest: +SKIP
        ...     question_name="age",
        ...     question_text="What is your age?",
        ...     question_type="numerical",
        ...     summary_stats={"mean": 35.5, "median": 34}
        ... )  # doctest: +SKIP
    """

    model: str = "gpt-4o"
    temperature: float = 0.7
    _client: Optional["OpenAI"] = field(default=None, init=False, repr=False)

    @property
    def client(self) -> "OpenAI":
        """Lazy initialization of OpenAI client to avoid event loop issues."""
        if self._client is None:
            try:
                # Import here to avoid issues at module load time
                from openai import OpenAI as OpenAIClient
                self._client = OpenAIClient()
            except Exception as e:
                raise RuntimeError(f"Failed to initialize OpenAI client: {e}")
        return self._client

    def _extract_question_metadata(self, question: "QuestionBase") -> Dict[str, Any]:
        """Extract metadata from a question object.

        Args:
            question: Question object from the survey

        Returns:
            Dictionary with question metadata
        """
        metadata = {
            "name": question.question_name,
            "text": question.question_text,
            "type": question.question_type,
        }

        # Add question options for multiple choice questions
        if hasattr(question, "question_options") and question.question_options:
            metadata["options"] = question.question_options

        return metadata

    def analyze_question_data(
        self,
        question_name: str,
        question_text: str,
        question_type: str,
        data_summary: Optional[Dict[str, Any]] = None,
        response_distribution: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Generate natural language insights about a question's results.

        Uses an LLM to analyze the data and provide meaningful insights about
        patterns, trends, and notable findings in the responses.

        Args:
            question_name: Name/identifier of the question
            question_text: The actual question text
            question_type: Type of question (multiple_choice, numerical, etc.)
            data_summary: Summary statistics (mean, median, mode, etc.)
            response_distribution: Distribution of responses (counts, percentages)

        Returns:
            Natural language description of insights and patterns
        """
        system_prompt = (
            "You are an expert data analyst providing insights about survey results. "
            "Given information about a survey question and its response data, provide "
            "clear, concise, and actionable insights. Focus on patterns, trends, and "
            "notable findings. Be specific and quantitative where possible."
        )

        user_prompt = {
            "question": {
                "name": question_name,
                "text": question_text,
                "type": question_type,
            },
            "data_summary": data_summary or {},
            "response_distribution": response_distribution or {},
            "task": (
                "Analyze this survey question's results and provide 3-5 key insights. "
                "Include specific observations about the data patterns, distributions, "
                "and any notable trends or outliers."
            )
        }

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": json.dumps(user_prompt, indent=2)},
                ],
                temperature=self.temperature,
            )
            return response.choices[0].message.content
        except RuntimeError as e:
            if "cannot enter context" in str(e) or "already entered" in str(e):
                # Asyncio context issue - try to work around it
                import asyncio
                try:
                    # Try to get or create an event loop
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        # We're in a running loop (like Jupyter), need nest_asyncio
                        try:
                            import nest_asyncio
                            nest_asyncio.apply()
                            # Retry the call
                            response = self.client.chat.completions.create(
                                model=self.model,
                                messages=[
                                    {"role": "system", "content": system_prompt},
                                    {"role": "user", "content": json.dumps(user_prompt, indent=2)},
                                ],
                                temperature=self.temperature,
                            )
                            return response.choices[0].message.content
                        except ImportError:
                            return f"Unable to generate insights due to async context error. Try: pip install nest-asyncio"
                except Exception:
                    return f"Unable to generate insights for {question_name} due to event loop issues."
            raise
        except Exception as e:
            return f"Error generating insights for {question_name}: {str(e)}"

    def analyze_visualization(
        self,
        question_name: str,
        question_text: str,
        question_type: str,
        image_data: Optional[bytes] = None,
        visualization_type: Optional[str] = None,
    ) -> str:
        """Analyze a visualization using OpenAI's vision capabilities.

        Sends a chart/graph image to OpenAI's vision API to generate insights
        about what the visualization shows.

        Args:
            question_name: Name/identifier of the question
            question_text: The actual question text
            question_type: Type of question
            image_data: PNG/JPG image bytes of the visualization
            visualization_type: Type of visualization (bar_chart, heatmap, etc.)

        Returns:
            Natural language analysis of the visualization
        """
        system_prompt = (
            "You are an expert at analyzing data visualizations. "
            "Describe what you see in the chart, identify key patterns, "
            "trends, and insights. Be specific about the data distribution, "
            "outliers, and any notable features."
        )

        messages = [
            {"role": "system", "content": system_prompt},
        ]

        if image_data:
            # Convert image bytes to base64 for OpenAI API
            import base64
            image_base64 = base64.b64encode(image_data).decode('utf-8')

            messages.append({
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            f"This is a {visualization_type or 'chart'} for the question:\n"
                            f"'{question_text}' (question type: {question_type})\n\n"
                            f"Analyze this visualization and provide key insights about the data patterns."
                        )
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{image_base64}"
                        }
                    }
                ]
            })
        else:
            # Fallback without image
            messages.append({
                "role": "user",
                "content": (
                    f"Analyzing {visualization_type or 'visualization'} for question:\n"
                    f"'{question_text}' (type: {question_type}, name: {question_name})\n\n"
                    f"Provide general guidance on what insights this type of "
                    f"visualization typically reveals."
                )
            })

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=self.temperature,
                max_tokens=500,
            )
            return response.choices[0].message.content
        except RuntimeError as e:
            if "cannot enter context" in str(e) or "already entered" in str(e):
                try:
                    import nest_asyncio
                    nest_asyncio.apply()
                    response = self.client.chat.completions.create(
                        model=self.model,
                        messages=messages,
                        temperature=self.temperature,
                        max_tokens=500,
                    )
                    return response.choices[0].message.content
                except ImportError:
                    return f"Unable to analyze visualization. Try: pip install nest-asyncio"
                except Exception:
                    return f"Unable to analyze visualization for {question_name}."
            raise
        except Exception as e:
            return f"Error analyzing visualization for {question_name}: {str(e)}"

    def generate_summary_report(
        self,
        analyses: Dict[str, Dict[str, Any]]
    ) -> str:
        """Generate an overall summary report across all question analyses.

        Args:
            analyses: Dictionary mapping question names to their analysis results

        Returns:
            Natural language summary report
        """
        system_prompt = (
            "You are an expert at synthesizing survey insights. "
            "Given analysis results from multiple survey questions, "
            "create a cohesive summary report highlighting key themes, "
            "patterns, and actionable insights across all questions."
        )

        user_prompt = {
            "analyses": analyses,
            "task": (
                "Create a summary report that:\n"
                "1. Highlights the most important findings across all questions\n"
                "2. Identifies common themes or patterns\n"
                "3. Provides actionable recommendations\n"
                "4. Is concise (2-3 paragraphs maximum)"
            )
        }

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": json.dumps(user_prompt, indent=2)},
                ],
                temperature=self.temperature,
            )
            return response.choices[0].message.content
        except RuntimeError as e:
            if "cannot enter context" in str(e) or "already entered" in str(e):
                try:
                    import nest_asyncio
                    nest_asyncio.apply()
                    response = self.client.chat.completions.create(
                        model=self.model,
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": json.dumps(user_prompt, indent=2)},
                        ],
                        temperature=self.temperature,
                    )
                    return response.choices[0].message.content
                except ImportError:
                    return "Unable to generate summary report. Try: pip install nest-asyncio"
                except Exception:
                    return "Unable to generate summary report due to event loop issues."
            raise
        except Exception as e:
            return f"Error generating summary report: {str(e)}"
