from typing import Optional

from edsl import Scenario, ScenarioList, Dataset
from edsl import QuestionDict

import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import random
import textwrap

import webbrowser
import tempfile
import os


class HTMLSnippet:
    """Represents a snippet of HTML, allowing raw access and browser display."""

    def __init__(self, html_content: str):
        if not isinstance(html_content, str):
            raise TypeError("HTML content must be a string.")
        self._html = html_content

    def __str__(self) -> str:
        return self._html

    def _repr_html_(self) -> str:
        return self._html

    def view(self):
        try:
            with tempfile.NamedTemporaryFile(
                "w", delete=False, suffix=".html", encoding="utf-8"
            ) as f:
                f.write(self._html)
                file_path = f.name
        except Exception as file_err:
            print(f"Error creating temporary HTML file: {file_err}")
            return
        try:
            webbrowser.open(f"file://{os.path.realpath(file_path)}")
            print("HTML output opened in your default web browser.")
            print(f"(Temporary file: {file_path})")
        except Exception as browser_err:
            print(f"Failed to open the HTML output in a browser: {browser_err}")
            print(f"You can find the HTML file at: {file_path}")


def semantic_columns(scenario_list: ScenarioList) -> ScenarioList:
    """Convert a ScenarioList's columns to more semantic names using LLM.

    Args:
        scenario_list: The ScenarioList to convert

    Returns:
        A new ScenarioList with semantic column names

    Raises:
        ValueError: If the scenario_list has no codebook
    """
    if scenario_list.codebook is None:
        raise ValueError("codebook is not set")

    s = Scenario({"columns": scenario_list.codebook})
    q = QuestionDict(
        question_name="better_columns",
        question_text=(
            "These are the columns of a CSV file representing a survey: '{{ scenario.columns }}'."
            "I could like to create, for each column, a better identifier that captures what that column means."
            "<example>"
            """E.g., a column 'How was your experience at dinner" ---> 'dinner_experience'"""
            "</example>"
            "Please do thise for each column, but making sure each name is unique, with no duplicates."
            "Please keep each one short, ideally one or two words. "
            "If the column name is unformative, repeat the identifier e.g., "
            "<example>"
            """{'col_5': "Unamed"} ---> {'col_5': "col_5"}"""
            "</example>"
        ),
        answer_keys=list(scenario_list.codebook.keys()),
    )
    new_columns = q.by(s).run(verbose=False)
    renaming_columns = new_columns.select("answer.*").first()
    return scenario_list.rename(renaming_columns)


def analyze_dataset(dataset: Dataset, context: Optional[str] = None) -> "str":
    """
    Analyze the dataset and return results in appropriate format based on environment.

    Args:
        dataset: The Dataset to analyze
        context: Optional additional context for the analysis

    Returns:
        str or IPython.display.Markdown: Markdown object in Jupyter environment, string otherwise
    """
    from edsl import QuestionFreeText

    data_in_json = dataset.to_pandas().to_json(orient="records", lines=True)
    q = QuestionFreeText(
        question_name="analysis",
        question_text=f"This is data from a study: {data_in_json}. {context}. Please write a short analysis of the data in markdown format.",
    )
    analysis = q.by(dataset).run(verbose=False).select("answer.*").first()

    # Check if we're in a Jupyter environment
    try:
        from IPython import get_ipython

        if get_ipython() is not None:
            from IPython.display import Markdown

            return Markdown(analysis)
    except ImportError:
        pass

    return analysis


def create_magazine_quote_layout(
    quotes, output_filename=None, colors=None, figsize=(12, 10), dpi=100, title="Quotes"
):
    """
    Create a magazine-style layout for quotes using Matplotlib.

    Parameters:
    -----------
    quotes : list of str
        The quotes to display
    output_filename : str, optional
        If provided, where to save the generated image
    colors : list of str
        List of colors to use for the tiles
    figsize : tuple
        Size of the figure in inches
    dpi : int
        Resolution of the output image
    title : str
        Title to display at the top of the layout
    """
    if colors is None:
        # Default color palette
        colors = [
            "#FF9AA2",
            "#FFB7B2",
            "#FFDAC1",
            "#E2F0CB",
            "#B5EAD7",
            "#C7CEEA",
            "#F8B195",
            "#F67280",
        ]

    # Create figure
    fig = plt.figure(figsize=figsize, dpi=dpi, facecolor="#f9f9f9")

    # Number of quotes
    n_quotes = len(quotes)

    # Create a grid layout
    # For magazine style, we'll use a more complex grid
    if n_quotes <= 4:
        rows, cols = 2, 2
    elif n_quotes <= 6:
        rows, cols = 2, 3
    elif n_quotes <= 9:
        rows, cols = 3, 3
    elif n_quotes <= 12:
        rows, cols = 3, 4
    else:
        rows, cols = 4, 4  # Max 16 quotes

    # Create a more irregular grid
    grid_sizes = []
    available_positions = [(r, c) for r in range(rows) for c in range(cols)]

    # Make sure we don't try to place more quotes than we have positions
    quotes_to_place = min(n_quotes, len(available_positions))

    # Place quotes one by one
    for _ in range(quotes_to_place):
        # Check if we still have positions available
        if not available_positions:
            break

        # Randomly decide if we want to try a larger tile (2x1 or 1x2)
        if (
            len(available_positions) > 1 and random.random() < 0.3
        ):  # 30% chance for a larger tile
            # Try to create a 2x1 or 1x2 tile
            direction = random.choice(["horizontal", "vertical"])

            if direction == "horizontal" and cols > 1:
                # Look for available adjacent positions horizontally
                valid_starts = [
                    (r, c)
                    for r, c in available_positions
                    if (r, c + 1) in available_positions
                ]

                if valid_starts:
                    r, c = random.choice(valid_starts)
                    grid_sizes.append((r, c, 1, 2))  # row, col, rowspan, colspan
                    available_positions.remove((r, c))
                    available_positions.remove((r, c + 1))
                elif available_positions:  # Fallback to 1x1 if we can't make a 2x1
                    r, c = available_positions.pop(
                        random.randrange(len(available_positions))
                    )
                    grid_sizes.append((r, c, 1, 1))

            elif direction == "vertical" and rows > 1:
                # Look for available adjacent positions vertically
                valid_starts = [
                    (r, c)
                    for r, c in available_positions
                    if (r + 1, c) in available_positions
                ]

                if valid_starts:
                    r, c = random.choice(valid_starts)
                    grid_sizes.append((r, c, 2, 1))  # row, col, rowspan, colspan
                    available_positions.remove((r, c))
                    available_positions.remove((r + 1, c))
                elif available_positions:  # Fallback to 1x1 if we can't make a 2x1
                    r, c = available_positions.pop(
                        random.randrange(len(available_positions))
                    )
                    grid_sizes.append((r, c, 1, 1))
            else:
                # Fallback to 1x1
                if available_positions:
                    r, c = available_positions.pop(
                        random.randrange(len(available_positions))
                    )
                    grid_sizes.append((r, c, 1, 1))
        else:
            # Create a 1x1 tile
            if available_positions:
                r, c = available_positions.pop(
                    random.randrange(len(available_positions))
                )
                grid_sizes.append((r, c, 1, 1))

    # Create a GridSpec
    gs = gridspec.GridSpec(rows, cols, figure=fig)

    # Layout quotes in the grid with some randomness
    for i, (quote, grid_pos) in enumerate(zip(quotes[: len(grid_sizes)], grid_sizes)):
        r, c, rs, cs = grid_pos
        ax = fig.add_subplot(gs[r : r + rs, c : c + cs])

        # Remove axes and ticks
        ax.set_xticks([])
        ax.set_yticks([])
        ax.set_frame_on(False)

        # Create rectangle background
        color = random.choice(colors)
        rect = plt.Rectangle(
            (0, 0),
            1,
            1,
            linewidth=3,
            edgecolor="white",
            facecolor=color,
            alpha=0.85,
            transform=ax.transAxes,
            zorder=1,
        )
        ax.add_patch(rect)

        # Adjust font size based on quote length and tile size
        font_size = 10 + min(70 / (len(quote) + 1), 10) * (rs * cs) ** 0.5

        # Wrap text to fit in the rectangle (adjust based on tile size)
        chars_per_line = int(25 * cs)
        wrapped_text = textwrap.fill(f'"{quote}"', width=chars_per_line)

        # Add text
        ax.text(
            0.5,
            0.5,
            wrapped_text,
            horizontalalignment="center",
            verticalalignment="center",
            fontsize=font_size,
            color="black",
            weight="bold",
            zorder=2,
            transform=ax.transAxes,
            wrap=True,
        )

    # Add title
    fig.suptitle(title, fontsize=20, y=0.98)

    # Adjust layout
    plt.tight_layout(rect=[0, 0, 1, 0.95])

    # Save figure only if output_filename is provided
    if output_filename:
        plt.savefig(output_filename, bbox_inches="tight")
    else:
        plt.show()
