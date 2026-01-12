from typing import Optional, Callable
import warnings

from .utilities import ensure_ready


class ResultsLikelyRemoveMixin:

    @property
    def created_columns(self) -> list[str]:
        """Get created_columns from store meta."""
        if not hasattr(self, "store") or self.store is None:
            return []
        return self.store.meta.get("created_columns", [])

    @property
    def _shelve_path(self) -> str:
        """Get shelve path, creating if needed."""
        if not hasattr(self, "_shelve_path_cache"):
            import tempfile
            import os

            object.__setattr__(
                self,
                "_shelve_path_cache",
                os.path.join(tempfile.gettempdir(), f"edsl_results_{os.getpid()}"),
            )
        return self._shelve_path_cache

    @property
    def _shelf_keys(self) -> set:
        """Get shelf keys set, creating if needed."""
        if not hasattr(self, "_shelf_keys_cache"):
            object.__setattr__(self, "_shelf_keys_cache", set())
        return self._shelf_keys_cache

    def view(self) -> None:
        """View the results in a Jupyter notebook."""
        from ..widgets.results_viewer import ResultsViewerWidget

        return ResultsViewerWidget(results=self)

    def transcripts(self, show_comments: bool = True) -> "Transcripts":
        """Return a Transcripts object for viewing interview responses across multiple respondents.

        This method creates a carousel-style viewer that allows navigation across different
        Result objects (respondents) while keeping the same question in focus. This is useful
        for comparing how different respondents answered the same question.

        The Transcripts viewer provides:
        - Navigation between respondents (Result objects)
        - Navigation between questions
        - Agent name display for each respondent
        - Synchronized question viewing across respondents
        - Copy button for plain text export

        In HTML/Jupyter, displays as an interactive carousel with:
        - "Prev/Next Respondent" buttons to navigate between agents
        - "Prev Q/Next Q" buttons to navigate between questions

        In terminal, displays Rich formatted output with agent headers and Q&A pairs.

        Args:
            show_comments: Whether to include respondent comments in the transcripts.
                Defaults to True.

        Returns:
            A Transcripts object that adapts its display to the environment.

        Examples:
            >>> from edsl.results import Results
            >>> results = Results.example()
            >>> transcripts = results.transcripts()
            >>> # In Jupyter: Interactive carousel navigation
            >>> # In terminal: Rich formatted display
            >>> # As string: Plain text format

            >>> # Without comments
            >>> transcripts_no_comments = results.transcripts(show_comments=False)
        """
        from .results_transcript import Transcripts

        return Transcripts(self, show_comments=show_comments)

    @property
    def vibe(self) -> "ResultsVibeAccessor":
        """Access vibe-based results analysis methods.

        Returns a ResultsVibeAccessor that provides natural language methods
        for analyzing and visualizing results data.

        Returns:
            ResultsVibeAccessor: Accessor for vibe methods

        Examples:
            >>> results = Results.example()  # doctest: +SKIP
            >>> results.vibe.analyze()  # doctest: +SKIP
            >>> results.vibe.plot()  # doctest: +SKIP
            >>> results.vibe.sql("Show me satisfaction scores")  # doctest: +SKIP
        """
        from .vibes.vibe_accessor import ResultsVibeAccessor

        return ResultsVibeAccessor(self)

    def vibe_analyze(
        self,
        *,
        model: str = "gpt-4o",
        temperature: float = 0.7,
        include_visualizations: bool = False,
        generate_summary: bool = True,
    ) -> "ResultsVibeAnalysis":
        """Analyze all questions with LLM-powered insights.

        This method iterates through each question in the survey, generates
        standard analysis using the existing analyze() method, and uses an LLM
        to provide natural language insights about the data patterns. Optionally,
        it can also send visualizations to OpenAI's vision API for analysis.

        In a Jupyter notebook, the results will display automatically with rich
        formatting. For the best experience with interactive plots, call .display()
        on the returned object.

        Args:
            model: OpenAI model to use for generating insights (default: "gpt-4o")
            temperature: Temperature for LLM generation (default: 0.7)
            include_visualizations: Whether to send visualizations to OpenAI for analysis
                (default: False). WARNING: This can significantly increase API costs.
            generate_summary: Whether to generate an overall summary report across
                all questions (default: True)

        Returns:
            ResultsVibeAnalysis: Container object with analyses for all questions.
                In Jupyter notebooks, will display automatically with HTML formatting.
                For interactive plots, call .display() method.

        Raises:
            ValueError: If no survey is available or visualization dependencies missing
            ImportError: If required packages are not installed

        Examples:
            >>> results = Results.example()  # doctest: +SKIP

            >>> # Basic usage - will show HTML summary in notebooks
            >>> results.vibe_analyze()  # doctest: +SKIP

            >>> # For interactive plots and rich display
            >>> analysis = results.vibe_analyze()  # doctest: +SKIP
            >>> analysis.display()  # Shows plots inline with insights  # doctest: +SKIP

            >>> # Access a specific question's analysis
            >>> q_analysis = analysis["how_feeling"]  # doctest: +SKIP
            >>> q_analysis.analysis.bar_chart  # doctest: +SKIP
            >>> print(q_analysis.llm_insights)  # doctest: +SKIP
            >>> # Charts are stored as PNG bytes for serialization
            >>> q_analysis.chart_png  # PNG bytes  # doctest: +SKIP

            >>> # With visualization analysis (more expensive - uses vision API)
            >>> analysis = results.vibe_analyze(  # doctest: +SKIP
            ...     include_visualizations=True
            ... )  # doctest: +SKIP
            >>> analysis.display()  # doctest: +SKIP

            >>> # Export to serializable format for notebooks
            >>> data = analysis.to_dict()  # doctest: +SKIP
            >>> import json  # doctest: +SKIP
            >>> json.dumps(data)  # Fully serializable  # doctest: +SKIP
        """
        return self.vibe.analyze(
            model=model,
            temperature=temperature,
            include_visualizations=include_visualizations,
            generate_summary=generate_summary,
        )

    def extend_sorted(self, other) -> "Results":
        """Extend the Results by appending items from another iterable, preserving order.

        This method creates a new Results instance with all items from both
        this Results and the other iterable, sorted by 'order' attribute if present,
        otherwise by 'iteration' attribute. Results is immutable.

        Args:
            other: Iterable of Result objects to append.

        Returns:
            Results: A new Results instance with the sorted, extended data.
        """
        from .results import Results

        # Collect all items (existing and new)
        all_items = list(self.data)
        all_items.extend(other)

        # Sort combined list by order attribute if available, otherwise by iteration
        def get_sort_key(item):
            if hasattr(item, "order"):
                return (0, item.order)  # Order attribute takes precedence
            return (1, item.data["iteration"])  # Iteration is secondary

        all_items.sort(key=get_sort_key)

        return Results(
            survey=self.survey,
            data=all_items,
            name=self.name,
            created_columns=self.created_columns,
            cache=self.cache,
            job_uuid=self._job_uuid,
            total_results=self._total_results,
            task_history=self.task_history,
            sort_by_iteration=False,  # Already sorted
        )

    def mutate(
        self, new_var_string: str, functions_dict: Optional[dict] = None
    ) -> "Results":
        """Create a new column based on a computational expression.

        This method delegates to the ResultsTransformer class to handle the mutation operation.

        Args:
            new_var_string: A string containing an assignment expression in the form
                "new_column_name = expression". The expression can reference
                any existing column and use standard Python syntax.
            functions_dict: Optional dictionary of custom functions that can be used in
                the expression. Keys are function names, values are function objects.

        Returns:
            A new Results object with the additional column.

        Examples:
            >>> from edsl.results import Results
            >>> r = Results.example()

            >>> # Create a simple derived column
            >>> r.mutate('how_feeling_x = how_feeling + "x"').select('how_feeling_x')
            Dataset([{'answer.how_feeling_x': ['OKx', 'Greatx', 'Terriblex', 'OKx']}])

            >>> # Create a binary indicator column
            >>> r.mutate('is_great = 1 if how_feeling == "Great" else 0').select('is_great')
            Dataset([{'answer.is_great': [0, 1, 0, 0]}])

            >>> # Create a column with custom functions
            >>> def sentiment(text):
            ...     return len(text) > 5
            >>> r.mutate('is_long = sentiment(how_feeling)',
            ...          functions_dict={'sentiment': sentiment}).select('is_long')
            Dataset([{'answer.is_long': [False, False, True, False]}])
        """
        from .results_transformer import ResultsTransformer

        transformer = ResultsTransformer(self)
        return transformer.mutate(new_var_string, functions_dict)

    @ensure_ready
    def rename(self, old_name: str, new_name: str) -> "Results":
        """Rename an answer column in a Results object.

        This method delegates to the ResultsTransformer class to handle the renaming operation.

        Args:
            old_name: The current name of the column to rename
            new_name: The new name for the column

        Returns:
            Results: A new Results object with the column renamed

        Examples:
            >>> from edsl.results import Results
            >>> s = Results.example()
            >>> s.rename('how_feeling', 'how_feeling_new').select('how_feeling_new')  # doctest: +SKIP
            Dataset([{'answer.how_feeling_new': ['OK', 'Great', 'Terrible', 'OK']}])
        """
        from .results_transformer import ResultsTransformer

        transformer = ResultsTransformer(self)
        return transformer.rename(old_name, new_name)

    @ensure_ready
    def shuffle(self, seed: Optional[str] = "edsl") -> "Results":
        """Return a shuffled copy of the results using Fisher-Yates algorithm.

        Args:
            seed: Random seed for reproducibility.

        Returns:
            Results: A new Results object with shuffled data.
        """
        from .results_sampler import ResultsSampler

        sampler = ResultsSampler(self)
        return sampler.shuffle(seed)

    @ensure_ready
    def sample(
        self,
        n: Optional[int] = None,
        frac: Optional[float] = None,
        with_replacement: bool = True,
        seed: Optional[str] = None,
    ) -> "Results":
        """Return a random sample of the results.

        Args:
            n: The number of samples to take.
            frac: The fraction of samples to take (alternative to n).
            with_replacement: Whether to sample with replacement.
            seed: Random seed for reproducibility.

        Returns:
            Results: A new Results object containing the sampled data.
        """
        from .results_sampler import ResultsSampler

        sampler = ResultsSampler(self)
        return sampler.sample(
            n=n, frac=frac, with_replacement=with_replacement, seed=seed
        )

    @classmethod
    def from_survey_monkey(
        cls,
        filepath: str,
        verbose: bool = False,
        create_semantic_names: bool = False,
        repair_excel_dates: bool = True,
        order_options_semantically: bool = True,
        disable_remote_inference: bool = True,
        **run_kwargs,
    ) -> "Results":
        """Create a Results object from a Survey Monkey CSV or Excel export.

        This method imports a Survey Monkey export (CSV or Excel) and generates a
        Results object by running agents (one per respondent) through the
        reconstructed survey.

        The import process:
        1. Converts Excel to CSV if needed
        2. Parses the CSV to extract questions, options, and responses
        3. Creates a Survey with questions matching the original
        4. Creates an AgentList with one agent per respondent
        5. Runs the agents through the survey to generate Results

        Args:
            filepath: Path to the Survey Monkey export file. Supports CSV (.csv)
                and Excel (.xlsx, .xls) formats.
            verbose: If True, print progress information during parsing.
            create_semantic_names: If True, rename questions with semantic names
                derived from question text instead of index-based names.
            repair_excel_dates: If True, use LLM to detect and repair Excel-mangled
                date formatting in answer options (e.g., "5-Mar" → "3-5").
                Enabled by default since Excel date mangling is common.
            order_options_semantically: If True, use LLM to analyze and reorder
                multiple choice options in semantically correct order (e.g., company
                sizes from small to large). Enabled by default.
            disable_remote_inference: If True, run locally without remote API calls.
                Defaults to True.
            **run_kwargs: Additional arguments passed to Jobs.run().

        Returns:
            Results: A Results object containing the imported survey responses.

        Examples:
            >>> # Basic usage with CSV
            >>> results = Results.from_survey_monkey("survey_results.csv")  # doctest: +SKIP

            >>> # Basic usage with Excel
            >>> results = Results.from_survey_monkey("survey_results.xlsx")  # doctest: +SKIP

            >>> # With semantic question names and verbose output
            >>> results = Results.from_survey_monkey(
            ...     "survey_results.csv",
            ...     verbose=True,
            ...     create_semantic_names=True
            ... )  # doctest: +SKIP

            >>> # Disable LLM-based processing for faster import
            >>> results = Results.from_survey_monkey(
            ...     "survey_results.csv",
            ...     repair_excel_dates=False,
            ...     order_options_semantically=False
            ... )  # doctest: +SKIP
        """
        import os
        import tempfile
        from ..conjure.survey_monkey import ImportSurveyMonkey

        # Check file extension to determine if conversion is needed
        _, ext = os.path.splitext(filepath.lower())

        if ext in (".xlsx", ".xls"):
            # Convert Excel to CSV
            import pandas as pd

            if verbose:
                print(f"Converting Excel file to CSV: {filepath}")

            df = pd.read_excel(filepath, header=None)

            # Create a temporary CSV file
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".csv", delete=False, newline=""
            ) as tmp_file:
                csv_path = tmp_file.name
                df.to_csv(tmp_file, index=False, header=False)

            try:
                importer = ImportSurveyMonkey(
                    csv_file=csv_path,
                    verbose=verbose,
                    create_semantic_names=create_semantic_names,
                    repair_excel_dates=repair_excel_dates,
                    order_options_semantically=order_options_semantically,
                )
                return importer.run(
                    disable_remote_inference=disable_remote_inference, **run_kwargs
                )
            finally:
                # Clean up temporary file
                os.unlink(csv_path)
        else:
            # Assume CSV format
            importer = ImportSurveyMonkey(
                csv_file=filepath,
                verbose=verbose,
                create_semantic_names=create_semantic_names,
                repair_excel_dates=repair_excel_dates,
                order_options_semantically=order_options_semantically,
            )
            return importer.run(
                disable_remote_inference=disable_remote_inference, **run_kwargs
            )

    @classmethod
    def from_qualtrics(
        cls,
        filepath: str,
        verbose: bool = False,
        create_semantic_names: bool = False,
        disable_remote_inference: bool = True,
        **run_kwargs,
    ) -> "Results":
        """Create a Results object from a Qualtrics CSV or tab-delimited export.

        This method imports a Qualtrics export (CSV or tab with 3-row headers) and generates a
        Results object by running agents (one per respondent) through the
        reconstructed survey.

        The import process:
        1. Parses the 3-row header Qualtrics format:
           - Row 1: Short labels (Q1, Q2_1, etc.)
           - Row 2: Question text
           - Row 3: ImportId metadata (JSON format)
        2. Detects question types and creates appropriate EDSL questions
        3. Creates a Survey with questions matching the original
        4. Creates an AgentList with one agent per respondent
        5. Runs the agents through the survey to generate Results

        Note: Tab-delimited files (.tab, .tsv) are automatically converted to CSV format
        before processing, so both CSV and tab formats are supported.

        Args:
            filepath: Path to the Qualtrics export file. Can be CSV (.csv) or
                tab-delimited (.tab, .tsv). Must be in the standard Qualtrics
                export format with 3 header rows.
            verbose: If True, print progress information during parsing.
            create_semantic_names: If True, rename questions with semantic names
                derived from question text instead of Q1, Q2, etc.
            disable_remote_inference: If True, run locally without remote API calls.
                Defaults to True.
            **run_kwargs: Additional arguments passed to Jobs.run().

        Returns:
            Results: A Results object containing the imported survey responses.

        Examples:
            >>> # Basic usage with CSV
            >>> results = Results.from_qualtrics("qualtrics_export.csv")  # doctest: +SKIP

            >>> # Basic usage with tab file
            >>> results = Results.from_qualtrics("qualtrics_export.tab")  # doctest: +SKIP

            >>> # With semantic question names and verbose output
            >>> results = Results.from_qualtrics(
            ...     "qualtrics_export.csv",
            ...     verbose=True,
            ...     create_semantic_names=True
            ... )  # doctest: +SKIP

            >>> # Run with additional parameters
            >>> results = Results.from_qualtrics(
            ...     "qualtrics_export.csv",
            ...     disable_remote_inference=True,
            ...     raise_validation_errors=False
            ... )  # doctest: +SKIP
        """
        import os
        import tempfile
        from ..conjure.qualtrics import ImportQualtrics

        # Check file extension to determine if conversion is needed
        _, ext = os.path.splitext(filepath.lower())

        if ext in (".tab", ".tsv"):
            # Convert tab-delimited to CSV
            import pandas as pd

            if verbose:
                print(f"Converting tab-delimited file to CSV: {filepath}")

            # Read tab-delimited file
            df = pd.read_csv(filepath, sep="\t", encoding="utf-8")

            # Create a temporary CSV file
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".csv", delete=False, newline=""
            ) as tmp_file:
                csv_path = tmp_file.name
                df.to_csv(tmp_file, index=False)

            try:
                importer = ImportQualtrics(
                    csv_file=csv_path,
                    verbose=verbose,
                    create_semantic_names=create_semantic_names,
                )
                return importer.run(
                    disable_remote_inference=disable_remote_inference, **run_kwargs
                )
            finally:
                # Clean up temporary file
                try:
                    os.unlink(csv_path)
                except OSError:
                    pass
        else:
            # Handle as CSV directly
            importer = ImportQualtrics(
                csv_file=filepath,
                verbose=verbose,
                create_semantic_names=create_semantic_names,
            )
            return importer.run(
                disable_remote_inference=disable_remote_inference, **run_kwargs
            )

    def give_agents_uuid_names(self) -> None:
        """Give the agents uuid names."""
        import uuid

        for agent in self.agents:
            agent.name = uuid.uuid4()
        return None

    def __add__(self, other: "Results") -> "Results":
        """Add two Results objects together.

        Combines two Results objects into a new one. Both objects must have the same
        survey and created columns. Results is immutable, so this creates a new instance.

        Args:
            other: A Results object to add to this one.

        Returns:
            A new Results object containing data from both objects.

        Raises:
            ResultsError: If the surveys or created columns of the two objects don't match.

        Examples:
            >>> from edsl.results import Results
            >>> r1 = Results.example()
            >>> r2 = Results.example()
            >>> # Combine two Results objects
            >>> r3 = r1 + r2
            >>> len(r3) == len(r1) + len(r2)
            True
        """
        from .exceptions import ResultsError

        if self.survey != other.survey:
            raise ResultsError(
                "The surveys are not the same so the results cannot be added together."
            )
        if self.created_columns != other.created_columns:
            raise ResultsError(
                "The created columns are not the same so they cannot be added together."
            )

        # Create a new Results with combined data
        combined_data = list(self.data)
        combined_data.extend(other.data)
        from .results import Results

        return Results(
            survey=self.survey,
            data=combined_data,
            name=self.name,
            created_columns=self.created_columns,
            cache=self.cache,
            job_uuid=self._job_uuid,
            total_results=self._total_results,
            task_history=self.task_history,
        )

    def to_disk(self, filepath: str) -> None:
        """Serialize the Results object to a zip file, preserving the SQLite database.

        This method delegates to the ResultsSerializer class to handle the disk serialization.

        This method creates a zip file containing:
        1. The SQLite database file from the data container
        2. A metadata.json file with the survey, created_columns, and other non-data info
        3. The cache data if present

        Args:
            filepath: Path where the zip file should be saved

        Raises:
            ResultsError: If there's an error during serialization
        """
        from .results_serializer import ResultsSerializer

        serializer = ResultsSerializer(self)
        return serializer.to_disk(filepath)

    @classmethod
    def from_disk(cls, filepath: str) -> "Results":
        """Load a Results object from a zip file.

        This method delegates to the ResultsSerializer class to handle the disk deserialization.

        This method:
        1. Extracts the SQLite database file
        2. Loads the metadata
        3. Creates a new Results instance with the restored data

        Args:
            filepath: Path to the zip file containing the serialized Results

        Returns:
            Results: A new Results instance with the restored data

        Raises:
            ResultsError: If there's an error during deserialization
        """
        from .results_serializer import ResultsSerializer

        return ResultsSerializer.from_disk(filepath)

    @ensure_ready
    def insert_sorted(self, item: "Result") -> "Results":
        """Insert a Result object while maintaining sort order.

        Uses the 'order' attribute if present, otherwise falls back to 'iteration' attribute.
        Returns a new Results instance since Results is immutable.

        Args:
            item: A Result object to insert

        Returns:
            Results: A new Results instance with the item inserted in sorted order.

        Examples:
            >>> from edsl.results import Results
            >>> r = Results.example()
            >>> new_result = r[0].copy()
            >>> new_result.order = 1.5  # Insert between items
            >>> r2 = r.insert_sorted(new_result)
            >>> len(r2) == len(r) + 1
            True
        """
        from bisect import bisect_left
        from .results import Results

        def get_sort_key(result):
            if hasattr(result, "order"):
                return (0, result.order)  # Order attribute takes precedence
            return (1, result.data["iteration"])  # Iteration is secondary

        # Get the sort key for the new item
        item_key = get_sort_key(item)

        # Get list of sort keys for existing items
        keys = [get_sort_key(x) for x in self.data]

        # Find insertion point
        index = bisect_left(keys, item_key)

        # Create new data list with item inserted
        new_data = list(self.data)
        new_data.insert(index, item)

        return Results(
            survey=self.survey,
            data=new_data,
            name=self.name,
            created_columns=self.created_columns,
            cache=self.cache,
            job_uuid=self._job_uuid,
            total_results=self._total_results,
            task_history=self.task_history,
            sort_by_iteration=False,  # Already sorted
        )

    def insert_from_shelf(self) -> "Results":
        """Move all shelved results into a new Results instance.

        Returns a new Results instance with the shelved results inserted in sorted order.
        Clears the shelf after successful insertion. Results is immutable.

        This method preserves the original order of results by using their 'order'
        attribute if available, which ensures consistent ordering even after
        serialization/deserialization.

        Returns:
            Results: A new Results instance with the shelved results inserted.

        Raises:
            ResultsError: If there's an error accessing or clearing the shelf
        """
        raise NotImplementedError(
            "insert_from_shelf is not implemented for Results objects"
        )
        import shelve

        if not self._shelf_keys:
            return self

        # Collect all results from shelf
        shelved_results = []
        with shelve.open(self._shelve_path) as shelf:
            for key in self._shelf_keys:
                result_dict = shelf[key]
                result = Result.from_dict(result_dict)
                shelved_results.append(result)

            # Clear the shelf
            for key in self._shelf_keys:
                del shelf[key]

        # Clear the tracking set
        self._shelf_keys.clear()

        # Create new Results with all shelved results inserted in sorted order
        return self.extend_sorted(shelved_results)

    def spot_issues(self, models: Optional["ModelList"] = None) -> "Results":
        """Run a survey to spot issues and suggest improvements for prompts that had no model response.

        This method delegates to the ResultsAnalyzer class to handle the analysis and debugging.

        Args:
            models: Optional ModelList to use for the analysis. If None, uses the default model.

        Returns:
            Results: A new Results object containing the analysis and suggestions for improvement.

        Notes:
            Future version: Allow user to optionally pass a list of questions to review,
            regardless of whether they had a null model response.
        """
        raise Exception("spot_issues is not implemented for Results objects")
        analyzer = ResultsAnalyzer(self)
        return analyzer.spot_issues(models)

    def shelve_result(self, result: "Result") -> str:
        """Store a Result object in persistent storage using its hash as the key.

        This method delegates to the ResultsSerializer class to handle the shelving operation.

        Args:
            result: A Result object to store

        Returns:
            str: The hash key for retrieving the result later

        Raises:
            ResultsError: If there's an error storing the Result
        """
        raise Exception("shelve_result is not implemented for Results objects")
        serializer = ResultsSerializer(self)
        return serializer.shelve_result(result)

    def get_shelved_result(self, key: str) -> "Result":
        """Retrieve a Result object from persistent storage.

        This method delegates to the ResultsSerializer class to handle the retrieval operation.

        Args:
            key: The hash key of the Result to retrieve

        Returns:
            Result: The stored Result object

        Raises:
            ResultsError: If the key doesn't exist or if there's an error retrieving the Result
        """
        raise Exception("get_shelved_result is not implemented for Results objects")
        serializer = ResultsSerializer(self)
        return serializer.get_shelved_result(key)

    @property
    def shelf_keys(self) -> set:
        """Return a copy of the set of shelved result keys.

        This property delegates to the ResultsSerializer class.
        """
        return self._properties.shelf_keys

    def score(self, f: Callable) -> list:
        """Score the results using a function.

        .. deprecated::
            Use `results.scoring.score(f)` instead. This method will be removed
            in a future version.

        This method delegates to the ResultsScorer class to handle the scoring operation.

        Args:
            f: A function that takes values from a Result object and returns a score.

        Returns:
            list: A list of scores, one for each Result object.

        Examples:
            >>> from edsl.results import Results
            >>> r = Results.example()
            >>> def f(status): return 1 if status == 'Joyful' else 0
            >>> r.score(f)
            [1, 1, 0, 0]
        """
        warnings.warn(
            "results.score(f) is deprecated. Use results.scoring.score(f) instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.scoring.score(f)

    def score_with_answer_key(self, answer_key: dict) -> list:
        """Score the results using an answer key.

        .. deprecated::
            Use `results.scoring.score_with_answer_key(answer_key)` instead.
            This method will be removed in a future version.

        This method delegates to the ResultsScorer class to handle the scoring operation.

        Args:
            answer_key: A dictionary that maps answer values to scores.

        Returns:
            list: A list of scores, one for each Result object.
        """
        warnings.warn(
            "results.score_with_answer_key(answer_key) is deprecated. "
            "Use results.scoring.score_with_answer_key(answer_key) instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.scoring.score_with_answer_key(answer_key)

    def split(
        self,
        train_questions=None,
        test_questions=None,
        exclude_questions=None,
        num_questions=None,
        seed=None,
    ):
        """Create an AgentList from the results with a train/test split.

        .. deprecated::
            Use `results.ml.split(...)` instead. This method will be removed
            in a future version.

        Args:
            train_questions: Questions to use as TRAIN (deterministic, creates split)
            test_questions: Questions to use as TEST (deterministic, creates split)
            exclude_questions: Questions to fully exclude from both train and test
            num_questions: Number of questions to randomly select for TRAIN (stochastic, creates split).
                          If None and no other split parameters are provided, defaults to half of available questions.
            seed: Optional random seed for reproducible random selection (only used with num_questions)

        Returns:
            AgentListSplit with train/test splits and corresponding surveys.

        Raises:
            ResultsError: If survey has skip logic or piping (not supported for splits)
        """
        warnings.warn(
            "results.split(...) is deprecated. Use results.ml.split(...) instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.ml.split(
            train_questions=train_questions,
            test_questions=test_questions,
            exclude_questions=exclude_questions,
            num_questions=num_questions,
            seed=seed,
        )

    def augmented_agents(
        self,
        *fields,
        include_existing_traits: bool = False,
        include_codebook: bool = False,
    ):
        """Augment the agent list by adding specified fields as new traits.

        .. deprecated::
            Use `results.ml.augmented_agents(...)` instead. This method will be removed
            in a future version.

        Args:
            *fields: Field names to add as traits.
            include_existing_traits: If True, keep existing traits on the agents.
            include_codebook: If True, keep existing codebook on the agents.

        Returns:
            AgentList: A new AgentList with the specified fields added as traits.
        """
        warnings.warn(
            "results.augmented_agents(...) is deprecated. "
            "Use results.ml.augmented_agents(...) instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.ml.augmented_agents(
            *fields,
            include_existing_traits=include_existing_traits,
            include_codebook=include_codebook,
        )
