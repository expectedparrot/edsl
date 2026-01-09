from typing import Optional
#from .scenario_list import ScenarioList
##from .scenario import Scenario
#from .conjoint_profile_generator import ConjointProfileGenerator
#from .scenarioml.feature_processor import FeatureProcessor
#from .scenarioml.model_selector import ModelSelector
from .scenarioml.prediction import Prediction
from typing import List, Union
from .exceptions import ScenarioError
import warnings
import os
from typing import Sequence

class ScenarioListLikelyRemove:


    def to_ranked_scenario_list(
        self,
        option_fields: Sequence[str],
        answer_field: str,
        include_rank: bool = True,
        rank_field: str = "rank",
        item_field: str = "item",
    ) -> "ScenarioList":
        """Convert the ScenarioList to a ranked ScenarioList based on pairwise comparisons.

        Args:
            option_fields: List of scenario column names containing options to compare.
            answer_field: Name of the answer column containing the chosen option's value.
            include_rank: If True, include a rank field on each returned Scenario.
            rank_field: Name of the rank field to include when include_rank is True.
            item_field: Field name used to store the ranked item value on each Scenario.

        Returns:
            ScenarioList ordered best-to-worst according to pairwise ranking.
        """
        from .ranking_algorithm import results_to_ranked_scenario_list

        return results_to_ranked_scenario_list(
            self,
            option_fields=option_fields,
            answer_field=answer_field,
            include_rank=include_rank,
            rank_field=rank_field,
            item_field=item_field,
        )

    def to_true_skill_ranked_list(
        self,
        option_fields: Sequence[str],
        answer_field: str,
        include_rank: bool = True,
        rank_field: str = "rank",
        item_field: str = "item",
        mu_field: str = "mu",
        sigma_field: str = "sigma",
        conservative_rating_field: str = "conservative_rating",
        initial_mu: float = 25.0,
        initial_sigma: float = 8.333,
        beta: float = None,
        tau: float = None,
    ) -> "ScenarioList":
        """Convert the ScenarioList to a ranked ScenarioList using TrueSkill algorithm.
        Args:
            option_fields: List of scenario column names containing options to compare.
            answer_field: Name of the answer column containing the ranking order.
            include_rank: If True, include a rank field on each returned Scenario.
            rank_field: Name of the rank field to include when include_rank is True.
            item_field: Field name used to store the ranked item value on each Scenario.
            mu_field: Field name for TrueSkill mu (skill estimate) value.
            sigma_field: Field name for TrueSkill sigma (uncertainty) value.
            conservative_rating_field: Field name for conservative rating (mu - 3*sigma).
            initial_mu: Initial skill rating (default 25.0).
            initial_sigma: Initial uncertainty (default 8.333).
            beta: Skill class width (defaults to initial_sigma/2).
            tau: Dynamics factor (defaults to initial_sigma/300).
        Returns:
            ScenarioList ordered best-to-worst according to TrueSkill ranking.
        """
        from .true_skill_algorithm import results_to_true_skill_ranked_list

        return results_to_true_skill_ranked_list(
            self,
            option_fields=option_fields,
            answer_field=answer_field,
            include_rank=include_rank,
            rank_field=rank_field,
            item_field=item_field,
            mu_field=mu_field,
            sigma_field=sigma_field,
            conservative_rating_field=conservative_rating_field,
            initial_mu=initial_mu,
            initial_sigma=initial_sigma,
            beta=beta,
            tau=tau,
        )


    @classmethod
    def from_directory(
        cls,
        path: Optional[str] = None,
        recursive: bool = False,
        key_name: str = "content",
    ) -> "ScenarioList":
        """Create a ScenarioList of Scenario objects from files in a directory.

        This method scans a directory and creates a Scenario object for each file found,
        where each Scenario contains a FileStore object under the specified key.
        Optionally filters files based on a wildcard pattern. If no path is provided,
        the current working directory is used.

        Args:
            path: The directory path to scan, optionally including a wildcard pattern.
                 If None, uses the current working directory.
                 Examples:
                 - "/path/to/directory" - scans all files in the directory
                 - "/path/to/directory/*.py" - scans only Python files in the directory
                 - "*.txt" - scans only text files in the current working directory
            recursive: Whether to scan subdirectories recursively. Defaults to False.
            key_name: The key to use for the FileStore object in each Scenario. Defaults to "content".

        Returns:
            A ScenarioList containing Scenario objects for all matching files, where each Scenario
            has a FileStore object under the specified key.

        Raises:
            FileNotFoundError: If the specified directory does not exist.

        Examples:
            # Get all files in the current directory with default key "content"
            sl = ScenarioList.from_directory()

            # Get all Python files in a specific directory with custom key "python_file"
            sl = ScenarioList.from_directory('*.py', key_name="python_file")

            # Get all image files in the current directory
            sl = ScenarioList.from_directory('*.png', key_name="image")

            # Get all files recursively including subdirectories
            sl = ScenarioList.from_directory(recursive=True, key_name="document")
        """

        warnings.warn(
            "from_directory is deprecated. Use ScenarioSource.from_source('directory', ...) instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        from .scenario_source import DirectorySource

        source = DirectorySource(
            directory=path or os.getcwd(),
            pattern="*",
            recursive=recursive,
            metadata=True,
        )

        # Get the ScenarioList with FileStore objects under "file" key
        sl = source.to_scenario_list()

        # If the requested key is different from the default "file" key used by DirectoryScanner.scan_directory,
        # rename the keys in all scenarios
        from .scenario_list import ScenarioList
        from .scenario import Scenario
        if key_name != "file":
            # Create a new ScenarioList
            result = ScenarioList([])
            for scenario in sl:
                # Create a new scenario with the file under the specified key
                new_data = {key_name: scenario["file"]}
                # Add all other fields from the original scenario
                for k, v in scenario.items():
                    if k != "file":
                        new_data[k] = v
                result.append(Scenario(new_data))
            return result

        return sl


    def vibe_filter(
        self,
        criteria: str,
        *,
        model: str = "gpt-4o",
        temperature: float = 0.1,
        show_expression: bool = False,
    ) -> 'ScenarioList':
        """
        Filter the scenario list using natural language criteria.

        This method uses an LLM to generate a filter expression based on
        natural language criteria, then applies it using the scenario list's filter method.

        Args:
            criteria: Natural language description of the filtering criteria.
                Examples:
                - "Keep only people over 30"
                - "Remove scenarios with missing data"
                - "Only include scenarios from the US"
                - "Filter out any scenarios where age is less than 18"
            model: OpenAI model to use for generating the filter (default: "gpt-4o")
            temperature: Temperature for generation (default: 0.1 for consistent logic)
            show_expression: If True, prints the generated filter expression

        Returns:
            ScenarioList: A new ScenarioList containing only the scenarios that match the criteria

        Examples:
            >>> from edsl.scenarios import Scenario, ScenarioList
            >>> sl = ScenarioList([
            ...     Scenario({'age': 25, 'occupation': 'student'}),
            ...     Scenario({'age': 35, 'occupation': 'engineer'}),
            ...     Scenario({'age': 42, 'occupation': 'teacher'})
            ... ])
            >>> filtered = sl.vibe_filter("Keep only people over 30")  # doctest: +SKIP

        Notes:
            - Requires OPENAI_API_KEY environment variable to be set
            - The LLM generates a filter expression using scenario keys directly
            - Uses the scenario list's built-in filter() method for safe evaluation
            - Use show_expression=True to see the generated filter logic
        """
        from .vibes.vibe_filter import VibeFilter

        # Collect all unique keys across all scenarios
        all_keys = set()
        for scenario in self.data:
            all_keys.update(scenario.keys())

        # Get sample scenarios to help the LLM understand the data structure
        sample_scenarios = []
        for scenario in self.data[:5]:  # Get up to 5 sample scenarios
            sample_scenarios.append(dict(scenario))

        # Create the filter generator
        filter_gen = VibeFilter(model=model, temperature=temperature)

        # Generate the filter expression
        filter_expr = filter_gen.create_filter(
            sorted(list(all_keys)), sample_scenarios, criteria
        )

        if show_expression:
            print(f"Generated filter expression: {filter_expr}")

        # Use the scenario list's built-in filter method which returns ScenarioList
        return self.filter(filter_expr)


    def few_shot_examples(
        self,
        n: int,
        x_fields: List[str],
        y_fields: List[str],
        seed: Optional[Union[str, int]] = None,
        separator: str = " --> ",
        field_name: str = "few_shot_examples",
        presence_field_name: str = "current_scenario_present_in_examples",
        line_separator: str = "\n",
        x_format: str = "({x})",
        y_format: str = "{y}",
        field_separator: str = ", ",
    ) -> "ScenarioList":
        """Create few-shot learning examples from sampled scenarios.

        This method samples n scenarios and creates a formatted string of examples
        that can be used for few-shot learning prompts. Each scenario in the returned
        ScenarioList will have the few-shot examples string added as a new field, along
        with a boolean indicator showing whether that specific scenario was included
        in the sampled examples.

        Args:
            n: Number of examples to sample for the few-shot prompt
            x_fields: List of field names to use as input/context (x values)
            y_fields: List of field names to use as output/target (y values)
            seed: Optional seed for reproducible sampling
            separator: String to separate x from y (default: " --> ")
            field_name: Name of field to store the examples string (default: "few_shot_examples")
            presence_field_name: Name of boolean field indicating if scenario is in examples
                                (default: "current_scenario_present_in_examples")
            line_separator: String to separate each example (default: "\\n")
            x_format: Format string for x values, use {x} as placeholder (default: "({x})")
            y_format: Format string for y values, use {y} as placeholder (default: "{y}")
            field_separator: String to separate multiple field values (default: ", ")

        Returns:
            A new ScenarioList where each scenario has:
            - A field with the few-shot examples string
            - A boolean field indicating if that scenario was in the sampled examples

        Examples:
            >>> from edsl.scenarios import Scenario, ScenarioList
            >>> sl = ScenarioList([
            ...     Scenario({'x': 1, 'y': 'a'}),
            ...     Scenario({'x': 2, 'y': 'b'}),
            ...     Scenario({'x': 3, 'y': 'c'}),
            ...     Scenario({'x': 4, 'y': 'd'})
            ... ])
            >>> result = sl.few_shot_examples(n=2, x_fields=['x'], y_fields=['y'], seed=42)
            >>> len(result) == len(sl)
            True
            >>> 'few_shot_examples' in result[0]
            True
            >>> 'current_scenario_present_in_examples' in result[0]
            True
            >>> isinstance(result[0]['current_scenario_present_in_examples'], bool)
            True

            >>> # Multi-field example
            >>> sl2 = ScenarioList([
            ...     Scenario({'name': 'Alice', 'age': 30, 'city': 'NYC', 'job': 'Engineer'}),
            ...     Scenario({'name': 'Bob', 'age': 25, 'city': 'LA', 'job': 'Designer'}),
            ... ])
            >>> result2 = sl2.few_shot_examples(
            ...     n=1,
            ...     x_fields=['name', 'age'],
            ...     y_fields=['city', 'job'],
            ...     seed=42
            ... )
            >>> 'few_shot_examples' in result2[0]
            True
        """
        # Validate inputs
        if n > len(self):
            raise ScenarioError(
                f"Cannot sample {n} examples from ScenarioList with only {len(self)} scenarios"
            )

        if not x_fields or not y_fields:
            raise ScenarioError("Both x_fields and y_fields must be non-empty lists")

        # Validate that all fields exist in at least one scenario
        all_fields = set(x_fields + y_fields)
        available_fields = set()
        for scenario in self:
            available_fields.update(scenario.keys())

        missing_fields = all_fields - available_fields
        if missing_fields:
            raise ScenarioError(
                f"Fields not found in any scenario: {missing_fields}. "
                f"Available fields: {available_fields}"
            )

        # Sample n scenarios
        sampled_scenarios = self.sample(n=n, seed=seed)

        # Create a set of scenario hashes for quick lookup
        sampled_hashes = {
            hash(str(scenario.to_dict())) for scenario in sampled_scenarios
        }

        # Build the few-shot examples string
        example_lines = []
        for scenario in sampled_scenarios:
            # Format x values
            x_values = []
            for field in x_fields:
                value = scenario.get(field, "")
                x_values.append(str(value))
            x_str = field_separator.join(x_values)
            x_formatted = x_format.format(x=x_str)

            # Format y values
            y_values = []
            for field in y_fields:
                value = scenario.get(field, "")
                y_values.append(str(value))
            y_str = field_separator.join(y_values)
            y_formatted = y_format.format(y=y_str)

            # Combine into example
            example = f"{x_formatted}{separator}{y_formatted}"
            example_lines.append(example)

        # Join all examples
        examples_string = line_separator.join(example_lines)

        # Create new ScenarioList with added fields
        from .scenario_list import ScenarioList
        
        new_scenarios = []
        for scenario in self:
            new_scenario = scenario.copy()
            new_scenario[field_name] = examples_string

            # Check if this scenario was in the sampled examples
            scenario_hash = hash(str(scenario.to_dict()))
            new_scenario[presence_field_name] = scenario_hash in sampled_hashes

            new_scenarios.append(new_scenario)

        return ScenarioList(new_scenarios, codebook=self.codebook)


    @classmethod
    def vibe_extract(
        cls,
        html_source: str,
        *,
        model: str = "gpt-4o",
        temperature: float = 0.0,
        instructions: str = "",
        max_rows: Optional[int] = None,
    ) -> "ScenarioList":
        """Create a ScenarioList by extracting table data from HTML using LLM.

        Uses an LLM to analyze HTML content containing tables and extract
        structured data to create scenarios.

        Args:
            html_source: Either HTML string content or path to an HTML file
            model: OpenAI model to use for extraction (default: "gpt-4o")
            temperature: Temperature for generation (default: 0.0 for consistency)
            instructions: Additional extraction instructions (optional)
            max_rows: Maximum number of rows to extract (None = all rows)

        Returns:
            ScenarioList: The extracted scenarios

        Examples:
            From HTML string:

            >>> html = "<table><tr><th>Name</th><th>Age</th></tr><tr><td>Alice</td><td>30</td></tr></table>"  # doctest: +SKIP
            >>> sl = ScenarioList.vibe_extract(html)  # doctest: +SKIP
            >>> len(sl)  # doctest: +SKIP
            1
            >>> sl[0]["name"]  # doctest: +SKIP
            'Alice'

            From HTML file:

            >>> sl = ScenarioList.vibe_extract("/path/to/file.html")  # doctest: +SKIP

            With custom instructions:

            >>> sl = ScenarioList.vibe_extract(  # doctest: +SKIP
            ...     html_content,  # doctest: +SKIP
            ...     instructions="Extract only the first table, ignore footer rows"  # doctest: +SKIP
            ... )  # doctest: +SKIP
        """
        import os

        # Check if html_source is a file path
        if os.path.exists(html_source) and os.path.isfile(html_source):
            # Read the file
            with open(html_source, "r", encoding="utf-8") as f:
                html_content = f.read()
        else:
            # Treat as HTML content string
            html_content = html_source

        from .vibes import extract_from_html_with_vibes

        scenario_list, metadata = extract_from_html_with_vibes(
            html_content,
            model=model,
            temperature=temperature,
            instructions=instructions,
            max_rows=max_rows,
        )

        # Store metadata as an attribute on the ScenarioList for reference
        scenario_list._extraction_metadata = metadata

        return scenario_list

    def vibe_describe(
        self,
        *,
        model: str = "gpt-4o",
        temperature: float = 0.7,
        max_sample_values: int = 5,
    ) -> dict:
        """Generate a title and description for the scenario list.

        This method uses an LLM to analyze the scenario list and generate
        a descriptive title and detailed description of what the scenario list represents.

        Args:
            model: OpenAI model to use for generation (default: "gpt-4o")
            temperature: Temperature for generation (default: 0.7)
            max_sample_values: Maximum number of sample values to include per key (default: 5)

        Returns:
            dict: Dictionary with keys:
                - "proposed_title": A single sentence title for the scenario list
                - "description": A paragraph-length description of the scenario list

        Examples:
            Basic usage:

            >>> from edsl.scenarios import Scenario, ScenarioList
            >>> sl = ScenarioList([  # doctest: +SKIP
            ...     Scenario({"name": "Alice", "age": 30, "city": "NYC"}),  # doctest: +SKIP
            ...     Scenario({"name": "Bob", "age": 25, "city": "SF"})  # doctest: +SKIP
            ... ])  # doctest: +SKIP
            >>> description = sl.vibe_describe()  # doctest: +SKIP
            >>> print(description["proposed_title"])  # doctest: +SKIP
            >>> print(description["description"])  # doctest: +SKIP

            Using a different model:

            >>> sl = ScenarioList.from_vibes("Customer demographics")  # doctest: +SKIP
            >>> description = sl.vibe_describe(model="gpt-4o-mini")  # doctest: +SKIP

        Notes:
            - Requires OPENAI_API_KEY environment variable to be set
            - The title will be a single sentence that captures the scenario list's essence
            - The description will be a paragraph explaining what the data represents
            - Analyzes all unique keys and samples values to understand the data theme
            - If a codebook is present, it will be included in the analysis
        """
        from .vibes import describe_scenario_list_with_vibes

        d = describe_scenario_list_with_vibes(
            self,
            model=model,
            temperature=temperature,
            max_sample_values=max_sample_values,
        )
        from ..scenarios import Scenario

        return Scenario(**d)


    @classmethod
    def from_vibes(cls, description: str) -> "ScenarioList":
        """Create a ScenarioList from a vibe description.

        Args:
            description: A description of the vibe.
        """
        from edsl.dataset.vibes.scenario_generator import ScenarioGenerator
        from .scenario import Scenario

        gen = ScenarioGenerator(model="gpt-4o", temperature=0.7)
        result = gen.generate_scenarios(description)
        return cls([Scenario(scenario) for scenario in result["scenarios"]])


    @classmethod
    def from_prompt(
        cls,
        description: str,
        name: Optional[str] = "item",
        target_number: int = 10,
        verbose=False,
    ):
        from ..questions.question_list import QuestionList

        q = QuestionList(
            question_name=name,
            question_text=description
            + f"\n Please try to return {target_number} examples.",
        )
        results = q.run(verbose=verbose)
        return results.select(name).to_scenario_list().expand(name)


    def create_conjoint_comparisons(
        self,
        attribute_field: str = "attribute",
        levels_field: str = "levels",
        count: int = 1,
        random_seed: Optional[int] = None,
    ) -> "ScenarioList":
        """
        Generate random product profiles for conjoint analysis from attribute definitions.

        This method uses the current ScenarioList (which should contain attribute definitions)
        to create random product profiles by sampling from the attribute levels. Each scenario
        in the current list should represent one attribute with its possible levels.

        Args:
            attribute_field: Field name containing the attribute names (default: 'attribute')
            levels_field: Field name containing the list of levels (default: 'levels')
            count: Number of product profiles to generate (default: 1)
            random_seed: Optional seed for reproducible random sampling

        Returns:
            ScenarioList containing randomly generated product profiles

        Example:
            >>> from edsl.scenarios import ScenarioList, Scenario
            >>> # Create attribute definitions
            >>> attributes = ScenarioList([
            ...     Scenario({'attribute': 'price', 'levels': ['$100', '$200', '$300']}),
            ...     Scenario({'attribute': 'color', 'levels': ['Red', 'Blue', 'Green']}),
            ...     Scenario({'attribute': 'size', 'levels': ['Small', 'Medium', 'Large']})
            ... ])
            >>> # Generate conjoint profiles
            >>> profiles = attributes.create_conjoint_comparisons(count=3, random_seed=42)
            >>> len(profiles)
            3
            >>> # Each profile will have price, color, and size with random values

        Raises:
            ScenarioError: If the current ScenarioList doesn't have the required fields
            ValueError: If count is not positive
        """
        from .conjoint_profile_generator import ConjointProfileGenerator

        if count <= 0:
            raise ValueError("Count must be positive")

        # Create the generator with the current ScenarioList
        generator = ConjointProfileGenerator(
            self,
            attribute_field=attribute_field,
            levels_field=levels_field,
            random_seed=random_seed,
        )

        # Generate the requested number of profiles
        return generator.generate_batch(count)

    def predict(self, y: str, **kwargs) -> "Prediction":
        """
        Build a predictive model using AutoML with automatic feature engineering.

        Creates a machine learning model to predict a target variable based on
        scenario features. Uses automatic feature type detection, multiple model
        comparison, and built-in overfitting prevention.

        Args:
            y: Name of the target column to predict
            **kwargs: Additional arguments (reserved for future extensions)

        Returns:
            Prediction object for making predictions on new data

        Raises:
            ValueError: If target column is missing or data is insufficient
            ImportError: If required ML dependencies are not installed

        Examples:
            >>> from edsl.scenarios import Scenario, ScenarioList
            >>> scenarios = ScenarioList([
            ...     Scenario({'industry': 'Tech', 'size': '50', 'satisfaction_rating': 8}),
            ...     Scenario({'industry': 'Finance', 'size': '200', 'satisfaction_rating': 6}),
            ...     Scenario({'industry': 'Healthcare', 'size': '100', 'satisfaction_rating': 9}),
            ... ])  # doctest: +SKIP
            >>> model = scenarios.predict(y='satisfaction_rating')  # doctest: +SKIP
            >>>
            >>> # Make predictions on new data
            >>> new_customer = {'industry': 'Tech', 'size': '100'}  # doctest: +SKIP
            >>> prediction = model.predict(new_customer)  # doctest: +SKIP
            >>> probabilities = model.predict_proba(new_customer)  # doctest: +SKIP
            >>>
            >>> # Get model diagnostics
            >>> diagnostics = model.diagnostics()  # doctest: +SKIP
            >>> print(f"Model accuracy: {diagnostics['test_score']:.3f}")  # doctest: +SKIP
        """
        try:
            # Import here to avoid circular imports and check dependencies
            from .scenarioml.feature_processor import FeatureProcessor
            from .scenarioml.model_selector import ModelSelector
            from .scenarioml.prediction import Prediction
        except ImportError as e:
            raise ImportError(
                f"Missing required dependencies for ScenarioML: {str(e)}. "
                "Please install with: pip install pandas scikit-learn"
            ) from e

        # Validate inputs
        if not isinstance(y, str):
            raise ValueError("Target variable 'y' must be a string column name")

        if len(self) == 0:
            raise ValueError("Cannot train model on empty ScenarioList")

        # Convert ScenarioList to DataFrame
        try:
            df = self.to_pandas()
        except Exception as e:
            raise ValueError(
                f"Failed to convert ScenarioList to DataFrame: {str(e)}"
            ) from e

        # Validate target column
        if y not in df.columns:
            available_cols = list(df.columns)
            raise ValueError(
                f"Target column '{y}' not found. Available columns: {available_cols}"
            )

        # Check for minimum data requirements
        if len(df) < 10:
            raise ValueError(
                f"Insufficient data for training: {len(df)} samples. "
                "Need at least 10 samples for reliable model training."
            )

        # Check target variable
        target_values = df[y].dropna()
        if len(target_values) == 0:
            raise ValueError(f"Target column '{y}' contains no valid (non-null) values")

        unique_targets = target_values.nunique()
        if unique_targets < 2:
            raise ValueError(
                f"Target column '{y}' must have at least 2 different values. "
                f"Found {unique_targets} unique value(s)."
            )

        try:
            # Initialize processors
            feature_processor = FeatureProcessor()
            model_selector = ModelSelector()

            # Process features
            print("Processing features...")
            X = feature_processor.fit_transform(df, y)
            y_values = df[y].values

            # Validate processed data
            model_selector.validate_data(X, y_values)

            # Compare models
            print("Training and comparing models...")
            model_results = model_selector.compare_models(
                X, y_values, feature_processor.feature_names
            )

            if not model_results:
                raise ValueError("No models could be trained successfully")

            # Select best model
            best_model = model_selector.select_best_model(model_results)

            # Create prediction object
            prediction = Prediction(
                model_result=best_model,
                feature_processor=feature_processor,
                target_column=y,
            )

            # Display results summary
            print(f"\\nBest model: {best_model.name}")
            print(
                f"Cross-validation score: {best_model.cv_score:.3f} ± {best_model.cv_std:.3f}"
            )
            print(f"Test score: {best_model.test_score:.3f}")
            print(f"Overfitting gap: {best_model.overfitting_gap:.3f}")

            if best_model.overfitting_gap > 0.1:
                warnings.warn(
                    f"High overfitting detected (gap: {best_model.overfitting_gap:.3f}). "
                    "Model may not generalize well to new data."
                )

            return prediction

        except Exception as e:
            # Provide helpful error context
            error_msg = f"Model training failed: {str(e)}"

            if "feature_processor" in str(e).lower():
                error_msg += "\\n\\nFeature processing issues often occur with:"
                error_msg += "\\n  - Mixed data types in columns"
                error_msg += "\\n  - Very sparse or inconsistent data"
                error_msg += "\\n  - Columns with mostly missing values"
            elif "model_selector" in str(e).lower():
                error_msg += "\\n\\nModel training issues often occur with:"
                error_msg += "\\n  - Insufficient data (need >50 samples recommended)"
                error_msg += "\\n  - Too many features relative to samples"
                error_msg += "\\n  - Target variable distribution problems"

            raise ValueError(error_msg) from e

    # =========================================================================
    # Deprecated methods (as of 2026-01-08) - will be removed in future version
    # =========================================================================

    def to_agent_traits(self, agent_name: Optional[str] = None) -> "Agent":
        """Convert all Scenario objects into traits of a single Agent.

        .. deprecated:: 2026-01-08
            Use ``sl.convert.agent_traits()`` instead.
        """
        warnings.warn(
            "to_agent_traits() is deprecated as of 2026-01-08. "
            "Use sl.convert.agent_traits() instead.",
            DeprecationWarning,
            stacklevel=2
        )
        return self.convert.agent_traits(agent_name)

    def to_scenario_list(self) -> "ScenarioList":
        """Convert the ScenarioList to a ScenarioList.

        .. deprecated:: 2026-01-08
            Use ``sl.convert.scenario_list()`` instead.
        """
        warnings.warn(
            "to_scenario_list() is deprecated as of 2026-01-08. "
            "Use sl.convert.scenario_list() instead.",
            DeprecationWarning,
            stacklevel=2
        )
        return self.convert.scenario_list()

    def times(self, other: "ScenarioList") -> "ScenarioList":
        """Takes the cross product of two ScenarioLists.

        .. deprecated::
            Use ``*`` operator instead.
        """
        warnings.warn("times is deprecated, use * instead", DeprecationWarning)
        return self.__mul__(other)

    def to_survey(self) -> "Survey":
        """Convert the ScenarioList to a Survey.

        .. deprecated:: 2026-01-08
            Use ``sl.convert.survey()`` instead.
        """
        warnings.warn(
            "to_survey() is deprecated as of 2026-01-08. "
            "Use sl.convert.survey() instead.",
            DeprecationWarning,
            stacklevel=2
        )
        return self.convert.survey()

    def to_dataset(self) -> "Dataset":
        """Convert the ScenarioList to a Dataset.

        .. deprecated:: 2026-01-08
            Use ``sl.convert.dataset()`` instead.
        """
        warnings.warn(
            "to_dataset() is deprecated as of 2026-01-08. "
            "Use sl.convert.dataset() instead.",
            DeprecationWarning,
            stacklevel=2
        )
        return self.convert.dataset()

    def to_scenario_of_lists(self) -> "Scenario":
        """Collapse to a single Scenario with list-valued fields.

        .. deprecated:: 2026-01-08
            Use ``sl.convert.scenario_of_lists()`` instead.
        """
        warnings.warn(
            "to_scenario_of_lists() is deprecated as of 2026-01-08. "
            "Use sl.convert.scenario_of_lists() instead.",
            DeprecationWarning,
            stacklevel=2
        )
        return self.convert.scenario_of_lists()

    def to_key_value(self, field: str, value=None) -> Union[dict, set]:
        """Return the set of values in the field.

        .. deprecated:: 2026-01-08
            Use ``sl.convert.key_value(field)`` instead.
        """
        warnings.warn(
            "to_key_value() is deprecated as of 2026-01-08. "
            "Use sl.convert.key_value(field) instead.",
            DeprecationWarning,
            stacklevel=2
        )
        return self.convert.key_value(field, value)

    def left_join(self, other: "ScenarioList", by: Union[str, list[str]]) -> "ScenarioList":
        """Perform a left join with another ScenarioList.

        .. deprecated:: 2026-01-08
            Use ``sl.join.left(other, by)`` instead.
        """
        warnings.warn(
            "left_join() is deprecated as of 2026-01-08. "
            "Use sl.join.left(other, by) instead.",
            DeprecationWarning,
            stacklevel=2
        )
        return self.join.left(other, by)

    def inner_join(
        self, other: "ScenarioList", by: Union[str, list[str]]
    ) -> "ScenarioList":
        """Perform an inner join with another ScenarioList.

        .. deprecated:: 2026-01-08
            Use ``sl.join.inner(other, by)`` instead.
        """
        warnings.warn(
            "inner_join() is deprecated as of 2026-01-08. "
            "Use sl.join.inner(other, by) instead.",
            DeprecationWarning,
            stacklevel=2
        )
        return self.join.inner(other, by)

    def right_join(
        self, other: "ScenarioList", by: Union[str, list[str]]
    ) -> "ScenarioList":
        """Perform a right join with another ScenarioList.

        .. deprecated:: 2026-01-08
            Use ``sl.join.right(other, by)`` instead.
        """
        warnings.warn(
            "right_join() is deprecated as of 2026-01-08. "
            "Use sl.join.right(other, by) instead.",
            DeprecationWarning,
            stacklevel=2
        )
        return self.join.right(other, by)

    def to_agent_list(self):
        """Convert the ScenarioList to an AgentList.

        .. deprecated:: 2026-01-08
            Use ``sl.convert.agent_list()`` instead.
        """
        warnings.warn(
            "to_agent_list() is deprecated as of 2026-01-08. "
            "Use sl.convert.agent_list() instead.",
            DeprecationWarning,
            stacklevel=2
        )
        return self.convert.agent_list()

    def to_agent_blueprint(
        self,
        *,
        seed: Optional[int] = None,
        cycle: bool = True,
        dimension_name_field: str = "dimension",
        dimension_values_field: str = "dimension_values",
        dimension_description_field: Optional[str] = None,
        dimension_probs_field: Optional[str] = None,
    ):
        """Create an AgentBlueprint from this ScenarioList.

        .. deprecated:: 2026-01-08
            Use ``sl.convert.agent_blueprint()`` instead.
        """
        warnings.warn(
            "to_agent_blueprint() is deprecated as of 2026-01-08. "
            "Use sl.convert.agent_blueprint() instead.",
            DeprecationWarning,
            stacklevel=2
        )
        return self.convert.agent_blueprint(
            seed=seed,
            cycle=cycle,
            dimension_name_field=dimension_name_field,
            dimension_values_field=dimension_values_field,
            dimension_description_field=dimension_description_field,
            dimension_probs_field=dimension_probs_field,
        )
