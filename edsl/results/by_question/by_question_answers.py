"""Abstract base class for analyzing answer distributions by question type.

This module provides a framework for analyzing and visualizing the distribution of
answers for a single question across multiple survey responses. Different question
types require different analysis and visualization approaches, which are implemented
in concrete subclasses.

The ByQuestionAnswers class takes a Question object and a vector of responses,
providing question-type-specific methods for statistical analysis and terminal-based
visualization using termplotlib.
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any, List, Optional, TYPE_CHECKING, Dict
from collections import Counter

if TYPE_CHECKING:
    from ..questions.question_base import QuestionBase
    from .results import Results

import termplotlib as tpl
import numpy as np


class ByQuestionAnswers(ABC):
    """Abstract base class for analyzing answer distributions for a single question.

    This class provides a framework for analyzing how respondents answered a specific
    question. It takes a Question object (which contains question metadata like type,
    text, and options) and a list of answers from multiple survey responses.

    Subclasses implement question-type-specific analysis and visualization methods.
    For example, multiple choice questions can show bar charts of option frequencies,
    while numerical questions can show histograms of value distributions.

    Attributes:
        question: The Question object containing question metadata
        answers: List of answer values extracted from Results

    Examples:
        Creating an analyzer from Results:

        >>> from edsl import Results
        >>> results = Results.example()
        >>> analyzer = ByQuestionAnswers.from_results(results, 'how_feeling')
        >>> analyzer.summary()  # Show summary statistics
        >>> analyzer.visualize()  # Show terminal visualization

        Direct instantiation with a question and answers:

        >>> from edsl.questions import QuestionMultipleChoice
        >>> q = QuestionMultipleChoice(
        ...     question_name="color",
        ...     question_text="What is your favorite color?",
        ...     question_options=["Red", "Blue", "Green"]
        ... )
        >>> answers = ["Red", "Blue", "Red", "Green", "Red"]
        >>> analyzer = ByQuestionAnswers.create(q, answers)
        >>> analyzer.visualize()  # Shows bar chart
    """

    def __init__(self, question: "QuestionBase", answers: List[Any]):
        """Initialize with a question and list of answers.

        Args:
            question: Question object with metadata (type, text, options, etc.)
            answers: List of answer values from survey responses
        """
        self.question = question
        self.answers = answers

    @classmethod
    def from_results(
        cls,
        results: "Results",
        question_name: str
    ) -> "ByQuestionAnswers":
        """Create an analyzer from a Results object and question name.

        This factory method extracts the question and answers from a Results
        object and creates the appropriate analyzer subclass based on the
        question type.

        Args:
            results: Results object containing survey responses
            question_name: Name of the question to analyze

        Returns:
            Appropriate ByQuestionAnswers subclass instance

        Raises:
            ValueError: If question_name not found in results

        Examples:
            >>> results = Results.example()
            >>> analyzer = ByQuestionAnswers.from_results(results, 'how_feeling')
            >>> type(analyzer).__name__
            'MultipleChoiceAnswers'
        """
        # Get the question object from results
        question = results.survey.get_question(question_name)

        # Get the answers from results
        answers = results.get_answers(question_name)

        # Create the appropriate subclass
        return cls.create(question, answers)

    @classmethod
    def create(
        cls,
        question: "QuestionBase",
        answers: List[Any]
    ) -> "ByQuestionAnswers":
        """Factory method to create the appropriate subclass based on question type.

        Args:
            question: Question object
            answers: List of answers

        Returns:
            Appropriate ByQuestionAnswers subclass instance

        Examples:
            >>> from edsl.questions import QuestionMultipleChoice
            >>> q = QuestionMultipleChoice(
            ...     question_name="test",
            ...     question_text="Test?",
            ...     question_options=["A", "B"]
            ... )
            >>> analyzer = ByQuestionAnswers.create(q, ["A", "B", "A"])
            >>> type(analyzer).__name__
            'MultipleChoiceAnswers'
        """
        question_type = question.question_type

        # Map question types to concrete classes
        type_map = {
            "multiple_choice": MultipleChoiceAnswers,
            "checkbox": CheckboxAnswers,
            "linear_scale": LinearScaleAnswers,
            "numerical": NumericalAnswers,
            "free_text": FreeTextAnswers,
            "yes_no": YesNoAnswers,
            "likert_five": LikertFiveAnswers,
            "rank": RankAnswers,
        }

        analyzer_class = type_map.get(question_type, DefaultAnswers)
        return analyzer_class(question, answers)

    @abstractmethod
    def summary(self) -> str:
        """Generate a text summary of the answer distribution.

        Returns:
            Formatted string with summary statistics
        """
        pass

    @abstractmethod
    def visualize(self) -> str:
        """Generate a terminal-based visualization of the answer distribution.

        Returns:
            String containing the terminal visualization
        """
        pass

    def show(self) -> None:
        """Print both summary and visualization to terminal.

        Examples:
            >>> analyzer = ByQuestionAnswers.from_results(results, 'question_name')
            >>> analyzer.show()  # Prints summary and visualization
        """
        print(self.summary())
        print()
        print(self.visualize())

    def _get_valid_answers(self) -> List[Any]:
        """Filter out None/null answers.

        Returns:
            List of non-None answers
        """
        return [a for a in self.answers if a is not None]


class MultipleChoiceAnswers(ByQuestionAnswers):
    """Analyzer for multiple choice questions.

    Provides frequency counts and horizontal bar charts showing the distribution
    of choices across respondents.
    """

    def summary(self) -> str:
        """Generate summary statistics for multiple choice responses.

        Returns:
            Formatted string with response counts and percentages
        """
        valid_answers = self._get_valid_answers()
        total = len(valid_answers)

        if total == 0:
            return f"Question: {self.question.question_text}\nNo valid responses"

        counts = Counter(valid_answers)

        lines = [
            f"Question: {self.question.question_text}",
            f"Type: Multiple Choice",
            f"Total responses: {total}",
            f"",
            "Distribution:"
        ]

        # Sort by frequency descending
        for choice, count in counts.most_common():
            pct = (count / total) * 100
            lines.append(f"  {choice}: {count} ({pct:.1f}%)")

        return "\n".join(lines)

    def visualize(self) -> str:
        """Generate a horizontal bar chart of response frequencies.

        Returns:
            String containing termplotlib bar chart
        """
        valid_answers = self._get_valid_answers()

        if not valid_answers:
            return "No data to visualize"

        counts = Counter(valid_answers)

        # Get all options from question if available
        if hasattr(self.question, 'question_options'):
            labels = self.question.question_options
            # Ensure all options are included, even with 0 counts
            values = [counts.get(label, 0) for label in labels]
        else:
            # Fall back to just the answers we have
            sorted_items = counts.most_common()
            labels = [item[0] for item in sorted_items]
            values = [item[1] for item in sorted_items]

        fig = tpl.figure()
        fig.barh(values, labels, force_ascii=False)

        # Capture the output
        import io
        import sys
        old_stdout = sys.stdout
        sys.stdout = buffer = io.StringIO()
        fig.show()
        output = buffer.getvalue()
        sys.stdout = old_stdout

        return output


class CheckboxAnswers(ByQuestionAnswers):
    """Analyzer for checkbox questions (multiple selections).

    Analyzes questions where respondents can select multiple options.
    """

    def summary(self) -> str:
        """Generate summary statistics for checkbox responses.

        Returns:
            Formatted string with selection frequencies
        """
        valid_answers = self._get_valid_answers()
        total = len(valid_answers)

        if total == 0:
            return f"Question: {self.question.question_text}\nNo valid responses"

        # Flatten list of lists to count individual selections
        all_selections = []
        for answer in valid_answers:
            if isinstance(answer, list):
                all_selections.extend(answer)
            else:
                all_selections.append(answer)

        counts = Counter(all_selections)

        lines = [
            f"Question: {self.question.question_text}",
            f"Type: Checkbox (multiple selections)",
            f"Total respondents: {total}",
            f"Total selections: {len(all_selections)}",
            f"Avg selections per respondent: {len(all_selections)/total:.1f}",
            f"",
            "Selection frequency:"
        ]

        for choice, count in counts.most_common():
            pct = (count / total) * 100
            lines.append(f"  {choice}: {count} ({pct:.1f}% of respondents)")

        return "\n".join(lines)

    def visualize(self) -> str:
        """Generate a horizontal bar chart of selection frequencies.

        Returns:
            String containing termplotlib bar chart
        """
        valid_answers = self._get_valid_answers()

        if not valid_answers:
            return "No data to visualize"

        # Flatten selections
        all_selections = []
        for answer in valid_answers:
            if isinstance(answer, list):
                all_selections.extend(answer)
            else:
                all_selections.append(answer)

        counts = Counter(all_selections)
        sorted_items = counts.most_common()

        labels = [item[0] for item in sorted_items]
        values = [item[1] for item in sorted_items]

        fig = tpl.figure()
        fig.barh(values, labels, force_ascii=False)

        import io
        import sys
        old_stdout = sys.stdout
        sys.stdout = buffer = io.StringIO()
        fig.show()
        output = buffer.getvalue()
        sys.stdout = old_stdout

        return output


class NumericalAnswers(ByQuestionAnswers):
    """Analyzer for numerical questions.

    Provides statistical summaries and histograms for numeric data.
    """

    def summary(self) -> str:
        """Generate statistical summary for numerical responses.

        Returns:
            Formatted string with mean, median, std dev, min, max
        """
        valid_answers = self._get_valid_answers()

        if not valid_answers:
            return f"Question: {self.question.question_text}\nNo valid responses"

        # Convert to numpy array for statistics
        values = np.array(valid_answers, dtype=float)

        lines = [
            f"Question: {self.question.question_text}",
            f"Type: Numerical",
            f"Total responses: {len(values)}",
            f"",
            "Statistics:",
            f"  Mean: {np.mean(values):.2f}",
            f"  Median: {np.median(values):.2f}",
            f"  Std Dev: {np.std(values):.2f}",
            f"  Min: {np.min(values):.2f}",
            f"  Max: {np.max(values):.2f}",
        ]

        return "\n".join(lines)

    def visualize(self) -> str:
        """Generate a histogram of numerical responses.

        Returns:
            String containing termplotlib histogram
        """
        valid_answers = self._get_valid_answers()

        if not valid_answers:
            return "No data to visualize"

        values = np.array(valid_answers, dtype=float)
        counts, bin_edges = np.histogram(values)

        fig = tpl.figure()
        fig.hist(counts, bin_edges, orientation="horizontal", force_ascii=False)

        import io
        import sys
        old_stdout = sys.stdout
        sys.stdout = buffer = io.StringIO()
        fig.show()
        output = buffer.getvalue()
        sys.stdout = old_stdout

        return output


class LinearScaleAnswers(ByQuestionAnswers):
    """Analyzer for linear scale questions.

    Similar to numerical but optimized for discrete scale values.
    """

    def summary(self) -> str:
        """Generate summary for linear scale responses.

        Returns:
            Formatted string with distribution and statistics
        """
        valid_answers = self._get_valid_answers()

        if not valid_answers:
            return f"Question: {self.question.question_text}\nNo valid responses"

        counts = Counter(valid_answers)
        values = np.array(valid_answers, dtype=float)

        lines = [
            f"Question: {self.question.question_text}",
            f"Type: Linear Scale",
            f"Total responses: {len(values)}",
            f"",
            "Statistics:",
            f"  Mean: {np.mean(values):.2f}",
            f"  Median: {np.median(values):.2f}",
            f"  Mode: {counts.most_common(1)[0][0]}",
            f"",
            "Distribution:"
        ]

        # Show distribution by scale value
        for value in sorted(counts.keys()):
            count = counts[value]
            pct = (count / len(values)) * 100
            lines.append(f"  {value}: {count} ({pct:.1f}%)")

        return "\n".join(lines)

    def visualize(self) -> str:
        """Generate a horizontal bar chart for scale distribution.

        Returns:
            String containing termplotlib bar chart
        """
        valid_answers = self._get_valid_answers()

        if not valid_answers:
            return "No data to visualize"

        counts = Counter(valid_answers)

        # Get scale range from question if available
        if hasattr(self.question, 'question_options'):
            scale_values = sorted(self.question.question_options)
        else:
            scale_values = sorted(counts.keys())

        labels = [str(v) for v in scale_values]
        values = [counts.get(v, 0) for v in scale_values]

        fig = tpl.figure()
        fig.barh(values, labels, force_ascii=False)

        import io
        import sys
        old_stdout = sys.stdout
        sys.stdout = buffer = io.StringIO()
        fig.show()
        output = buffer.getvalue()
        sys.stdout = old_stdout

        return output


class FreeTextAnswers(ByQuestionAnswers):
    """Analyzer for free text questions.

    Provides basic statistics about text responses.
    """

    def summary(self) -> str:
        """Generate summary for free text responses.

        Returns:
            Formatted string with response count and length statistics
        """
        valid_answers = self._get_valid_answers()

        if not valid_answers:
            return f"Question: {self.question.question_text}\nNo valid responses"

        # Calculate text statistics
        lengths = [len(str(answer)) for answer in valid_answers]
        word_counts = [len(str(answer).split()) for answer in valid_answers]

        lines = [
            f"Question: {self.question.question_text}",
            f"Type: Free Text",
            f"Total responses: {len(valid_answers)}",
            f"",
            "Text Statistics:",
            f"  Avg characters: {np.mean(lengths):.1f}",
            f"  Avg words: {np.mean(word_counts):.1f}",
            f"  Shortest response: {min(lengths)} chars",
            f"  Longest response: {max(lengths)} chars",
        ]

        return "\n".join(lines)

    def visualize(self) -> str:
        """Generate a histogram of response lengths.

        Returns:
            String containing termplotlib histogram
        """
        valid_answers = self._get_valid_answers()

        if not valid_answers:
            return "No data to visualize"

        lengths = np.array([len(str(answer)) for answer in valid_answers])
        counts, bin_edges = np.histogram(lengths)

        fig = tpl.figure()
        fig.hist(counts, bin_edges, orientation="horizontal", force_ascii=False)

        import io
        import sys
        old_stdout = sys.stdout
        sys.stdout = buffer = io.StringIO()
        fig.show()
        output = buffer.getvalue()
        sys.stdout = old_stdout

        return output.replace("Histogram", "Response Length Distribution")


class YesNoAnswers(MultipleChoiceAnswers):
    """Analyzer for yes/no questions.

    Inherits from MultipleChoiceAnswers since yes/no is essentially
    a binary multiple choice question.
    """
    pass


class LikertFiveAnswers(LinearScaleAnswers):
    """Analyzer for Likert 5-point scale questions.

    Inherits from LinearScaleAnswers since Likert scales are
    discrete ordered scales.
    """
    pass


class RankAnswers(ByQuestionAnswers):
    """Analyzer for ranking questions.

    Analyzes questions where respondents rank options in order.
    """

    def summary(self) -> str:
        """Generate summary for ranking responses.

        Returns:
            Formatted string with average rankings
        """
        valid_answers = self._get_valid_answers()

        if not valid_answers:
            return f"Question: {self.question.question_text}\nNo valid responses"

        # Calculate average position for each option
        position_sums: Dict[Any, List[int]] = {}

        for ranking in valid_answers:
            if isinstance(ranking, list):
                for position, option in enumerate(ranking, start=1):
                    if option not in position_sums:
                        position_sums[option] = []
                    position_sums[option].append(position)

        lines = [
            f"Question: {self.question.question_text}",
            f"Type: Rank",
            f"Total responses: {len(valid_answers)}",
            f"",
            "Average Rankings (lower is better):"
        ]

        # Sort by average position
        avg_positions = {
            opt: np.mean(positions)
            for opt, positions in position_sums.items()
        }

        for option, avg_pos in sorted(avg_positions.items(), key=lambda x: x[1]):
            lines.append(f"  {option}: {avg_pos:.2f}")

        return "\n".join(lines)

    def visualize(self) -> str:
        """Generate a bar chart of average rankings.

        Returns:
            String containing termplotlib bar chart
        """
        valid_answers = self._get_valid_answers()

        if not valid_answers:
            return "No data to visualize"

        # Calculate average position for each option
        position_sums: Dict[Any, List[int]] = {}

        for ranking in valid_answers:
            if isinstance(ranking, list):
                for position, option in enumerate(ranking, start=1):
                    if option not in position_sums:
                        position_sums[option] = []
                    position_sums[option].append(position)

        # Calculate averages and sort
        avg_positions = {
            opt: np.mean(positions)
            for opt, positions in position_sums.items()
        }
        sorted_items = sorted(avg_positions.items(), key=lambda x: x[1])

        labels = [item[0] for item in sorted_items]
        values = [item[1] for item in sorted_items]

        fig = tpl.figure()
        fig.barh(values, labels, force_ascii=False)

        import io
        import sys
        old_stdout = sys.stdout
        sys.stdout = buffer = io.StringIO()
        fig.show()
        output = buffer.getvalue()
        sys.stdout = old_stdout

        return output.replace("Histogram", "Average Rankings")


class DefaultAnswers(ByQuestionAnswers):
    """Default analyzer for question types without specific implementations.

    Provides basic frequency analysis for any question type.
    """

    def summary(self) -> str:
        """Generate basic summary for any question type.

        Returns:
            Formatted string with value counts
        """
        valid_answers = self._get_valid_answers()

        if not valid_answers:
            return f"Question: {self.question.question_text}\nNo valid responses"

        counts = Counter(valid_answers)

        lines = [
            f"Question: {self.question.question_text}",
            f"Type: {self.question.question_type}",
            f"Total responses: {len(valid_answers)}",
            f"Unique values: {len(counts)}",
            f"",
            "Top 10 values:"
        ]

        for value, count in counts.most_common(10):
            pct = (count / len(valid_answers)) * 100
            # Truncate long values
            value_str = str(value)
            if len(value_str) > 50:
                value_str = value_str[:47] + "..."
            lines.append(f"  {value_str}: {count} ({pct:.1f}%)")

        return "\n".join(lines)

    def visualize(self) -> str:
        """Generate a basic bar chart for any question type.

        Returns:
            String containing termplotlib bar chart of top values
        """
        valid_answers = self._get_valid_answers()

        if not valid_answers:
            return "No data to visualize"

        counts = Counter(valid_answers)
        top_items = counts.most_common(10)

        labels = [str(item[0])[:30] for item in top_items]  # Truncate labels
        values = [item[1] for item in top_items]

        fig = tpl.figure()
        fig.barh(values, labels, force_ascii=False)

        import io
        import sys
        old_stdout = sys.stdout
        sys.stdout = buffer = io.StringIO()
        fig.show()
        output = buffer.getvalue()
        sys.stdout = old_stdout

        return output
