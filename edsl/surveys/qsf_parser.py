from __future__ import annotations

import json
import re
from dataclasses import dataclass, field, asdict
from html import unescape
from pathlib import Path
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

_HTML_TAG_RE = re.compile(r"<[^>]+>")


def strip_html(text: Optional[str]) -> str:
    """
    Very simple HTML stripper for Qualtrics QuestionText.

    Parameters
    ----------
    text : Optional[str]

    Returns
    -------
    str
    """
    if not text:
        return ""
    text = unescape(text)
    return _HTML_TAG_RE.sub("", text).strip()


def convert_qualtrics_piping_to_edsl(text: Optional[str]) -> str:
    """
    Convert Qualtrics piping syntax to EDSL piping syntax.

    Qualtrics uses patterns like:
    - ${q://QID1/ChoiceGroup/SelectedChoices}
    - ${q://QID2/ChoiceTextEntryValue}
    - ${q://QID3/DisplayValue}

    EDSL uses patterns like:
    - {{ variable_name.answer }}

    Parameters
    ----------
    text : Optional[str]
        Text that may contain Qualtrics piping syntax

    Returns
    -------
    str
        Text with Qualtrics piping converted to EDSL format
    """
    if not text:
        return ""

    # Pattern to match Qualtrics piping: ${q://QID/...}
    qualtrics_piping_pattern = re.compile(r"\$\{q://([^/]+)(?:/[^}]*)?\}")

    def replace_piping(match):
        qid = match.group(1)
        # Convert QID to a valid variable name using Survey's sanitization
        from .survey import Survey

        variable_name = Survey._sanitize_name(qid)
        # Convert to EDSL piping format
        return f"{{{{ {variable_name}.answer }}}}"

    return qualtrics_piping_pattern.sub(replace_piping, text)


# ---------------------------------------------------------------------------
# Normalized schema dataclasses
# ---------------------------------------------------------------------------


@dataclass
class Choice:
    id: str
    text: str
    order: int
    recode: Optional[str] = None
    export_tag: Optional[str] = None


@dataclass
class Validation:
    force_response: bool = False
    force_type: Optional[str] = None
    type: Optional[str] = None
    raw: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Question:
    id: str  # Qualtrics QID
    export_tag: Optional[str]
    text: str  # stripped text
    raw_text: str  # original HTML
    type: str  # logical type: single_choice, text, matrix_single, ...
    metadata: Dict[str, Any]  # original qsf type/selector/subselector/etc.
    choices: List[Choice] = field(default_factory=list)
    scale: List[Choice] = field(default_factory=list)  # for matrix, likert, etc.
    validation: Optional[Validation] = None
    randomization: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BlockElement:
    kind: str  # "question" | "page_break" | "descriptive" | "other"
    question_id: Optional[str]
    raw: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Block:
    id: str
    name: str
    type: str  # "default", "standard", ...
    elements: List[BlockElement] = field(default_factory=list)
    raw: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EmbeddedField:
    name: str
    source: str  # "custom" | "recipient" | ...
    value: Optional[str] = None
    analyze_text: Optional[bool] = None
    raw: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SurveyOptions:
    back_button: bool = False
    save_and_continue: bool = False
    protection: Optional[str] = None
    expiration: Optional[str] = None
    termination_behavior: Optional[str] = None
    progress_bar: Optional[str] = None
    partial_data_policy: Optional[str] = None
    skin: Optional[str] = None
    raw: Dict[str, Any] = field(default_factory=dict)


@dataclass
class FlowRandomizer:
    present: Optional[int] = None
    evenly: bool = False


@dataclass
class FlowNode:
    id: Optional[str]
    type: str  # "root", "block", "branch", "randomizer", ...
    block_id: Optional[str] = None
    embedded_fields: List[EmbeddedField] = field(default_factory=list)
    branch_logic: Optional[Dict[str, Any]] = None
    randomizer: Optional[FlowRandomizer] = None
    children: List["FlowNode"] = field(default_factory=list)
    raw: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StandardSurvey:
    id: str
    name: str
    description: Optional[str]
    language: Optional[str]
    metadata: Dict[str, Any]
    blocks: List[Block]
    questions: List[Question]
    flow: FlowNode
    embedded_data: List[EmbeddedField]
    options: SurveyOptions

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the dataclass tree into plain dictionaries for JSON export.
        """
        return asdict(self)


# ---------------------------------------------------------------------------
# QSF Parser
# ---------------------------------------------------------------------------


class QSFParser:
    """
    Parse a Qualtrics QSF JSON document into a normalized StandardSurvey.

    Usage
    -----
    You can pass in a pre-loaded dict:

    >>> data = {"SurveyEntry": {"SurveyID": "S1", "SurveyName": "Test", "SurveyDescription": "", "SurveyLanguage": "EN"}, "SurveyElements": []}
    >>> parser = QSFParser(data)
    >>> survey = parser.parse()  # will raise due to missing FL element
    Traceback (most recent call last):
        ...
    ValueError: No flow (FL) element found in QSF.

    For a minimal working example:

    >>> minimal_data = {
    ...     "SurveyEntry": {
    ...         "SurveyID": "SV_test",
    ...         "SurveyName": "Test Survey",
    ...         "SurveyDescription": "A test survey",
    ...         "SurveyLanguage": "EN"
    ...     },
    ...     "SurveyElements": [
    ...         {"Element": "FL", "Payload": {"Type": "Root", "Flow": []}}
    ...     ]
    ... }
    >>> parser = QSFParser(minimal_data)
    >>> survey = parser.parse()
    >>> survey.name
    'Test Survey'
    >>> survey.id
    'SV_test'
    """

    def __init__(self, qsf: Dict[str, Any]) -> None:
        self.data = qsf

        self._survey_entry: Dict[str, Any] = {}
        self._blocks_raw: Optional[Any] = None
        self._flow_raw: Optional[Dict[str, Any]] = None
        self._options_raw: Optional[Dict[str, Any]] = None
        self._questions_raw: Dict[str, Dict[str, Any]] = {}
        self._misc_elements: List[Dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Constructors
    # ------------------------------------------------------------------

    @classmethod
    def from_file(cls, path: str | Path, encoding: str = "utf-8") -> "QSFParser":
        path = Path(path)
        with path.open("r", encoding=encoding) as f:
            data = json.load(f)
        return cls(data)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def parse(self) -> StandardSurvey:
        """
        Main entry point. Returns a fully-populated StandardSurvey instance.
        """
        self._validate_top_level()
        self._survey_entry = self.data["SurveyEntry"]
        self._index_survey_elements()

        survey_id = self._survey_entry.get("SurveyID", "")
        survey_name = self._survey_entry.get("SurveyName", "")
        survey_description = self._survey_entry.get("SurveyDescription")
        survey_language = self._survey_entry.get("SurveyLanguage")

        questions = self._parse_questions()
        blocks = self._parse_blocks()
        options = self._parse_options()
        flow_root = self._parse_flow()
        embedded_fields = self._collect_embedded_fields(flow_root)

        metadata = {
            "qsf_SurveyEntry": self._survey_entry,
            "qsf_misc_elements": self._misc_elements,
        }

        # Order questions based on flow/block structure
        ordered_questions = self._order_questions_by_flow(questions, blocks, flow_root)

        # Create QID to sanitized export tag mapping for improved piping conversion
        # We need to use the same sanitization logic that Survey uses for question names
        from .survey import Survey

        qid_to_export_tag = {
            qid: Survey._sanitize_name(question.export_tag or qid)
            for qid, question in questions.items()
        }

        # Apply improved piping conversion to all questions using the mapping
        improved_questions = self._apply_improved_piping_conversion(
            ordered_questions, qid_to_export_tag
        )

        return StandardSurvey(
            id=survey_id,
            name=survey_name,
            description=survey_description,
            language=survey_language,
            metadata=metadata,
            blocks=blocks,
            questions=improved_questions,
            flow=flow_root,
            embedded_data=embedded_fields,
            options=options,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _order_questions_by_flow(
        self, questions: Dict[str, Question], blocks: List[Block], flow_root: FlowNode
    ) -> List[Question]:
        """
        Order questions based on the flow/block structure to preserve the original QSF ordering.

        Args:
            questions: Dictionary of questions indexed by question ID
            blocks: List of blocks parsed from QSF
            flow_root: Flow structure from QSF

        Returns:
            List of questions in the proper order
        """
        ordered_questions = []
        processed_question_ids = set()

        def extract_questions_from_flow_node(node: FlowNode):
            """Recursively extract question IDs from flow node structure."""
            question_ids = []

            if node.type == "block" and node.block_id:
                # Find the block and extract its questions in order
                for block in blocks:
                    if block.id == node.block_id:
                        for element in block.elements:
                            if element.kind == "question" and element.question_id:
                                question_ids.append(element.question_id)
                        break

            # Process child nodes
            for child in node.children:
                question_ids.extend(extract_questions_from_flow_node(child))

            return question_ids

        # Extract question IDs in flow order
        flow_question_ids = extract_questions_from_flow_node(flow_root)

        # Add questions in flow order
        for qid in flow_question_ids:
            if qid in questions and qid not in processed_question_ids:
                ordered_questions.append(questions[qid])
                processed_question_ids.add(qid)

        # Add any remaining questions that weren't in the flow (edge case)
        for qid, question in questions.items():
            if qid not in processed_question_ids:
                ordered_questions.append(question)
                processed_question_ids.add(qid)

        return ordered_questions

    def _apply_improved_piping_conversion(
        self, questions: List[Question], qid_to_export_tag: Dict[str, str]
    ) -> List[Question]:
        """
        Apply improved piping conversion using export tag mapping.

        Args:
            questions: List of questions to process
            qid_to_export_tag: Mapping from QID to export tag/variable name

        Returns:
            List of questions with improved piping conversion
        """

        def improved_piping_converter(text: str) -> str:
            """Convert Qualtrics piping using export tag mapping."""
            if not text:
                return text

            # Pattern to match Qualtrics piping: ${q://QID/...}
            qualtrics_piping_pattern = re.compile(r"\$\{q://([^/]+)(?:/[^}]*)?\}")

            def replace_piping(match):
                qid = match.group(1)
                # Use export tag if available, otherwise fall back to sanitized QID
                # Import here to avoid circular imports
                from .survey import Survey

                variable_name = qid_to_export_tag.get(qid, Survey._sanitize_name(qid))
                # Convert to EDSL piping format
                return f"{{{{ {variable_name}.answer }}}}"

            return qualtrics_piping_pattern.sub(replace_piping, text)

        # Apply improved piping conversion to all questions
        improved_questions = []
        for question in questions:
            # Convert question text
            if question.text:
                question.text = improved_piping_converter(question.text)

            # Convert choice text
            improved_choices = []
            for choice in question.choices:
                if choice.text:
                    choice.text = improved_piping_converter(choice.text)
                improved_choices.append(choice)
            question.choices = improved_choices

            # Convert scale text (for matrix questions, etc.)
            improved_scale = []
            for scale_item in question.scale:
                if scale_item.text:
                    scale_item.text = improved_piping_converter(scale_item.text)
                improved_scale.append(scale_item)
            question.scale = improved_scale

            improved_questions.append(question)

        return improved_questions

    def _validate_top_level(self) -> None:
        if "SurveyEntry" not in self.data:
            raise ValueError("QSF JSON missing 'SurveyEntry' key.")
        if "SurveyElements" not in self.data or not isinstance(
            self.data["SurveyElements"], list
        ):
            raise ValueError("QSF JSON missing 'SurveyElements' list.")

    def _index_survey_elements(self) -> None:
        """
        Walk SurveyElements once and index by type.
        """
        elements = self.data["SurveyElements"]

        for el in elements:
            etype = el.get("Element")
            primary = el.get("PrimaryAttribute")
            payload = el.get("Payload")

            if etype == "BL":
                self._blocks_raw = payload
            elif etype == "FL":
                self._flow_raw = payload
            elif etype == "SO":
                self._options_raw = payload
            elif etype == "SQ":
                if not primary:
                    raise ValueError("Question element (SQ) missing PrimaryAttribute.")
                self._questions_raw[primary] = el
            else:
                self._misc_elements.append(el)

        if self._flow_raw is None:
            raise ValueError("No flow (FL) element found in QSF.")

    # -------------------------- Questions ---------------------------------

    def _parse_questions(self) -> Dict[str, Question]:
        """
        Normalize all SQ elements into Question objects.
        """
        out: Dict[str, Question] = {}

        for qid, el in self._questions_raw.items():
            payload = el.get("Payload", {})
            q = self._normalize_question(qid, payload)
            out[q.id] = q

        return out

    def _normalize_question(self, qid: str, payload: Dict[str, Any]) -> Question:
        qtype = payload.get("QuestionType")
        selector = payload.get("Selector")
        subselector = payload.get("SubSelector")

        logical_type = self._classify_question_type(qtype, selector, subselector)

        raw_text = payload.get("QuestionText", "") or ""
        text = strip_html(raw_text)
        # Note: Piping conversion will be applied later with improved mapping

        export_tag = payload.get("DataExportTag")

        # Choices (for MC, Matrix, etc.)
        choices_norm: List[Choice] = []
        scale_norm: List[Choice] = []

        # MC choices or matrix column/row choices
        if payload.get("Choices"):
            choices_norm = self._normalize_choice_dict(
                payload.get("Choices") or {},
                payload.get("ChoiceOrder"),
                payload.get("RecodeValues") or {},
                payload.get("ChoiceDataExportTags") or {},
            )

        # Matrix "Answers" / "AnswerOrder" (one axis of the matrix)
        if payload.get("Answers"):
            answers_norm = self._normalize_choice_dict(
                payload.get("Answers") or {},
                payload.get("AnswerOrder"),
                {},  # rarely recoded at this level
                {},  # rarely export tags at this level
            )
            # Decide convention: treat Answers as "scale" and Choices as "choices"
            # or vice versa. Here, we put Answers into scale.
            scale_norm = answers_norm

        validation_norm = self._normalize_validation(payload.get("Validation") or {})
        randomization = payload.get("Randomization") or {}

        metadata = {
            "qsf_question_type": qtype,
            "qsf_selector": selector,
            "qsf_subselector": subselector,
            "qsf_configuration": payload.get("Configuration"),
            "qsf_language": payload.get("Language"),
        }

        return Question(
            id=payload.get("QuestionID", qid),
            export_tag=export_tag,
            text=text,
            raw_text=raw_text,
            type=logical_type,
            metadata=metadata,
            choices=choices_norm,
            scale=scale_norm,
            validation=validation_norm,
            randomization=randomization,
        )

    @staticmethod
    def _classify_question_type(
        qtype: Optional[str], selector: Optional[str], subselector: Optional[str]
    ) -> str:
        """
        Map Qualtrics QuestionType/Selector/SubSelector into a small
        set of logical types.
        """
        if qtype == "TE":
            return "text"
        if qtype == "DB":
            return "descriptive"
        if qtype == "MC":
            # Single-answer variants
            if selector in {"SAVR", "SAHR", "SACOL", "DL", "SB"}:
                return "single_choice"
            # Multi-answer variants
            if selector in {"MAVR", "MAHR", "MACOL", "MSB"}:
                return "multi_choice"
            return "choice"
        if qtype == "Matrix":
            if subselector in {"SingleAnswer", "DL"}:
                return "matrix_single"
            if subselector == "MultipleAnswer":
                return "matrix_multi"
            return "matrix"
        if qtype == "SBS":
            return "side_by_side"
        if qtype == "Slider":
            return "slider"
        if qtype == "DD":
            return "dropdown"
        return "unknown"

    @staticmethod
    def _normalize_choice_dict(
        choices: Dict[str, Any],
        order: Optional[List[Any]],
        recode_values: Dict[str, Any],
        export_tags: Dict[str, Any],
    ) -> List[Choice]:
        """
        Normalize Qualtrics Choices/Answers to a list of Choice objects.
        """
        result: List[Choice] = []

        if order is None:
            # fall back to key order
            ordered_ids = list(choices.keys())
        else:
            # Qualtrics keys sometimes are ints; ensure we use string keys
            ordered_ids = [str(cid) for cid in order]

        for pos, cid in enumerate(ordered_ids):
            c_obj = choices.get(str(cid), {})
            text = c_obj.get("Display", "")
            # Note: Piping conversion will be applied later with improved mapping
            recode = recode_values.get(str(cid))
            export_tag = export_tags.get(str(cid))

            result.append(
                Choice(
                    id=str(cid),
                    text=text,
                    order=pos,
                    recode=None if recode is None else str(recode),
                    export_tag=export_tag,
                )
            )

        return result

    @staticmethod
    def _normalize_validation(raw_validation: Dict[str, Any]) -> Optional[Validation]:
        settings = raw_validation.get("Settings")
        if not settings:
            return None

        force_flag = settings.get("ForceResponse") == "ON"
        return Validation(
            force_response=force_flag,
            force_type=settings.get("ForceResponseType"),
            type=settings.get("Type"),
            raw=settings,
        )

    # -------------------------- Blocks ------------------------------------

    def _parse_blocks(self) -> List[Block]:
        """
        Normalize BL payload into a list of Block objects.
        """
        if self._blocks_raw is None:
            # Some QSFs might technically be valid but lack blocks;
            # decide whether to fail hard or return empty list.
            return []

        # blocks_raw may be a list of blocks or a dict keyed by ID
        if isinstance(self._blocks_raw, dict):
            blocks_iterable = self._blocks_raw.values()
        else:
            blocks_iterable = self._blocks_raw

        result: List[Block] = []

        for b_payload in blocks_iterable:
            bid = b_payload.get("ID")
            if not bid:
                # skip malformed
                continue

            name = b_payload.get("Description") or ""
            btype = (b_payload.get("Type") or "Standard").lower()
            elements = self._normalize_block_elements(
                b_payload.get("BlockElements") or []
            )

            result.append(
                Block(
                    id=bid,
                    name=name,
                    type=btype,
                    elements=elements,
                    raw=b_payload,
                )
            )

        return result

    @staticmethod
    def _normalize_block_elements(
        block_elements: List[Dict[str, Any]]
    ) -> List[BlockElement]:
        result: List[BlockElement] = []

        for be in block_elements:
            etype = be.get("Type")

            if etype == "Question":
                result.append(
                    BlockElement(
                        kind="question", question_id=be.get("QuestionID"), raw=be
                    )
                )
            elif etype == "Page Break":
                result.append(BlockElement(kind="page_break", question_id=None, raw=be))
            elif etype == "DescriptiveText":
                result.append(
                    BlockElement(kind="descriptive", question_id=None, raw=be)
                )
            else:
                result.append(
                    BlockElement(kind="other", question_id=be.get("QuestionID"), raw=be)
                )

        return result

    # -------------------------- Options -----------------------------------

    def _parse_options(self) -> SurveyOptions:
        """
        Normalize SO payload into SurveyOptions.
        """
        if self._options_raw is None:
            return SurveyOptions()

        so = self._options_raw

        back_button = so.get("BackButton") == "true"
        save_and_continue = so.get("SaveAndContinue") == "true"

        return SurveyOptions(
            back_button=back_button,
            save_and_continue=save_and_continue,
            protection=so.get("SurveyProtection"),
            expiration=so.get("SurveyExpiration"),
            termination_behavior=so.get("SurveyTermination"),
            progress_bar=so.get("ProgressBarDisplay"),
            partial_data_policy=so.get("PartialData"),
            skin=so.get("Skin"),
            raw=so,
        )

    # --------------------------- Flow -------------------------------------

    def _parse_flow(self) -> FlowNode:
        """
        Normalize FL payload into a FlowNode tree.
        """
        if self._flow_raw is None:
            raise ValueError("No flow (FL) element found in QSF.")

        return self._normalize_flow_node(self._flow_raw)

    def _normalize_flow_node(self, node_raw: Dict[str, Any]) -> FlowNode:
        node_type = node_raw.get("Type")
        flow_id = node_raw.get("FlowID")

        # Root node: contains a Flow list
        if node_type == "Root":
            children = [
                self._normalize_flow_node(ch) for ch in node_raw.get("Flow", [])
            ]
            return FlowNode(
                id=flow_id,
                type="root",
                children=children,
                raw=node_raw,
            )

        # Simple block reference
        if node_type == "Block":
            return FlowNode(
                id=flow_id,
                type="block",
                block_id=node_raw.get("ID"),
                raw=node_raw,
            )

        # Embedded data node
        if node_type == "EmbeddedData":
            embedded_fields: List[EmbeddedField] = []
            for f in node_raw.get("EmbeddedData", []):
                embedded_fields.append(
                    EmbeddedField(
                        name=f.get("Field"),
                        source=(f.get("Type") or "Custom").lower(),
                        value=f.get("Value"),
                        analyze_text=f.get("AnalyzeText"),
                        raw=f,
                    )
                )
            return FlowNode(
                id=flow_id,
                type="embedded_data",
                embedded_fields=embedded_fields,
                raw=node_raw,
            )

        # Branch logic node
        if node_type == "Branch":
            children = [
                self._normalize_flow_node(ch) for ch in node_raw.get("Flow", [])
            ]
            return FlowNode(
                id=flow_id,
                type="branch",
                branch_logic=node_raw.get("BranchLogic"),
                children=children,
                raw=node_raw,
            )

        # Randomizer node
        if node_type == "Randomizer":
            children = [
                self._normalize_flow_node(ch) for ch in node_raw.get("Flow", [])
            ]
            rand = FlowRandomizer(
                present=node_raw.get("Count"),
                evenly=node_raw.get("EvenPresentation", False),
            )
            return FlowNode(
                id=flow_id,
                type="randomizer",
                randomizer=rand,
                children=children,
                raw=node_raw,
            )

        # End of survey node
        if node_type == "EndSurvey":
            return FlowNode(
                id=flow_id,
                type="end_survey",
                raw=node_raw,
            )

        # Group, Authenticator, Loop & Merge, etc.
        children = [self._normalize_flow_node(ch) for ch in node_raw.get("Flow", [])]
        return FlowNode(
            id=flow_id,
            type=(node_type or "unknown").lower(),
            block_id=node_raw.get("ID"),
            children=children,
            raw=node_raw,
        )

    # ---------------------- Embedded data collection -----------------------

    def _collect_embedded_fields(self, root: FlowNode) -> List[EmbeddedField]:
        """
        Traverse the flow tree and collect a deduplicated list of EmbeddedField
        definitions by 'name'.
        """
        collected: Dict[str, EmbeddedField] = {}

        def visit(node: FlowNode) -> None:
            for ef in node.embedded_fields:
                if ef.name and ef.name not in collected:
                    collected[ef.name] = ef
            for child in node.children:
                visit(child)

        visit(root)
        return list(collected.values())


# ---------------------------------------------------------------------------
# CLI helper (optional)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser(
        description="Normalize a Qualtrics QSF file into a standard survey JSON."
    )
    parser.add_argument("qsf_path", help="Path to input QSF file")
    parser.add_argument(
        "-o", "--output", help="Path to output JSON file (default: stdout)"
    )
    args = parser.parse_args()

    qsf_parser = QSFParser.from_file(args.qsf_path)
    survey = qsf_parser.parse()
    result = json.dumps(survey.to_dict(), indent=2, ensure_ascii=False)

    if args.output:
        Path(args.output).write_text(result, encoding="utf-8")
    else:
        sys.stdout.write(result + "\n")
