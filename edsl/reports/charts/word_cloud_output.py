from .chart_output import ChartOutput
import pandas as pd
import tempfile
import io
import base64


class WordCloudOutput(ChartOutput):
    """A word cloud visualization for free text responses."""

    pretty_name = "Word Cloud"
    pretty_short_name = "Word cloud"
    methodology = "Generates a word cloud visualization showing the most frequently occurring words in free text responses, with size proportional to frequency"

    def __init__(self, results, *question_names, free_text_sample_config=None):
        if len(question_names) != 1:
            raise ValueError("WordCloudOutput requires exactly one question name")
        super().__init__(results, *question_names)
        self.question = self.questions[0]
        self.answers = self.results.select(
            self.get_data_column(self.questions[0])
        ).to_list()
        self.free_text_sample_config = free_text_sample_config or {}

        # Apply sampling if configured (similar to ThemeFinderOutput)
        self._sampled_answers = self._apply_sampling(
            self.answers, self.question_names[0]
        )

    def _apply_sampling(self, answers, question_name):
        """Apply sampling configuration to the answers for this question."""
        if not self.free_text_sample_config:
            return answers

        # Check for question-specific configuration first
        if question_name in self.free_text_sample_config:
            sample_size = self.free_text_sample_config[question_name]
        elif "_global" in self.free_text_sample_config:
            sample_size = self.free_text_sample_config["_global"]
        else:
            return answers

        # Filter out None values before sampling
        valid_answers = [a for a in answers if a is not None]

        if not valid_answers or len(valid_answers) <= sample_size:
            return answers

        # Sample without replacement
        import random

        random.seed("reports_sampling")
        sampled_answers = random.sample(valid_answers, sample_size)
        return sampled_answers

    @property
    def narrative(self):
        return f"A word cloud showing the most frequently used words in responses to the question: '{self.question.question_text}'. Larger words appear more frequently in the responses."

    @classmethod
    def can_handle(cls, *question_objs):
        """
        Check if this chart type can handle the given questions.
        Returns True if there is exactly one question and it is free_text.
        """
        return len(question_objs) == 1 and question_objs[0].question_type == "free_text"

    def output(self):
        """
        Generate a word cloud visualization.

        Returns:
            An HTML image element with the word cloud as a base64-encoded PNG
        """
        try:
            from wordcloud import WordCloud
            import matplotlib

            matplotlib.use("Agg")  # Use non-interactive backend
            import matplotlib.pyplot as plt
        except ImportError:
            # Return a helpful message if wordcloud is not installed
            return self._create_fallback_message()

        # Filter out None values and combine all text
        valid_answers = [str(a) for a in self._sampled_answers if a is not None]

        if not valid_answers:
            return self._create_empty_message()

        # Combine all text
        text = " ".join(valid_answers)

        # Generate word cloud
        wordcloud = WordCloud(
            width=800,
            height=400,
            background_color="white",
            colormap="viridis",
            max_words=100,
            relative_scaling=0.5,
            min_font_size=10,
        ).generate(text)

        # Create matplotlib figure
        fig, ax = plt.subplots(figsize=(10, 5))
        ax.imshow(wordcloud, interpolation="bilinear")
        ax.axis("off")
        ax.set_title("Word Cloud", fontsize=16, pad=20)

        # Save to bytes buffer
        buf = io.BytesIO()
        plt.savefig(buf, format="png", bbox_inches="tight", dpi=150)
        plt.close(fig)
        buf.seek(0)

        # Encode as base64
        img_base64 = base64.b64encode(buf.read()).decode("utf-8")
        buf.close()

        # Return as HTML img tag wrapped in a simple container
        return WordCloudImage(img_base64)

    def _create_fallback_message(self):
        """Create a message when wordcloud library is not installed."""
        return WordCloudMessage(
            "Word cloud visualization requires the 'wordcloud' library.\n"
            "Install it with: pip install wordcloud"
        )

    def _create_empty_message(self):
        """Create a message when there are no valid responses."""
        return WordCloudMessage(
            "No valid text responses available to generate word cloud."
        )


class WordCloudImage:
    """Container for word cloud image that can be displayed in Jupyter."""

    def __init__(self, img_base64):
        self.img_base64 = img_base64

    def _repr_html_(self):
        """Return HTML representation for Jupyter display."""
        return f'<img src="data:image/png;base64,{self.img_base64}" style="max-width: 100%; height: auto;">'

    def to_html(self):
        """Return HTML representation (for consistency with Altair charts)."""
        return self._repr_html_()

    def save(self, filename):
        """Save the word cloud image to a file."""
        import base64

        with open(filename, "wb") as f:
            f.write(base64.b64decode(self.img_base64))

    def __repr__(self):
        return "WordCloudImage()"


class WordCloudMessage:
    """Container for word cloud messages (errors, warnings)."""

    def __init__(self, message):
        self.message = message

    def _repr_html_(self):
        """Return HTML representation for Jupyter display."""
        return f"""
        <div style="padding: 20px; background-color: #fff3cd; border-left: 4px solid #ffc107; border-radius: 5px;">
            <p style="margin: 0; color: #856404; font-family: -apple-system, sans-serif;">
                {self.message}
            </p>
        </div>
        """

    def to_html(self):
        """Return HTML representation (for consistency with Altair charts)."""
        return self._repr_html_()

    def __repr__(self):
        return f"WordCloudMessage({self.message})"

    def __str__(self):
        return self.message
