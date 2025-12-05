from __future__ import annotations
from typing import Union, Optional, List, Any, Dict

from jinja2 import Template
from pydantic import BaseModel, Field
from rank_bm25 import BM25Okapi

from .question_base import QuestionBase
from .descriptors import QuestionOptionsDescriptor
from .decorators import inject_exception
from .response_validator_abc import ResponseValidatorABC


class BaseDropdownResponse(BaseModel):
    """
    Base model for dropdown responses.

    The answer will be one of the original question_options after BM25 search.
    """
    answer: str = Field(..., description="Selected option after BM25 search")
    comment: Optional[str] = Field(None, description="Optional comment field")
    generated_tokens: Optional[Any] = Field(None, description="Generated tokens")


class DropdownResponseValidator(ResponseValidatorABC):
    """
    Validator for dropdown responses.

    Since the answer comes from BM25 search of original options,
    validation is straightforward - just ensure it's in the options list.
    """

    required_params = ["question_options", "question"]

    def _preprocess(self, data: dict) -> dict:
        """
        Transform search terms to actual options via BM25 search.

        This runs BEFORE Pydantic validation, so the answer field
        will contain a valid option when validation occurs.
        """
        # Get the raw answer (which contains search terms from the LLM)
        raw_answer = data.get("answer")

        if raw_answer and isinstance(raw_answer, str):
            # Check if it's already a valid option (shouldn't happen with proper templates)
            if raw_answer in [str(opt) for opt in self.question_options]:
                return data

            # Run BM25 search on the search terms
            try:
                search_results = self.question.perform_bm25_search(raw_answer)

                # If we got results, use the top one as the answer
                if search_results and len(search_results) > 0:
                    data["answer"] = search_results[0]
                else:
                    # Fallback: if no search results, keep original
                    # (this will likely fail validation, but that's expected)
                    pass
            except Exception:
                # If BM25 search fails, keep original answer
                # (this will likely fail validation)
                pass

        return data

    def fix(self, response, verbose=False):
        """
        Fix dropdown response. Since answers come from BM25 search,
        they should always be valid options.
        """
        answer = response.get("answer")
        if answer in self.question_options:
            return response

        # If somehow an invalid answer got through, try to match it
        if isinstance(answer, str):
            for option in self.question_options:
                if str(option).strip().lower() == answer.strip().lower():
                    return {
                        "answer": option,
                        "comment": response.get("comment"),
                        "generated_tokens": response.get("generated_tokens"),
                    }

        # Return original if no fix possible
        return response

    valid_examples = [
        ({"answer": "Option A"}, {"question_options": ["Option A", "Option B", "Option C"]})
    ]

    invalid_examples = [
        (
            {"answer": "Invalid Option"},
            {"question_options": ["Option A", "Option B", "Option C"]},
            "Value error, answer must be one of the provided options",
        )
    ]


class QuestionDropdown(QuestionBase):
    """
    A question that uses BM25 search to select from large option sets.

    QuestionDropdown is designed for scenarios where there are hundreds or thousands of options.
    Instead of presenting all options to the LLM, it:

    1. Shows the question_text and a sample of options (specified by indices) to the LLM
    2. LLM generates search keywords
    3. Uses BM25 to rank all options against the keywords
    4. Returns the top k options (or top 1 if feeling_lucky=True)

    Key Features:
    - Handles large option sets efficiently
    - Uses BM25 search for relevant option ranking
    - Optional detailed descriptions for richer search context
    - "Feeling lucky" mode for automatic top result selection
    - Configurable sample indices for LLM context

    Examples:
        Basic usage with large city list:

        ```python
        cities = ["New York", "Paris", "Tokyo", "London", ...]  # 1000+ cities
        q = QuestionDropdown(
            question_name="city_choice",
            question_text="Which city matches your travel preferences for cultural activities?",
            question_options=cities,
            sample_indices=[0, 10, 20, 30, 40],  # Show specific examples
            max_options_shown=5
        )
        ```

        With detailed descriptions and feeling lucky:

        ```python
        restaurants = ["Mario's Pizza", "Sushi Zen", "Burger Palace", ...]
        details = [
            "Authentic Italian pizza with wood-fired oven and family recipes",
            "Traditional Japanese sushi with daily fresh fish from Tsukiji market",
            "American-style gourmet burgers with grass-fed beef and artisan buns",
            ...
        ]
        q = QuestionDropdown(
            question_name="restaurant",
            question_text="Which restaurant would you prefer for a romantic dinner?",
            question_options=restaurants,
            question_options_details=details,
            sample_indices=None,  # Use first 10 by default
            feeling_lucky=True    # Automatically pick the best match
        )
        ```
    """

    question_type = "dropdown"
    purpose = "When options are numerous and need to be searched"
    question_options: Union[list[str], list[list], list[float], list[int]] = (
        QuestionOptionsDescriptor()
    )
    _response_model = None
    response_validator_class = DropdownResponseValidator

    def __init__(
        self,
        question_name: str,
        question_text: str,
        question_options: Union[list[str], list[list], list[float], list[int]],
        question_options_details: Optional[List[str]] = None,
        sample_indices: Optional[List[int]] = None,
        max_options_shown: int = 5,
        feeling_lucky: bool = False,
        include_comment: bool = True,
        use_code: bool = False,
        answering_instructions: Optional[str] = None,
        question_presentation: Optional[str] = None,
        permissive: bool = False,
        **kwargs  # Handle additional parameters like 'answer' during deserialization
    ):
        """
        Initialize a new dropdown question with BM25 search capability.

        Parameters
        ----------
        question_name : str
            The name of the question, used as an identifier.

        question_text : str
            The actual text of the question to be asked.

        question_options : Union[list[str], list[list], list[float], list[int]]
            The large list of options to choose from (can be hundreds/thousands).

        question_options_details : Optional[List[str]], default=None
            Optional detailed descriptions for each option. Must be same length as
            question_options if provided. These are indexed along with the options
            for richer BM25 search context.

        sample_indices : Optional[List[int]], default=None
            List of indices specifying which options to show to the LLM as examples.
            If None, defaults to the first 10 options (or all if fewer than 10).

        max_options_shown : int, default=5
            Maximum number of top-ranked options to return after BM25 search.

        feeling_lucky : bool, default=False
            If True, automatically return only the top-ranked option after BM25 search.
            If False, return up to max_options_shown options for the LLM to choose from.

        include_comment : bool, default=True
            Whether to include a comment field in the response.

        use_code : bool, default=False
            If True, the answer will be the index of the selected option.

        answering_instructions : Optional[str], default=None
            Custom instructions for how the model should answer.

        question_presentation : Optional[str], default=None
            Custom template for how the question is presented.

        permissive : bool, default=False
            If True, accept answers not in the search results (rarely needed).
        """
        self.question_name = question_name
        self.question_text = question_text
        self.question_options = self._clean_nan_from_options(question_options)
        self.question_options_details = question_options_details

        # Set sample indices - default to first 10 if None
        if sample_indices is None:
            default_count = min(10, len(self.question_options))
            self.sample_indices = list(range(default_count))
        else:
            # Validate sample indices
            max_index = len(self.question_options) - 1
            invalid_indices = [i for i in sample_indices if i < 0 or i > max_index]
            if invalid_indices:
                raise ValueError(
                    f"Invalid sample indices {invalid_indices}. "
                    f"Must be between 0 and {max_index} for {len(self.question_options)} options."
                )
            self.sample_indices = sample_indices

        self.max_options_shown = max_options_shown
        self.feeling_lucky = feeling_lucky

        # Validate question_options_details if provided
        if question_options_details is not None:
            if len(question_options_details) != len(question_options):
                raise ValueError(
                    f"question_options_details must have same length as question_options. "
                    f"Got {len(question_options_details)} details for {len(question_options)} options."
                )

        self._include_comment = include_comment
        self.use_code = use_code
        self.answering_instructions = answering_instructions
        self.question_presentation = question_presentation
        self.permissive = permissive

        # Handle any additional kwargs (like 'answer' during deserialization)
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)

        # Initialize BM25 index
        self._bm25_index = None
        self._search_corpus = None
        self._initialize_bm25_index()

    @property
    def data(self) -> dict:
        """Return a dictionary of question attributes excluding internal BM25 attributes."""
        # Get the base data
        exclude_list = [
            "question_type",
            "_fake_data_factory",
            "_model_instructions",
            "_bm25_index",  # Exclude BM25 index from serialization
            "_search_corpus",  # Exclude search corpus from serialization
        ]
        only_if_not_na_list = ["_answering_instructions", "_question_presentation"]
        only_if_not_default_list = {"_include_comment": True, "_use_code": False}

        d = {}
        for key, value in self.__dict__.items():
            if key in exclude_list:
                continue
            elif key in only_if_not_na_list and value is None:
                continue
            elif key in only_if_not_default_list and value == only_if_not_default_list[key]:
                continue
            else:
                # Clean up private attribute names for public API
                clean_key = key.lstrip("_") if key.startswith("_") else key
                d[clean_key] = value

        return d

    @property
    def fake_data_factory(self):
        """Override fake_data_factory to provide deterministic, valid options for testing."""
        if not hasattr(self, "_fake_data_factory"):
            from polyfactory.factories.pydantic_factory import ModelFactory

            # Capture self reference for closure
            question_self = self

            class DropdownFakeData(ModelFactory[self.response_model]):
                @classmethod
                def build_answer(cls):
                    # Always return the first option for deterministic testing
                    if question_self.use_code:
                        return 0  # First option index
                    else:
                        return str(question_self.question_options[0])  # First option text

                @classmethod
                def build_comment(cls):
                    # Consistent comment for testing
                    return "Deterministic test comment"

                @classmethod
                def build_generated_tokens(cls):
                    # Consistent generated tokens for testing
                    return None

            self._fake_data_factory = DropdownFakeData
        return self._fake_data_factory

    def _simulate_answer(self, human_readable: bool = False) -> dict:
        """
        Generate a deterministic simulated answer for testing.

        Override base implementation to ensure consistency with example_model.
        """
        if self.use_code:
            answer = 0  # First option index
        else:
            answer = str(self.question_options[0])  # First option text

        result = {"answer": answer, "comment": None, "generated_tokens": None}

        if self._include_comment:
            result["comment"] = "Deterministic test comment"

        return result

    def _clean_nan_from_options(self, options):
        """Clean NaN values from question options, replacing them with None."""
        import math

        if not isinstance(options, list):
            return options

        cleaned_options = []
        for option in options:
            if isinstance(option, float) and math.isnan(option):
                cleaned_options.append(None)
            else:
                cleaned_options.append(option)
        return cleaned_options

    def _initialize_bm25_index(self):
        """Initialize the BM25 index for searching options."""
        # Prepare search corpus
        self._search_corpus = []
        for i, option in enumerate(self.question_options):
            # Combine option text with details if available
            if self.question_options_details:
                combined_text = f"{option} {self.question_options_details[i]}"
            else:
                combined_text = str(option)

            # Tokenize for BM25
            self._search_corpus.append(combined_text.lower().split())

        # Initialize BM25 index
        self._bm25_index = BM25Okapi(self._search_corpus)

    def _get_sample_options(self) -> List[str]:
        """Get the sample options to show to the LLM based on sample_indices."""
        return [str(self.question_options[i]) for i in self.sample_indices]

    def perform_bm25_search(self, search_terms: str, verbose: bool = False) -> List[str]:
        """
        Perform BM25 search on options using the provided search terms.

        Args:
            search_terms: Keywords generated by the LLM
            verbose: Whether to print debug information

        Returns:
            List of top-ranked options based on BM25 scores
        """
        if not search_terms.strip():
            # If no search terms, return sample
            return self._get_sample_options()[:self.max_options_shown]

        if verbose:
            print(f"BM25 search with terms: '{search_terms}'")
            print(f"Searching {len(self.question_options)} options")

        # Tokenize query
        query_tokens = search_terms.lower().split()

        # Get BM25 scores
        scores = self._bm25_index.get_scores(query_tokens)

        # Create list of (score, index, option) tuples
        scored_results = [
            (score, i, self.question_options[i])
            for i, score in enumerate(scores)
        ]

        # Sort by score (descending)
        scored_results.sort(key=lambda x: x[0], reverse=True)

        # Get top results
        if self.feeling_lucky:
            top_options = [scored_results[0][2]] if scored_results else []
        else:
            top_options = [result[2] for result in scored_results[:self.max_options_shown]]

        if verbose:
            print(f"Top {len(top_options)} options after BM25 search:")
            for i, (score, idx, option) in enumerate(scored_results[:len(top_options)]):
                print(f"  {i+1}. {option} (score: {score:.3f})")

        return [str(opt) for opt in top_options]

    def create_response_model(self, replacement_dict: dict = None):
        """
        Create the response model for validation.

        Since the dropdown works by search, the response model accepts
        any of the original question_options.
        """
        if replacement_dict is None:
            replacement_dict = {}

        # For dropdown, any of the original options could be returned after search
        from .question_multiple_choice import create_response_model

        if self.use_code:
            # Use indices
            valid_codes = list(range(len(self.question_options)))
            return create_response_model(valid_codes, self.permissive)
        else:
            # Use the actual option values
            valid_options = [str(opt) for opt in self.question_options]
            return create_response_model(valid_options, self.permissive)

    def _translate_answer_code_to_answer(
        self, answer_code: int, replacements_dict: Optional[dict] = None
    ):
        """Translate answer code to actual answer text."""
        if replacements_dict is None:
            replacements_dict = {}

        if self.use_code:
            try:
                return str(self.question_options[int(answer_code)])
            except (IndexError, TypeError, ValueError):
                from .exceptions import QuestionValueError
                raise QuestionValueError(
                    f"Answer code {answer_code} is out of range for dropdown options."
                )
        else:
            return answer_code


    @property
    def question_html_content(self) -> str:
        """Return the HTML version of the dropdown question."""
        sample_options = self._get_sample_options()

        html_content = Template(
            """
        <div class="dropdown-question">
            <p>{{ question_text }}</p>
            <p><em>This dropdown will search through {{ total_options }} options.
               Sample options (indices {{ sample_indices }}) shown below:</em></p>
            <select name="{{ question_name }}" id="{{ question_name }}" disabled>
                <option value="">-- Search will be performed --</option>
                {% for option in sample_options %}
                <option value="{{ option }}">{{ option }}</option>
                {% endfor %}
                <option value="">... and {{ remaining }} more options</option>
            </select>
        </div>
        """
        ).render(
            question_text=self.question_text,
            question_name=self.question_name,
            sample_options=sample_options,
            total_options=len(self.question_options),
            sample_indices=self.sample_indices,
            remaining=len(self.question_options) - len(sample_options)
        )
        return html_content

    @classmethod
    @inject_exception
    def example(cls, include_comment=True, use_code=False) -> "QuestionDropdown":
        """Return an example instance with many city options."""
        cities = [
            "New York", "Los Angeles", "Chicago", "Houston", "Phoenix", "Philadelphia",
            "San Antonio", "San Diego", "Dallas", "San Jose", "Austin", "Jacksonville",
            "Fort Worth", "Columbus", "Charlotte", "San Francisco", "Indianapolis",
            "Seattle", "Denver", "Washington", "Boston", "El Paso", "Nashville",
            "Detroit", "Oklahoma City", "Portland", "Las Vegas", "Memphis", "Louisville",
            "Baltimore", "Milwaukee", "Albuquerque", "Tucson", "Fresno", "Sacramento",
            "Kansas City", "Long Beach", "Mesa", "Atlanta", "Colorado Springs", "Virginia Beach",
            "Raleigh", "Omaha", "Miami", "Oakland", "Minneapolis", "Tulsa", "Wichita",
            "New Orleans", "Arlington", "Cleveland", "Bakersfield", "Tampa", "Aurora",
            "Honolulu", "Anaheim", "Santa Ana", "Corpus Christi", "Riverside", "St. Louis",
            "Lexington", "Pittsburgh", "Anchorage", "Stockton", "Cincinnati", "St. Paul"
        ]

        city_details = [
            "The most populous city in the United States, famous for Times Square and Central Park",
            "The entertainment capital of the world, home to Hollywood and beautiful beaches",
            "The Windy City, known for deep-dish pizza and stunning architecture",
            "The most populous city in Texas, known for NASA Space Center",
            "Desert metropolis in Arizona, known for year-round sunshine",
            "The City of Brotherly Love, birthplace of American independence",
        ] + ["Major city with unique culture and attractions"] * (len(cities) - 6)

        return cls(
            question_text="Which city would you most like to visit for a cultural vacation?",
            question_options=cities,
            question_options_details=city_details,
            question_name="city_preference",
            sample_indices=[0, 5, 10, 15, 20, 25],  # Show specific examples
            max_options_shown=4,
            feeling_lucky=False,
            include_comment=include_comment,
            use_code=use_code,
        )


if __name__ == "__main__":
    import doctest
    doctest.testmod(optionflags=doctest.ELLIPSIS)