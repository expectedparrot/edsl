import copy
import base64
import functools
import inspect
import markdown2
import math
import matplotlib.pyplot as plt
import numpy as np
import os
import pandas as pd
import seaborn as sns
import string
import tempfile
import textwrap
import warnings
import webbrowser
from abc import ABC, abstractmethod, ABCMeta
from collections import Counter
from dataclasses import asdict
from io import BytesIO
from IPython.display import display, HTML
from scipy import stats
from scipy.stats import chisquare
from statsmodels.miscmodels.ordinal_model import OrderedModel
from statsmodels.tools.sm_exceptions import HessianInversionWarning, ConvergenceWarning
from typing import Callable
from wordcloud import WordCloud
from edsl.report.InputOutputDataTypes import (
    CategoricalData,
    NumericalData,
    PlotData,
    TallyData,
    CrossTabData,
    FreeTextData,
    ChiSquareData,
    RegressionData,
)
from edsl.utilities import is_notebook

warnings.filterwarnings(
    "ignore",
    category=FutureWarning,
    module="seaborn._oldcore",
    message=".*is_categorical_dtype is deprecated.*",
)
warnings.filterwarnings("ignore", category=RuntimeWarning, module="statsmodels.*")
warnings.filterwarnings("ignore", category=RuntimeWarning, module="scipy.optimize.*")
warnings.filterwarnings("ignore", category=HessianInversionWarning)
warnings.filterwarnings("ignore", category=ConvergenceWarning)


class RegisterElementMeta(ABCMeta):
    "Metaclass to register output elements in a registry i.e., those that have a parent"
    _registry = {}  # Initialize the registry as a dictionary

    def __init__(cls, name, bases, dct):
        super(RegisterElementMeta, cls).__init__(name, bases, dct)
        if cls.LeftInputType is not None or cls.RightInputType is not None:
            # Register the class in the registry
            RegisterElementMeta._registry[name] = cls

    @classmethod
    def get_registered_classes(cls):
        return cls._registry


def camel_to_snake(name: str) -> str:
    """Converts a camel case string to snake case, e.g.,
    >>> camel_to_snake("HelloWorld")
    'hello_world'
    """
    snake_name = ""
    for index, char in enumerate(name):
        if char.isupper() and index != 0:
            snake_name += "_"
        snake_name += char.lower()

    return snake_name


class CustomFunctionWrapper:
    """A wrapper for a function that adds a name and docstring."""

    def __init__(self, func, name, doc):
        self._func = func
        self.name = name
        self.doc = doc

    def __call__(self, *args, **kwargs):
        return self._func(*args, **kwargs)

    def __repr__(self):
        return f"Method: {self.name}\nDescription: {self.doc or 'No description available'}"

    def _repr_html_(self):
        html = markdown2.markdown(
            f"**Method:** {self.name}\n\n**Description:** {self.doc or 'No description available'}"
        )
        # return markdown2.markdown(f"**Method:** {self.name}\n\n**Description:** {self.doc or 'No description available'}")
        # return f"<b>Method:</b> {self.name}<br><b>Description:</b> {self.doc or 'No description available'}"
        return html


def html_decorator(func: Callable) -> Callable:
    "A decorator that displays the output of a function as HTML."

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        obj = func(*args, **kwargs)
        html = obj.html()
        if is_notebook():  # if in a jupyter notebook
            return display(HTML(html))
        else:
            return obj.view()  # otherwise open in a browser

    return wrapper


class Element(ABC, metaclass=RegisterElementMeta):
    """Base class for all elements.


    LeftInputType: The type of the left parent. Could be None.
    RightInputType: The type of the right parent. Could Be None.
    OutputDataType: The type of the output data.

    "Root" elements are those that do not have a parent, and are created from the results.

    """

    LeftInputType = None
    RightInputType = None
    OutputDataType = None

    def __init__(self, left_parent=None, right_parent=None, output_data=None, **kwargs):
        self.left_parent = left_parent
        self.right_parent = right_parent
        self.left_data = getattr(left_parent, "output_data", None)
        self.right_data = getattr(right_parent, "output_data", None)

        for key, value in kwargs.items():
            setattr(self, key, value)

        if (
            self.LeftInputType is not None
            and type(self.left_data) != self.LeftInputType
        ):
            raise TypeError(f"Left parent must be of type {self.LeftInputType}")

        if (
            self.RightInputType is not None
            and type(self.right_data) != self.RightInputType
        ):
            raise TypeError(f"Right parent must be of type {self.RightInputType}")

        if output_data is None:
            self.output_data = self.create_output(
                self.left_data, self.right_data, **kwargs
            )
        else:
            self.output_data = output_data

    @classmethod
    def unary(cls):
        print("Switch to using the cls.element_type method instead")
        return cls.RightInputType is None

    @property
    def data(self):
        print("Shift to using self.output_data")
        return self.output_data

    @classmethod
    @property
    def function_name(cls):
        return camel_to_snake(cls.__name__)

    @classmethod
    def element_type(cls):
        if cls.LeftInputType is None and cls.RightInputType is None:
            return "root"
        if cls.LeftInputType is not None and cls.RightInputType is None:
            return "unary"
        if cls.LeftInputType is not None and cls.RightInputType is not None:
            return "binary"

    @classmethod
    def code_generation(cls, results_name: str, left_column, right_column=None):
        if cls.element_type() == "unary":
            return f'{results_name}.{cls.function_name}("{left_column}")'
        elif cls.element_type() == "binary":
            return (
                f'{results_name}.{cls.function_name}("{left_column}", "{right_column}")'
            )
        elif cls.element_type() == "root":
            raise Exception("Should not be called on a root element")

    @abstractmethod
    def _primary_function(self):
        "The function that creates the output data, as a dictionary."
        raise NotImplementedError

    @abstractmethod
    def _html(self):
        "The function that creates the HTML representation of the output data"
        raise NotImplementedError

    def create_output(self, LeftInput, RightInput, **kwargs):
        if self.element_type() == "unary":
            output_data = self._primary_function(LeftInput, **kwargs)
        elif self.element_type() == "binary":
            output_data = self._primary_function(LeftInput, RightInput, **kwargs)
        elif self.element_type() == "root":
            raise Exception("Should not be called on a root element")
        else:
            raise Exception("Unknown element type")
        return self.OutputDataType(**output_data)

    @classmethod
    def example(cls, **kwargs):
        class MockParent:
            def __init__(self, data):
                self.output_data = data

        left_parent = MockParent(cls.LeftInputType.example())
        right_parent = (
            None
            if cls.RightInputType is None
            else MockParent(cls.RightInputType.example())
        )

        return cls(left_parent, right_parent, **kwargs)

    def html(self):
        return self._html(**asdict(self.output_data))

    def view(self, **kwargs):
        temporary_directory = tempfile.mkdtemp()
        with open(os.path.join(temporary_directory, "temp.html"), "w") as f:
            f.write(self.html(**kwargs))
        webbrowser.open(os.path.join(temporary_directory, "temp.html"))

    @classmethod
    def parameters(cls):
        return inspect.signature(cls._primary_function).parameters

    @classmethod
    def create_external_function(cls, results) -> Callable:
        """Adds a function to the Results class that creates an output element."""

        def create_parent(data_type, key, input_type):
            RootElement = create_root_element(input_type)
            parent = RootElement.from_results(results, key, input_type)
            return parent

        if cls.RightInputType is None:

            def func(column, **kwargs):
                left_parent = create_parent(
                    *results._parse_column(column), input_type=cls.LeftInputType
                )
                return cls(left_parent=left_parent, **kwargs)

        else:

            def func(left_column, right_column, **kwargs):
                left_parent = create_parent(
                    *results._parse_column(left_column), cls.LeftInputType
                )
                right_parent = create_parent(
                    *results._parse_column(right_column), cls.RightInputType
                )
                return cls(left_parent=left_parent, right_parent=right_parent, **kwargs)

        return CustomFunctionWrapper(
            html_decorator(func), doc=cls.help(), name=cls.function_name
        )

    @classmethod
    def help(cls):
        help_text = textwrap.dedent(
            f"""\
        {cls._primary_function.__doc__}
        """
        )
        # return self._primary_function.__doc__
        return help_text


def create_root_element(output_data_type):
    class Container(Element):
        LeftInputType = None
        RightInputType = None
        OutputDataType = output_data_type

        def _primary_function(self):
            raise Exception("Should not be called directly")

        @classmethod
        def from_results(cls, results, data_name, index=None):
            data_type, key = results._parse_column(data_name)
            output_data = results._fetch_element(data_type, key, cls.OutputDataType)
            return cls(
                name=data_name,
                left_parent=None,
                right_parent=None,
                output_data=output_data,
                index=index,
            )

        def _html(self):
            return self.output_data.html()

    return Container


class PlotMixin:
    OutputDataType = PlotData

    image_format = "svg"

    @staticmethod
    def plt_to_buf(plt, format=image_format):
        buf = BytesIO()
        plt.savefig(buf, format=format)
        buf.seek(0)
        plt.close()
        return buf

    def _html(
        self,
        buffer,
        title,
        format=image_format,
        option_codes=None,
        width_pct=100,
        **kwargs,
    ):
        image_base64 = base64.b64encode(buffer.getvalue()).decode("utf-8")
        html = []
        html.append(title)
        format_line = "png" if format == "png" else "svg+xml"
        html.append(
            f"""<img src="data:image/{format_line};base64,{image_base64}" style="width: {width_pct}%; height: auto;"  />"""
        )
        if option_codes is not None:
            left_option_codes = option_codes.get("left_option_codes", None)
            if left_option_codes is not None:
                html.append("<p>Codes:</p>")
                for key, value in left_option_codes.items():
                    html.append(f"<p><b>{value}</b>: {key}</p>")
            right_option_codes = option_codes.get("right_option_codes", None)
            if right_option_codes is not None:
                if right_option_codes is not None:
                    html.append("<p>2nd variable Codes:</p>")
                    for key, value in right_option_codes.items():
                        html.append(f"<p><b>{value}</b>: {key}</p>")
        return "\n".join(html)


def tally(responses, options):
    response_counts = dict(Counter(responses))
    for key in options:
        if key not in response_counts:
            response_counts[key] = 0
    return response_counts


def replace_with_alpha_codes(
    options: list[str], responses: list[str], prefix: str = ""
):
    code_gen = (chr(i) for i in range(65, 91))
    option_codes = {}
    for option in options:
        option_codes[option] = prefix + next(code_gen)
    new_options = [option_codes[option] for option in options]
    new_responses = [option_codes[response] for response in responses]
    return new_options, new_responses, option_codes


def header_version(options, index):
    cleaned_versions = [
        option.translate(str.maketrans("", "", string.punctuation)).lower()
        for option in options
    ]
    split_versions = [option.split(" ") for option in cleaned_versions]
    versions = [split_version[:index] for split_version in split_versions]
    return ["_".join(version) for version in versions]


def find_version(options, index):
    candidate = header_version(options, index)
    if len(set(candidate)) == len(candidate):
        return candidate
    else:
        return find_version(options, index + 1)


def get_option_codes_short_name(options):
    return dict(zip(options, find_version(options, 1)))


def to_strings(split_versions):
    return ["_".join(version) for version in split_versions]


def is_unique(split_versions):
    return len(set(to_strings(split_versions))) == len(to_strings(split_versions))


def get_option_codes(options: list[str]):
    """Creates a dictionary mapping options to codes."""
    cleaned_versions = [
        option.translate(str.maketrans("", "", string.punctuation)).lower()
        for option in options
    ]
    new_cleaned_versions = []
    shortshands = {"not sure": "not-sure", "need more": "need-more"}
    for option in cleaned_versions:
        candidate = copy.copy(option)
        for key, value in shortshands.items():
            candidate = candidate.replace(key, value)
            # print(f"Replacing {key} with {value}")
            # print(option)
            # print(option.replace(key, value))
        new_cleaned_versions.append(candidate)

    cleaned_versions = new_cleaned_versions
    split_versions = [option.split(" ") for option in cleaned_versions]
    # get rid of stop words, is possible
    stop_words = [
        "a",
        "an",
        "am",
        "the",
        "of",
        "and",
        "or",
        "to",
        "for",
        "in",
        "on",
        "im",
        "that",
        "are",
        "i",
    ]
    # removes stop words so long as doing so doesn't make responses non-unique
    for version in split_versions:
        for stop_word in stop_words:
            if stop_word in version:
                index = version.index(stop_word)
                del version[index]
                if not is_unique(split_versions):
                    version.insert(index, stop_word)
                    # break

    # starts at the end and pops off options if it keeps everything unique
    # if it goes through and doesn't pop anything for each option, it stops
    while True:
        num_pops = 0
        for version in split_versions:
            if len(version) > 1:  # we we get to one word, stop
                removed = version.pop()
                if is_unique(split_versions):  # no problem
                    pass
                else:  # oops, we cut into bone
                    version.append(removed)
                    num_pops += 1
            else:
                num_pops += 1
        if num_pops == len(
            split_versions
        ):  # stop the loop if we tried popping everyting w/ no luck
            break

    return dict(zip(options, ["_".join(version) for version in split_versions]))


def replace_with_codes(
    options: list[str], responses: list[str], short_names_dict=None, prefix=""
):
    if short_names_dict is not None:
        option_codes = short_names_dict
    else:
        option_codes = get_option_codes(options)

    new_options = [option_codes[option] for option in options]
    new_responses = [option_codes[response] for response in responses]
    return new_options, new_responses, option_codes


class BarChart(PlotMixin, Element):
    "Creates a bar chart plot for categorical data."
    LeftInputType = CategoricalData
    RightInputType = None

    def _primary_function(
        self,
        CategoricalDataObject,
        width=10,
        height=5,
        xlabel="Counts",
        ylabel="",
        footer_fontsize=8,
        title=None,
        use_code=None,
        width_pct=100,
        show_percentage=True,
    ) -> dict:
        """
        Generates a bar chart from the provided categorical data object.

        ### Args:
            - CategoricalDataObject (CategoricalData): An object containing categorical data to be plotted.
            - `width (int, optional)`: Width of the plot. Defaults to 10.
            - height (int, optional): Height of the plot. Defaults to 5.
            - xlabel (str, optional): Label for the x-axis. Defaults to "Counts".
            - ylabel (str, optional): Label for the y-axis. Defaults to an empty string.
            - footer_fontsize (int, optional): Font size for the footer text. Defaults to 8.
            - title (str, optional): Title of the plot. If None, title is taken from CategoricalDataObject.text. Defaults to None.
            - use_code (bool, optional): Whether to use alphabetical codes for categorical options. Defaults to False.

        Note:
            If 'use_code' is set to True, each category in the plot is represented by an alphabetical code (A, B, C, ...),
            and a footer is added to the plot mapping these codes back to the original category names.
        """
        responses = CategoricalDataObject.responses
        options = CategoricalDataObject.options
        if title is None:
            title = CategoricalDataObject.text

        option_codes = None

        max_option_length = max([len(option) for option in options])
        if use_code is None:
            use_code = max_option_length > 10

        if use_code:
            if not (d := CategoricalDataObject.short_names_dict) == {}:
                options, responses, option_codes = replace_with_codes(
                    options, responses, short_names_dict=d
                )
            else:
                options, responses, option_codes = replace_with_codes(
                    options, responses
                )

        response_count = tally(responses, options)
        total_responses = sum(response_count.values())
        data = {key: response_count[key] for key in options}
        data_df = pd.DataFrame(list(data.items()), columns=["Keys", "Counts"])
        sns.set(style="whitegrid")
        plt.figure(figsize=(width, height))
        # sns.barplot(x="Counts", y="Keys", data=data_df, palette="Blues_d")
        ax = sns.barplot(x="Counts", y="Keys", data=data_df, palette="Blues_d")
        # Adjust layout and add footer if necessary
        plt.xlabel(xlabel)
        plt.ylabel(ylabel)
        plt.title(f"{title}")

        if show_percentage:
            for p in ax.patches:
                percentage = f"{100 * p.get_width() / total_responses:.1f}%"  # Calculate percentage
                x = p.get_x() + p.get_width() + 0.5
                y = p.get_y() + p.get_height() / 2
                ax.text(x, y, percentage, ha="center", va="center")

        plt.tight_layout()

        return {
            "buffer": self.plt_to_buf(plt),
            "title": title,
            "option_codes": {
                "left_option_codes": option_codes,
                "right_option_codes": None,
            },
            "width_pct": width_pct,
        }


class HistogramPlot(PlotMixin, Element):
    LeftInputType = NumericalData
    RightInputType = None

    def _primary_function(
        self,
        NumericalDataObject,
        alpha=0.7,
        bins=30,
        xlabel="Value",
        ylabel="Frequency",
        color="blue",
        title=None,
        max_title_length=40,
        width_pct=100,
    ):
        """
        Generates a histogram plot from a NumericalDataObject.

        This method plots a histogram based on the responses contained within the NumericalDataObject.
        It allows customization of the plot's appearance including the number of bins, transparency,
        color, and axis labels. Optionally, a custom title can be set, or it defaults to the 'text'
        attribute of the NumericalDataObject.

        Parameters:
            NumericalDataObject (NumericalData): An object containing numerical data and associated responses.
            alpha (float, optional): The transparency level of the histogram bars. Defaults to 0.7.
            bins (int, optional): The number of bins in the histogram. Defaults to 30.
            xlabel (str, optional): Label for the x-axis. Defaults to "Value".
            ylabel (str, optional): Label for the y-axis. Defaults to "Frequency".
            color (str, optional): Color of the histogram bars. Defaults to "blue".
            title (str, optional): Custom title for the histogram. If None, uses the 'text' attribute from NumericalDataObject.

        """
        responses = [
            float(x) if x is not None else None for x in NumericalDataObject.responses
        ]
        max_title_length = 40
        if title is None:
            if len(NumericalDataObject.text) > max_title_length:
                text = NumericalDataObject.text[:max_title_length] + "..."
            else:
                text = NumericalDataObject.text
        else:
            text = title
        plt.hist(responses, bins=bins, alpha=alpha, color=color)
        plt.title(f"{text}")
        plt.xlabel(xlabel)
        plt.ylabel(ylabel)
        plt.tight_layout()
        return {
            "buffer": self.plt_to_buf(plt),
            "title": text,
            "option_codes": None,
            "width_pct": width_pct,
        }


class ScatterPlot(PlotMixin, Element):
    LeftInputType = NumericalData
    RightInputType = NumericalData

    def _primary_function(
        self,
        LeftNumericalDataObject,
        RightNumericalDataObject,
        alpha=0.5,
        title=None,
        regression_line=True,
        x_text=None,
        y_text=None,
        width_pct=100,
    ):
        """
        Generates a scatter plot using numerical data from two provided data objects.

        This method creates a scatter plot to visually represent the relationship between
        two sets of numerical data. It offers customization for the plot's transparency
        (alpha) and title.

        Args:
            LeftNumericalDataObject (NumericalData): The first numerical data object,
                                                        used for the x-axis data.
            RightNumericalDataObject (NumericalData): The second numerical data object,
                                                        used for the y-axis data.
            alpha (float, optional): The transparency level of the scatter plot points.
                                        A value between 0 (transparent) and 1 (opaque).
                                        Defaults to 0.5.
            title (str, optional): Title for the scatter plot. If None, a default title
                                    is generated using the text attributes of the
                                    NumericalData objects. Defaults to None.
        """
        x = LeftNumericalDataObject.responses
        y = RightNumericalDataObject.responses
        if x_text is None:
            x_text = LeftNumericalDataObject.text
        if y_text is None:
            y_text = RightNumericalDataObject.text

        if title is None:
            title = f"{x_text} vs {y_text}"

        plt.title("")
        plt.xlabel(x_text)
        plt.ylabel(y_text)
        plt.scatter(x, y, alpha=alpha)

        if regression_line:
            slope, intercept, r_value, p_value, std_err = stats.linregress(x, y)
            x_array = np.array(x)
            plt.plot(
                x, intercept + slope * x_array, color="red"
            )  # Plotting the regression line
            regression_info_text = (
                f"Slope: {slope:.3f}\n"
                f"Std Error in Slope: {std_err:.3f}\n"
                f"Intercept: {intercept:.2f}\n"
            )
            plt.text(
                0.05,
                0.95,
                regression_info_text,
                transform=plt.gca().transAxes,
                fontsize=9,
                verticalalignment="top",
                bbox=dict(boxstyle="round,pad=0.3", facecolor="white", alpha=0.5),
            )

        plt.tight_layout()
        return {
            "buffer": self.plt_to_buf(plt),
            "title": "",
            "option_codes": None,
            "width_pct": width_pct,
        }


class WordCloudPlot(PlotMixin, Element):
    LeftInputType = FreeTextData
    RightInputType = None

    def _primary_function(
        self,
        FreeTextDataObject,
        width=800,
        height=400,
        background_color="white",
        width_pct=100,
    ):
        """Creates a word cloud plot for free text data.

        Parameters
        ----------
        column: str
            Name of the column in the results to use.
        width : int
            Width of the plot in pixels.
        height : int
            Height of the plot in pixels.
        background_color : str
            Background color of the plot.
        """
        responses = " ".join(FreeTextDataObject.responses)
        text = FreeTextDataObject.text

        wordcloud = WordCloud(
            width=width, height=height, background_color=background_color
        ).generate(responses)
        plt.figure(figsize=(10, 5))
        plt.imshow(wordcloud, interpolation="bilinear")
        plt.axis("off")
        plt.title(f"{text}")
        return {
            "buffer": self.plt_to_buf(plt),
            "title": "",
            "option_codes": None,
            "width_pct": width_pct,
        }


class Tally(Element):
    LeftInputType = CategoricalData
    RightInputType = None
    OutputDataType = TallyData

    def _primary_function(self, CategoricalDataObject, **kwargs):
        """Creates a tally of responses to a categorical question."""
        responses = CategoricalDataObject.responses
        text = CategoricalDataObject.text
        options = CategoricalDataObject.options

        response_count = dict(Counter(responses))
        # Add 0s for things that weren't selected even once
        for key in options:
            if key not in response_count:
                response_count[key] = 0

        options.reverse()
        return {
            "responses": {key: response_count[key] for key in options},
            "text": text,
        }

    def _html(self, responses, text, **kwargs):
        report_html = [
            "<div>",
            f"<p>{text}</p>" "<table>",
        ]
        for key, value in responses.items():
            report_html.append(f"<tr><td>{key}</td><td>{value}</td></tr>")
        report_html.append("</table>")
        report_html.append("</div>")
        return "\n".join(report_html)


def compute_cross_tab(left_responses, left_options, right_responses, right_options):
    left_response_count = dict(Counter(left_responses))
    right_response_count = dict(Counter(right_responses))
    # Add 0s for things that weren't selected even once
    for key in left_options:
        if key not in left_response_count:
            left_response_count[key] = 0
    for key in right_options:
        if key not in right_response_count:
            right_response_count[key] = 0

    left_options.reverse()
    right_options.reverse()

    cross_tab = {
        left_option: {right_option: 0 for right_option in right_options}
        for left_option in left_options
    }
    # Perform the cross-tabulation
    for left_response, right_response in zip(left_responses, right_responses):
        cross_tab[left_response][right_response] += 1
    return cross_tab


class CrossTab(Element):
    LeftInputType = CategoricalData
    RightInputType = CategoricalData
    OutputDataType = CrossTabData

    def _primary_function(
        self, LeftCategoricalDataObject, RightCategoricalDataObject, **kwargs
    ):
        """Creates a cross tabulation of two categorical variables.
        Parameters
        ----------
        left_column: str
            Name of the column in the results to use for the left side.
        right_column: str
            Name of the column in the results to use for the right side.
        """
        left_responses = LeftCategoricalDataObject.responses
        right_responses = RightCategoricalDataObject.responses
        left_text = LeftCategoricalDataObject.text
        right_text = RightCategoricalDataObject.text
        left_options = LeftCategoricalDataObject.options
        right_options = RightCategoricalDataObject.options

        cross_tab = compute_cross_tab(
            left_responses, left_options, right_responses, right_options
        )
        return {
            "cross_tab": cross_tab,
            "left_title": left_text,
            "right_title": right_text,
        }

    def _html(self, cross_tab, left_title, right_title, **kwargs):
        report_html = [
            "<div>",
            f"<p>Cross tabulation of: {left_title} and {right_title}</p>",
            "<table>",
        ]

        # Assuming all inner dictionaries have the same keys, use the keys from the first one
        first_key = next(iter(cross_tab))
        left_options = cross_tab[first_key].keys()
        headers = [""] + list(left_options)
        report_html.append(
            "<tr>" + "".join(f"<th>{header}</th>" for header in headers) + "</tr>"
        )

        # Fill in the rows of the table
        for right_option, counts in cross_tab.items():
            row = [f"<td>{right_option}</td>"]
            for left_option in left_options:
                row.append(f"<td>{counts[left_option]}</td>")
            report_html.append("<tr>" + "".join(row) + "</tr>")

        report_html.append("</table>")
        report_html.append("</div>")
        return "\n".join(report_html)


class FacetedBarChart(PlotMixin, Element):
    LeftInputType = CategoricalData
    RightInputType = CategoricalData

    def _primary_function(
        self,
        LeftCategoricalDataObject,
        RightCategoricalDataObject,
        num_cols=None,
        height=5,
        label_angle=45,
        title=None,
        use_code_left=None,
        use_code_right=None,
        sharey=True,
        width_pct=100,
    ):
        """ "
            Generates a set of bar plots as a FacetGrid to compare two categorical data sets.

        This method creates a series of bar plots, one for each category in the RightCategoricalDataObject,
        to compare the frequencies of categories from LeftCategoricalDataObject. The plots are
        arranged in a grid layout, with an option to specify the number of columns and the height of each plot.
        Additionally, the angle of the x-axis labels and the title of the grid can be customized.

        Args:
            LeftCategoricalDataObject (CategoricalData): The first categorical data object,
                                                        used for the x-axis data in the bar plots.
            RightCategoricalDataObject (CategoricalData): The second categorical data object,
                                                        whose categories define the grid columns.
            num_cols (int, optional): The number of columns in the FacetGrid. If None, it's calculated
                                    based on the number of categories in RightCategoricalDataObject.
                                    Defaults to None.
            height (int, optional): The height of each subplot in the grid. Defaults to 5.
            label_angle (int, optional): The angle for rotating the x-axis labels for readability.
                                        Defaults to 45 degrees.
            title (str, optional): The overall title of the FacetGrid. If None, a default title is
                                generated based on the texts of the categorical data objects.
                                Defaults to None.
            use_code_left (bool, optional): Whether to use alphabetical codes for categorical options
                                            in the left data object.
            use_code_right (bool, optional): Whether to use alphabetical codes for categorical options
            sharey (bool, optional): Whether to share the y-axis across all plots. Defaults to True.

        Notes:
            - The bar plots are generated using seaborn's barplot function within a FacetGrid.
            - The layout of the grid is adjusted to accommodate the overall title and to prevent
            overlap of plot elements.
        """
        left_responses = LeftCategoricalDataObject.responses
        right_responses = RightCategoricalDataObject.responses
        left_text = LeftCategoricalDataObject.text
        right_text = RightCategoricalDataObject.text
        left_options = LeftCategoricalDataObject.options
        right_options = RightCategoricalDataObject.options

        if use_code_left is None:
            max_option_length_left = max([len(option) for option in left_options])
            use_code_left = max_option_length_left > 10
        if use_code_right is None:
            max_option_length_right = max([len(option) for option in right_options])
            use_code_right = max_option_length_right > 10

        if title is None:
            title = f'"{left_text}" \n by "{right_text}"'

        if len(left_text) > 40:
            left_text = left_text[:20] + "..."
        if len(right_text) > 40:
            right_text = right_text[:20] + "..."

        left_option_codes = None
        right_option_codes = None

        if use_code_left:
            left_options, left_responses, left_option_codes = replace_with_codes(
                left_options, left_responses, prefix="L-"
            )
        if use_code_right:
            right_options, right_responses, right_option_codes = replace_with_codes(
                right_options, right_responses, prefix="R-"
            )

        # Figures out how many columns to use in the FacetGrid if not specified
        if num_cols is None:
            if len(right_options) < 6:
                num_cols = len(right_options)
            else:
                num_cols = math.ceil(math.sqrt(len(right_options)))

        cross_tab = compute_cross_tab(
            right_responses, right_options, left_responses, left_options
        )

        d = {}
        if use_code_left:
            d = {v: k for k, v in left_option_codes.items()}
        left_option_name = d.get(left_text, left_text)
        if use_code_right:
            d = {v: k for k, v in right_option_codes.items()}
        right_option_name = d.get(right_text, right_text)

        df = pd.DataFrame(cross_tab)
        # Reset index to turn the index into a column
        df = df.reset_index()
        # Rename the columns to be more descriptive
        df.rename(columns={"index": left_option_name}, inplace=True)
        # Melt the DataFrame to long format
        df_long = df.melt(
            id_vars=left_option_name, var_name=right_option_name, value_name="Count"
        )
        sns.set(style="whitegrid")
        # Creating a FacetGrid
        g = sns.FacetGrid(
            df_long,
            col=right_option_name,
            col_wrap=num_cols,
            sharey=sharey,
            height=height,
        )
        # Adding bar plots to the FacetGrid
        g = g.map(
            sns.barplot,
            left_option_name,
            "Count",
            order=df_long[left_option_name].unique(),
            palette="viridis",
        )
        # Rotating x-axis labels for better readability
        for ax in g.axes.ravel():
            for label in ax.get_xticklabels():
                label.set_rotation(label_angle)

        g.fig.suptitle(f"{title}", fontsize=16)

        # Adjust the layout to make room for the title and prevent overlap
        g.fig.subplots_adjust(top=0.9)  # you can adjust the value as needed

        plt.tight_layout()
        return {
            "buffer": self.plt_to_buf(plt),
            "title": "",
            "option_codes": {
                "left_option_codes": left_option_codes,
                "right_option_codes": right_option_codes,
            },
            "width_pct": width_pct,
        }


class ChiSquare(Element):
    LeftInputType = CategoricalData
    RightInputType = None
    OutputDataType = ChiSquareData

    def _primary_function(self, CategoricalDataObject, **kwargs):
        responses = CategoricalDataObject.responses
        text = CategoricalDataObject.text
        options = CategoricalDataObject.options

        response_count = dict(Counter(responses))
        # Add 0s for things that weren't selected even once
        for key in options:
            if key not in response_count:
                response_count[key] = 0

        observed_counts = list(response_count.values())
        chi_square, p_value = chisquare(observed_counts)
        return {"chi_square": chi_square, "p_value": p_value, "text": text}

    def _html(self, chi_square, p_value, text, digits=3, **kwargs):
        report_html = ["<div>", f"<p>Chi-square test for: {text}</p>" "<table>"]
        report_html.append(f"<p>Chi-square statistic: {round(chi_square, digits)}</p>")
        report_html.append(f"<p>p-value: {round(p_value, digits)}</p>")
        report_html.append("</div>")
        return "\n".join(report_html)


class OrderedLogit(Element):
    LeftInputType = CategoricalData
    RightInputType = CategoricalData
    OutputDataType = RegressionData

    def _primary_function(
        self, LeftSideCategoricalData, RightSideCategoricalData, **kwargs
    ):
        y = LeftSideCategoricalData.responses
        category_order = LeftSideCategoricalData.options
        X = RightSideCategoricalData.responses
        outcome_description = LeftSideCategoricalData.text
        if not (isinstance(y, list) and isinstance(X, list) and len(y) == len(X)):
            print(y)
            print(X)
            raise ValueError("y and X must be lists of the same length.")

        y_ordered = pd.Categorical(y, categories=category_order, ordered=True)

        # Create a DataFrame from the inputs
        data = pd.DataFrame({"Outcome": y_ordered, "Predictor": X})

        # Convert the categorical variable into dummy/indicator variables
        data = pd.get_dummies(data, columns=["Predictor"], drop_first=True)

        for col in data.columns.drop("Outcome"):
            data[col] = pd.to_numeric(data[col], errors="coerce")

        for col in data.select_dtypes(include=["bool"]).columns:
            data[col] = data[col].astype(int)
        try:
            model = OrderedModel(
                data["Outcome"], data.drop(columns=["Outcome"]), distr="logit"
            )  # Use 'logit' for logistic distribution
            result = model.fit()
            return {
                "model_outcome": result.summary().as_html(),
                "outcome_description": outcome_description,
            }
        except Exception as e:
            return {
                "model_outcome": f"Error: {e}",
                "outcome_description": outcome_description,
            }

    def _html(self, model_outcome: str, outcome_description: str):
        report_html = [
            "<h1>Ordered logit</h1>",
            "<div>",
            f"<p>Outcome: {outcome_description}</p>",
        ]
        report_html.append(model_outcome)
        report_html.append("</div>")
        return "\n".join(report_html)
