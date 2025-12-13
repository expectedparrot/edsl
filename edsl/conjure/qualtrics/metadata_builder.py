"""Metadata builder for Qualtrics columns."""

import json
import re
from typing import List, Optional

from .data_classes import QualtricsQuestionMetadata


class QualtricsMetadataBuilder:
    """Build metadata for Qualtrics CSV columns.
    
    Handles:
    - Parsing import IDs from JSON cells
    - Canonicalizing labels into question names
    - Extracting subparts from labels
    - Identifying metadata vs question columns
    """
    
    # Patterns that indicate metadata columns (not survey questions)
    METADATA_PATTERNS = [
        "startdate",
        "enddate",
        "status",
        "progress",
        "duration",
        "finished",
        "recordeddate",
        "responseid",
        "distributionchannel",
        "userlanguage",
        "ipaddress",
    ]
    
    def __init__(self, verbose: bool = False):
        """
        Initialize the metadata builder.
        
        Args:
            verbose: Print detailed processing information
        """
        self.verbose = verbose
        self._parse_errors_shown = 0
    
    def build(
        self,
        short_labels: List[str],
        question_texts: List[str],
        import_ids: List[str],
    ) -> List[QualtricsQuestionMetadata]:
        """Build metadata for all columns.
        
        Args:
            short_labels: Row 1 headers (Q1, Q2_1, etc.)
            question_texts: Row 2 headers (question text)
            import_ids: Row 3 headers (JSON with ImportId)
            
        Returns:
            List of QualtricsQuestionMetadata objects
        """
        if self.verbose:
            print("Building column metadata...")
        
        metadata_list = []
        for col_idx, (short_label, question_text, import_cell) in enumerate(
            zip(short_labels, question_texts, import_ids)
        ):
            import_id = self.parse_import_id(import_cell)
            question_name = self.canonicalize_label(short_label)
            subpart = self.extract_subpart(short_label)
            
            metadata = QualtricsQuestionMetadata(
                short_label=short_label,
                question_text=question_text or "",
                import_id=import_id or "",
                question_name=question_name,
                subpart=subpart,
                column_index=col_idx,
            )
            metadata_list.append(metadata)
        
        if self.verbose:
            print(f"Built metadata for {len(metadata_list)} columns")
        
        return metadata_list
    
    def parse_import_id(self, cell: str) -> Optional[str]:
        """Parse a cell like '{"ImportId":"QID90_1"}' -> 'QID90_1'.
        
        Args:
            cell: The raw cell value from row 3
            
        Returns:
            The extracted import ID, or None if parsing fails
        """
        if not isinstance(cell, str):
            return None
        s = cell.strip()
        if not (s.startswith("{") and "ImportId" in s):
            return None
        
        # Handle CSV escape sequences - fix common issues
        s = s.replace('\\"', '"').replace('{"', '{"').replace('"}', '"}')
        
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
                match = re.search(r'ImportId["\s]*:["\s]*([^"]+)', s)
                if match:
                    import_id = match.group(1)
                    if "#" in import_id:
                        import_id = import_id.split("#")[0]
                    return import_id
            except:
                pass
            
            # Debug: Only show first few exceptions
            if self._parse_errors_shown < 3:
                print(f"Debug: Parse error for '{cell[:50]}...': {e}")
                self._parse_errors_shown += 1
            return None
    
    def canonicalize_label(self, label: str) -> str:
        """Normalize the short header label into a stable 'question_name'.
        
        Examples:
            'Q1'     -> 'Q1'
            'Q2_1'   -> 'Q2'
            'Q3_TEXT' -> 'Q3'
            '0#1'    -> 'Q0'
            
        Args:
            label: The short label from row 1
            
        Returns:
            A normalized question name
        """
        if not isinstance(label, str):
            return str(label)
        
        # Clean the label by removing invalid characters
        cleaned = label.strip()
        
        # Replace # with underscore temporarily
        cleaned = cleaned.replace("#", "_")
        
        # Keep everything before the LAST underscore as base (if any)
        if "_" in cleaned:
            base, _ = cleaned.rsplit("_", 1)
            cleaned = base.strip()
        
        # Ensure it starts with a letter or underscore (valid Python identifier)
        if cleaned and not (cleaned[0].isalpha() or cleaned[0] == "_"):
            cleaned = f"Q{cleaned}"
        
        # Replace any remaining invalid characters with underscores
        cleaned = re.sub(r"[^\w]", "_", cleaned)
        
        # Ensure it's not empty
        if not cleaned:
            cleaned = "Unknown"
        
        return cleaned
    
    def extract_subpart(self, label: str) -> Optional[str]:
        """Extract a subpart suffix from the label when present.
        
        Examples:
            'Q1_1' -> '1'
            'Q2_TEXT' -> 'TEXT'
            'Q3' -> None
            
        Args:
            label: The short label from row 1
            
        Returns:
            The subpart suffix, or None if not present
        """
        if not isinstance(label, str):
            return None
        if "_" in label:
            _, tail = label.rsplit("_", 1)
            return tail.strip()
        return None
    
    def is_metadata_column(self, metadata: QualtricsQuestionMetadata) -> bool:
        """Check if this column contains metadata rather than survey responses.
        
        Args:
            metadata: The column metadata to check
            
        Returns:
            True if this is a metadata column, False otherwise
        """
        return any(
            pattern in metadata.short_label.lower() 
            for pattern in self.METADATA_PATTERNS
        )
