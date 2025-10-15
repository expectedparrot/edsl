"""Parser for Qualtrics CSV exports with three or four header rows."""
import json
import re
import sqlite3
from pathlib import Path
from typing import Optional, Tuple, List, Dict
from collections import OrderedDict

import pandas as pd


def _parse_import_id(cell: str) -> Optional[str]:
    """Parse a cell like '{"ImportId":"QID90_1"}' -> 'QID90_1'."""
    if not isinstance(cell, str):
        return None
    s = cell.strip()
    if not (s.startswith("{") and "ImportId" in s):
        return None
    try:
        obj = json.loads(s)
        return obj.get("ImportId")
    except Exception:
        return None


def _canonicalize_label(label: str) -> str:
    """
    Normalize the short header label into a stable 'question_name'.
    Examples:
      'C14 - B+ feat app_1'     -> 'C14 - B+ feat app'
      'C27 - Hesitations_12_TEXT' -> 'C27 - Hesitations'
      'C36 - industry_19_TEXT'  -> 'C36 - industry'
    """
    if not isinstance(label, str):
        return str(label)
    # Keep everything before the LAST underscore as base (if any)
    if "_" in label:
        base, _ = label.rsplit("_", 1)
        return base.strip()
    return label.strip()


def _subpart_from_label(label: str) -> Optional[str]:
    """
    Extract a subpart suffix (e.g., '1', '12_TEXT', 'TEXT', 'freq') from the label when present.
    """
    if not isinstance(label, str):
        return None
    # Common '..._NN[_TEXT]' or '..._TEXT'
    if "_" in label:
        _, tail = label.rsplit("_", 1)
        return tail.strip()

    # Fallback: allow -freq style
    if label.endswith("-freq"):
        return "freq"
    return None


def _strip_html(s: str) -> str:
    """Remove simple HTML tags if present; leaves text as-is if parsing not needed."""
    if not isinstance(s, str):
        return s
    return re.sub(r"<[^>]*>", "", s).strip()


def _to_python_identifier(s: str) -> str:
    """
    Convert a string to a valid Python identifier.
    - Lowercase
    - Replace spaces and hyphens with underscores
    - Remove invalid characters
    - Ensure doesn't start with a digit
    """
    if not isinstance(s, str):
        s = str(s)

    # Convert to lowercase
    s = s.lower()

    # Replace spaces and hyphens with underscores
    s = re.sub(r'[\s\-]+', '_', s)

    # Remove invalid characters (keep only alphanumeric and underscore)
    s = re.sub(r'[^a-z0-9_]', '', s)

    # Ensure doesn't start with a digit
    if s and s[0].isdigit():
        s = '_' + s

    # Remove multiple consecutive underscores
    s = re.sub(r'_+', '_', s)

    # Strip leading/trailing underscores
    s = s.strip('_')

    return s or 'unnamed'


DEFAULT_ID_CANDIDATES: List[str] = [
    "PERSON_ID", "ResponseId", "ResponseID", "RecipientEmail",
    "ExternalReference", "IPAddress"
]


def tidy_qualtrics_three_header_csv(
    csv_path: str,
    out_sqlite: Optional[str] = None,
    respondent_id_col: Optional[str] = None,
    keep_empty: bool = False,
    add_question_text: bool = True,
    strip_html_values: bool = False,
    header_rows: int = 3,
    delimiter: str = ",",
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Tidy a Qualtrics CSV with multiple header rows.

    Parameters
    ----------
    csv_path : str
        Path to the Qualtrics CSV file
    out_sqlite : Optional[str]
        Path to SQLite database to write results to
    respondent_id_col : Optional[str]
        Column name to use as respondent ID
    keep_empty : bool
        Whether to keep empty values
    add_question_text : bool
        Whether to add question_text column to the output
    strip_html_values : bool
        Whether to strip HTML tags from values
    header_rows : int
        Number of header rows (3 or 4)
        - If 3: row 0 = short labels, row 1 = question text, row 2 = ImportId
        - If 4: row 0 = generic columns, row 1 = short labels, row 2 = question text, row 3 = ImportId

    Returns
    -------
    responses_long : DataFrame
        Columns: respondent_id, question_name, import_id, subpart, value
        (+ question_text if add_question_text=True)
    columns_meta : DataFrame
        Columns: original_col, question_name, import_id, subpart, question_text
    """
    csv_path = Path(csv_path)
    df_raw = pd.read_csv(
        csv_path,
        header=None,
        dtype=str,
        keep_default_na=False,
        sep=delimiter,
    )

    min_rows = header_rows + 1
    if df_raw.shape[0] < min_rows:
        raise ValueError(f"Expected at least {min_rows} rows: {header_rows} header rows + ≥1 data row.")

    if header_rows == 3:
        short_labels = df_raw.iloc[0].tolist()
        question_texts = df_raw.iloc[1].tolist()
        import_row = df_raw.iloc[2].tolist()
        data = df_raw.iloc[3:].copy()
    elif header_rows == 4:
        # Skip the first generic column row (Column19, Column20, etc.)
        short_labels = df_raw.iloc[1].tolist()
        question_texts = df_raw.iloc[2].tolist()
        import_row = df_raw.iloc[3].tolist()
        data = df_raw.iloc[4:].copy()
    else:
        raise ValueError(f"header_rows must be 3 or 4, got {header_rows}")

    data.columns = short_labels

    # Build column metadata
    meta_records = []
    for col, qtext, import_cell in zip(short_labels, question_texts, import_row):
        qname = _canonicalize_label(col)
        subpart = _subpart_from_label(col)
        import_id = _parse_import_id(import_cell) or None

        meta_records.append(
            {
                "original_col": col,
                "question_name": qname,
                "import_id": import_id,
                "subpart": subpart,
                "question_text": (qtext or "").strip(),
            }
        )
    columns_meta = pd.DataFrame(meta_records)

    # Choose respondent_id
    rid_col = None
    if respondent_id_col and respondent_id_col in data.columns:
        rid_col = respondent_id_col
    else:
        for cand in DEFAULT_ID_CANDIDATES:
            if cand in data.columns:
                rid_col = cand
                break

    if rid_col:
        data["_respondent_id"] = data[rid_col].astype(str)
    else:
        data["_respondent_id"] = range(1, len(data) + 1)

    # Melt to long, join metadata
    long = (
        data.melt(
            id_vars=["_respondent_id"],
            var_name="original_col",
            value_name="value",
        )
        .merge(columns_meta, on="original_col", how="left")
        .rename(columns={"_respondent_id": "respondent_id"})
    )

    # Cleanup values
    long["value"] = long["value"].astype(str)
    if strip_html_values:
        long["value"] = long["value"].map(_strip_html)
    else:
        long["value"] = long["value"].str.strip()

    if not keep_empty:
        long["value"] = long["value"].replace({"": pd.NA})
        long = long.dropna(subset=["value"])

    if not add_question_text:
        long = long.drop(columns=["question_text"])

    # Write to SQLite if requested
    if out_sqlite:
        con = sqlite3.connect(out_sqlite)
        try:
            long.to_sql("responses_long", con, if_exists="replace", index=False)
            columns_meta.to_sql("columns_meta", con, if_exists="replace", index=False)
            with con:
                con.execute("CREATE INDEX IF NOT EXISTS idx_resp ON responses_long(respondent_id)")
                con.execute("CREATE INDEX IF NOT EXISTS idx_q ON responses_long(question_name)")
                con.execute("CREATE INDEX IF NOT EXISTS idx_qid ON responses_long(import_id)")
                con.execute("CREATE INDEX IF NOT EXISTS idx_q_sub ON responses_long(question_name, subpart)")
        finally:
            con.close()

    return long, columns_meta


def generate_question_list(
    long_df: pd.DataFrame,
    columns_meta: pd.DataFrame,
    min_option_frequency: int = 2,
) -> List[dict]:
    """
    Generate a list of dictionaries describing each unique question in the survey.

    Parameters
    ----------
    long_df : DataFrame
        The tidy long-format data from tidy_qualtrics_three_header_csv()
    columns_meta : DataFrame
        The columns metadata from tidy_qualtrics_three_header_csv()
    min_option_frequency : int
        Minimum number of times an option must appear to be included as a fixed option
        (useful for filtering out one-off "Other" text responses). Default is 2.

    Returns
    -------
    List[dict]
        Each dictionary contains:
        - raw_question_name: str (original question name)
        - question_name: str (valid Python identifier)
        - question_text: str (if available)
        - question_type: str (free_text, linear_scale, checkbox, multiple_choice, etc.)
        - question_options: List[str] (unique response values or checkbox options)
        - n_subparts: int (number of subparts/columns for this question)
    """
    questions = []
    meta_by_question: Dict[str, pd.DataFrame] = {
        q: columns_meta[columns_meta["question_name"] == q] for q in columns_meta["question_name"].unique()
    }

    # Group by question_name
    for qname, group in long_df.groupby("question_name", sort=False):
        # Get question text (first non-empty)
        qtext = ""
        if "question_text" in group.columns:
            qtext = group["question_text"].iloc[0] if len(group) > 0 else ""

        # Count unique subparts for this question
        subparts = group["subpart"].dropna().unique()
        n_subparts = len(subparts)

        # Get unique response values (excluding empty/NaN)
        values = group["value"].dropna().unique()
        values = [v for v in values if str(v).strip()]

        # Count responses per respondent
        responses_per_respondent = group.groupby("respondent_id").size()
        max_responses = responses_per_respondent.max() if len(responses_per_respondent) > 0 else 0

        # Infer question type
        qtype, options, option_order_hint = _infer_question_type(
            values,
            n_subparts,
            subparts,
            max_responses,
            group,
            min_option_frequency
        )

        derived_hints = {
            "raw_question_name": qname,
            "source": "qualtrics_three_row",
            "n_subparts": int(n_subparts),
            "allows_multiple": qtype in {"checkbox", "multiple_response"},
            "option_order": option_order_hint,
        }

        question_meta = meta_by_question.get(qname)
        if question_meta is not None:
            import_ids = [imp for imp in question_meta["import_id"].dropna().unique().tolist() if imp]
            if import_ids:
                derived_hints["import_ids"] = import_ids
            subpart_labels = question_meta["subpart"].dropna().tolist()
            if subpart_labels:
                derived_hints["subparts"] = subpart_labels

        questions.append(
            {
                "raw_question_name": qname,
                "question_name": _to_python_identifier(qname),
                "question_text": qtext,
                "question_type": qtype,
                "question_options": options,
                "n_subparts": n_subparts,
                "derived_hints": derived_hints,
            }
        )

    return questions


def _infer_question_type(
    values: list,
    n_subparts: int,
    subparts: list,
    max_responses_per_respondent: int,
    group_df: pd.DataFrame,
    min_option_frequency: int = 2,
) -> Tuple[str, List[str], str]:
    """
    Infer question type from response patterns.

    Parameters
    ----------
    values : list
        Unique values from the response data
    n_subparts : int
        Number of subparts for this question
    subparts : list
        List of subpart identifiers
    max_responses_per_respondent : int
        Maximum responses per respondent
    group_df : DataFrame
        DataFrame for this question group
    min_option_frequency : int
        Minimum number of times an option must appear to be included

    Returns
    -------
    (question_type, options)
    """
    if len(values) == 0:
        return "unknown", [], "unspecified"

    # Check for "select all that apply" or "select up to N" pattern in question text
    qtext = ""
    if "question_text" in group_df.columns and len(group_df) > 0:
        qtext = str(group_df["question_text"].iloc[0]).lower()

    # Check if this is an "Other (please specify)" text field
    is_other_text = "other" in qtext and ("text" in qtext or "specify" in qtext)

    # If this is a free text "Other" field with many unique responses, treat as free_text
    if is_other_text and len(values) > 20:
        return "free_text", [], "no_options"

    select_all_pattern = any(phrase in qtext for phrase in [
        "select all that apply",
        "check all that apply",
        "choose all that apply",
        "mark all that apply",
        "select up to",
        "choose up to",
        "check up to",
        "mark up to"
    ])

    # If "select all that apply" is detected, parse comma-separated values as checkbox options
    if select_all_pattern:
        # Extract individual checkbox options from comma-separated responses
        # and count their frequency
        option_counts: Dict[str, int] = OrderedDict()
        for val in values:
            val_str = str(val).strip()
            if val_str:
                # Split by comma and clean up each option
                options = [opt.strip() for opt in val_str.split(',') if opt.strip()]
                for opt in options:
                    option_counts[opt] = option_counts.get(opt, 0) + 1

        # Filter options by minimum frequency
        filtered_options = [opt for opt, count in option_counts.items()
                          if count >= min_option_frequency]

        if filtered_options:
            # Checkbox questions don't have a separate "_with_other" type in EDSL
            return "checkbox", filtered_options, "select_all_parse"

    # Checkbox detection: multiple subparts with binary-like responses
    if n_subparts > 1:
        # Check if responses are binary (checked/unchecked pattern)
        unique_vals = set(str(v).lower() for v in values)
        is_binary = unique_vals.issubset({'1', '0', 'true', 'false', 'yes', 'no', 'checked', ''})

        if is_binary or len(values) <= 3:
            # Checkbox question - use subpart names as options
            # Get the original column labels for each subpart
            options = []
            for subpart in subparts:
                # Try to extract meaningful label from subpart
                if subpart and str(subpart).strip():
                    # Look up in original columns to get better labels
                    subpart_rows = group_df[group_df["subpart"] == subpart]
                    if len(subpart_rows) > 0:
                        # Get first actual checked value as the option label
                        checked_vals = subpart_rows[subpart_rows["value"].notna()]["value"].unique()
                        if len(checked_vals) > 0 and str(checked_vals[0]).strip():
                            options.append(str(checked_vals[0]))
                        else:
                            options.append(str(subpart))
                    else:
                        options.append(str(subpart))

            if not options:
                options = [str(s) for s in subparts]

            return "checkbox", options, "source_subpart_order"

    # Try to detect linear scale: all numeric values in a range
    try:
        numeric_vals = []
        for v in values:
            try:
                numeric_vals.append(float(str(v)))
            except (ValueError, TypeError):
                pass

        if len(numeric_vals) == len(values) and len(numeric_vals) >= 2:
            # All numeric - check if it looks like a scale
            min_val, max_val = min(numeric_vals), max(numeric_vals)
            unique_nums = sorted(set(numeric_vals))

            # Linear scale if: small range, integers, relatively few unique values
            if (max_val - min_val <= 20 and
                all(v == int(v) for v in numeric_vals) and
                len(unique_nums) <= 11):
                return "linear_scale", [str(int(v)) for v in unique_nums], "numeric_ascending"
    except Exception:
        pass

    # Multiple choice: categorical with moderate number of options
    if len(values) <= 20 and max_responses_per_respondent <= 1:
        # Sort by frequency for better presentation and apply frequency filter
        value_counts = group_df["value"].value_counts()
        filtered_values = [
            val for val, count in value_counts.items() if count >= min_option_frequency
        ]

        if filtered_values:
            qtype = "multiple_choice"
            if is_other_text or "other" in qtext:
                qtype = "multiple_choice_with_other"
            return qtype, filtered_values, "frequency_desc"
        else:
            # If all values filtered out, return without filter
            return "multiple_choice", value_counts.index.tolist(), "frequency_desc"

    # Free text: many unique values or long text
    if len(values) > 20:
        return "free_text", [], "no_options"

    # Check average length - if responses are long, likely free text
    avg_length = sum(len(str(v)) for v in values) / len(values)
    if avg_length > 50:
        return "free_text", [], "no_options"

    # Multiple response (can select multiple categorical options)
    if max_responses_per_respondent > 1:
        value_counts = group_df["value"].value_counts()
        # Filter by minimum frequency
        filtered_values = [val for val, count in value_counts.items()
                          if count >= min_option_frequency]

        if filtered_values:
            return "multiple_response", filtered_values, "frequency_desc"
        else:
            # If all values filtered out, return without filter
            return "multiple_response", value_counts.index.tolist(), "frequency_desc"

    # Default to categorical with all unique values
    # Apply frequency filter for categorical as well
    value_counts = group_df["value"].value_counts()
    filtered_values = [val for val, count in value_counts.items()
                      if count >= min_option_frequency]

    if filtered_values and len(filtered_values) < len(values):
        # If we filtered some out, use the filtered list
        return "categorical", sorted(filtered_values, key=str), "alphabetical"
    else:
        # Otherwise return all unique values
        return "categorical", sorted(values, key=str), "alphabetical"


def generate_respondent_answers(
    long_df: pd.DataFrame,
    questions: List[dict],
) -> List[dict]:
    """
    Generate a list of dictionaries, one per respondent, with their answers.

    Parameters
    ----------
    long_df : DataFrame
        The tidy long-format data from tidy_qualtrics_three_header_csv()
    questions : List[dict]
        The question list from generate_question_list()

    Returns
    -------
    List[dict]
        Each dictionary contains:
        - respondent_id: str (the respondent identifier)
        - answers: dict mapping question_name to answer value(s)
          For checkbox questions, values are lists of selected options
          For questions with subparts, values may be dicts with subpart keys
          For single-response questions, values are the response string
    """
    # Create a mapping from raw question names to their types
    # We'll convert raw names to Python identifiers on the fly
    question_types = {}

    for q in questions:
        raw_qname = q.get('raw_question_name')
        py_qname = q.get('question_name')
        qtype = q.get('question_type', 'unknown')

        # Store type using both keys in case one was popped
        if raw_qname:
            question_types[raw_qname] = qtype
        if py_qname:
            question_types[py_qname] = qtype

    respondents = []

    for respondent_id, resp_group in long_df.groupby("respondent_id"):
        answers = {}

        # Group by question_name (this is the raw/canonical version from the CSV)
        for raw_qname, q_group in resp_group.groupby("question_name"):
            # Convert raw name to Python identifier
            py_qname = _to_python_identifier(raw_qname)
            qtype = question_types.get(raw_qname, question_types.get(py_qname, "unknown"))

            # Handle checkbox questions (comma-separated values or multiple selections)
            if qtype == "checkbox":
                # Parse comma-separated values into a list
                all_selections = []
                for val in q_group["value"].dropna().unique():
                    val_str = str(val).strip()
                    if val_str:
                        # Split by comma and collect all options
                        selections = [opt.strip() for opt in val_str.split(',') if opt.strip()]
                        all_selections.extend(selections)
                # Deduplicate while preserving order
                seen = set()
                unique_selections = []
                for sel in all_selections:
                    if sel not in seen:
                        seen.add(sel)
                        unique_selections.append(sel)
                answers[py_qname] = unique_selections

            # Handle questions with multiple subparts
            elif q_group["subpart"].notna().any() and len(q_group["subpart"].dropna().unique()) > 1:
                # Create a dict with subpart keys
                subpart_dict = {}
                for _, row in q_group.iterrows():
                    if pd.notna(row["subpart"]) and pd.notna(row["value"]):
                        subpart_dict[str(row["subpart"])] = str(row["value"])
                answers[py_qname] = subpart_dict

            # Handle single-value questions
            else:
                # Take the first non-null value
                values = q_group["value"].dropna()
                if len(values) > 0:
                    answers[py_qname] = str(values.iloc[0])

        respondents.append({
            "respondent_id": str(respondent_id),
            "answers": answers
        })

    return respondents
