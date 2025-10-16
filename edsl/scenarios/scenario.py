"""
A Scenario is a dictionary-like object that stores key-value pairs for parameterizing questions.

Scenarios are a fundamental concept in EDSL, providing a mechanism to parameterize
questions with dynamic values. Each Scenario contains key-value pairs that can be
referenced within question templates using Jinja syntax. This allows for creating
questions that vary based on the specific scenario being presented.

Key features include:
- Dictionary-like behavior (inherits from UserDict)
- Support for combination operations (addition, multiplication)
- Conversion to/from various formats (dict, dataset)
- Methods for file and data source integration

Scenarios can be created from various sources including files, URLs, PDFs, images,
and HTML content. They serve as the primary mechanism for providing context or variable
information to questions in surveys.
"""

from __future__ import annotations
import copy
from collections import UserDict
from typing import Union, List, Optional, TYPE_CHECKING, Dict, Any, Iterable, Mapping

from ..base import Base
from .exceptions import ScenarioError

if TYPE_CHECKING:
    from .scenario_list import ScenarioList
    from ..dataset import Dataset
    from ..jobs import Jobs
    from ..questions import QuestionBase as Question
    from ..surveys import Survey


from .firecrawl_scenario import FirecrawlRequest


class Scenario(Base, UserDict):
    """
    A dictionary-like object that stores key-value pairs for parameterizing questions.

    A Scenario inherits from both the EDSL Base class and Python's UserDict, allowing
    it to function as a dictionary while providing additional functionality. Scenarios
    are used to parameterize questions by providing variable data that can be referenced
    within question templates using Jinja syntax.

    Scenarios can be created directly with dictionary data or constructed from various
    sources using class methods (from_file, from_url, from_pdf, etc.). They support
    operations like addition (combining scenarios) and multiplication (creating cross
    products with other scenarios or scenario lists).

    Attributes:
        data (dict): The underlying dictionary data.
        name (str, optional): A name for the scenario.

    Examples:
        Create a simple scenario:
        >>> s = Scenario({"product": "coffee", "price": 4.99})

        Combine scenarios:
        >>> s1 = Scenario({"product": "coffee"})
        >>> s2 = Scenario({"price": 4.99})
        >>> s3 = s1 + s2
        >>> s3
        Scenario({'product': 'coffee', 'price': 4.99})

        Create a scenario from a file:
        >>> import tempfile
        >>> with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        ...     _ = f.write("Hello World")
        ...     data_path = f.name
        >>> s = Scenario.from_file(data_path, "document")
        >>> import os
        >>> os.unlink(data_path) # Clean up temp file
    """

    firecrawl = FirecrawlRequest()

    __documentation__ = "https://docs.expectedparrot.com/en/latest/scenarios.html"

    def __init__(
        self,
        data: Optional[Union[Dict[str, Any], Mapping[str, Any]]] = None,
        name: Optional[str] = None,
        **kwargs: Any,
    ):
        """
        Initialize a new Scenario.

        Args:
            data: A dictionary of key-value pairs for parameterizing questions.
                  Any dictionary-like object that can be converted to a dict is accepted.
            name: An optional name for the scenario to aid in identification.
            **kwargs: Additional keyword arguments that will be added to the scenario data.
                     If both data and kwargs are provided, they will be merged with kwargs
                     taking precedence for overlapping keys.

        Raises:
            ScenarioError: If the data cannot be converted to a dictionary.

        Examples:
            >>> s = Scenario({"product": "coffee", "price": 4.99})
            >>> s = Scenario({"question": "What is your favorite color?"}, name="color_question")
            
            Using keyword arguments:
            >>> s = Scenario(product="coffee", price=4.99)
            >>> s
            Scenario({'product': 'coffee', 'price': 4.99})
            
            >>> s = Scenario(a="b")
            >>> s
            Scenario({'a': 'b'})
            
            Mixing data and kwargs (kwargs take precedence):
            >>> s = Scenario({"a": 1, "b": 2}, a=10, c=3)
            >>> s
            Scenario({'a': 10, 'b': 2, 'c': 3})
        """
        if not isinstance(data, dict) and data is not None:
            try:
                data = dict(data)
            except Exception as e:
                raise ScenarioError(
                    f"You must pass in a dictionary to initialize a Scenario. You passed in {data}"
                    + "Exception message:"
                    + str(e),
                )

        super().__init__()
        self.data = data if data is not None else {}
        # Merge kwargs into data, with kwargs taking precedence
        self.data.update(kwargs)
        self.name = name

    def __mul__(
        self, scenario_list_or_scenario: Union["ScenarioList", "Scenario"]
    ) -> "ScenarioList":
        """Takes the cross product of a Scenario with another Scenario or ScenarioList.

        Args:
            scenario_list_or_scenario: A Scenario or ScenarioList to multiply with.

        Returns:
            A ScenarioList containing the cross product.

        Example:
            >>> s1 = Scenario({'a': 1})
            >>> s2 = Scenario({'b': 2})
            >>> s1 * s2
            ScenarioList([Scenario({'a': 1, 'b': 2})])

            >>> from edsl.scenarios import ScenarioList
            >>> sl = ScenarioList([Scenario({'b': 2}), Scenario({'b': 3})])
            >>> new_s = s1 * sl
            >>> new_s == ScenarioList([Scenario({'a': 1, 'b': 2}), Scenario({'a': 1, 'b': 3})])
            True
        """
        from .scenario_list import ScenarioList

        if isinstance(scenario_list_or_scenario, ScenarioList):
            return scenario_list_or_scenario * self
        elif isinstance(scenario_list_or_scenario, Scenario):
            return ScenarioList([self]) * scenario_list_or_scenario
        else:
            raise TypeError(
                f"Cannot multiply Scenario with {type(scenario_list_or_scenario)}"
            )

    def replicate(self, n: int) -> "ScenarioList":
        """Replicate a scenario n times to return a ScenarioList.

        Args:
            n: The number of times to replicate the scenario. Must be non-negative.

        Returns:
            A ScenarioList containing n copies of this scenario.

        Raises:
            ValueError: If n is negative.

        Examples:
            >>> s = Scenario({"food": "wood chips"})
            >>> s.replicate(2)
            ScenarioList([Scenario({'food': 'wood chips'}), Scenario({'food': 'wood chips'})])
        """
        if n < 0:
            raise ValueError("Number of replications must be non-negative")

        from .scenario_list import ScenarioList

        return ScenarioList([copy.deepcopy(self) for _ in range(n)])

    @property
    def has_jinja_braces(self) -> bool:
        """Return whether the scenario has jinja braces. This matters for rendering.

        >>> s = Scenario({"food": "I love {{wood chips}}"})
        >>> s.has_jinja_braces
        True
        """
        for _, value in self.items():
            if isinstance(value, str):
                if "{{" in value and "}}" in value:
                    return True
        return False

    def _convert_jinja_braces(
        self, replacement_left: str = "<<", replacement_right: str = ">>"
    ) -> Scenario:
        """Convert Jinja braces to some other character.

        >>> s = Scenario({"food": "I love {{wood chips}}"})
        >>> s._convert_jinja_braces()
        Scenario({'food': 'I love <<wood chips>>'})

        """
        new_scenario = Scenario()
        for key, value in self.items():
            if isinstance(value, str):
                new_scenario[key] = value.replace("{{", replacement_left).replace(
                    "}}", replacement_right
                )
            else:
                new_scenario[key] = value
        return new_scenario

    def __add__(self, other_scenario: Optional["Scenario"]) -> "Scenario":
        """Combine two scenarios by taking the union of their keys.

        If the other scenario is None, then just return self.

        Args:
            other_scenario: The other scenario to combine with. Can be None.

        Returns:
            A new Scenario containing the union of both scenarios' keys.

        Examples:
            >>> s1 = Scenario({"price": 100, "quantity": 2})
            >>> s2 = Scenario({"color": "red"})
            >>> s1 + s2
            Scenario({'price': 100, 'quantity': 2, 'color': 'red'})
            >>> (s1 + s2).__class__.__name__
            'Scenario'
        """
        if other_scenario is None:
            return self
        else:
            data1 = copy.deepcopy(self.data)
            data2 = copy.deepcopy(other_scenario.data)
            s = Scenario(data1 | data2)
            return s

    def rename(
        self,
        old_name_or_replacement_dict: Union[str, Dict[str, str]],
        new_name: Optional[str] = None,
    ) -> "Scenario":
        """Rename the keys of a scenario.

        Args:
            old_name_or_replacement_dict: Either a dictionary mapping old keys to new keys,
                or a string representing the old key name.
            new_name: The new name for the key. Required if old_name_or_replacement_dict
                is a string, ignored if it's a dictionary.

        Returns:
            A new Scenario with renamed keys.

        Raises:
            TypeError: If old_name_or_replacement_dict is a string but new_name is None.

        Examples:
            Using a dictionary:
            >>> s = Scenario({"food": "wood chips"})
            >>> s.rename({"food": "food_preference"})
            Scenario({'food_preference': 'wood chips'})

            Using individual arguments:
            >>> s = Scenario({"food": "wood chips"})
            >>> s.rename("food", "snack")
            Scenario({'snack': 'wood chips'})
        """
        if isinstance(old_name_or_replacement_dict, str):
            if new_name is None:
                raise TypeError(
                    "new_name must be provided when old_name_or_replacement_dict is a string"
                )
            replacement_dict = {old_name_or_replacement_dict: new_name}
        else:
            replacement_dict = old_name_or_replacement_dict

        new_scenario = Scenario()
        for key, value in self.items():
            if key in replacement_dict:
                new_scenario[replacement_dict[key]] = value
            else:
                new_scenario[key] = value
        return new_scenario

    def new_column_names(self, new_names: List[str]) -> "Scenario":
        """Rename all keys of a scenario using a list of new names.

        Args:
            new_names: A list of new key names. Must have the same length as the
                number of keys in the scenario.

        Returns:
            A new Scenario with keys renamed according to the provided list.

        Raises:
            ValueError: If the length of new_names doesn't match the number of keys.

        Examples:
            >>> s = Scenario({"food": "wood chips"})
            >>> s.new_column_names(["food_preference"])
            Scenario({'food_preference': 'wood chips'})
        """
        if len(new_names) != len(self.keys()):
            raise ValueError(
                f"The number of new names ({len(new_names)}) must match the number of keys ({len(self.keys())})"
            )

        new_scenario = Scenario()
        for new_name, value in zip(new_names, self.values()):
            new_scenario[new_name] = value
        return new_scenario

    def zip(self, field_a: str, field_b: str, new_name: str) -> "Scenario":
        """Zip two iterable fields into a dict and store it under a new key.

        Creates a new Scenario identical to this one, with an additional key
        named ``new_name`` whose value is ``dict(zip(self[field_a], self[field_b]))``.

        Args:
            field_a: Name of the first iterable field whose values become dict keys.
            field_b: Name of the second iterable field whose values become dict values.
            new_name: Name of the new field to store the resulting dictionary under.

        Returns:
            A new Scenario with the added zipped dictionary field.

        Raises:
            KeyError: If either field name does not exist in the Scenario.
            ScenarioError: If the referenced fields are not iterable.

        Examples:
            >>> s = Scenario({"keys": ["a", "b"], "vals": [1, 2]})
            >>> s2 = s.zip("keys", "vals", "mapping")
            >>> s2["mapping"]
            {'a': 1, 'b': 2}
        """
        a_values = self[field_a]
        b_values = self[field_b]

        try:
            zipped_dict = dict(zip(a_values, b_values))
        except TypeError as e:
            raise ScenarioError(
                f"Fields '{field_a}' and '{field_b}' must be iterable to be zipped."
            ) from e

        new_scenario = Scenario(copy.deepcopy(self.data))
        new_scenario[new_name] = zipped_dict
        return new_scenario

    def string_cat(
        self,
        key: str,
        addend: str,
        position: str = "suffix",
        inplace: bool = False,
    ) -> "Scenario":
        """Concatenate a string to the value at ``key``.

        Appends or prepends ``addend`` to the existing string value stored at
        ``key``. By default, concatenation happens as a suffix. Set
        ``position='prefix'`` to prepend. Returns a new ``Scenario`` unless
        ``inplace`` is True.

        Args:
            key: The key whose value will be concatenated.
            addend: The string to concatenate to the existing value.
            position: Either "suffix" (default) or "prefix" for where to add ``addend``.
            inplace: If True, modify this Scenario and return it. Otherwise, return a copy.

        Returns:
            A ``Scenario`` with the updated value.

        Raises:
            KeyError: If ``key`` does not exist in the Scenario.
            TypeError: If the existing value at ``key`` is not a string.
            ValueError: If ``position`` is not "suffix" or "prefix".

        Examples:
            >>> s = Scenario({"greeting": "Hello"})
            >>> s2 = s.string_cat("greeting", ", world!")
            >>> s2["greeting"]
            'Hello, world!'

            >>> s3 = s.string_cat("greeting", "Well, ", position="prefix")
            >>> s3["greeting"]
            'Well, Hello'

            In-place modification:
            >>> s_in = Scenario({"name": "Alice"})
            >>> _ = s_in.string_cat("name", " Smith", inplace=True)
            >>> s_in["name"]
            'Alice Smith'
        """
        if key not in self:
            raise KeyError(f"Key '{key}' not found in Scenario")

        current_value = self[key]
        if not isinstance(current_value, str):
            raise TypeError(
                f"Value for key '{key}' must be a string to concatenate; got {type(current_value)}"
            )

        if position not in {"suffix", "prefix"}:
            raise ValueError("position must be either 'suffix' or 'prefix'")

        target = self if inplace else Scenario(copy.deepcopy(self.data))
        if position == "suffix":
            target[key] = current_value + addend if inplace else target[key] + addend
        else:  # prefix
            target[key] = addend + current_value if inplace else addend + target[key]

        return target

    def table(self, tablefmt: str = "grid") -> str:
        """Display a scenario as a formatted table.

        Args:
            tablefmt: The table format to use. Common options include "grid",
                "simple", "pipe", "orgtbl", "rst", "mediawiki", "html", "latex".

        Returns:
            A string representation of the scenario formatted as a table.

        Examples:
            >>> s = Scenario({"food": "chips", "drink": "water"})
            >>> print(s.table("simple"))  # doctest: +SKIP
            key    value
            -----  -------
            food   chips
            drink  water
        """
        return self.to_dataset().table(tablefmt=tablefmt)

    def offload(self, inplace: bool = False) -> "Scenario":
        """
        Offload base64-encoded content from the scenario by replacing 'base64_string'
        fields with 'offloaded'. This reduces memory usage.

        This method delegates to ScenarioOffloader for the actual offloading logic.
        It handles three types of base64 content:
        1. Direct base64_string in the scenario (from FileStore.to_dict())
        2. FileStore objects containing base64 content
        3. Dictionary values containing base64_string fields

        Args:
            inplace: If True, modify the current scenario. If False, return a new one.

        Returns:
            The modified scenario (either self or a new instance).

        Examples:
            Basic offloading:
            >>> s = Scenario({"base64_string": "SGVsbG8gV29ybGQ=", "name": "test"})
            >>> offloaded = s.offload()
            >>> offloaded["base64_string"]
            'offloaded'
            >>> offloaded["name"]
            'test'

            In-place offloading:
            >>> s = Scenario({"base64_string": "SGVsbG8gV29ybGQ=", "name": "test"})
            >>> result = s.offload(inplace=True)
            >>> result is s
            True
            >>> s["base64_string"]
            'offloaded'
        """
        from .scenario_offloader import ScenarioOffloader

        return ScenarioOffloader(self).offload(inplace)

    def save_to_gcs_bucket(
        self, signed_url_or_dict: Union[str, Dict[str, str]]
    ) -> Dict[str, Any]:
        """
        Saves FileStore objects contained within this Scenario to a Google Cloud Storage bucket.

        This method finds all FileStore objects in the Scenario and uploads them to GCS using
        the provided signed URL(s). If the Scenario itself was created from a FileStore (has
        base64_string as a top-level key), it uploads that content directly.

        Args:
            signed_url_or_dict: Either:
                - str: Single signed URL (for single FileStore or Scenario from FileStore)
                - dict: Mapping of scenario keys to signed URLs for multiple FileStore objects
                        e.g., {"video": "signed_url_1", "image": "signed_url_2"}

        Returns:
            dict: Summary of upload operations performed

        Raises:
            ValueError: If no uploadable content found or content is offloaded
            requests.RequestException: If any upload fails
        """
        from .scenario_gcs import ScenarioGCS

        return ScenarioGCS(self).save_to_gcs_bucket(signed_url_or_dict)

    def get_filestore_info(self) -> Dict[str, Any]:
        """
        Returns information about FileStore objects present in this Scenario.

        This method is useful for determining how many signed URLs need to be generated
        and what file extensions/types are present before calling save_to_gcs_bucket().

        Returns:
            dict: Information about FileStore objects containing:
                - total_count: Total number of FileStore objects
                - filestore_keys: List of scenario keys that contain FileStore objects
                - file_extensions: Dictionary mapping keys to file extensions
                - file_types: Dictionary mapping keys to MIME types
                - is_filestore_scenario: Boolean indicating if this Scenario was created from a FileStore
                - summary: Human-readable summary of files


        """
        from .scenario_gcs import ScenarioGCS

        return ScenarioGCS(self).get_filestore_info()

    def to_agent_list(self) -> "AgentList":
        """Convert the scenario to an agent list.
        """
        from .scenario_list import ScenarioList
        return ScenarioList([self]).to_agent_list()

    def to(self, question_or_survey: Union["Question", "Survey"]) -> "Jobs":
        """Send the scenario to a question or survey for execution.

        Args:
            question_or_survey: A Question or Survey object to parameterize with this scenario.

        Returns:
            A Jobs object that can be run to execute the question or survey with this scenario.

        Examples:
            >>> from edsl.questions import QuestionFreeText
            >>> s = Scenario({"name": "Alice"})
            >>> q = QuestionFreeText(question_name="greeting", question_text="Hello {{name}}")
            >>> jobs = s.to(q)  # doctest: +SKIP
        """
        return question_or_survey.by(self)

    def open_url(self, position: int = 0) -> None:
        """Open a URL field from the scenario in the default web browser.

        Args:
            position: The index of the URL to open (0-based). Defaults to 0 for the first URL.

        Raises:
            ValueError: If no URL fields are found in the scenario, or if the position
                is out of range.

        Examples:
            >>> s = Scenario({"website": "https://example.com", "name": "test"})
            >>> s.open_url()  # Opens the first URL found  # doctest: +SKIP
        """
        urls = [v for v in self.values() if isinstance(v, str) and v.startswith("http")]
        if not urls:
            raise ValueError("No URL fields found in scenario")
        if position >= len(urls):
            raise ValueError(
                f"Position {position} is out of range for {len(urls)} URLs"
            )

        import webbrowser

        webbrowser.open(urls[position])

    def to_dict(
        self, add_edsl_version: bool = True, offload_base64: bool = False
    ) -> Dict[str, Any]:
        """Convert a scenario to a dictionary.

        Args:
            add_edsl_version: If True, adds the EDSL version to the returned dictionary.
            offload_base64: If True, replaces any base64_string fields with 'offloaded'
                           to reduce memory usage.

        Example:

        >>> s = Scenario({"food": "wood chips"})
        >>> s.to_dict()  # doctest: +ELLIPSIS
        {'food': 'wood chips', 'edsl_version': '...', 'edsl_class_name': 'Scenario'}

        >>> s.to_dict(add_edsl_version = False)
        {'food': 'wood chips'}

        """
        from .scenario_serializer import ScenarioSerializer

        return ScenarioSerializer(self).to_dict(add_edsl_version, offload_base64)

    def __hash__(self) -> int:
        """Return a hash of the scenario.

        Example:

        >>> s = Scenario({"food": "wood chips"})
        >>> hash(s)
        1153210385458344214
        """
        # Use cached hash if already computed
        if hasattr(self, "_cached_hash"):
            return self._cached_hash

        # Compute hash for first time and cache it in the object
        from .scenario_serializer import ScenarioSerializer

        serializer = ScenarioSerializer(self)
        self._cached_hash = serializer.compute_hash()
        return self._cached_hash

    def __repr__(self):
        return "Scenario(" + repr(self.data) + ")"

    def __getattr__(self, name: str) -> Any:
        """Allow accessing scenario values using dot notation.

        This enables accessing scenario dictionary values as attributes.
        For example, if s = Scenario({'a': 'b'}), then s.a returns 'b'.

        Args:
            name: The attribute name to look up in the scenario data.

        Returns:
            The value associated with the key in the scenario data.

        Raises:
            AttributeError: If the key doesn't exist in the scenario data.

        Examples:
            >>> s = Scenario({'product': 'coffee', 'price': 4.99})
            >>> s.product
            'coffee'
            >>> s.price
            4.99
        """
        # Avoid infinite recursion during copy.deepcopy by checking __dict__ directly
        # This prevents recursion when deepcopy checks for special methods like __setstate__
        if 'data' not in self.__dict__:
            raise AttributeError(f"'Scenario' object has no attribute '{name}'")
        try:
            return self.data[name]
        except KeyError:
            raise AttributeError(f"'Scenario' object has no attribute '{name}'")

    def to_dataset(self) -> "Dataset":
        """Convert a scenario to a dataset.

        >>> s = Scenario({"food": "wood chips"})
        >>> s.to_dataset()
        Dataset([{'key': ['food']}, {'value': ['wood chips']}])
        """
        from .scenario_serializer import ScenarioSerializer

        return ScenarioSerializer(self).to_dataset()

    def select(self, *args: Union[str, Iterable[str]]) -> "Scenario":
        """Select a subset of keys from a scenario.

        This method delegates to ScenarioSelector for the actual selection logic.
        It supports both individual string arguments and collection arguments
        for backward compatibility.

        Args:
            *args: Either a single collection of keys (for backward compatibility)
                   or individual string arguments for keys to select.

        Returns:
            A new Scenario containing only the selected keys and their values.

        Raises:
            KeyError: If any of the specified keys don't exist in the scenario.
            ValueError: If no arguments are provided.

        Examples:
            Using a list (backward compatible):
            >>> s = Scenario({"food": "wood chips", "drink": "water"})
            >>> s.select(["food"])
            Scenario({'food': 'wood chips'})

            Using individual string arguments:
            >>> s = Scenario({"food": "wood chips", "drink": "water", "dessert": "cookies"})
            >>> s.select("food", "drink")
            Scenario({'food': 'wood chips', 'drink': 'water'})

            Single string argument:
            >>> s.select("food")
            Scenario({'food': 'wood chips'})
        """
        from .scenario_selector import ScenarioSelector

        return ScenarioSelector(self).select(*args)

    def drop(self, *args: Union[str, Iterable[str]]) -> "Scenario":
        """Drop a subset of keys from a scenario.

        This method delegates to ScenarioSelector for the actual dropping logic.
        It supports both individual string arguments and collection arguments
        for backward compatibility.

        Args:
            *args: Either a single collection of keys (for backward compatibility)
                   or individual string arguments for keys to drop.

        Returns:
            A new Scenario containing all keys except the dropped ones.

        Raises:
            ValueError: If no arguments are provided.

        Examples:
            Using a list (backward compatible):
            >>> s = Scenario({"food": "wood chips", "drink": "water"})
            >>> s.drop(["food"])
            Scenario({'drink': 'water'})

            Using individual string arguments:
            >>> s = Scenario({"food": "wood chips", "drink": "water", "dessert": "cookies"})
            >>> s.drop("drink", "dessert")
            Scenario({'food': 'wood chips'})

            Single string argument:
            >>> s.drop("drink")
            Scenario({'food': 'wood chips', 'dessert': 'cookies'})
        """
        from .scenario_selector import ScenarioSelector

        return ScenarioSelector(self).drop(*args)

    def keep(self, *args: Union[str, Iterable[str]]) -> "Scenario":
        """Keep a subset of keys from a scenario (alias for select).

        This method delegates to ScenarioSelector for the actual selection logic.
        It is functionally identical to select() but provides more intuitive naming.

        Args:
            *args: Either a single collection of keys (for backward compatibility)
                   or individual string arguments for keys to keep.

        Returns:
            A new Scenario containing only the kept keys and their values.

        Raises:
            KeyError: If any of the specified keys don't exist in the scenario.
            ValueError: If no arguments are provided.

        Examples:
            Using a list (backward compatible):
            >>> s = Scenario({"food": "wood chips", "drink": "water"})
            >>> s.keep(["food"])
            Scenario({'food': 'wood chips'})

            Using individual string arguments:
            >>> s = Scenario({"food": "wood chips", "drink": "water", "dessert": "cookies"})
            >>> s.keep("food", "drink")
            Scenario({'food': 'wood chips', 'drink': 'water'})
        """
        from .scenario_selector import ScenarioSelector

        return ScenarioSelector(self).keep(*args)

    @classmethod
    def from_url(
        cls, url: str, field_name: Optional[str] = "text", testing: bool = False
    ) -> "Scenario":
        """
        Creates a Scenario from the content of a URL.

        This method fetches content from a web URL and creates a Scenario containing the URL
        and the extracted text. When available, BeautifulSoup is used for better HTML parsing
        and text extraction, otherwise a basic requests approach is used.

        Args:
            url: The URL to fetch content from.
            field_name: The key name to use for storing the extracted text in the Scenario.
                        Defaults to "text".
            testing: If True, uses a simplified requests method instead of BeautifulSoup.
                    This is primarily for testing purposes.

        Returns:
            A Scenario containing the URL and extracted text.

        Raises:
            requests.exceptions.RequestException: If the URL cannot be accessed.

        Examples:
            Create a scenario from a URL (requires network access):

            s = Scenario.from_url("https://example.com", testing=True)
            # Returns a Scenario with "url" and "text" fields

            s = Scenario.from_url("https://example.com", field_name="content", testing=True)
            # Returns a Scenario with "url", "html", and "content" fields

        Notes:
            - The method attempts to use BeautifulSoup and fake_useragent for better
              HTML parsing and to mimic a real browser.
            - If these packages are not available, it falls back to basic requests.
            - When using BeautifulSoup, it extracts text from paragraph and heading tags.
        """
        from .scenario_factory import ScenarioFactory

        return ScenarioFactory.from_url(url, field_name, testing)

    @classmethod
    def from_file(cls, file_path: str, field_name: str) -> "Scenario":
        """
        Creates a Scenario containing a FileStore object from a file.

        This method creates a Scenario with a single key-value pair where the value
        is a FileStore object that encapsulates the specified file. The FileStore
        handles appropriate file loading, encoding, and extraction based on the file type.

        Args:
            file_path: Path to the file to be incorporated into the Scenario.
            field_name: Key name to use for storing the FileStore in the Scenario.

        Returns:
            A Scenario containing a FileStore object linked to the specified file.

        Raises:
            FileNotFoundError: If the specified file does not exist.

        Examples:
            >>> import tempfile
            >>> with tempfile.NamedTemporaryFile(suffix=".txt", mode="w") as f:
            ...     _ = f.write("This is a test.")
            ...     _ = f.flush()
            ...     s = Scenario.from_file(f.name, "file")
            >>> s  # doctest: +ELLIPSIS
            Scenario({'file': FileStore(path='...', ...)})

        Notes:
            - The FileStore object handles various file formats differently
            - FileStore provides methods to access file content, extract text,
              and manage file operations appropriate to the file type
        """
        from .scenario_factory import ScenarioFactory

        return ScenarioFactory.from_file(file_path, field_name)

    @classmethod
    def from_image(
        cls, image_path: str, image_name: Optional[str] = None
    ) -> "Scenario":
        """
        Creates a Scenario containing an image file as a FileStore object.

        This method creates a Scenario with a single key-value pair where the value
        is a FileStore object that encapsulates the specified image file. The image
        is stored as a base64-encoded string, allowing it to be easily serialized
        and transmitted.

        Args:
            image_path: Path to the image file to be incorporated into the Scenario.
            image_name: Key name to use for storing the FileStore in the Scenario.
                       If not provided, uses the filename without extension.

        Returns:
            A Scenario containing a FileStore object with the image data.

        Raises:
            FileNotFoundError: If the specified image file does not exist.

        Examples:
            >>> import os
            >>> # Assuming an image file exists
            >>> if os.path.exists("image.jpg"):
            ...     s = Scenario.from_image("image.jpg")
            ...     s_named = Scenario.from_image("image.jpg", "picture")

        Notes:
            - The resulting FileStore can be displayed in notebooks or used in questions
            - Supported image formats include JPG, PNG, GIF, etc.
            - The image is stored as a base64-encoded string for portability
        """
        from .scenario_factory import ScenarioFactory

        return ScenarioFactory.from_image(image_path, image_name)

    @classmethod
    def from_pdf(cls, pdf_path: str) -> "Scenario":
        """
        Creates a Scenario containing text extracted from a PDF file.

        This method extracts text and metadata from a PDF file and creates a Scenario
        containing this information. It uses the PdfExtractor class which provides
        access to text content, metadata, and structure from PDF files.

        Args:
            pdf_path: Path to the PDF file to extract content from.

        Returns:
            A Scenario containing extracted text and metadata from the PDF.

        Raises:
            FileNotFoundError: If the specified PDF file does not exist.
            ImportError: If the required PDF extraction libraries are not installed.

        Examples:
            >>> import os
            >>> # Assuming a PDF file exists
            >>> if os.path.exists("document.pdf"):
            ...     s = Scenario.from_pdf("document.pdf")

        Notes:
            - The returned Scenario contains various keys with PDF content and metadata
            - PDF extraction requires the PyMuPDF library
            - The extraction process parses the PDF to maintain structure where possible
        """
        from .scenario_factory import ScenarioFactory

        return ScenarioFactory.from_pdf(pdf_path)

    @classmethod
    def from_html(cls, url: str, field_name: Optional[str] = None) -> "Scenario":
        """
        Creates a Scenario containing both HTML content and extracted text from a URL.

        This method fetches HTML content from a URL, extracts readable text from it,
        and creates a Scenario containing the original URL, the raw HTML, and the
        extracted text. Unlike from_url, this method preserves the raw HTML content.

        Args:
            url: URL to fetch HTML content from.
            field_name: Key name to use for the extracted text in the Scenario.
                       If not provided, defaults to "text".

        Returns:
            A Scenario containing the URL, raw HTML, and extracted text.

        Raises:
            requests.exceptions.RequestException: If the URL cannot be accessed.

        Examples:
            Create a scenario from HTML content (requires network access):

            s = Scenario.from_html("https://example.com")
            # Returns a Scenario with "url", "html", and "text" fields

            s = Scenario.from_html("https://example.com", field_name="content")
            # Returns a Scenario with "url", "html", and "content" fields

        Notes:
            - Uses BeautifulSoup for HTML parsing when available
            - Stores both the raw HTML and the extracted text
            - Provides a more comprehensive representation than from_url
            - Useful when the HTML structure or specific elements are needed
        """
        from .scenario_factory import ScenarioFactory

        return ScenarioFactory.from_html(url, field_name)

    @classmethod
    def from_pdf_to_image(cls, pdf_path: str, image_format: str = "jpeg") -> "Scenario":
        """
        Converts each page of a PDF into an image and creates a Scenario containing them.

        This method takes a PDF file, converts each page to an image in the specified
        format, and creates a Scenario containing the original file path and FileStore
        objects for each page image. This is particularly useful for visualizing PDF
        content or for image-based processing of PDF documents.

        Args:
            pdf_path: Path to the PDF file to convert to images.
            image_format: Format of the output images (default is 'jpeg').
                         Other formats include 'png', 'tiff', etc.

        Returns:
            A Scenario containing the original PDF file path and FileStore objects
            for each page image, with keys like "page_0", "page_1", etc.

        Raises:
            FileNotFoundError: If the specified PDF file does not exist.
            ImportError: If pdf2image is not installed.

        Examples:
            >>> import os
            >>> # Assuming a PDF file exists
            >>> if os.path.exists("document.pdf"):
            ...     s = Scenario.from_pdf_to_image("document.pdf")
            ...     s_png = Scenario.from_pdf_to_image("document.pdf", "png")

        Notes:
            - Requires the pdf2image library which depends on poppler
            - Creates a separate image for each page of the PDF
            - Images are stored in FileStore objects for easy display and handling
            - Images are created in a temporary directory which is automatically cleaned up
        """
        from .scenario_factory import ScenarioFactory

        return ScenarioFactory.from_pdf_to_image(pdf_path, image_format)

    def to_scenario_list(self) -> "ScenarioList":
        """
        Convert the Scenario to a ScenarioList.
        """
        from .scenario_list import ScenarioList
        return ScenarioList([self])

    def replace_value(self, key: str, value: Any) -> "Scenario":
        """Replace the value of a key in the Scenario.
        """
        self[key] = value
        return self

    @classmethod
    def from_docx(cls, docx_path: str) -> "Scenario":
        """
        Creates a Scenario containing text extracted from a Microsoft Word document.

        This method extracts text and structure from a DOCX file and creates a Scenario
        containing this information. It uses the DocxScenario class to handle the
        extraction process and maintain document structure where possible.

        Args:
            docx_path: Path to the DOCX file to extract content from.

        Returns:
            A Scenario containing the file path and extracted text from the DOCX file.

        Raises:
            FileNotFoundError: If the specified DOCX file does not exist.
            ImportError: If the python-docx library is not installed.

        Examples:
            >>> from docx import Document
            >>> doc = Document()
            >>> _ = doc.add_heading("EDSL Survey")
            >>> _ = doc.add_paragraph("This is a test.")
            >>> doc.save("test.docx")
            >>> s = Scenario.from_docx("test.docx")
            >>> s
            Scenario({'file_path': 'test.docx', 'text': 'EDSL Survey\\nThis is a test.'})
            >>> import os; os.remove("test.docx")

        Notes:
            - The returned Scenario typically contains the file path and extracted text
            - The extraction process attempts to maintain document structure
            - Requires the python-docx library to be installed
        """
        from .scenario_factory import ScenarioFactory

        return ScenarioFactory.from_docx(docx_path)

    def chunk_text(self, 
    field: str,
    chunk_size_field: str, 
    unit: str = "word",
    include_original: bool = False,
    hash_original: bool = False,
    ) -> "ScenarioList":
        """
        Chunks a text field into smaller chunks of a specified size, creating a ScenarioList.

        This method takes a field containing text and divides it into smaller chunks
        based on either word count or line count. It's particularly useful for processing
        large text documents in manageable pieces, such as for summarization, analysis,
        or when working with models that have token limits.
        """
        from .document_chunker import DocumentChunker
        if unit == "word":
            num_words = self[chunk_size_field]
            num_lines = None
        elif unit == "line":
            num_lines = self[chunk_size_field]
            num_words = None
        else:
            raise Exception(f"Invalid unit: {unit}. Must be 'word' or 'line'.")
        return  DocumentChunker(self).chunk(
            field, num_words, num_lines, include_original, hash_original
        )
        
    def chunk(
        self,
        field: str,
        num_words: Optional[int] = None,
        num_lines: Optional[int] = None,
        include_original: bool = False,
        hash_original: bool = False,
    ) -> "ScenarioList":
        """
        Splits a text field into chunks of a specified size, creating a ScenarioList.

        This method takes a field containing text and divides it into smaller chunks
        based on either word count or line count. It's particularly useful for processing
        large text documents in manageable pieces, such as for summarization, analysis,
        or when working with models that have token limits.

        Args:
            field: The key name of the field in the Scenario to split.
            num_words: The number of words to include in each chunk. Mutually exclusive
                      with num_lines.
            num_lines: The number of lines to include in each chunk. Mutually exclusive
                      with num_words.
            include_original: If True, includes the original complete text in each chunk
                             with a "_original" suffix.
            hash_original: If True and include_original is True, stores a hash of the
                          original text instead of the full text.

        Returns:
            A ScenarioList containing multiple Scenarios, each with a chunk of the
            original text. Each Scenario includes the chunk text, chunk index, character
            count, and word count.

        Raises:
            ValueError: If neither num_words nor num_lines is specified, or if both are.
            KeyError: If the specified field doesn't exist in the Scenario.

        Examples:
            Split by lines (1 line per chunk):
            >>> s = Scenario({"text": "This is a test.\\nThis is a test.\\n\\nThis is a test."})
            >>> s.chunk("text", num_lines=1)
            ScenarioList([Scenario({'text': 'This is a test.', 'text_chunk': 0, 'text_char_count': 15, 'text_word_count': 4}), Scenario({'text': 'This is a test.', 'text_chunk': 1, 'text_char_count': 15, 'text_word_count': 4}), Scenario({'text': '', 'text_chunk': 2, 'text_char_count': 0, 'text_word_count': 0}), Scenario({'text': 'This is a test.', 'text_chunk': 3, 'text_char_count': 15, 'text_word_count': 4})])

            Split by words (2 words per chunk):
            >>> s.chunk("text", num_words=2)
            ScenarioList([Scenario({'text': 'This is', 'text_chunk': 0, 'text_char_count': 7, 'text_word_count': 2}), Scenario({'text': 'a test.', 'text_chunk': 1, 'text_char_count': 7, 'text_word_count': 2}), Scenario({'text': 'This is', 'text_chunk': 2, 'text_char_count': 7, 'text_word_count': 2}), Scenario({'text': 'a test.', 'text_chunk': 3, 'text_char_count': 7, 'text_word_count': 2}), Scenario({'text': 'This is', 'text_chunk': 4, 'text_char_count': 7, 'text_word_count': 2}), Scenario({'text': 'a test.', 'text_chunk': 5, 'text_char_count': 7, 'text_word_count': 2})])

            Include original text in each chunk:
            >>> s = Scenario({"text": "Hello World"})
            >>> s.chunk("text", num_words=1, include_original=True)
            ScenarioList([Scenario({'text': 'Hello', 'text_chunk': 0, 'text_char_count': 5, 'text_word_count': 1, 'text_original': 'Hello World'}), Scenario({'text': 'World', 'text_chunk': 1, 'text_char_count': 5, 'text_word_count': 1, 'text_original': 'Hello World'})])

            Use a hash of the original text:
            >>> s.chunk("text", num_words=1, include_original=True, hash_original=True)
            ScenarioList([Scenario({'text': 'Hello', 'text_chunk': 0, 'text_char_count': 5, 'text_word_count': 1, 'text_original': 'b10a8db164e0754105b7a99be72e3fe5'}), Scenario({'text': 'World', 'text_chunk': 1, 'text_char_count': 5, 'text_word_count': 1, 'text_original': 'b10a8db164e0754105b7a99be72e3fe5'})])

        Notes:
            - Either num_words or num_lines must be specified, but not both
            - Each chunk is assigned a sequential index in the 'text_chunk' field
            - Character and word counts for each chunk are included
            - When include_original is True, the original text is preserved in each chunk
            - The hash_original option is useful to save space while maintaining traceability
        """
        from .document_chunker import DocumentChunker

        return DocumentChunker(self).chunk(
            field, num_words, num_lines, include_original, hash_original
        )

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Scenario":
        """
        Creates a Scenario from a dictionary, with special handling for FileStore objects.

        This method creates a Scenario using the provided dictionary. It has special handling
        for dictionary values that represent serialized FileStore objects, which it will
        deserialize back into proper FileStore instances.

        Args:
            d: A dictionary to convert to a Scenario.

        Returns:
            A new Scenario containing the provided dictionary data.

        Examples:
            >>> Scenario.from_dict({"food": "wood chips"})
            Scenario({'food': 'wood chips'})

            >>> # Example with a serialized FileStore
            >>> from edsl import FileStore  # doctest: +SKIP
            >>> file_dict = {"path": "example.txt", "base64_string": "SGVsbG8gV29ybGQ="}  # doctest: +SKIP
            >>> s = Scenario.from_dict({"document": file_dict})  # doctest: +SKIP
            >>> isinstance(s["document"], FileStore)  # doctest: +SKIP
            True

        Notes:
            - Any dictionary values that match the FileStore format will be converted to FileStore objects
            - The method detects FileStore objects by looking for "base64_string" and "path" keys
            - EDSL version information is automatically removed by the @remove_edsl_version decorator
            - This method is commonly used when deserializing scenarios from JSON or other formats
        """
        from .scenario_serializer import ScenarioSerializer

        return ScenarioSerializer.from_dict(d)

    def _table(self) -> tuple[List[Dict[str, str]], List[str]]:
        """Prepare generic table data for scenario attributes.

        Returns:
            A tuple containing:
            - A list of dictionaries with 'Attribute' and 'Value' keys
            - A list of column names

        Examples:
            >>> s = Scenario({"food": "wood chips"})
            >>> table_data, columns = s._table()
            >>> columns
            ['Attribute', 'Value']
            >>> len(table_data) >= 1  # At least data attribute
            True
        """
        table_data = []
        for attr_name, attr_value in self.__dict__.items():
            table_data.append({"Attribute": attr_name, "Value": repr(attr_value)})
        column_names = ["Attribute", "Value"]
        return table_data, column_names

    @classmethod
    def example(cls, randomize: bool = False) -> "Scenario":
        """Returns an example Scenario instance.

        Args:
            randomize: If True, adds a random string to the value of the example key
                to ensure uniqueness.

        Returns:
            A Scenario instance with example data suitable for testing or demonstration.

        Examples:
            >>> s = Scenario.example()
            >>> 'persona' in s
            True
            >>> s1 = Scenario.example(randomize=True)
            >>> s2 = Scenario.example(randomize=True)
            >>> s1.data != s2.data  # Should be different due to randomization
            True
        """
        from .scenario_factory import ScenarioFactory

        return ScenarioFactory.example(randomize)

    def code(self) -> List[str]:
        """Generate Python code to recreate this scenario.

        Returns:
            A list of strings representing Python code lines that can be executed
            to recreate this scenario.

        Examples:
            >>> s = Scenario({"name": "Alice", "age": 30})
            >>> code_lines = s.code()
            >>> print("\\n".join(code_lines))  # doctest: +SKIP
            from edsl.scenarios import Scenario
            s = Scenario({'name': 'Alice', 'age': 30})
        """
        lines = []
        lines.append("from edsl.scenarios import Scenario")
        lines.append(f"s = Scenario({self.data!r})")
        return lines


if __name__ == "__main__":
    import doctest

    doctest.testmod(optionflags=doctest.ELLIPSIS)
