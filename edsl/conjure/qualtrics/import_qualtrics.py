"""Import Qualtrics CSV exports and convert to EDSL objects."""

import csv
import json
import re
from collections import defaultdict
from typing import List, Dict, Any, Optional, Callable, Tuple

from edsl.agents import Agent, AgentList
from edsl.scenarios import ScenarioList
from edsl.surveys import Survey
from edsl.questions import (
    QuestionFreeText,
    QuestionMultipleChoice,
    QuestionCheckBox,
    QuestionLinearScale,
)

from .data_classes import (
    Column,
    PrependData,
    QuestionMapping,
    QualtricsQuestionMetadata,
    DataType,
)
from .vibe import VibeProcessor, VibeConfig


class ImportQualtrics:
    """Convert Qualtrics CSV export to EDSL objects."""

    def __init__(
        self,
        csv_file: str,
        verbose: bool = False,
        create_semantic_names: bool = False,
        repair_excel_dates: bool = False,  # Not implemented for Qualtrics yet
        order_options_semantically: bool = False,  # Not implemented for Qualtrics yet
        vibe_config: Optional[VibeConfig] | bool = True,  # AI-powered question cleanup, True=use defaults
    ):
        """
        Initialize Qualtrics CSV importer.

        Args:
            csv_file: Path to Qualtrics CSV export file
            verbose: Print detailed processing information
            create_semantic_names: Use semantic names vs index-based names
            repair_excel_dates: Enable Excel date repair (not implemented)
            order_options_semantically: Enable semantic option ordering (not implemented)
            vibe_config: Configuration for AI-powered question cleanup and enhancement
        """
        self.csv_file = csv_file
        self.verbose = verbose
        self.create_semantic_names = create_semantic_names
        self.repair_excel_dates = repair_excel_dates
        self.order_options_semantically = order_options_semantically
        self.vibe_config = vibe_config

        # Initialize vibe processor if config provided
        if vibe_config is True:
            # Use default config when True is passed
            self.vibe_processor = VibeProcessor(VibeConfig())
        elif vibe_config is False or vibe_config is None:
            # Explicitly disabled
            self.vibe_processor = None
        else:
            # Custom config provided
            self.vibe_processor = VibeProcessor(vibe_config)

        # Internal state
        self._columns: List[Column] = []
        self._metadata_columns: List[QualtricsQuestionMetadata] = []
        self._prepend_data: List[PrependData] = []
        self._survey: Optional[Survey] = None
        self._agents: Optional[AgentList] = None
        self._scenarios: Optional[ScenarioList] = None
        self._question_mappings: List[QuestionMapping] = []
        self._response_records: List[Dict[str, Any]] = []
        self._results = None

        # Piping support
        self._qid_to_question_name: Dict[str, str] = {}  # Maps QID to question_name
        self._piping_patterns: List[Tuple[str, str, str]] = []  # [(full_pattern, qid, field_type)]

        # Process the CSV
        self._read_csv()
        self._build_metadata()
        self._build_qid_mappings()
        self._detect_piping_patterns()
        self._build_survey()
        self._apply_vibe_processing()  # AI-powered question enhancement
        self._build_question_mappings()
        self._build_response_records()
        self._build_agents()

    def _read_csv(self) -> None:
        """Read and parse the Qualtrics CSV file."""
        if self.verbose:
            print(f"Reading CSV file: {self.csv_file}")

        # Detect delimiter based on file extension and content
        delimiter = ","
        if self.csv_file.endswith((".tab", ".tsv")):
            delimiter = "\t"
        else:
            # Auto-detect delimiter by checking first line
            with open(self.csv_file, "r", encoding="utf-8") as f:
                first_line = f.readline()
                if first_line.count("\t") > first_line.count(","):
                    delimiter = "\t"

        with open(self.csv_file, "r", encoding="utf-8") as f:
            reader = csv.reader(f, delimiter=delimiter)
            rows = list(reader)

        if len(rows) < 4:
            raise ValueError(
                "Qualtrics CSV must have at least 4 rows: 3 header rows + 1 data row"
            )

        # Extract the three header rows
        short_labels = rows[0]
        question_texts = rows[1]
        import_ids_row = rows[2]
        data_rows = rows[3:]

        # Create columns from data
        self._columns = []
        for col_idx, short_label in enumerate(short_labels):
            values = [row[col_idx] if col_idx < len(row) else "" for row in data_rows]
            self._columns.append(Column(name=short_label, _values=values))

        if self.verbose:
            print(f"Loaded {len(self._columns)} columns, {len(data_rows)} responses")

    def _parse_import_id(self, cell: str) -> Optional[str]:
        """Parse a cell like '{"ImportId":"QID90_1"}' -> 'QID90_1'."""
        if not isinstance(cell, str):
            return None
        s = cell.strip()
        if not (s.startswith("{") and "ImportId" in s):
            return None

        # Handle CSV escape sequences - fix common issues
        # Sometimes CSV parsing creates malformed JSON with escaped quotes
        s = s.replace('\\\"', '"').replace('{"', '{"').replace('"}', '"}')

        try:
            obj = json.loads(s)
            import_id = obj.get("ImportId")
            # Handle Qualtrics format variations like "QID148#1_1" -> "QID148"
            if import_id and "#" in import_id:
                import_id = import_id.split("#")[0]
            return import_id
        except Exception as e:
            # Try alternative parsing for malformed JSON
            try:
                # Extract ImportId with regex as fallback
                import re
                match = re.search(r'ImportId["\s]*:["\s]*([^"]+)', s)
                if match:
                    import_id = match.group(1)
                    # Handle Qualtrics format variations
                    if "#" in import_id:
                        import_id = import_id.split("#")[0]
                    return import_id
            except:
                pass

            # Debug: Only show first few exceptions
            if not hasattr(self, '_parse_errors_shown'):
                self._parse_errors_shown = 0
            if self._parse_errors_shown < 3:
                print(f"Debug: Parse error for '{cell[:50]}...': {e}")
                self._parse_errors_shown += 1
            return None

    def _canonicalize_label(self, label: str) -> str:
        """
        Normalize the short header label into a stable 'question_name'.
        Examples:
          'Q1'     -> 'Q1'
          'Q2_1'   -> 'Q2'
          'Q3_TEXT' -> 'Q3'
          '0#1'    -> 'Q0'
        """
        if not isinstance(label, str):
            return str(label)

        # Clean the label by removing invalid characters and replacing with valid ones
        cleaned = label.strip()

        # Replace # with underscore temporarily
        cleaned = cleaned.replace("#", "_")

        # Keep everything before the LAST underscore as base (if any)
        if "_" in cleaned:
            base, _ = cleaned.rsplit("_", 1)
            cleaned = base.strip()

        # Ensure it starts with a letter or underscore (valid Python identifier)
        if cleaned and not (cleaned[0].isalpha() or cleaned[0] == '_'):
            cleaned = f"Q{cleaned}"

        # Replace any remaining invalid characters with underscores
        import re
        cleaned = re.sub(r'[^\w]', '_', cleaned)

        # Ensure it's not empty
        if not cleaned:
            cleaned = "Unknown"

        return cleaned

    def _subpart_from_label(self, label: str) -> Optional[str]:
        """
        Extract a subpart suffix (e.g., '1', 'TEXT') from the label when present.
        """
        if not isinstance(label, str):
            return None
        if "_" in label:
            _, tail = label.rsplit("_", 1)
            return tail.strip()
        return None

    def _build_metadata(self) -> None:
        """Build metadata for each column from the three header rows."""
        if self.verbose:
            print("Building column metadata...")

        # Re-read the header rows using same delimiter detection
        delimiter = ","
        if self.csv_file.endswith((".tab", ".tsv")):
            delimiter = "\t"
        else:
            with open(self.csv_file, "r", encoding="utf-8") as f:
                first_line = f.readline()
                if first_line.count("\t") > first_line.count(","):
                    delimiter = "\t"

        with open(self.csv_file, "r", encoding="utf-8") as f:
            reader = csv.reader(f, delimiter=delimiter)
            rows = [next(reader) for _ in range(3)]

        short_labels, question_texts, import_ids_row = rows

        self._metadata_columns = []
        for col_idx, (short_label, question_text, import_cell) in enumerate(
            zip(short_labels, question_texts, import_ids_row)
        ):
            import_id = self._parse_import_id(import_cell)
            question_name = self._canonicalize_label(short_label)
            subpart = self._subpart_from_label(short_label)

            metadata = QualtricsQuestionMetadata(
                short_label=short_label,
                question_text=question_text or "",
                import_id=import_id or "",
                question_name=question_name,
                subpart=subpart,
                column_index=col_idx,
            )
            self._metadata_columns.append(metadata)

        if self.verbose:
            print(f"Built metadata for {len(self._metadata_columns)} columns")

    def _build_qid_mappings(self) -> None:
        """Build mapping from QID (import_id) to question_name."""
        if self.verbose:
            print("Building QID to question name mappings...")

        for meta in self._metadata_columns:
            if meta.import_id and not self._is_metadata_column(meta):
                self._qid_to_question_name[meta.import_id] = meta.question_name

        if self.verbose:
            print(f"Built {len(self._qid_to_question_name)} QID mappings")
            if len(self._qid_to_question_name) == 0:
                # Debug: Show some sample metadata
                print("Debug: First 5 metadata entries:")
                for i, meta in enumerate(self._metadata_columns[:5]):
                    print(f"  {i}: label='{meta.short_label}', import_id='{meta.import_id}', "
                          f"question_name='{meta.question_name}', is_metadata={self._is_metadata_column(meta)}")
                # Also check some entries that should have QIDs
                print("Debug: Sample non-metadata entries:")
                non_meta_count = 0
                for i, meta in enumerate(self._metadata_columns):
                    if not self._is_metadata_column(meta):
                        print(f"  {i}: label='{meta.short_label}', import_id='{meta.import_id}', "
                              f"question_name='{meta.question_name}'")
                        non_meta_count += 1
                        if non_meta_count >= 3:
                            break

    def _detect_piping_patterns(self) -> None:
        """Detect piping patterns in question text."""
        if self.verbose:
            print("Detecting piping patterns...")

        # Multiple piping formats used by Qualtrics
        # Format 1: ${q://QID/FieldType}
        piping_regex1 = re.compile(r'\$\{q://([^/]+)/([^}]+)\}')
        # Format 2: [QID-FieldType-SubField] or [QID4-ChoiceGroup-SelectedChoices]
        piping_regex2 = re.compile(r'\[([A-Z]+\d+)-([^-\]]+)-([^\]]+)\]')

        all_patterns = set()

        # Search through question texts for piping patterns
        for meta in self._metadata_columns:
            if not self._is_metadata_column(meta) and meta.question_text:
                # Format 1: ${q://QID/FieldType}
                matches1 = piping_regex1.findall(meta.question_text)
                for qid, field_type in matches1:
                    pattern = f"${{q://{qid}/{field_type}}}"
                    all_patterns.add((pattern, qid, field_type, "format1"))

                # Format 2: [QID-FieldType-SubField]
                matches2 = piping_regex2.findall(meta.question_text)
                for qid, field_type, sub_field in matches2:
                    pattern = f"[{qid}-{field_type}-{sub_field}]"
                    # Map to equivalent field type for consistency
                    if field_type == "ChoiceGroup" and sub_field == "SelectedChoices":
                        mapped_field_type = "ChoiceValue"
                    else:
                        mapped_field_type = f"{field_type}-{sub_field}"
                    all_patterns.add((pattern, qid, mapped_field_type, "format2"))

        # Search through response data for piping patterns
        for col in self._columns:
            for value in col.values:
                if value and isinstance(value, str):
                    # Format 1: ${q://QID/FieldType}
                    matches1 = piping_regex1.findall(value)
                    for qid, field_type in matches1:
                        pattern = f"${{q://{qid}/{field_type}}}"
                        all_patterns.add((pattern, qid, field_type, "format1"))

                    # Format 2: [QID-FieldType-SubField]
                    matches2 = piping_regex2.findall(value)
                    for qid, field_type, sub_field in matches2:
                        pattern = f"[{qid}-{field_type}-{sub_field}]"
                        if field_type == "ChoiceGroup" and sub_field == "SelectedChoices":
                            mapped_field_type = "ChoiceValue"
                        else:
                            mapped_field_type = f"{field_type}-{sub_field}"
                        all_patterns.add((pattern, qid, mapped_field_type, "format2"))

        # Convert to list but keep format info
        self._piping_patterns = [(pattern, qid, field_type, fmt) for pattern, qid, field_type, fmt in all_patterns]

        if self.verbose:
            print(f"Found {len(self._piping_patterns)} unique piping patterns")
            for pattern, qid, field_type, fmt in self._piping_patterns:
                print(f"  {pattern} -> QID: {qid}, Field: {field_type} ({fmt})")

    def _resolve_piping_in_text(self, text: str, response_data: Dict[str, Any] = None) -> str:
        """
        Convert Qualtrics piping to EDSL piping syntax, or resolve if response_data provided.

        Args:
            text: Text containing potential piping patterns
            response_data: Dict of question_name -> answer for piping resolution.
                          If None, converts to EDSL syntax. If provided, resolves to actual values.

        Returns:
            Text with piping patterns converted to EDSL format or resolved to values
        """
        if not text or not isinstance(text, str):
            return text

        resolved_text = text

        for pattern, qid, field_type, fmt in self._piping_patterns:
            if pattern in resolved_text:
                # Find the target question name for this QID
                target_question = self._qid_to_question_name.get(qid)

                if target_question:
                    if response_data and target_question in response_data:
                        # Resolve to actual value (for response data processing)
                        target_answer = response_data[target_question]

                        if field_type == "ChoiceValue" and target_answer:
                            # Replace with the actual choice value
                            resolved_text = resolved_text.replace(pattern, str(target_answer))
                        elif field_type == "QuestionText":
                            # Replace with question text (find it from metadata)
                            target_meta = next(
                                (meta for meta in self._metadata_columns
                                 if meta.import_id == qid),
                                None
                            )
                            if target_meta and target_meta.question_text:
                                resolved_text = resolved_text.replace(pattern, target_meta.question_text)
                    else:
                        # Convert to EDSL piping syntax (for question text)
                        if field_type == "ChoiceValue":
                            # Convert ${q://QID1/ChoiceValue} or [QID4-ChoiceGroup-SelectedChoices] to {{ Q1.answer }}
                            edsl_syntax = f"{{{{ {target_question}.answer }}}}"
                            resolved_text = resolved_text.replace(pattern, edsl_syntax)
                        elif field_type == "QuestionText":
                            # For QuestionText piping, we could reference the question text
                            # but EDSL doesn't have a direct equivalent, so we'll leave as static text
                            target_meta = next(
                                (meta for meta in self._metadata_columns
                                 if meta.import_id == qid),
                                None
                            )
                            if target_meta and target_meta.question_text:
                                resolved_text = resolved_text.replace(pattern, target_meta.question_text)

        return resolved_text

    def _resolve_piping_in_record(self, record: Dict[str, Any]) -> None:
        """
        Resolve piping patterns in a response record.

        Args:
            record: Dict of question_name -> answer that gets modified in place
        """
        # We need to resolve piping across multiple passes since one answer
        # might depend on another that also has piping
        max_iterations = 5  # Prevent infinite loops
        iteration = 0

        while iteration < max_iterations:
            changes_made = False
            iteration += 1

            # Check each answer for piping patterns
            for question_name, answer in record.items():
                if answer and isinstance(answer, str):
                    resolved_answer = self._resolve_piping_in_text(answer, record)
                    if resolved_answer != answer:
                        record[question_name] = resolved_answer
                        changes_made = True

            # If no changes were made this iteration, we're done
            if not changes_made:
                break

    def _is_metadata_column(self, metadata: QualtricsQuestionMetadata) -> bool:
        """Check if this column contains metadata rather than survey responses."""
        metadata_patterns = [
            "startdate",
            "enddate",
            "status",
            "progress",
            "duration",
            "finished",
            "recordeddate",
            "responseid",
            "distributionChannel",
            "userlanguage",
            "ipaddress",
        ]

        return any(
            pattern in metadata.short_label.lower() for pattern in metadata_patterns
        )

    def _detect_question_type(
        self, question_group: List[QualtricsQuestionMetadata]
    ) -> DataType:
        """Detect the question type for a group of related columns."""
        if len(question_group) == 0:
            return DataType.UNKNOWN

        # Check if all are metadata columns
        if all(self._is_metadata_column(meta) for meta in question_group):
            return DataType.METADATA

        # Single column questions
        if len(question_group) == 1:
            meta = question_group[0]
            question_text = meta.question_text.lower()

            # Look for checkbox indicators
            if any(
                phrase in question_text
                for phrase in [
                    "select all that apply",
                    "check all that apply",
                    "mark all that apply",
                ]
            ):
                return DataType.QUESTION_CHECKBOX

            # Look for scale indicators
            if any(
                phrase in question_text
                for phrase in ["scale of", "rate from", "rating scale", "slider"]
            ):
                return DataType.QUESTION_LINEAR_SCALE

            # Check response patterns
            col_values = self._columns[meta.column_index].values
            unique_values = list(set([v for v in col_values if v and str(v).strip()]))

            # Linear scale detection: all numeric, small range
            try:
                numeric_values = [float(v) for v in unique_values]
                if (
                    len(numeric_values) == len(unique_values)
                    and len(numeric_values) <= 11
                ):
                    return DataType.QUESTION_LINEAR_SCALE
            except (ValueError, TypeError):
                pass

            # Multiple choice vs free text based on unique values
            if len(unique_values) <= 20:
                return DataType.QUESTION_MULTIPLE_CHOICE
            else:
                return DataType.QUESTION_TEXT

        # Multi-column questions (checkboxes or multi-part)
        else:
            # Check for binary responses (typical of checkboxes)
            all_binary = True
            for meta in question_group:
                col_values = self._columns[meta.column_index].values
                unique_values = set(
                    [str(v).lower() for v in col_values if v and str(v).strip()]
                )
                if not unique_values.issubset(
                    {"1", "0", "true", "false", "yes", "no", "checked", ""}
                ):
                    all_binary = False
                    break

            if all_binary:
                return DataType.QUESTION_CHECKBOX
            else:
                return DataType.QUESTION_MULTIPLE_CHOICE

    def _build_survey(self) -> None:
        """Build EDSL Survey from the detected questions."""
        if self.verbose:
            print("Building EDSL Survey...")

        # Group metadata by question_name
        question_groups = defaultdict(list)
        for meta in self._metadata_columns:
            if not self._is_metadata_column(meta):
                question_groups[meta.question_name].append(meta)

        # Build questions
        questions = []
        for question_name, group in question_groups.items():
            group.sort(key=lambda x: x.column_index)  # Ensure consistent ordering

            question_type = self._detect_question_type(group)
            question_text = group[0].question_text  # Use first column's text

            # Resolve piping in question text (without response data for now)
            question_text = self._resolve_piping_in_text(question_text)

            if self.create_semantic_names:
                # Create semantic name from question text
                clean_text = re.sub(r"[^\w\s]", "", question_text)
                semantic_name = "_".join(clean_text.lower().split()[:5])
                if semantic_name:
                    question_name = semantic_name

            try:
                if question_type == DataType.QUESTION_TEXT:
                    questions.append(
                        QuestionFreeText(
                            question_name=question_name, question_text=question_text
                        )
                    )

                elif question_type == DataType.QUESTION_MULTIPLE_CHOICE:
                    # Get unique response options
                    options = set()
                    for meta in group:
                        col_values = self._columns[meta.column_index].values
                        for value in col_values:
                            if value and str(value).strip():
                                options.add(str(value).strip())

                    if options:
                        questions.append(
                            QuestionMultipleChoice(
                                question_name=question_name,
                                question_text=question_text,
                                question_options=sorted(list(options)),
                            )
                        )

                elif question_type == DataType.QUESTION_CHECKBOX:
                    # For checkboxes, use subpart names as options
                    if len(group) > 1:
                        options = []
                        for meta in group:
                            if meta.subpart:
                                options.append(meta.subpart)
                            else:
                                options.append(meta.short_label)

                        if options:
                            questions.append(
                                QuestionCheckBox(
                                    question_name=question_name,
                                    question_text=question_text,
                                    question_options=options,
                                )
                            )

                elif question_type == DataType.QUESTION_LINEAR_SCALE:
                    # Detect scale range from responses
                    all_values = []
                    for meta in group:
                        col_values = self._columns[meta.column_index].values
                        for value in col_values:
                            if value and str(value).strip():
                                try:
                                    all_values.append(int(float(value)))
                                except (ValueError, TypeError):
                                    pass

                    if all_values:
                        min_val = min(all_values)
                        max_val = max(all_values)
                        questions.append(
                            QuestionLinearScale(
                                question_name=question_name,
                                question_text=question_text,
                                question_options=[min_val, max_val],
                            )
                        )

            except Exception as e:
                if self.verbose:
                    print(f"Warning: Could not create question {question_name}: {e}")
                # Fallback to free text
                questions.append(
                    QuestionFreeText(
                        question_name=question_name,
                        question_text=question_text or f"Question {question_name}",
                    )
                )

        self._survey = Survey(questions=questions)

        if self.verbose:
            print(f"Created survey with {len(questions)} questions")

    def _apply_vibe_processing(self) -> None:
        """Apply AI-powered question enhancement if vibe processor is configured."""
        if not self.vibe_processor or not self._survey:
            return

        if self.verbose:
            print("Applying vibe processing to enhance questions...")

        try:
            # Process the survey asynchronously
            enhanced_survey = self.vibe_processor.process_survey_sync(self._survey)
            self._survey = enhanced_survey

            if self.verbose:
                print(f"Vibe processing completed for {len(enhanced_survey.questions)} questions")
                # Print change summary
                self.vibe_processor.print_change_summary()

        except Exception as e:
            if self.verbose:
                print(f"Warning: Vibe processing failed: {e}")
            # Continue with original survey if vibe processing fails

    def _build_question_mappings(self) -> None:
        """Build mappings from question names to column indices."""
        if self.verbose:
            print("Building question mappings...")

        mappings = defaultdict(list)
        for meta in self._metadata_columns:
            if not self._is_metadata_column(meta):
                mappings[meta.question_name].append(meta.column_index)

        self._question_mappings = []
        for question_name, indices in mappings.items():
            # Determine if it's a checkbox question
            is_checkbox = len(indices) > 1

            self._question_mappings.append(
                QuestionMapping(
                    question_name=question_name,
                    column_indices=indices,
                    is_checkbox=is_checkbox,
                )
            )

    def _build_response_records(self) -> None:
        """Extract response records for each respondent."""
        if self.verbose:
            print("Building response records...")

        self._response_records = []

        if not self._columns:
            return

        num_respondents = len(self._columns[0].values)

        for respondent_idx in range(num_respondents):
            record = {}

            for mapping in self._question_mappings:
                question_name = mapping.question_name

                if mapping.is_checkbox:
                    # Collect checkbox responses
                    selected = []
                    for col_idx in mapping.column_indices:
                        if col_idx < len(self._columns):
                            value = self._columns[col_idx].values[respondent_idx]
                            if value and str(value).strip() not in [
                                "",
                                "0",
                                "false",
                                "no",
                            ]:
                                meta = self._metadata_columns[col_idx]
                                option_name = meta.subpart or meta.short_label
                                selected.append(option_name)
                    record[question_name] = selected
                else:
                    # Single response
                    if mapping.column_indices:
                        col_idx = mapping.column_indices[0]
                        if col_idx < len(self._columns):
                            value = self._columns[col_idx].values[respondent_idx]
                            record[question_name] = str(value) if value else None

            # Resolve piping in responses after collecting all responses for this record
            self._resolve_piping_in_record(record)

            self._response_records.append(record)

        if self.verbose:
            print(f"Built {len(self._response_records)} response records")

    def _build_agents(self) -> None:
        """Create EDSL agents with stored responses."""
        if self.verbose:
            print("Building EDSL agents...")

        agents = []
        for index, record in enumerate(self._response_records):
            agent = Agent()

            # Store actual responses as direct answering method
            def construct_answer_func(rec: dict) -> Callable:
                def func(self, question, scenario=None):
                    return rec.get(question.question_name, None)

                return func

            agent.add_direct_question_answering_method(construct_answer_func(record))
            agent.traits["_index"] = index
            agents.append(agent)

        self._agents = AgentList(agents)

        if self.verbose:
            print(f"Created {len(agents)} agents")

    @property
    def survey(self) -> Survey:
        """The Survey object with all questions."""
        return self._survey

    @property
    def agents(self) -> AgentList:
        """One agent per respondent with their actual responses."""
        return self._agents

    @property
    def scenarios(self) -> ScenarioList:
        """Scenarios (empty for basic Qualtrics import)."""
        if self._scenarios is None:
            self._scenarios = ScenarioList([])
        return self._scenarios

    def run(self, disable_remote_inference: bool = True, **kwargs) -> "Results":
        """Execute survey with agents and return Results."""
        if self._survey is None or self._agents is None:
            raise RuntimeError("Survey and agents must be built before running")

        jobs = self._survey.by(self._agents)
        self._results = jobs.run(
            disable_remote_inference=disable_remote_inference, **kwargs
        )
        return self._results

    def get_vibe_change_log(self) -> List[Dict[str, Any]]:
        """
        Get detailed log of all changes made during vibe processing.

        Returns:
            List of change dictionaries with diffs and reasoning
        """
        if self.vibe_processor:
            return self.vibe_processor.get_change_log()
        return []

    def get_vibe_summary(self) -> Dict[str, Any]:
        """
        Get summary of vibe processing changes.

        Returns:
            Summary dictionary with counts and statistics
        """
        if self.vibe_processor:
            return self.vibe_processor.get_change_summary()
        return {
            'total_changes': 0,
            'changes_by_type': {},
            'questions_modified': 0,
            'average_confidence': 0.0
        }

    @property
    def results(self):
        """Results from last run (None if not run yet)."""
        return self._results
