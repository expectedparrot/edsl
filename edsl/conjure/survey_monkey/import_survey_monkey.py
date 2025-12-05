"""Import Survey Monkey CSV exports into EDSL objects."""

import csv
import re
import uuid
from collections import Counter
from typing import List, Optional, Callable, TYPE_CHECKING, Dict, Any

from .data_classes import (
    Column,
    DataType,
    ColumnType,
    PrependData,
    GroupData,
    MonadicQuestion,
    QuestionMapping,
    SURVEY_MONKEY_HEADERS,
)
from .excel_date_repairer import ExcelDateRepairer
from .option_semantic_orderer import OptionSemanticOrderer

if TYPE_CHECKING:
    from edsl import Survey, ScenarioList, AgentList, Results


class ImportSurveyMonkey:
    """
    Import a Survey Monkey CSV export and generate EDSL objects.

    This class parses Survey Monkey CSV exports and creates:
    - Survey: with questions matching the original survey
    - ScenarioList: for monadic questions with varying parameters
    - AgentList: one agent per respondent with their actual responses
    - Results: by running the agents through the survey

    Excel Date Repair:
    When Excel opens CSV files, it auto-converts numeric ranges like "1-2", "3-5",
    "6-10" into date formats like "2-Jan", "5-Mar", "10-Jun". This class can
    automatically detect and repair these Excel-mangled formats using LLM calls.

    Semantic Option Ordering:
    Multiple choice options are often imported in random order. This class can
    analyze question text and reorder options semantically (e.g., company sizes
    from small to large, experience levels from beginner to expert, age ranges
    in chronological order) using LLM calls for better survey readability.

    Examples
    --------
    Basic usage (both Excel repair and semantic ordering enabled by default):
        importer = ImportSurveyMonkey("survey_results.csv")
        survey = importer.survey  # Options repaired and semantically ordered
        importer.print_excel_date_repairs()       # See what was repaired
        importer.print_semantic_ordering_changes() # See what was reordered
        results = importer.run()

    Disable features if not needed:
        importer = ImportSurveyMonkey("survey_results.csv",
                                    repair_excel_dates=False,
                                    order_options_semantically=False)
        survey = importer.survey  # No processing applied
        results = importer.run()
    """
    
    def __init__(self, csv_file: str, verbose: bool = False, create_semantic_names: bool = False, repair_excel_dates: bool = True, order_options_semantically: bool = True):
        """
        Initialize the importer with a CSV file path.

        Parameters
        ----------
        csv_file : str
            Path to the Survey Monkey CSV export file.
        verbose : bool
            If True, print progress information during parsing.
        create_semantic_names : bool
            If True, rename questions with semantic names derived from question text.
        repair_excel_dates : bool, default True
            If True, use LLM to detect and repair Excel-mangled date formatting
            in answer options and response values (e.g., "5-Mar" → "3-5").
            Enabled by default since Excel date mangling is very common.
        order_options_semantically : bool, default True
            If True, use LLM to analyze and reorder multiple choice options in
            semantically correct order (e.g., company sizes from small to large,
            experience levels from beginner to expert). Enabled by default.
        """
        self.csv_file = csv_file
        self.verbose = verbose
        self.create_semantic_names = create_semantic_names
        self.repair_excel_dates = repair_excel_dates
        self.order_options_semantically = order_options_semantically
        
        # Internal state
        self._columns: List[Column] = []
        self._groups: List[GroupData] = []
        self._prepend_data: List[PrependData] = []
        self._first_lines: List[str] = []
        self._second_lines: List[str] = []
        self._monadic_questions: List[MonadicQuestion] = []
        self._question_mappings: List[QuestionMapping] = []
        self._response_records: List[dict] = []
        self._agent_to_scenario_idx: dict = {}

        # Excel date repair functionality
        self._excel_repairer: Optional[ExcelDateRepairer] = None
        self._repair_mapping: Dict[str, str] = {}  # original_value -> repaired_value

        # Initialize Excel date repairer if requested
        if self.repair_excel_dates:
            try:
                self._excel_repairer = ExcelDateRepairer(verbose=self.verbose)
                self._log("Excel date repair enabled")
            except Exception as e:
                self._log(f"Warning: Could not initialize Excel date repairer: {e}")
                self.repair_excel_dates = False

        # Semantic option ordering functionality
        self._option_orderer: Optional[OptionSemanticOrderer] = None
        self._ordering_changes: List[Dict[str, Any]] = []  # Track ordering changes

        # Initialize semantic option orderer if requested
        if self.order_options_semantically:
            try:
                self._option_orderer = OptionSemanticOrderer(verbose=self.verbose)
                self._log("Semantic option ordering enabled")
            except Exception as e:
                self._log(f"Warning: Could not initialize semantic option orderer: {e}")
                self.order_options_semantically = False
        
        # Output objects (lazily created)
        self._survey: Optional["Survey"] = None
        self._scenarios: Optional["ScenarioList"] = None
        self._agents: Optional["AgentList"] = None
        self._results: Optional["Results"] = None
        
        # Parse the CSV
        self._read_csv()
        self._build_groups()
        self._build_survey()
        self._build_scenarios()
        self._build_question_mappings()
        self._build_response_records()
        self._build_agents()
    
    def _log(self, message: str):
        """Print message if verbose mode is enabled."""
        if self.verbose:
            print(message)
    
    def _slugify(self, text: str, used_names: set) -> str:
        """Create a valid Python identifier from question text.
        
        Parameters
        ----------
        text : str
            The question text to convert.
        used_names : set
            Set of already used names to ensure uniqueness.
        
        Returns
        -------
        str
            A valid Python identifier.
        """
        # Remove question marks and extra whitespace
        text = re.sub(r"[?]+", "", text.lower()).strip()
        
        # Split into words
        words = re.findall(r"\b\w+\b", text)
        
        # Remove common question words
        question_words = {
            "what", "how", "when", "where", "why", "which", "who",
            "do", "are", "would", "have", "did", "will", "can",
            "should", "could", "is", "was", "were", "does",
            "you", "your", "the", "a", "an", "of", "to", "in",
            "for", "on", "with", "at", "by", "from", "or", "and",
            "please", "specify", "other", "following", "below",
        }
        
        # Filter out question words
        meaningful_words = [word for word in words if word not in question_words]
        
        # Take first 3 meaningful words
        if len(meaningful_words) >= 3:
            slug = "_".join(meaningful_words[:3])
        elif len(meaningful_words) >= 1:
            slug = "_".join(meaningful_words)
        elif len(words) >= 2:
            slug = "_".join(words[:2])
        elif len(words) == 1:
            slug = words[0]
        else:
            slug = f"q_{uuid.uuid4().hex[:8]}"
        
        # Clean up the slug - only allow valid identifier characters
        slug = re.sub(r"[^a-z0-9]+", "_", slug).strip("_")
        
        # Ensure it doesn't start with a number
        if slug and slug[0].isdigit():
            slug = "q_" + slug
        
        if not slug:
            slug = f"q_{uuid.uuid4().hex[:8]}"
        
        # Truncate to reasonable length
        slug = slug[:30]
        
        # Ensure uniqueness
        base_slug = slug
        counter = 1
        while slug in used_names:
            slug = f"{base_slug}_{counter}"
            counter += 1
        
        used_names.add(slug)
        return slug
    
    # -------------------------------------------------------------------------
    # CSV Reading
    # -------------------------------------------------------------------------
    
    def _read_csv(self):
        """Read the CSV file and create Column objects."""
        with open(self.csv_file, "r", newline="") as f:
            reader = csv.reader(f)
            rows = list(reader)

        if not rows:
            return

        num_columns = len(rows[0])
        data = [[] for _ in range(num_columns)]

        for row in rows:
            for i, value in enumerate(row):
                data[i].append(value)

        self._columns = [Column(i, values) for i, values in enumerate(data)]
        self._first_lines = [col[0] for col in self._columns]
        self._second_lines = [col[1] for col in self._columns]
    
    # -------------------------------------------------------------------------
    # Column Grouping
    # -------------------------------------------------------------------------
    
    def _classify_column(self, first_line: str) -> ColumnType:
        """Classify a column based on its first line."""
        if "Custom" in first_line or first_line in SURVEY_MONKEY_HEADERS:
            return ColumnType.PREPEND
        if first_line == "Question Viewed":
            return ColumnType.QUESTION_VIEWED
        if first_line != "":
            return ColumnType.QUESTION_START
        return ColumnType.QUESTION_CONTINUATION
    
    def _is_continuation_of_previous(self, index: int) -> bool:
        """Check if this column continues the previous group."""
        if index == 0:
            return False
        
        current_first = self._first_lines[index]
        prev_first = self._first_lines[index - 1]
        
        # Empty first line = standard continuation
        if current_first == "":
            return True
        
        # Same first line as previous = monadic question continuation
        if current_first == prev_first and current_first != "":
            return True
        
        return False
    
    def _close_and_start_group(self, current_group: GroupData, index: int, 
                                new_data_type: DataType, next_start_offset: int = 0) -> GroupData:
        """Close the current group and start a new one."""
        current_group.end_index = index - 1
        current_group._first_lines = self._first_lines
        current_group._second_lines = self._second_lines
        self._groups.append(current_group)
        return GroupData(
            data_type=new_data_type,
            start_index=index + next_start_offset,
            end_index=None,
            _first_lines=self._first_lines,
            _second_lines=self._second_lines,
        )
    
    def _build_groups(self):
        """Parse columns into logical groups."""
        current_group = GroupData(
            data_type=DataType.PREPEND, 
            start_index=0, 
            end_index=None,
            _first_lines=self._first_lines,
            _second_lines=self._second_lines,
        )
        
        for index, column in enumerate(self._columns):
            if self._is_continuation_of_previous(index):
                continue
            
            col_type = self._classify_column(self._first_lines[index])
            
            if col_type == ColumnType.PREPEND:
                self._prepend_data.append(PrependData(
                    index, self._first_lines[index], list(column[2:])
                ))
                current_group = self._close_and_start_group(
                    current_group, index, DataType.PREPEND, next_start_offset=1
                )
            elif col_type in (ColumnType.QUESTION_START, ColumnType.QUESTION_VIEWED):
                current_group = self._close_and_start_group(
                    current_group, index, DataType.SURVEY_RESPONSE, next_start_offset=0
                )
        
        # Close the final group
        if current_group.end_index is None:
            current_group.end_index = len(self._columns) - 1
            current_group._first_lines = self._first_lines
            current_group._second_lines = self._second_lines
            self._groups.append(current_group)
    
    # -------------------------------------------------------------------------
    # Monadic Question Detection
    # -------------------------------------------------------------------------
    
    def _detect_monadic_question(self, group: GroupData) -> Optional[MonadicQuestion]:
        """Detect if a group represents a monadic question."""
        from edsl.conjure.text_differ import extract_template
        
        if len(group) != 2:
            return None
        
        first_second_line = self._second_lines[group.start_index]
        second_second_line = self._second_lines[group.start_index + 1]
        
        if first_second_line != "Question Viewed" or second_second_line != "Response":
            return None
        
        question_texts = list(self._columns[group.start_index][2:])
        responses = list(self._columns[group.start_index + 1][2:])
        
        result = extract_template(question_texts)
        if result is None:
            return None
        
        return MonadicQuestion(
            question_template=result.template,
            slots=result.slots,
            responses=responses,
            column_index=group.start_index
        )
    
    # -------------------------------------------------------------------------
    # Survey Building
    # -------------------------------------------------------------------------
    
    def _tally_responses(self, column_index: int) -> List[str]:
        """Get unique non-empty response values from a column."""
        column = self._columns[column_index]
        responses_tally = Counter(column[2:])
        options = [x for x in list(responses_tally.keys()) if x != ""]

        # Apply Excel date repair if enabled
        if self.repair_excel_dates and self._excel_repairer and options:
            question_id = f"column_{column_index}"
            try:
                repair_result = self._excel_repairer.repair_question_options(question_id, options)
                if repair_result.any_repairs_applied:
                    self._log(f"Applied {len(repair_result.repairs_made)} repairs to options in column {column_index}")

                    # Update repair mapping for response value translation
                    for repair in repair_result.repairs_made:
                        self._repair_mapping[repair.original] = repair.repaired

                    return repair_result.repaired_options
            except Exception as e:
                self._log(f"Warning: Excel date repair failed for column {column_index}: {e}")

        return options

    def _apply_semantic_ordering(self, question_text: str, question_identifier: str, options: List[str]) -> List[str]:
        """Apply semantic ordering to question options if enabled.

        Parameters
        ----------
        question_text : str
            The text of the survey question
        question_identifier : str
            Identifier for the question (for logging)
        options : List[str]
            List of answer options (already repaired if repair was enabled)

        Returns
        -------
        List[str]
            Semantically ordered options
        """
        if not self.order_options_semantically or not self._option_orderer or not options or len(options) < 2:
            return options

        try:
            ordering_result = self._option_orderer.order_question_options(
                question_text, question_identifier, options
            )

            if ordering_result.ordering_details.reordering_applied:
                self._log(f"Semantically reordered options for {question_identifier}: "
                         f"{ordering_result.ordering_details.ordering_type}")

                # Track the ordering change for transparency
                self._ordering_changes.append({
                    'question_text': question_text,
                    'question_identifier': question_identifier,
                    'original_order': ordering_result.ordering_details.original_order,
                    'semantic_order': ordering_result.ordering_details.semantic_order,
                    'ordering_type': ordering_result.ordering_details.ordering_type,
                    'confidence': ordering_result.ordering_details.confidence,
                    'explanation': ordering_result.ordering_details.explanation
                })

                return ordering_result.ordering_details.semantic_order
            else:
                return options

        except Exception as e:
            self._log(f"Warning: Semantic ordering failed for {question_identifier}: {e}")
            return options

    def _build_survey(self):
        """Build the Survey object from parsed groups."""
        from edsl import Survey
        from edsl import (
            QuestionMultipleChoice,
            QuestionMultipleChoiceWithOther,
            QuestionFreeText,
            QuestionCheckBox,
        )
        
        self._survey = Survey()
        used_names = set()
        
        # Track index-based names to semantic names for question mappings
        self._name_mapping = {}
        
        for group in self._groups:
            if group.data_type != DataType.SURVEY_RESPONSE:
                continue
            
            question_text = self._first_lines[group.start_index]
            index_name = f"index_{group.start_index}"
            
            # Determine question name
            if self.create_semantic_names:
                question_name = self._slugify(question_text, used_names)
                self._name_mapping[index_name] = question_name
            else:
                question_name = index_name
                used_names.add(question_name)
            
            # Check for monadic question
            monadic = self._detect_monadic_question(group)
            if monadic:
                self._log(f"Detected monadic question with {len(monadic.slots)} slot(s)")
                self._log(f"  Template: {monadic.question_template[:80]}...")
                for slot in monadic.slots:
                    self._log(f"  {slot.name} = {slot.unique_values}")
                self._monadic_questions.append(monadic)
                
                q = QuestionMultipleChoice(
                    question_name=question_name,
                    question_text=monadic.question_template,
                    question_options=["Yes", "No"],
                )
                self._survey.add_question(q)
                continue
            
            if len(group) == 1:
                second_line = self._second_lines[group.start_index]
                if second_line == "Response":
                    self._log("Adding a multiple choice question")
                    # Get options (with Excel date repair applied if enabled)
                    raw_options = self._tally_responses(group.start_index)
                    # Apply semantic ordering
                    ordered_options = self._apply_semantic_ordering(question_text, question_name, raw_options)

                    q = QuestionMultipleChoice(
                        question_name=question_name,
                        question_text=question_text,
                        question_options=ordered_options,
                    )
                    self._survey.add_question(q)
                elif second_line == "Open-ended response":
                    self._log("Adding a free text question")
                    q = QuestionFreeText(
                        question_name=question_name,
                        question_text=question_text,
                    )
                    self._survey.add_question(q)
            elif len(group) > 1:
                options = group.second_lines()
                if options == ["Response", "Other (please specify)"]:
                    self._log("Adding a multiple choice question with other")
                    # Get options (with Excel date repair applied if enabled)
                    raw_options = self._tally_responses(group.start_index)
                    # Apply semantic ordering
                    ordered_options = self._apply_semantic_ordering(question_text, question_name, raw_options)

                    q = QuestionMultipleChoiceWithOther(
                        question_name=question_name,
                        question_text=question_text,
                        question_options=ordered_options,
                    )
                    self._survey.add_question(q)
                else:
                    self._log("Adding a check box question")

                    # Apply Excel date repair to checkbox options if enabled
                    repaired_options = options
                    if self.repair_excel_dates and self._excel_repairer and options:
                        question_id = f"{question_name}_checkbox"
                        try:
                            repair_result = self._excel_repairer.repair_question_options(question_id, options)
                            if repair_result.any_repairs_applied:
                                self._log(f"Applied {len(repair_result.repairs_made)} repairs to checkbox options for {question_name}")

                                # Update repair mapping for response value translation
                                for repair in repair_result.repairs_made:
                                    self._repair_mapping[repair.original] = repair.repaired

                                repaired_options = repair_result.repaired_options
                        except Exception as e:
                            self._log(f"Warning: Excel date repair failed for checkbox question {question_name}: {e}")

                    # Apply semantic ordering to checkbox options
                    ordered_options = self._apply_semantic_ordering(question_text, f"{question_name}_checkbox", repaired_options)

                    q = QuestionCheckBox(
                        question_name=question_name,
                        question_text=question_text,
                        question_options=ordered_options,
                    )
                    self._survey.add_question(q)
    
    # -------------------------------------------------------------------------
    # Scenario Building
    # -------------------------------------------------------------------------
    
    def _build_scenarios(self):
        """Build ScenarioList from monadic question unique values."""
        from edsl import ScenarioList, Scenario
        from edsl.conjure.text_differ import tokenize
        
        self._scenarios = ScenarioList()
        
        if not self._monadic_questions:
            return
        
        # Handle the first monadic question
        mq = self._monadic_questions[0]
        slot = mq.slots[0]
        
        self._log(f"\n=== Building Scenarios ===")
        self._log(f"  Slot: {slot.name}")
        self._log(f"  Unique values: {slot.unique_values}")
        
        # Create scenarios from unique values only
        value_to_scenario_idx = {}
        for idx, value in enumerate(slot.unique_values):
            self._scenarios.append(Scenario({slot.name: value, '_index': idx}))
            value_to_scenario_idx[value] = idx
        
        # Build agent-to-scenario mapping from original question texts
        # This ensures proper alignment with respondent indices
        question_texts = list(self._columns[mq.column_index][2:])
        for agent_idx, text in enumerate(question_texts):
            if text and text.strip():
                tokens = tokenize(text)
                if slot.position < len(tokens):
                    value = tokens[slot.position]
                    if value in value_to_scenario_idx:
                        self._agent_to_scenario_idx[agent_idx] = value_to_scenario_idx[value]
        
        self._log(f"  Created {len(self._scenarios)} scenarios")
    
    # -------------------------------------------------------------------------
    # Question Mapping & Response Records
    # -------------------------------------------------------------------------
    
    def _build_question_mappings(self):
        """Build mappings from question names to column indices."""
        for group in self._groups:
            if group.data_type != DataType.SURVEY_RESPONSE:
                continue
            
            index_name = f"index_{group.start_index}"
            # Use semantic name if available, otherwise use index-based name
            question_name = self._name_mapping.get(index_name, index_name)
            column_indices = list(range(group.start_index, group.end_index + 1))
            
            # Check for monadic question
            if len(group) == 2:
                first_second = self._second_lines[group.start_index]
                second_second = self._second_lines[group.start_index + 1]
                if first_second == "Question Viewed" and second_second == "Response":
                    self._question_mappings.append(QuestionMapping(
                        question_name=question_name,
                        column_indices=[group.start_index + 1],
                        is_checkbox=False
                    ))
                    continue
            
            is_checkbox = False
            is_multiple_choice_with_other = False
            
            if len(group) > 1:
                options = [self._second_lines[i] for i in column_indices]
                if options == ["Response", "Other (please specify)"]:
                    is_multiple_choice_with_other = True
                else:
                    is_checkbox = True
            
            self._question_mappings.append(QuestionMapping(
                question_name=question_name,
                column_indices=column_indices,
                is_checkbox=is_checkbox,
                is_multiple_choice_with_other=is_multiple_choice_with_other
            ))
    
    def _build_response_records(self):
        """Build response records from CSV data."""
        if not self._columns:
            return

        num_rows = len(self._columns[0]) - 2  # Skip header rows

        for row_idx in range(num_rows):
            data_row_idx = row_idx + 2
            record = {}

            for mapping in self._question_mappings:
                if mapping.is_checkbox:
                    selected = []
                    for col_idx in mapping.column_indices:
                        value = self._columns[col_idx][data_row_idx]
                        if value != "":
                            # Apply Excel date repair to checkbox response values
                            repaired_value = self._repair_mapping.get(value, value)
                            selected.append(repaired_value)
                    record[mapping.question_name] = selected
                elif mapping.is_multiple_choice_with_other:
                    # First column is the response, second column is the "other" text
                    primary_answer = self._columns[mapping.column_indices[0]][data_row_idx]
                    other_text = ""
                    if len(mapping.column_indices) > 1:
                        other_text = self._columns[mapping.column_indices[1]][data_row_idx]

                    # If second column has text, use that (they selected "Other")
                    # Otherwise use the primary answer (with repair applied)
                    if other_text:
                        record[mapping.question_name] = other_text
                    else:
                        # Apply Excel date repair to multiple choice response values
                        repaired_answer = self._repair_mapping.get(primary_answer, primary_answer)
                        record[mapping.question_name] = repaired_answer
                else:
                    col_idx = mapping.column_indices[0]
                    value = self._columns[col_idx][data_row_idx]
                    # Apply Excel date repair to response values
                    repaired_value = self._repair_mapping.get(value, value)
                    record[mapping.question_name] = repaired_value

            self._response_records.append(record)
    
    # -------------------------------------------------------------------------
    # Agent Building
    # -------------------------------------------------------------------------
    
    def _build_agents(self):
        """Build AgentList with direct answering methods."""
        from edsl import Agent, AgentList
        
        self._agents = AgentList()
        
        for index, record in enumerate(self._response_records):
            agent = Agent()
            
            def construct_answer_func(rec: dict) -> Callable:
                def func(self, question, scenario=None):
                    return rec.get(question.question_name, None)
                return func
            
            agent.add_direct_question_answering_method(construct_answer_func(record))
            agent.traits['_index'] = index
            
            if index in self._agent_to_scenario_idx:
                agent.traits['_scenario_index'] = self._agent_to_scenario_idx[index]
            
            # Add prepend data (Survey Monkey headers, custom data) as traits
            for prepend in self._prepend_data:
                trait_name = "_" + prepend.column_name.lower().replace(" ", "_")
                if index < len(prepend.values):
                    agent.traits[trait_name] = prepend.values[index]
            
            self._agents.append(agent)
    
    # -------------------------------------------------------------------------
    # Public Properties
    # -------------------------------------------------------------------------
    
    @property
    def survey(self) -> "Survey":
        """The Survey object with questions from the CSV."""
        return self._survey
    
    @property
    def scenarios(self) -> "ScenarioList":
        """ScenarioList for monadic questions (empty if none detected)."""
        return self._scenarios
    
    @property
    def agents(self) -> "AgentList":
        """AgentList with one agent per respondent."""
        return self._agents
    
    @property
    def monadic_questions(self) -> List[MonadicQuestion]:
        """List of detected monadic questions."""
        return self._monadic_questions
    
    @property
    def prepend_data(self) -> List[PrependData]:
        """Metadata fields from the CSV (Respondent ID, dates, etc.)."""
        return self._prepend_data

    def get_excel_date_repairs(self) -> Dict[str, str]:
        """
        Get a dictionary of Excel date repairs that were applied.

        Returns
        -------
        Dict[str, str]
            Dictionary mapping original Excel-mangled values to repaired values.
            Empty if repair_excel_dates=False or no repairs were needed.

        Examples
        --------
        >>> importer = ImportSurveyMonkey("survey.csv", repair_excel_dates=True)
        >>> repairs = importer.get_excel_date_repairs()
        >>> print(repairs)
        {'5-Mar': '3-5', '10-Jun': '6-10', '15-Jan': '1-15'}
        """
        return self._repair_mapping.copy()

    def print_excel_date_repairs(self):
        """
        Print a summary of Excel date repairs that were applied.

        This method provides transparency about what changes were made
        to both question options and response values during import.
        """
        if not self.repair_excel_dates:
            print("Excel date repair was not enabled for this import.")
            return

        if not self._repair_mapping:
            print("No Excel date formatting issues were detected.")
            return

        print(f"Excel Date Repairs Applied ({len(self._repair_mapping)} total):")
        print("-" * 50)
        for original, repaired in self._repair_mapping.items():
            print(f"'{original}' → '{repaired}'")

        print("\nThese repairs were applied to:")
        print("• Question answer options")
        print("• Individual respondent answers")
        print("\nThis ensures consistency between the survey structure and response data.")

    def get_semantic_ordering_changes(self) -> List[Dict[str, Any]]:
        """
        Get a list of semantic ordering changes that were applied.

        Returns
        -------
        List[Dict[str, Any]]
            List of dictionaries with ordering change details including:
            - question_text: The survey question text
            - question_identifier: Question name/identifier
            - original_order: Original option order
            - semantic_order: Semantically ordered options
            - ordering_type: Type of ordering applied
            - confidence: Confidence score (0.0 to 1.0)
            - explanation: Reasoning for the ordering
            Empty if order_options_semantically=False or no changes were made.

        Examples
        --------
        >>> importer = ImportSurveyMonkey("survey.csv", order_options_semantically=True)
        >>> changes = importer.get_semantic_ordering_changes()
        >>> for change in changes:
        ...     print(f"{change['question_text']}: {change['ordering_type']}")
        """
        return self._ordering_changes.copy()

    def print_semantic_ordering_changes(self):
        """
        Print a summary of semantic ordering changes that were applied.

        This method provides transparency about what option reorderings were made
        to improve the logical flow and readability of multiple choice questions.
        """
        if not self.order_options_semantically:
            print("Semantic option ordering was not enabled for this import.")
            return

        if not self._ordering_changes:
            print("No semantic ordering changes were needed.")
            return

        print(f"Semantic Ordering Changes Applied ({len(self._ordering_changes)} questions):")
        print("=" * 70)

        for change in self._ordering_changes:
            print(f"\nQuestion: {change['question_text']}")
            print(f"Ordering Type: {change['ordering_type']} (confidence: {change['confidence']:.2f})")
            print(f"Reasoning: {change['explanation']}")
            print("Before:", change['original_order'])
            print("After: ", change['semantic_order'])
            print("-" * 50)

        print(f"\nSummary:")
        print(f"• {len(self._ordering_changes)} questions had their options reordered")
        print(f"• Common orderings: company sizes, experience levels, frequencies, ratings")
        print(f"• This improves survey readability and respondent experience")

    # -------------------------------------------------------------------------
    # Run Method
    # -------------------------------------------------------------------------
    
    def run(self, disable_remote_inference: bool = True, **kwargs) -> "Results":
        """
        Run the survey with agents and scenarios to generate Results.
        
        Parameters
        ----------
        disable_remote_inference : bool
            If True, run locally without remote API calls.
        **kwargs
            Additional arguments passed to Jobs.run().
        
        Returns
        -------
        Results
            The results of running all agents through the survey.
        """
        if self._monadic_questions and len(self._scenarios) > 0:
            jobs = (
                self._survey
                .by(self._agents)
                .by(self._scenarios)
                .include_when("{{ scenario._index == agent._scenario_index }}")
            )
        else:
            jobs = self._survey.by(self._agents)
        
        self._results = jobs.run(disable_remote_inference=disable_remote_inference, **kwargs)
        return self._results
    
    @property
    def results(self) -> Optional["Results"]:
        """Results from the last run (None if run() hasn't been called)."""
        return self._results

if __name__ == "__main__":
    importer = ImportSurveyMonkey("web_takeoff_monadic_results.csv", create_semantic_names=True)
    survey = importer.survey
    agents = importer.agents
    scenarios = importer.scenarios
    results = importer.run()
    #print(results)