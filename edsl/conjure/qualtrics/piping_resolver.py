"""Piping pattern detection and resolution for Qualtrics."""

import re
from typing import Dict, List, Tuple, Any, Optional

from .data_classes import QualtricsQuestionMetadata, Column


class QualtricsPipingResolver:
    """Detect and resolve Qualtrics piping patterns.
    
    Handles:
    - Building QID-to-question-name mappings
    - Detecting piping patterns in question text
    - Resolving piping in text (to EDSL syntax or actual values)
    - Resolving piping in response records
    """
    
    # Piping pattern formats used by Qualtrics
    # Format 1: ${q://QID/FieldType}
    PIPING_REGEX_FORMAT1 = re.compile(r"\$\{q://([^/]+)/([^}]+)\}")
    # Format 2: [QID-FieldType-SubField] or [QID4-ChoiceGroup-SelectedChoices]
    PIPING_REGEX_FORMAT2 = re.compile(r"\[([A-Z]+\d+)-([^-\]]+)-([^\]]+)\]")
    
    def __init__(self, verbose: bool = False):
        """
        Initialize the piping resolver.
        
        Args:
            verbose: Print detailed processing information
        """
        self.verbose = verbose
        self._qid_to_question_name: Dict[str, str] = {}
        self._piping_patterns: List[Tuple[str, str, str, str]] = []
        self._metadata_columns: List[QualtricsQuestionMetadata] = []
    
    def build_qid_mappings(
        self,
        metadata_columns: List[QualtricsQuestionMetadata],
        is_metadata_func,
    ) -> None:
        """Build mapping from QID (import_id) to question_name.
        
        Args:
            metadata_columns: List of column metadata
            is_metadata_func: Function to check if a column is metadata
        """
        if self.verbose:
            print("Building QID to question name mappings...")
        
        self._metadata_columns = metadata_columns
        self._qid_to_question_name = {}
        
        for meta in metadata_columns:
            if meta.import_id and not is_metadata_func(meta):
                self._qid_to_question_name[meta.import_id] = meta.question_name
        
        if self.verbose:
            print(f"Built {len(self._qid_to_question_name)} QID mappings")
    
    def detect_patterns(
        self,
        metadata_columns: List[QualtricsQuestionMetadata],
        columns: List[Column],
        is_metadata_func,
    ) -> None:
        """Detect piping patterns in question text and response data.
        
        Args:
            metadata_columns: List of column metadata
            columns: List of data columns
            is_metadata_func: Function to check if a column is metadata
        """
        if self.verbose:
            print("Detecting piping patterns...")
        
        all_patterns = set()
        
        # Search through question texts for piping patterns
        for meta in metadata_columns:
            if not is_metadata_func(meta) and meta.question_text:
                self._extract_patterns_from_text(meta.question_text, all_patterns)
        
        # Search through response data for piping patterns
        for col in columns:
            for value in col.values:
                if value and isinstance(value, str):
                    self._extract_patterns_from_text(value, all_patterns)
        
        self._piping_patterns = list(all_patterns)
        
        if self.verbose:
            print(f"Found {len(self._piping_patterns)} unique piping patterns")
            for pattern, qid, field_type, fmt in self._piping_patterns:
                print(f"  {pattern} -> QID: {qid}, Field: {field_type} ({fmt})")
    
    def _extract_patterns_from_text(self, text: str, patterns_set: set) -> None:
        """Extract piping patterns from text and add to the set.
        
        Args:
            text: Text to search for patterns
            patterns_set: Set to add found patterns to
        """
        # Format 1: ${q://QID/FieldType}
        matches1 = self.PIPING_REGEX_FORMAT1.findall(text)
        for qid, field_type in matches1:
            pattern = f"${{q://{qid}/{field_type}}}"
            patterns_set.add((pattern, qid, field_type, "format1"))
        
        # Format 2: [QID-FieldType-SubField]
        matches2 = self.PIPING_REGEX_FORMAT2.findall(text)
        for qid, field_type, sub_field in matches2:
            pattern = f"[{qid}-{field_type}-{sub_field}]"
            # Map to equivalent field type for consistency
            if field_type == "ChoiceGroup" and sub_field == "SelectedChoices":
                mapped_field_type = "ChoiceValue"
            else:
                mapped_field_type = f"{field_type}-{sub_field}"
            patterns_set.add((pattern, qid, mapped_field_type, "format2"))
    
    def resolve_text(
        self, 
        text: str, 
        response_data: Optional[Dict[str, Any]] = None
    ) -> str:
        """Convert Qualtrics piping to EDSL piping syntax, or resolve if response_data provided.
        
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
                target_question = self._qid_to_question_name.get(qid)
                
                if target_question:
                    if response_data and target_question in response_data:
                        # Resolve to actual value (for response data processing)
                        target_answer = response_data[target_question]
                        
                        if field_type == "ChoiceValue" and target_answer:
                            resolved_text = resolved_text.replace(
                                pattern, str(target_answer)
                            )
                        elif field_type == "QuestionText":
                            target_meta = next(
                                (meta for meta in self._metadata_columns 
                                 if meta.import_id == qid),
                                None,
                            )
                            if target_meta and target_meta.question_text:
                                resolved_text = resolved_text.replace(
                                    pattern, target_meta.question_text
                                )
                    else:
                        # Convert to EDSL piping syntax (for question text)
                        if field_type == "ChoiceValue":
                            edsl_syntax = f"{{{{ {target_question}.answer }}}}"
                            resolved_text = resolved_text.replace(pattern, edsl_syntax)
                        elif field_type == "QuestionText":
                            target_meta = next(
                                (meta for meta in self._metadata_columns 
                                 if meta.import_id == qid),
                                None,
                            )
                            if target_meta and target_meta.question_text:
                                resolved_text = resolved_text.replace(
                                    pattern, target_meta.question_text
                                )
        
        return resolved_text
    
    def resolve_record(self, record: Dict[str, Any]) -> None:
        """Resolve piping patterns in a response record (modifies in place).
        
        Args:
            record: Dict of question_name -> answer that gets modified in place
        """
        max_iterations = 5  # Prevent infinite loops
        iteration = 0
        
        while iteration < max_iterations:
            changes_made = False
            iteration += 1
            
            for question_name, answer in record.items():
                if answer and isinstance(answer, str):
                    resolved_answer = self.resolve_text(answer, record)
                    if resolved_answer != answer:
                        record[question_name] = resolved_answer
                        changes_made = True
            
            if not changes_made:
                break
    
    @property
    def qid_to_question_name(self) -> Dict[str, str]:
        """Get the QID to question name mapping."""
        return self._qid_to_question_name
    
    @property
    def piping_patterns(self) -> List[Tuple[str, str, str, str]]:
        """Get the detected piping patterns."""
        return self._piping_patterns
