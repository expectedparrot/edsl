"""
ThemeFinder module for Reports.

This module contains the ThemeFinder class which analyzes free text survey responses
to identify common themes and sentiment patterns. It uses Large Language Models (LLMs)
through the EDSL framework to process and categorize responses.

The ThemeFinder provides methods to:
- Identify common themes in text responses
- Analyze sentiment associated with each theme
- Generate visualizations of theme distributions and sentiment patterns
- Sample and process large sets of text responses for analysis
"""

import random
from typing import List, Optional

import pandas as pd
import altair as alt
import numpy as np
import functools


from edsl import Scenario, ScenarioList, Agent
from edsl import QuestionMultipleChoice, QuestionCheckBox, QuestionList
from edsl import Results

from .warning_utils import print_warning


def cached_property(func):
    """
    Decorator that converts a method into a cached property.

    This decorator implements a lazy property pattern where the result of the decorated
    method is cached after first access, improving performance for expensive operations.

    Args:
        func: The method to convert into a cached property

    Returns:
        A property that caches its value after first access
    """
    cache_name = f"_cache_{func.__name__}"

    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        # Initialize cache dict if it doesn't exist
        if not hasattr(self, "_cache"):
            self._cache = {}

        # Check if result is already cached
        if cache_name not in self._cache:
            # Execute the function and store result in cache
            self._cache[cache_name] = func(self, *args, **kwargs)

        return self._cache[cache_name]

    return property(wrapper)


class ThemeFinder:
    """
    A class for analyzing themes and sentiment in free text survey responses.

    ThemeFinder processes a list of text responses using LLMs to identify common themes,
    assigns responses to these themes, and analyzes sentiment associated with each theme.
    It also provides visualization capabilities for the results.

    Attributes:
        answers (List[str]): The list of text responses to analyze
        question (str): The question text that prompted the responses
        context (Optional[str]): Additional context about the survey (optional)
        MAX_PER_ANSWER_CHARACTER_LENGTH (int): Maximum length for any single answer
        MAX_SAMPLE_STRING_LENGTH (int): Maximum combined length for sampled answers
        _cache (Dict): Cache for storing the results of expensive operations
    """

    MAX_PER_ANSWER_CHARACTER_LENGTH = 10_000
    MAX_SAMPLE_STRING_LENGTH = 100_000

    def __init__(
        self, answers: List[str], question: str, context: Optional[str] = None
    ):
        """
        Initialize a new ThemeFinder instance.

        Args:
            answers: List of text responses to analyze
            question: The question text that prompted these responses
            context: Additional context about the survey (optional)

        Raises:
            ValueError: If question is not a string or answers is not a non-empty list
        """
        self.answers = answers
        self.question = question
        self.context = context

        if not isinstance(self.question, str):
            raise ValueError(
                "Question must be a string---you probably meant to pass the question_text"
            )

        # Validate answers
        if not self.answers or not isinstance(self.answers, list):
            raise ValueError("Answers must be a non-empty list of responses")

        # Check if all answers are numeric (might be linear scale responses)
        if all(
            isinstance(a, (int, float)) or (isinstance(a, str) and a.isdigit())
            for a in self.answers
            if a is not None
        ):
            from .warning_utils import print_info

            print_info(
                "All answers appear to be numeric. ThemeFinder works best with text responses."
            )
            # Convert numeric answers to strings for processing
            self.answers = [str(a) if a is not None else None for a in self.answers]

    @cached_property
    def sample_answers(self) -> str:
        """
        Get a representative sample of answers for theme analysis.

        This cached property returns a concatenated string of answers that will
        be used for theme identification. The answers are sampled to stay within
        size limits for efficient processing by LLMs.

        Returns:
            A string with concatenated answer samples
        """
        return self._get_sample_answers()

    @cached_property
    def answer_ratings(self) -> Results:
        """
        Get usefulness ratings for each answer.

        This cached property evaluates each answer on a 1-10 scale based on:
        - Clarity of expression
        - Depth of thought
        - Relevance to the question
        - Concreteness of recommendations
        - Originality of recommendations

        Returns:
            Results object containing ratings for each answer
        """
        return self._get_answers_ratings()

    def _get_answers_ratings(self) -> Results:
        """
        Internal method to generate ratings for each answer's usefulness.

        Uses an LLM to rate each answer on a scale of 1-10 based on multiple
        criteria including clarity, depth, relevance, concreteness, and originality.

        Returns:
            Results object containing the ratings for each answer
        """
        from edsl import QuestionLinearScale

        q_rating = QuestionLinearScale(
            question_text="""
        <survey_context>
            {{ scenario.context }}                 
        </survey_context>

        <question_being_asked>
            {{ scenario.question }}
        </question_being_asked>
                                    
        <one_answer>
            {{ scenario.answer }}
        </one_answer>
                                       
        We want to identify the most useful answers.
        Please rate the following answers on a scale of 1 to 10, where 1 is the least useful and 10 is the most useful.
        You can use the following criteria to help you rate the answers:
        Criteria: 
        - Clarity of expression
           * 0 points: The answer is not clear or understandable.
           * 1 point: The answer is somewhat clear or understandable.
           * 2 points: The answer is clear and understandable.
        - Depth of thought
           * 0 points: The answer is not deep or thoughtful.
           * 1 point: The answer is somewhat deep or thoughtful.
           * 2 points: The answer is deep and thoughtful.
        - Relevance to the question
           * 0 points: The answer is not relevant to the question.
           * 1 point: The answer is somewhat relevant to the question.
           * 2 points: The answer is relevant to the question.
        - Concreteness of the recommendations
           * 0 points: The answer is not concrete or actionable.
           * 1 point: The answer is somewhat concrete or actionable.
           * 2 points: The answer is concrete and actionable.
        - Originality of the recommendations
           * 0 points: The recommendation is not original or creative or not recommendation was made.
           * 1 point: The recommendation is somewhat original or creative.
           * 2 points: The recommendation is original and creative.
        """,
            question_name="rating",
            question_options=list(range(1, 11)),
        )
        sl = (
            ScenarioList.from_list("answer", self.answers)
            .add_value("context", self.context)
            .add_value("question", self.question)
        )
        return q_rating.by(sl).run(verbose=False, stop_on_exception=True)

    def _get_sample_answers(self, seed: str = "reports") -> str:
        """
        Process and prepare a sample of answers for analysis.

        This method:
        1. Filters out None values
        2. Truncates overly long answers
        3. Shuffles answers for better diversity
        4. Concatenates answers up to the maximum allowed length

        Returns:
            A string containing concatenated answer samples separated by a delimiter
        """
        random.seed(seed)
        # Filter out None values and truncate long answers
        valid_answers = []
        for answer in self.answers:
            if answer is None:
                continue

            # Convert to string if necessary
            answer_str = str(answer)

            # Truncate if needed
            if len(answer_str) > self.MAX_PER_ANSWER_CHARACTER_LENGTH:
                answer_str = answer_str[: self.MAX_PER_ANSWER_CHARACTER_LENGTH]

            valid_answers.append(answer_str)

        # If no valid answers, create a dummy one to avoid errors
        if not valid_answers:
            print_warning("No valid answers found, adding placeholder")
            valid_answers = ["No valid response provided"]

        # Shuffle the answers for variety
        random.shuffle(valid_answers)

        # Join answers with delimiter until max length reached
        delimiter = "NEXT ANSWER:"
        result = []
        total_length = 0

        for answer in valid_answers:
            answer_length = len(answer) + len(delimiter)
            if total_length + answer_length > self.MAX_SAMPLE_STRING_LENGTH:
                break
            result.append(answer)
            total_length += answer_length

        # print(f"Processed {len(result)} answers out of {len(valid_answers)} valid answers")

        return delimiter.join(result)

    @property
    def themes(self) -> List[str]:
        """
        Get the list of identified themes.

        This property extracts the themes identified by the LLM from the
        themes_results object.

        Returns:
            List of theme strings identified in the responses
        """
        return self.themes_results.select("answer.themes").to_list()[0]

    @cached_property
    def themes_results(self) -> Results:
        """
        Get the full results of theme identification.

        This cached property contains the complete Results object from
        the theme identification process, which includes metadata and
        additional information beyond just the theme list.

        Returns:
            Results object with the theme identification data
        """
        return self._get_themes_results()

    def _get_themes_results(self, num_themes: int = 7) -> Results:
        """
        Internal method to identify themes in the responses.

        Uses an LLM to analyze the sampled answers and identify common themes
        that can be used to categorize the responses.

        Args:
            num_themes: Target number of themes to identify (default: 7)

        Returns:
            Results object containing the identified themes
        """
        a = Agent(
            traits={
                "skills": "You are an expert in the field of survey analysis and theme identification."
            }
        )
        s = Scenario(
            {
                "context": self.context,
                "question": self.question,
                "comment_sample": self.sample_answers,
                "num_themes": num_themes,
            }
        )
        # print("Running with scenario: ", str(s))
        q = QuestionList(
            question_text="""
        <survey_context>
            {{ scenario.context }}                 
        </survey_context>

        <question_being_asked>
            {{ scenario.question }}
        </question_being_asked>
            
        <answer_sample>
           {{ scenario.comment_sample }}.
        </answer_sample>    
        
        Please give about {{ scenario.num_themes }} themes by which these answers could be classified.
        """,
            question_name="themes",
        )
        return q.by(s).by(a).run(verbose=False, stop_on_exception=True)

    def word_cloud(self) -> None:
        """
        Generate and display a word cloud visualization of the responses.

        This method creates a word cloud from all the text responses,
        which visually represents the frequency of words in the text,
        with more frequent words appearing larger.

        Note:
            This method requires matplotlib and wordcloud packages.
            It displays the visualization directly and doesn't return anything.
        """
        try:
            from wordcloud import WordCloud
            import matplotlib.pyplot as plt
        except ImportError:
            print_warning(
                "wordcloud or matplotlib package not found. Please install with: pip install wordcloud matplotlib"
            )
            return

        # Create wordcloud from text
        text = "".join(str(a) for a in self.answers if a is not None)
        wordcloud = WordCloud(width=800, height=400, background_color="white").generate(
            text
        )
        # Display the wordcloud
        plt.figure(figsize=(10, 5))
        plt.imshow(wordcloud, interpolation="bilinear")
        plt.axis("off")
        plt.tight_layout()
        plt.show()
        # return results

    @cached_property
    def answer_theme_results(self) -> Results:
        """
        Get results of theme assignment for each answer.

        This cached property contains the mapping between individual responses
        and the themes they are associated with. Each response can be associated
        with multiple themes.

        Returns:
            Results object with theme assignments for each answer
        """
        return self._get_answer_theme_results()

    def _get_answer_theme_results(self) -> Results:
        """
        Internal method to assign themes to each answer.

        Uses an LLM to analyze each response and determine which of the
        identified themes apply to it. This allows for responses to be
        categorized by theme for further analysis.

        Returns:
            Results object with theme assignments for each answer
        """
        q_themes = QuestionCheckBox(
            question_text="""
        <survey_context>
            {{ scenario.context }}                 
        </survey_context>

        <question_being_asked>
            {{ scenario.question }}
        </question_being_asked>
                                    
        <one_answer>
            {{ scenario.answer }}
        </one_answer>

        We want to identify which themes this comment touches upon.
        """,
            question_name="relevant_theme",
            question_options=self.themes,
        )
        sl = (
            ScenarioList.from_list("answer", self.answers)
            .add_value("context", self.context)
            .add_value("question", self.question)
        )
        return q_themes.by(sl).run(verbose=False)

    @cached_property
    def sentiment_by_theme_results(self) -> Results:
        """
        Get sentiment analysis results for each theme.

        This cached property contains the sentiment assessment for each
        response with respect to each theme it covers. The sentiment
        is categorized from "Very Negative" to "Very Positive".

        Returns:
            Results object with sentiment analysis data by theme
        """
        return self._get_sentiment_by_theme_results()

    def _get_sentiment_by_theme_results(self) -> Results:
        """
        Internal method to analyze sentiment by theme.

        Uses an LLM to determine the sentiment expressed in each response
        with respect to each theme it covers. This allows for analysis of
        sentiment patterns across different themes.

        Returns:
            Results object with sentiment analysis data by theme
        """
        scenario = (
            self.answer_theme_results.select(
                "context", "question", "answer", "relevant_theme"
            )
            .remove_prefix()
            .expand("relevant_theme")
        )

        q_sentiment = QuestionMultipleChoice(
            question_text="""
        <survey_context>
            {{ scenario.context }}                 
        </survey_context>

        <question_being_asked>
            {{ scenario.question }}
        </question_being_asked>
                                    
        <one_answer>
            {{ scenario.answer }}
        </one_answer>
        This comment was classified as belonging, in part, to the theme: '{{ scenario.relevant_theme }}'
        What was the sentiment of the comment with respect to that theme?
        """,
            question_options=[
                "Very Negative",
                "Negative",
                "Neutral/NA",
                "Positive",
                "Very Positive",
            ],
            question_name="sentiment",
        )
        return q_sentiment.by(scenario).run(verbose=False)

    @cached_property
    def suggestions(self) -> Results:
        """
        Get suggestions extracted from the answers.

        This cached property analyzes each answer to identify if it contains
        a suggestion for improvement, and if so, extracts a succinct version
        of that suggestion.

        Returns:
            Results object containing:
            - has_suggestion: Boolean indicating if the answer contains a suggestion
            - suggestion_text: The extracted suggestion text (if any)
        """
        return self._get_suggestions()

    def _get_suggestions(self) -> Results:
        """
        Internal method to identify and extract suggestions from answers.

        Uses an LLM to analyze each answer and determine if it contains
        a suggestion for improvement. If a suggestion is found, it extracts
        a succinct version of that suggestion.

        Returns:
            Results object with suggestion analysis data
        """
        from edsl import QuestionYesNo, QuestionFreeText

        # First question: Does this answer contain a suggestion?
        q_has_suggestion = QuestionYesNo(
            question_text="""
            <survey_context>
                {{ scenario.context }}                 
            </survey_context>

            <question_being_asked>
                {{ scenario.question }}
            </question_being_asked>
                                        
            <one_answer>
                {{ scenario.answer }}
            </one_answer>

            Does this answer contain a specific suggestion for improvement or change?
            A suggestion should be actionable and directed at the organizers or those who can make changes.
            """,
            question_name="has_suggestion",
        )

        # Second question: If there is a suggestion, what is it?
        q_suggestion_text = QuestionFreeText(
            question_text="""
            <survey_context>
                {{ scenario.context }}                 
            </survey_context>

            <question_being_asked>
                {{ scenario.question }}
            </question_being_asked>
                                        
            <one_answer>
                {{ scenario.answer }}
            </one_answer>

            If this answer contains a suggestion, please extract it in a clear, succinct form.
            Focus on the actionable recommendation, not the context or explanation.
            If there is no suggestion, write "No suggestion".
            """,
            question_name="suggestion_text",
        )

        # Create scenario list
        sl = (
            ScenarioList.from_list("answer", self.answers)
            .add_value("context", self.context)
            .add_value("question", self.question)
        )

        from edsl import Survey

        s = Survey([q_has_suggestion, q_suggestion_text]).add_stop_rule(
            "has_suggestion", "{{ has_suggestion.answer }} == 'No'"
        )

        # Run both questions
        results = s.by(sl).run(verbose=False)

        return results

    # First, let's prepare the data
    # We need to count occurrences and calculate percentages per theme
    @staticmethod
    def prepare_data(df: pd.DataFrame) -> pd.DataFrame:
        """
        Prepare sentiment data for visualization.

        This method processes raw sentiment data to calculate percentages,
        standard errors, and confidence intervals. It also ensures that
        all possible sentiment values are included for each theme.

        Args:
            df: DataFrame containing raw sentiment data with 'relevant_theme'
                and 'sentiment' columns

        Returns:
            Processed DataFrame with counts, percentages, and statistics
        """
        # Ensure sentiment has the correct order
        sentiment_order = [
            "Very Negative",
            "Negative",
            "Neutral/NA",
            "Positive",
            "Very Positive",
        ]

        # Count occurrences by theme and sentiment
        theme_sentiment_counts = (
            df.groupby(["relevant_theme", "sentiment"]).size().reset_index(name="count")
        )

        # Calculate total counts per theme
        theme_totals = (
            theme_sentiment_counts.groupby("relevant_theme")["count"]
            .sum()
            .reset_index(name="total")
        )

        # Merge to get percentage
        result = pd.merge(theme_sentiment_counts, theme_totals, on="relevant_theme")
        result["percentage"] = result["count"] / result["total"] * 100

        # Calculate standard error
        # For proportions, std_error = sqrt(p * (1-p) / n)
        result["std_error"] = np.sqrt(
            (result["percentage"] / 100)
            * (1 - result["percentage"] / 100)
            / result["total"]
        )

        # Confidence intervals
        result["ci_lower"] = result["percentage"] - 1.96 * result["std_error"]
        result["ci_upper"] = result["percentage"] + 1.96 * result["std_error"]

        # Make sure we include all possible sentiment values for each theme
        # Create a complete grid of all theme-sentiment combinations
        all_themes = result["relevant_theme"].unique()

        # Create a complete grid
        grid = pd.MultiIndex.from_product(
            [all_themes, sentiment_order], names=["relevant_theme", "sentiment"]
        ).to_frame(index=False)

        # Merge with the existing data
        result = pd.merge(grid, result, on=["relevant_theme", "sentiment"], how="left")

        # Fill NAs with zeros
        result.fillna(
            {
                "count": 0,
                "total": 0,
                "percentage": 0,
                "std_error": 0,
                "ci_lower": 0,
                "ci_upper": 0,
            },
            inplace=True,
        )

        # For rows where total is 0, copy the total from other rows with the same theme
        if (result["total"] == 0).any():
            totals_by_theme = result.loc[
                result["total"] > 0, ["relevant_theme", "total"]
            ].drop_duplicates()
            result = result.merge(
                totals_by_theme,
                on="relevant_theme",
                how="left",
                suffixes=("", "_filled"),
            )
            result.loc[result["total"] == 0, "total"] = result.loc[
                result["total"] == 0, "total_filled"
            ]
            result.drop("total_filled", axis=1, inplace=True)

        return result

    def create_sentiment_chart(
        self, facet_column: str = "relevant_theme", columns: int = 4
    ) -> alt.Chart:
        """
        Create a faceted bar chart of sentiment analysis.

        This method generates a visualization of sentiment distribution across
        different themes. Each theme has its own facet showing the percentage
        of responses in each sentiment category from Very Negative to Very Positive.

        Args:
            facet_column: The column to use for faceting (default: 'relevant_theme')
            columns: Number of columns in the facet grid (default: 4)

        Returns:
            Altair chart object ready for display
        """
        raw_df = self.sentiment_by_theme_results.select(
            "relevant_theme", "sentiment"
        ).to_pandas(remove_prefix=True)
        df = self.prepare_data(raw_df)
        # Define the color scheme with colors matching sentiment order
        color_scale = alt.Scale(
            domain=[
                "Very Negative",
                "Negative",
                "Neutral/NA",
                "Positive",
                "Very Positive",
            ],
            range=["#8B0000", "#FF4500", "#FFFFFF", "#90EE90", "#006400"],
        )
        # Sort themes by total count
        theme_totals = (
            df.groupby("relevant_theme")["count"].sum().sort_values(ascending=False)
        )
        theme_order = theme_totals.index.tolist()

        # Create the base chart - bars with black outline
        bars = (
            alt.Chart(df)
            .mark_bar(stroke="black")
            .encode(
                x=alt.X(
                    "sentiment:N",
                    sort=[
                        "Very Negative",
                        "Negative",
                        "Neutral/NA",
                        "Positive",
                        "Very Positive",
                    ],
                    axis=alt.Axis(labelAngle=45, title="Sentiment"),
                ),
                y=alt.Y("percentage:Q", title="Percentage"),
                color=alt.Color(
                    "sentiment:N",
                    scale=color_scale,
                    legend=alt.Legend(title="Sentiment", orient="right"),
                ),
                tooltip=[facet_column, "sentiment", "percentage", "count", "total"],
            )
        )

        # Add points at the top of each bar
        points = (
            alt.Chart(df)
            .mark_point(size=40)
            .encode(
                x=alt.X(
                    "sentiment:N",
                    sort=[
                        "Very Negative",
                        "Negative",
                        "Neutral/NA",
                        "Positive",
                        "Very Positive",
                    ],
                ),
                y="percentage:Q",
            )
        )

        # Add error bars
        error_bars = (
            alt.Chart(df)
            .mark_errorbar(ticks=True)
            .encode(
                x=alt.X(
                    "sentiment:N",
                    sort=[
                        "Very Negative",
                        "Negative",
                        "Neutral/NA",
                        "Positive",
                        "Very Positive",
                    ],
                ),
                y="ci_lower:Q",
                y2="ci_upper:Q",
            )
        )

        # Combine the layers and apply faceting with ordered themes
        chart = (
            (bars + points + error_bars)
            .facet(
                facet=alt.Facet(
                    f"{facet_column}:N", title=None, sort=theme_order
                ),  # Sort facets by theme order
                columns=columns,
            )
            .resolve_scale(y="independent")
        )

        # Set the width and height for the base charts (before faceting)
        bars = bars.properties(width=200, height=200)
        points = points.properties(width=200, height=200)
        error_bars = error_bars.properties(width=200, height=200)

        # Apply theme similar to theme_bw() in ggplot
        chart = chart.configure_view(stroke="black", strokeWidth=0.25).configure_axis(
            domainColor="black", gridColor="lightgray", gridOpacity=0.5
        )
        return chart

    def create_sentiment_dot_chart(self, columns: int = 4) -> alt.Chart:
        """
        Create a dot chart showing individual responses colored by sentiment.

        This visualization shows each response as a colored dot stacked vertically,
        with tooltips showing the actual comment text. Each theme is its own facet,
        sentiment is on the x-axis, and dots are stacked on the y-axis.

        Args:
            columns: Number of columns in the facet grid (default: 4)

        Returns:
            Altair chart object ready for display
        """
        # Get the raw data with individual responses
        raw_df = self.sentiment_by_theme_results.select(
            "relevant_theme", "sentiment", "answer"
        ).to_pandas(remove_prefix=True)

        # Create a ranking for each response within theme/sentiment combination to stack dots
        raw_df["y_position"] = (
            raw_df.groupby(["relevant_theme", "sentiment"]).cumcount() + 1
        )

        # Define the color scheme matching the existing sentiment chart
        color_scale = alt.Scale(
            domain=[
                "Very Negative",
                "Negative",
                "Neutral/NA",
                "Positive",
                "Very Positive",
            ],
            range=["#8B0000", "#FF4500", "#FFFFFF", "#90EE90", "#006400"],
        )

        # Sort themes by total count for consistent ordering
        theme_totals = (
            raw_df.groupby("relevant_theme").size().sort_values(ascending=False)
        )
        theme_order = theme_totals.index.tolist()

        # Create the dot chart
        chart = (
            alt.Chart(raw_df)
            .mark_circle(size=60, stroke="black", strokeWidth=1, opacity=0.8)
            .encode(
                x=alt.X(
                    "sentiment:N",
                    sort=[
                        "Very Negative",
                        "Negative",
                        "Neutral/NA",
                        "Positive",
                        "Very Positive",
                    ],
                    axis=alt.Axis(labelAngle=45, title="Sentiment"),
                ),
                y=alt.Y(
                    "y_position:O",
                    axis=alt.Axis(
                        title="Responses (stacked)", labels=False, ticks=False
                    ),
                ),
                color=alt.Color(
                    "sentiment:N",
                    scale=color_scale,
                    legend=alt.Legend(title="Sentiment", orient="right"),
                ),
                tooltip=["relevant_theme:N", "sentiment:N", "answer:N"],
            )
            .properties(width=200, height=200)
            .facet(
                facet=alt.Facet("relevant_theme:N", title=None, sort=theme_order),
                columns=columns,
            )
            .resolve_scale(y="independent")
        )

        # Apply consistent styling
        chart = (
            chart.configure_view(stroke="black", strokeWidth=0.25)
            .configure_axis(domainColor="black", gridColor="lightgray", gridOpacity=0.5)
            .configure_facet(spacing=10)
        )

        return chart

    def create_theme_counts_chart(self) -> alt.Chart:
        """
        Create a bar chart showing the count of responses for each theme.

        This method generates a visualization of the number of responses
        associated with each identified theme, sorted by frequency.

        Returns:
            Altair chart object ready for display
        """
        # Get the raw data from answer_theme_results and convert to pandas
        try:
            raw_df = (
                self.answer_theme_results.select("answer", "relevant_theme")
                .remove_prefix()
                .expand("relevant_theme")
                .to_pandas()
            )
        except Exception as e:
            print(f"Error in expand operation: {e}")
            print(
                f"Data structure: {self.answer_theme_results.select('answer', 'relevant_theme').remove_prefix()}"
            )
            raise
        theme_counts = (
            raw_df.explode("relevant_theme")
            .groupby("relevant_theme")
            .size()
            .reset_index(name="count")
        )

        # Sort by count in descending order
        theme_counts = theme_counts.sort_values("count", ascending=False)

        # Create the bar chart
        chart = (
            alt.Chart(theme_counts)
            .mark_bar(stroke="black", cornerRadius=2)
            .encode(
                x=alt.X(
                    "relevant_theme:N",
                    sort="-y",
                    title="Theme",
                    axis=alt.Axis(labelAngle=45),
                ),
                y=alt.Y("count:Q", title="Number of Responses"),
                tooltip=["relevant_theme", "count"],
            )
            .properties(width=600, height=400, title="Response Counts by Theme")
        )

        # Add text labels on top of the bars
        text = chart.mark_text(align="center", baseline="bottom", dy=-5).encode(
            text="count:Q"
        )

        # Combine chart and text, and apply styling
        final_chart = (
            (chart + text)
            .configure_view(stroke="black", strokeWidth=0.25)
            .configure_axis(domainColor="black", gridColor="lightgray", gridOpacity=0.5)
        )

        return final_chart

    def create_sentiment_examples_chart(
        self,
        max_examples: int = 2,
        columns: int = 2,
        chars_per_line: int = 60,
        random_seed: int = 42,
    ) -> alt.Chart:
        """
        Create a faceted chart showing example answers for each sentiment level within each theme.

        This method uses the sentiment_by_theme_results to create a visualization where each facet
        represents a theme, showing example quotes for each sentiment level.

        Args:
            max_examples: Maximum number of examples to show for each sentiment level (default: 2)
            columns: Number of columns in the facet grid (default: 2)
            chars_per_line: Number of characters per line before wrapping (default: 60)
            random_seed: Random seed for reproducible quote selection (default: 42)

        Returns:
            Altair chart object ready for display
        """
        # Get the data from sentiment_by_theme_results
        sentiment_df = self.sentiment_by_theme_results.select(
            "relevant_theme", "sentiment", "answer"
        ).to_pandas(remove_prefix=True)

        # Use the static method to create the chart
        return self.create_sentiment_examples_chart_from_data(
            data=sentiment_df,
            max_examples=max_examples,
            columns=columns,
            chars_per_line=chars_per_line,
            random_seed=random_seed,
        )

    def create_all_responses_table(
        self, max_response_length: int = 300
    ) -> pd.DataFrame:
        """
        Create a table showing all responses and the themes they were labeled with.

        This method generates a DataFrame where each row represents a response and
        the themes that were assigned to it. This provides a comprehensive view of
        how each individual response was categorized.

        Args:
            max_response_length: Maximum length for displayed responses (default: 300)

        Returns:
            DataFrame with columns 'Response' and 'Themes' showing all responses and
            their assigned themes
        """
        # Get the answer-theme mapping data
        raw_df = self.answer_theme_results.select("answer", "relevant_theme").to_pandas(
            remove_prefix=True
        )

        # Group by answer to collect all themes for each answer
        grouped = raw_df.groupby("answer")["relevant_theme"].apply(list).reset_index()

        # Create a more readable format for the themes
        grouped["Themes"] = grouped["relevant_theme"].apply(lambda x: ", ".join(x))

        # Truncate long responses for display
        grouped["Display Response"] = grouped["answer"].apply(
            lambda x: (str(x)[:max_response_length] + "...")
            if len(str(x)) > max_response_length
            else str(x)
        )

        # Create final DataFrame with selected columns
        result_df = pd.DataFrame(
            {"Response": grouped["Display Response"], "Themes": grouped["Themes"]}
        )

        return result_df

    def create_all_responses_html_table(self, max_response_length: int = 300) -> str:
        """
        Create an HTML table showing all responses and their assigned themes.

        This method generates a formatted HTML table where each row represents a response
        and the themes that were assigned to it, suitable for inclusion in reports.
        Uses a scrollable interface with a sticky header for better usability.

        Args:
            max_response_length: Maximum length for displayed responses (default: 300)

        Returns:
            HTML string containing a formatted table of responses and themes with scrollable interface
        """
        # Get DataFrame
        df = self.create_all_responses_table(max_response_length=max_response_length)

        # Add row numbers as index
        df.index = df.index + 1  # Make it 1-based
        df.index.name = "Response #"

        # Style the DataFrame with scrollable container like AllResponsesTable
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
                # Header row styling with sticky positioning
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

        # Generate summary HTML
        total_responses = len(df)
        themes_count = len(self.themes)

        summary_html = f"""
        <div class="response-summary">
            <p><strong>Total Responses:</strong> {total_responses}</p>
            <p><strong>Total Themes:</strong> {themes_count}</p>
            <p><strong>Themes:</strong> {', '.join(self.themes)}</p>
        </div>
        """

        # Generate HTML for the table
        html_table = styled_df.to_html(escape=False)

        # Wrap in a container
        table_html = f"""
        <div class="custom-table-wrapper">
            {summary_html}
            {html_table}
        </div>
        """

        return table_html

    def create_sentiment_examples_chart_from_data(
        self,
        data: pd.DataFrame,
        max_examples: int = 2,
        columns: int = 2,
        chars_per_line: int = 60,
        random_seed: int = 42,
    ) -> alt.Chart:
        """
        Create a faceted chart showing example answers for each sentiment level within each theme.

        Args:
            data: DataFrame with columns ['relevant_theme', 'sentiment', 'answer']
            max_examples: Maximum number of examples to show for each sentiment level (default: 2)
            columns: Number of columns in the facet grid (default: 2)
            chars_per_line: Number of characters per line before wrapping (default: 60)
            random_seed: Random seed for reproducible quote selection (default: 42)

        Returns:
            Altair chart object ready for display
        """
        # Set random seed for reproducibility
        np.random.seed(random_seed)

        def split_text(text: str, width: int) -> tuple[str, str]:
            """Split text into two lines of specified width."""
            if len(text) <= width:
                return text, ""

            # Find the last space before the wrap point
            wrap_point = text.rfind(" ", 0, width)
            if wrap_point == -1:  # No space found
                wrap_point = width

            # Split into two lines
            line1 = text[:wrap_point].strip()
            line2 = text[wrap_point:].strip()

            # Truncate second line if needed
            if len(line2) > width:
                line2 = line2[:width] + "..."

            return line1, line2

        # Randomly sample one quote per theme-sentiment combination
        data = data.copy()
        data = (
            data.groupby(["relevant_theme", "sentiment"])
            .apply(lambda x: x.sample(n=1) if len(x) > 0 else x)
            .reset_index(drop=True)
        )

        # Split text into two lines for each answer
        split_results = data["answer"].apply(lambda x: split_text(x, chars_per_line))
        data["line1"] = split_results.apply(lambda x: x[0])
        data["line2"] = split_results.apply(lambda x: x[1])

        # Define the sentiment order (from positive to negative)
        sentiment_order = [
            "Very Positive",
            "Positive",
            "Neutral/NA",
            "Negative",
            "Very Negative",
        ]

        # Define the color scheme
        color_scale = alt.Scale(
            domain=sentiment_order,
            range=["#006400", "#90EE90", "#000000", "#FF4500", "#8B0000"],
        )

        # Sort themes by total count
        theme_totals = (
            data.groupby("relevant_theme").size().sort_values(ascending=False)
        )
        theme_order = theme_totals.index.tolist()

        # Ensure all themes have all sentiment levels by creating a complete grid
        themes = data["relevant_theme"].unique()
        complete_grid = pd.DataFrame(
            [
                {"relevant_theme": theme, "sentiment": sentiment}
                for theme in themes
                for sentiment in sentiment_order
            ]
        )

        # Merge with existing data, keeping all combinations
        data = pd.merge(
            complete_grid, data, on=["relevant_theme", "sentiment"], how="left"
        )

        # Fill missing answers with empty string
        data["line1"] = data["line1"].fillna("")
        data["line2"] = data["line2"].fillna("")

        # Create the base chart with fixed y-axis
        base = alt.Chart(data).encode(
            y=alt.Y(
                "sentiment:N",
                sort=sentiment_order,
                axis=alt.Axis(title="Sentiment"),
                scale=alt.Scale(domain=sentiment_order),
            )
        )

        # Create text marks for line 1
        text1 = (
            base.mark_text(
                align="left",
                baseline="bottom",  # Position at bottom of allocated space
                dx=5,
                dy=-4,  # Shift up slightly
                fontSize=11,
            )
            .encode(
                x=alt.value(10),
                text="line1:N",
                color=alt.Color("sentiment:N", scale=color_scale, legend=None),
            )
            .transform_window(
                row_number="row_number()", groupby=["relevant_theme", "sentiment"]
            )
            .transform_filter(alt.datum.row_number <= max_examples)
        )

        # Create text marks for line 2
        text2 = (
            base.mark_text(
                align="left",
                baseline="top",  # Position at top of allocated space
                dx=5,
                dy=4,  # Shift down slightly
                fontSize=11,
            )
            .encode(
                x=alt.value(10),
                text="line2:N",
                color=alt.Color("sentiment:N", scale=color_scale, legend=None),
            )
            .transform_window(
                row_number="row_number()", groupby=["relevant_theme", "sentiment"]
            )
            .transform_filter(alt.datum.row_number <= max_examples)
        )

        # Create light background rectangles (no color variation)
        rect = base.mark_rect(opacity=0.1, color="#F0F0F0").encode(
            x=alt.value(0), x2=alt.value(400)
        )

        # Layer the charts and configure the faceting
        chart = (
            (rect + text1 + text2)
            .properties(width=400, height=300)
            .facet(
                facet=alt.Facet("relevant_theme:N", title=None, sort=theme_order),
                columns=columns,
            )
        )

        # Apply styling
        chart = chart.configure_view(stroke="black", strokeWidth=0.25).configure_axis(
            domainColor="black", gridColor="lightgray", gridOpacity=0.5
        )

        return chart

    @classmethod
    def example(cls) -> "ThemeFinder":
        """
        Create an example ThemeFinder instance with sample data.

        This class method provides a convenient way to create a ThemeFinder
        instance pre-populated with sample data for demonstration purposes.

        Returns:
            A fully initialized ThemeFinder instance with sample data
        """
        context = """We are conducting a survey about people's experiences with remote work during the COVID-19 pandemic."""

        question = """What challenges have you faced while working remotely, and what solutions have you found most helpful?"""

        sample_answers = [
            "The biggest challenge was maintaining work-life balance. I started using a dedicated office space and strict working hours to separate work from personal time.",
            "Poor internet connectivity was a major issue. I invested in a better router and backup internet connection which helped tremendously.",
            "I struggled with team communication at first. We implemented daily virtual stand-ups and started using Slack more effectively.",
            "Staying focused with kids at home was difficult. Creating a schedule with my spouse for childcare duties and using noise-canceling headphones helped.",
            "The lack of social interaction affected my mental health. Regular virtual coffee chats with colleagues and online team building activities made a difference.",
            "Screen fatigue was real. I started taking regular breaks using the 20-20-20 rule and adjusted my monitor settings.",
            "Missing casual office conversations impacted collaboration. We created virtual water cooler channels and informal video calls to maintain team bonding.",
            "My home office setup wasn't ergonomic. Investing in a proper desk and chair resolved my back pain issues.",
        ]

        return cls(answers=sample_answers, question=question, context=context)

    @classmethod
    def from_data(
        cls, data, question_name: str, question_text: str, context: Optional[str] = None
    ) -> "ThemeFinder":
        """
        Create a ThemeFinder instance from a data object containing survey responses.

        Args:
            data: A data object (e.g., EDSL Results) containing survey responses
            question_name: The name of the column/field containing the responses
            question_text: The actual question text that was asked
            context: Optional context about the survey (default: None)

        Returns:
            ThemeFinder: A new ThemeFinder instance initialized with the filtered responses

        Example:
            >>> data = Results(...)  # Some EDSL Results object
            >>> tf = ThemeFinder.from_data(
            ...     data=data,
            ...     question_name='feedback_comments',
            ...     question_text='What feedback do you have about the event?'
            ... )
        """
        # Filter out None values from the data
        filtered_data = data.select(question_name).filter(f"{question_name} != None")

        # Convert to list of responses
        answers = filtered_data.to_list()

        # Create and return new instance
        return cls(answers=answers, question=question_text, context=context)

    @staticmethod
    def create_sample_sentiment_data() -> pd.DataFrame:
        """Create sample data for sentiment examples chart."""
        data = {
            "relevant_theme": [
                "Work-Life Balance",
                "Work-Life Balance",
                "Work-Life Balance",
                "Work-Life Balance",
                "Work-Life Balance",
                "Communication",
                "Communication",
                "Communication",
                "Communication",
                "Communication",
                "Technology",
                "Technology",
                "Technology",
                "Technology",
                "Technology",
                "Productivity",
                "Productivity",
                "Productivity",
                "Productivity",
                "Productivity",
            ],
            "sentiment": [
                "Very Positive",
                "Positive",
                "Neutral/NA",
                "Negative",
                "Very Negative",
                "Very Positive",
                "Positive",
                "Neutral/NA",
                "Negative",
                "Very Negative",
                "Very Positive",
                "Positive",
                "Neutral/NA",
                "Negative",
                "Very Negative",
                "Very Positive",
                "Positive",
                "Neutral/NA",
                "Negative",
                "Very Negative",
            ],
            "answer": [
                "Working remotely has completely transformed my work-life balance for the better - I can now have breakfast with my family, take short breaks to exercise, and still be more productive than ever before.",
                "Having a dedicated home office space and setting clear boundaries has helped me maintain a healthy separation between work and personal time, though it took some adjustment.",
                "My work-life balance remains about the same as it was in the office, just with a different daily structure that takes some getting used to.",
                "Finding the right balance has been challenging since my workspace is in my living area, making it difficult to mentally disconnect from work at the end of the day.",
                "The complete erosion of boundaries between work and personal life has been devastating - I feel like I'm perpetually on call and never truly able to relax or spend quality time with family.",
                "Our team communication has reached new heights with daily virtual stand-ups and well-structured digital collaboration - we're more connected and aligned than ever before.",
                "The transition to digital communication tools has generally improved our team's ability to stay in touch and share information, despite some occasional technical hiccups.",
                "We maintain regular communication through various channels, though sometimes messages get lost in the mix of different platforms we use.",
                "The lack of spontaneous office interactions has made it harder to build relationships and share quick updates, leading to occasional misunderstandings and delays.",
                "Virtual communication has completely broken down our once-cohesive team dynamic - critical information gets lost, meetings are chaotic, and team bonding is non-existent.",
                "Our new digital infrastructure has revolutionized how we work - seamless cloud integration, reliable video conferencing, and automated workflows have made remote work incredibly efficient.",
                "The technology we've implemented works well most of the time, with just occasional connectivity issues that are usually quick to resolve.",
                "Our current tech setup gets the job done, though we sometimes have to find workarounds for certain tasks that were easier in the office.",
                "Frequent technical issues with VPN and video calls make remote collaboration frustrating and time-consuming, impacting our ability to work effectively.",
                "The constant technical failures, system crashes, and connectivity problems have made it nearly impossible to accomplish even basic tasks - we're operating at a fraction of our normal capacity.",
                "Remote work has supercharged my productivity - zero commute time, fewer interruptions, and the ability to design my optimal work environment has led to the best work of my career.",
                "I've found that I can focus better at home once I got my workspace set up properly, though some collaborative tasks take a bit longer to coordinate.",
                "My productivity levels fluctuate depending on the day and type of work - some tasks are easier at home, while others require more effort to accomplish remotely.",
                "Staying focused at home is a constant struggle with household distractions and less structure than the office environment provided.",
                "My productivity has plummeted since working remotely - the isolation, lack of structure, and technical hurdles have made it impossible to maintain my previous performance levels.",
            ],
        }
        return pd.DataFrame(data)

    def report(self) -> str:
        """
        Generate a comprehensive HTML report of all ThemeFinder analyses.

        This method combines all major visualizations and analyses into a single
        HTML report, including:
        - Theme counts
        - Sentiment analysis by theme
        - Example quotes for each theme and sentiment
        - Word cloud (if matplotlib is available)

        Returns:
            str: HTML string containing the complete report
        """
        import tempfile
        import os
        import base64

        # Start building the HTML report
        html_parts = []

        # Add title and context
        html_parts.append(f"""<h1>Question: "{self.question}"</h1>""")

        html_parts.append(f"<h2>Question</h2><p>{self.question}</p>")

        if self.context:
            html_parts.append(f"<h2>Context</h2><p>{self.context}</p>")

        # Add summary statistics
        html_parts.append("<h2>Summary Statistics</h2>")
        html_parts.append(f"<p>Total responses analyzed: {len(self.answers)}</p>")
        html_parts.append(f"<p>Number of themes identified: {len(self.themes)}</p>")

        # Add raw responses section right after summary stats
        html_parts.append("<h2>Raw Responses</h2>")
        html_parts.append('<div class="scrollable-box responses-box">')
        html_parts.append("<ul>")
        for answer in self.answers:
            if answer:  # Only include non-empty responses
                html_parts.append(f"<li>{answer}</li>")
        html_parts.append("</ul>")
        html_parts.append("</div>")

        # Add themes list
        html_parts.append("<h2>Identified Themes</h2>")
        html_parts.append("<ul>")
        for theme in self.themes:
            html_parts.append(f"<li>{theme}</li>")
        html_parts.append("</ul>")

        # Create temporary directory for charts
        with tempfile.TemporaryDirectory() as tmpdir:
            # Add theme counts chart
            html_parts.append("<h2>Response Distribution by Theme</h2>")
            theme_counts_chart = self.create_theme_counts_chart()
            theme_counts_path = os.path.join(tmpdir, "theme_counts.png")
            theme_counts_chart.save(theme_counts_path, scale_factor=2.0)
            with open(theme_counts_path, "rb") as f:
                img_base64 = base64.b64encode(f.read()).decode()
                html_parts.append(
                    f'<img src="data:image/png;base64,{img_base64}" alt="Theme Counts" style="max-width: 100%;">'
                )

            # Add sentiment analysis chart
            html_parts.append("<h2>Sentiment Analysis by Theme</h2>")
            sentiment_chart = self.create_sentiment_chart()
            sentiment_path = os.path.join(tmpdir, "sentiment.png")
            sentiment_chart.save(sentiment_path, scale_factor=2.0)
            with open(sentiment_path, "rb") as f:
                img_base64 = base64.b64encode(f.read()).decode()
                html_parts.append(
                    f'<img src="data:image/png;base64,{img_base64}" alt="Sentiment Analysis" style="max-width: 100%;">'
                )

            # Add sentiment dot chart
            html_parts.append("<h2>Individual Responses by Sentiment</h2>")
            html_parts.append(
                "<p>Each dot represents an individual response, colored by sentiment. Hover over dots to see the actual comment.</p>"
            )
            dot_chart = self.create_sentiment_dot_chart()
            dot_path = os.path.join(tmpdir, "sentiment_dots.png")
            dot_chart.save(dot_path, scale_factor=2.0)
            with open(dot_path, "rb") as f:
                img_base64 = base64.b64encode(f.read()).decode()
                html_parts.append(
                    f'<img src="data:image/png;base64,{img_base64}" alt="Individual Responses by Sentiment" style="max-width: 100%;">'
                )

            # Add example quotes
            html_parts.append("<h2>Example Quotes by Theme and Sentiment</h2>")
            examples_chart = self.create_sentiment_examples_chart()
            examples_path = os.path.join(tmpdir, "examples.png")
            examples_chart.save(examples_path, scale_factor=2.0)
            with open(examples_path, "rb") as f:
                img_base64 = base64.b64encode(f.read()).decode()
                html_parts.append(
                    f'<img src="data:image/png;base64,{img_base64}" alt="Example Quotes" style="max-width: 100%;">'
                )

        # Try to add word cloud if matplotlib is available
        try:
            from wordcloud import WordCloud
            import matplotlib.pyplot as plt
            import io
            import base64

            html_parts.append("<h2>Word Cloud</h2>")

            # Create word cloud
            text = " ".join(str(a) for a in self.answers if a is not None)
            wordcloud = WordCloud(
                width=800, height=400, background_color="white"
            ).generate(text)

            # Save word cloud to bytes
            img_bytes = io.BytesIO()
            plt.figure(figsize=(10, 5))
            plt.imshow(wordcloud, interpolation="bilinear")
            plt.axis("off")
            plt.savefig(img_bytes, format="png", bbox_inches="tight")
            plt.close()

            # Convert to base64 and add to HTML
            img_base64 = base64.b64encode(img_bytes.getvalue()).decode()
            html_parts.append(
                f'<img src="data:image/png;base64,{img_base64}" alt="Word Cloud" style="max-width: 100%;">'
            )

        except ImportError:
            html_parts.append(
                "<p>Note: Word cloud visualization requires wordcloud and matplotlib packages.</p>"
            )

        # Add suggestions section if available
        if hasattr(self, "suggestions"):
            html_parts.append("<h2>Key Suggestions</h2>")
            suggestions_df = self.suggestions.to_pandas(remove_prefix=True)
            suggestions_with_text = suggestions_df[
                (suggestions_df["has_suggestion"] == "Yes")
                & (suggestions_df["suggestion_text"] != "No suggestion")
            ]
            if not suggestions_with_text.empty:
                html_parts.append('<div class="scrollable-box responses-box">')
                html_parts.append("<ul>")
                for suggestion in suggestions_with_text["suggestion_text"].unique():
                    html_parts.append(f"<li>{suggestion}</li>")
                html_parts.append("</ul>")
                html_parts.append("</div>")
            else:
                html_parts.append(
                    "<p>No specific suggestions identified in the responses.</p>"
                )

        # Combine all parts with some basic styling
        style = """
        <style>
            .themefinder-report {
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
                max-width: 1200px;
                margin: 0 auto;
                padding: 20px;
            }
            .themefinder-report h1 { color: #2c3e50; }
            .themefinder-report h2 { 
                color: #34495e;
                margin-top: 30px;
            }
            .themefinder-report p { line-height: 1.6; }
            .themefinder-report ul { margin-bottom: 20px; }
            .themefinder-report li { margin-bottom: 8px; }
            .themefinder-report img {
                margin: 20px 0;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }
            .themefinder-report .scrollable-box {
                max-height: 300px;
                overflow-y: auto;
                border: 1px solid #e0e0e0;
                border-radius: 4px;
                padding: 15px;
                background-color: #f8f9fa;
                margin: 15px 0;
            }
            .themefinder-report .responses-box {
                color: #000000;
                background-color: #ffffff;
            }
            .themefinder-report .scrollable-box ul {
                margin: 0;
                padding-left: 20px;
            }
            .themefinder-report .scrollable-box li {
                margin-bottom: 10px;
                word-wrap: break-word;
                white-space: pre-wrap;
            }
        </style>
        """

        return (
            f"{style}<div class='themefinder-report'>"
            + "\n".join(html_parts)
            + "</div>"
        )

    def _repr_html_(self) -> str:
        """
        Return HTML representation of the ThemeFinder instance.

        This method is automatically called when the object is displayed
        in a Jupyter notebook. It returns the complete HTML report.

        Returns:
            str: HTML string containing the complete report
        """
        return self.report()


if __name__ == "__main__":
    # Example 1: Using the full ThemeFinder pipeline
    # tf = ThemeFinder.example()
    # tf.create_sentiment_examples_chart(max_examples=2).show()

    # Example 2: Using the new direct data method
    sample_data = ThemeFinder.create_sample_sentiment_data()
    ThemeFinder.create_sentiment_examples_chart_from_data(
        sample_data, max_examples=2, columns=2
    ).serve()
