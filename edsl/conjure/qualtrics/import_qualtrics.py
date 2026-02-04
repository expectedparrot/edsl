"""Import Qualtrics CSV exports and convert to EDSL objects."""

from typing import List, Dict, Any, Optional

from edsl.agents import AgentList
from edsl.scenarios import ScenarioList
from edsl.surveys import Survey

from .data_classes import Column, QualtricsQuestionMetadata, QuestionMapping
from .csv_reader import QualtricsCSVReader
from .metadata_builder import QualtricsMetadataBuilder
from .piping_resolver import QualtricsPipingResolver
from .survey_builder import QualtricsSurveyBuilder
from .response_extractor import QualtricsResponseExtractor
from .agent_builder import QualtricsAgentBuilder
from .vibe import VibeProcessor, VibeConfig


class ImportQualtrics:
    """Convert Qualtrics CSV export to EDSL objects.

    This class orchestrates the conversion process by delegating to
    specialized helper classes:
    - QualtricsCSVReader: Reads and parses the CSV file
    - QualtricsMetadataBuilder: Builds column metadata
    - QualtricsPipingResolver: Handles piping patterns
    - QualtricsSurveyBuilder: Builds the EDSL Survey
    - QualtricsResponseExtractor: Extracts response records
    - QualtricsAgentBuilder: Creates EDSL agents
    """

    def __init__(
        self,
        csv_file: str,
        verbose: bool = False,
        create_semantic_names: bool = False,
        repair_excel_dates: bool = False,
        order_options_semantically: bool = False,
        vibe_config: Optional[VibeConfig] | bool = True,
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

        # Initialize vibe processor
        self.vibe_processor = self._init_vibe_processor(vibe_config)

        # Initialize helper classes
        self.csv_reader = QualtricsCSVReader(csv_file, verbose)
        self.metadata_builder = QualtricsMetadataBuilder(verbose)
        self.piping_resolver = QualtricsPipingResolver(verbose)
        self.agent_builder = QualtricsAgentBuilder(verbose)

        # Internal state
        self._columns: List[Column] = []
        self._metadata_columns: List[QualtricsQuestionMetadata] = []
        self._survey: Optional[Survey] = None
        self._agents: Optional[AgentList] = None
        self._scenarios: Optional[ScenarioList] = None
        self._question_mappings: List[QuestionMapping] = []
        self._response_records: List[Dict[str, Any]] = []
        self._results = None

        # Process the CSV
        self._process()

    def _init_vibe_processor(self, vibe_config) -> Optional[VibeProcessor]:
        """Initialize the vibe processor based on config."""
        if vibe_config is True:
            config = VibeConfig()
            config.enable_logging = self.verbose
            return VibeProcessor(config)
        elif vibe_config is False or vibe_config is None:
            return None
        else:
            return VibeProcessor(vibe_config)

    def _process(self) -> None:
        """Run the full processing pipeline."""
        # 1. Read CSV
        csv_data = self.csv_reader.read()
        self._columns = csv_data.columns

        # 2. Build metadata
        self._metadata_columns = self.metadata_builder.build(
            csv_data.short_labels,
            csv_data.question_texts,
            csv_data.import_ids,
        )

        # 3. Setup piping
        self.piping_resolver.build_qid_mappings(
            self._metadata_columns,
            self.metadata_builder.is_metadata_column,
        )
        self.piping_resolver.detect_patterns(
            self._metadata_columns,
            self._columns,
            self.metadata_builder.is_metadata_column,
        )

        # 4. Build survey
        survey_builder = QualtricsSurveyBuilder(
            columns=self._columns,
            metadata_columns=self._metadata_columns,
            is_metadata_func=self.metadata_builder.is_metadata_column,
            resolve_piping_func=self.piping_resolver.resolve_text,
            create_semantic_names=self.create_semantic_names,
            verbose=self.verbose,
        )
        self._survey = survey_builder.build()

        # 5. Apply vibe processing
        self._apply_vibe_processing()

        # 6. Extract responses
        response_extractor = QualtricsResponseExtractor(
            columns=self._columns,
            metadata_columns=self._metadata_columns,
            survey=self._survey,
            is_metadata_func=self.metadata_builder.is_metadata_column,
            resolve_piping_func=self.piping_resolver.resolve_record,
            verbose=self.verbose,
        )
        self._question_mappings = response_extractor.build_mappings()
        self._response_records = response_extractor.extract_records()

        # 7. Build agents
        self._agents = self.agent_builder.build(self._response_records)

    def _apply_vibe_processing(self) -> None:
        """Apply AI-powered question enhancement if vibe processor is configured."""
        if not self.vibe_processor or not self._survey:
            return

        if self.verbose:
            print("Applying vibe processing to enhance questions...")

        try:
            response_data = self._extract_response_data_for_vibe()
            enhanced_survey = self.vibe_processor.process_survey_sync(
                self._survey, response_data
            )
            self._survey = enhanced_survey

            if self.verbose:
                print(
                    f"Vibe processing completed for {len(enhanced_survey.questions)} questions"
                )
                try:
                    self.vibe_processor.print_change_summary()
                except AttributeError as e:
                    print(f"Note: Change summary not available: {e}")
                except Exception as e:
                    print(f"Note: Could not print change summary: {e}")

        except Exception as e:
            if self.verbose:
                print(f"Warning: Vibe processing failed: {e}")

    def _extract_response_data_for_vibe(self) -> Dict[str, List[str]]:
        """Extract response data for questions to help with option analysis and type detection."""
        response_data = {}

        for meta in self._metadata_columns:
            if self.metadata_builder.is_metadata_column(meta):
                continue

            column = self._columns[meta.column_index]
            question_name = meta.question_name

            # Extract response data for ALL question columns to enable proper type detection
            # Previously only extracted _TEXT/_DO/OTHER columns, but LLM needs actual response
            # data to distinguish between question types (e.g., numerical vs likert vs multiple choice)
            responses = []
            for value in column.values:
                if (
                    value
                    and str(value).strip()
                    and str(value).strip().lower() not in ["nan", "null", ""]
                ):
                    responses.append(str(value).strip())

            if responses:
                if question_name not in response_data:
                    response_data[question_name] = []
                response_data[question_name].extend(responses)

        if self.verbose and response_data:
            print(f"Extracted response data for {len(response_data)} questions:")
            for q_name, responses in response_data.items():
                print(f"  {q_name}: {len(responses)} responses")
                if responses:
                    unique_responses = list(set(responses))[:5]
                    print(f"    Examples: {unique_responses}")

        return response_data

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
        """Get detailed log of all changes made during vibe processing."""
        if self.vibe_processor:
            return self.vibe_processor.get_change_log()
        return []

    def get_vibe_summary(self) -> Dict[str, Any]:
        """Get summary of vibe processing changes."""
        if self.vibe_processor:
            return self.vibe_processor.get_change_summary()
        return {
            "total_changes": 0,
            "changes_by_type": {},
            "questions_modified": 0,
            "average_confidence": 0.0,
        }

    @property
    def results(self):
        """Results from last run (None if not run yet)."""
        return self._results
