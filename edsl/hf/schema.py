"""Infer a whole-column schema and reversibly encode Python values."""

from __future__ import annotations

import base64
import json
import logging

from .exceptions import HFSchemaError

logger = logging.getLogger(__name__)
_TAG = "__edsl_hf_value__"


def is_file(value):
    from edsl.scenarios.file_store import FileStore

    return isinstance(value, FileStore)


def restore_file(fields):
    """Restore data without opening paths, following URLs, or extracting text.

    FileStore.__init__ performs I/O even when serialized bytes are supplied (for
    URL paths and absent extracted_text). A stored attachment is already fully
    initialized; restore its data and runtime path state directly instead.
    """
    from edsl.scenarios.file_store import FileStore
    from edsl.scenarios.scenario import Scenario

    result = FileStore.__new__(FileStore)
    Scenario.__init__(result, dict(fields))
    # The serialized path is provenance only: a local file at that path may
    # have changed since export. Materialize embedded bytes when path is used.
    result._path = None
    result._temp_path = None
    for key in (
        "base64_string",
        "mime_type",
        "suffix",
        "binary",
        "external_locations",
        "extracted_text",
    ):
        setattr(result, key, fields.get(key))
    return result


def pack(value, coerce="error"):
    """JSON-safe data, with explicit tags only where JSON is insufficient.

    Escape tag-shaped user dictionaries too; never infer an EDSL object from
    untagged user data or deserialize executable Python objects.
    """
    if is_file(value):
        return {_TAG: "filestore", "value": pack(dict(value), coerce)}
    if type(value) is dict:
        if _TAG in value or any(type(k) is not str for k in value):
            return {
                _TAG: "dict",
                "value": [[pack(k, coerce), pack(v, coerce)] for k, v in value.items()],
            }
        return {k: pack(v, coerce) for k, v in value.items()}
    if type(value) is list:
        return [pack(v, coerce) for v in value]
    if value is None or type(value) in (str, int, float, bool):
        return value
    if coerce != "error":
        return str(value)
    raise HFSchemaError(f"Unsupported Python type {type(value).__name__}")


def unpack(value):
    if isinstance(value, list):
        return [unpack(v) for v in value]
    if isinstance(value, dict):
        if value.get(_TAG) == "filestore":
            return restore_file(unpack(value["value"]))
        if value.get(_TAG) == "dict":
            return {unpack(k): unpack(v) for k, v in value["value"]}
        return {k: unpack(v) for k, v in value.items()}
    return value


def dumps(value, coerce="error"):
    return json.dumps(pack(value, coerce), ensure_ascii=False)


def loads(value):
    return unpack(json.loads(value))


def file_bytes(value, column, row, limit):
    encoded = value.get("base64_string")
    if not isinstance(encoded, str) or encoded == "offloaded":
        raise HFSchemaError(
            f"Column {column!r}, row {row}: FileStore must contain local base64 bytes; "
            "external_locations are not downloaded."
        )
    # Avoid allocating a potentially huge decoded buffer just to reject it.
    if len(encoded) // 4 * 3 - encoded[-2:].count("=") > limit:
        raise HFSchemaError(
            f"Column {column!r}, row {row}: FileStore exceeds max_file_bytes={limit}"
        )
    try:
        raw = base64.b64decode(encoded, validate=True)
    except ValueError as exc:
        raise HFSchemaError(
            f"Column {column!r}, row {row}: invalid FileStore base64"
        ) from exc
    if len(raw) > limit:
        raise HFSchemaError(
            f"Column {column!r}, row {row}: FileStore exceeds max_file_bytes={limit}"
        )
    return raw


def check_nested_files(value, column, row, limit):
    if is_file(value):
        file_bytes(value, column, row, limit)
        return True
    values = value.values() if isinstance(value, dict) else value
    if isinstance(value, (dict, list)):
        found = [check_nested_files(v, column, row, limit) for v in values]
        return any(found)
    return False


def infer_column(column, values, coerce, hf):
    """Return (HF feature, EDSL type, encoding), considering all non-null rows."""
    present = [(i, v) for i, v in enumerate(values) if v is not None]
    types = {type(v) for _, v in present}
    if present and all(is_file(v) for _, v in present):
        kinds = {str(v.get("mime_type", "")).split("/")[0] for _, v in present}
        if kinds == {"image"}:
            return hf.Image(), "filestore", "Image"
        if kinds == {"audio"}:
            return hf.Audio(decode=False), "filestore", "Audio"
        return (
            {"bytes": hf.Value("binary"), "path": hf.Value("string")},
            "filestore",
            "struct",
        )
    if not types:
        return hf.Value("null"), "null", None
    if types == {bool}:
        return hf.Value("bool"), "bool", None
    if types == {int} and all(-(2**63) <= v < 2**63 for _, v in present):
        return hf.Value("int64"), "int", None
    if types <= {int, float} and float in types:
        # Original integer values accompany floats, avoiding precision loss for
        # integers beyond float64's exact range and preserving numeric types.
        try:
            for _, value in present:
                float(value)
        except OverflowError:
            pass
        else:
            return hf.Value("float64"), "float", "numeric"
    if types == {str}:
        return hf.Value("string"), "str", None
    if types == {list}:
        elements = [v for _, row in present for v in row if v is not None]
        scalar_types = {type(v) for v in elements}
        if not scalar_types:
            return hf.Sequence(hf.Value("null")), "list", None
        if len(scalar_types) == 1 and scalar_types <= {str, int, float, bool}:
            dtype = {str: "string", int: "int64", float: "float64", bool: "bool"}[
                type(elements[0])
            ]
            if scalar_types != {int} or all(-(2**63) <= v < 2**63 for v in elements):
                return hf.Sequence(hf.Value(dtype)), "list", None
        return hf.Value("string"), "json", "json"
    if types == {dict}:
        return hf.Value("string"), "json", "json"
    if coerce != "error":
        return hf.Value("string"), "json" if coerce == "json" else "str", coerce
    first_i, first = present[0]
    second_i, second = next(
        ((i, v) for i, v in present if type(v) is not type(first)), present[-1]
    )
    raise HFSchemaError(
        f"Column {column!r} has incompatible values: row {first_i} ({type(first).__name__}) "
        f"{repr(first)[:100]} and row {second_i} ({type(second).__name__}) {repr(second)[:100]}. "
        "Use coerce='string' or coerce='json' to export this column."
    )


def encode_columns(records, kind, coerce, max_file_bytes, hf):
    """Flatten fields into rows; return rows, features and per-column metadata."""
    keys = list(dict.fromkeys(k for row in records for k in row))
    for key in keys:
        if not isinstance(key, str) or key.startswith("_edsl_"):
            raise HFSchemaError(
                f"Invalid field {key!r}: names must be strings and cannot start with '_edsl_'"
            )
    rows = [{} for _ in records]
    originals = [{} for _ in records]
    features, columns = {}, {}
    for key in keys:
        values = [r.get(key) for r in records]
        feature, edsl_type, encoding = infer_column(key, values, coerce, hf)
        features[key] = feature
        spec = {"kind": kind, "edsl_type": edsl_type, "original_key": key}
        columns[key] = spec
        if any(v is None for v in values):
            spec["nullable"] = True
        if encoding:
            spec["encoding"] = encoding
        if encoding in ("string", "json", "numeric"):
            spec["original_types"] = sorted(
                {type(v).__name__ for v in values if v is not None}
            )
        if edsl_type == "filestore":
            meta_key = key + "__meta"
            if meta_key in keys:
                raise HFSchemaError(
                    f"File column {key!r} needs companion column {meta_key!r}, which already exists"
                )
            spec.update(hf_feature=encoding, meta_column=meta_key)
            features[meta_key] = {
                "mime_type": hf.Value("string"),
                "suffix": hf.Value("string"),
                "binary": hf.Value("bool"),
                "path": hf.Value("string"),
                "extracted_text": hf.Value("string"),
                "external_locations": hf.Value("string"),
            }
        nested = False
        for i, value in enumerate(values):
            rows[i][key] = value
            if edsl_type == "filestore":
                rows[i][meta_key] = None
            if value is None:
                continue
            if edsl_type == "filestore":
                rows[i][key] = {
                    "bytes": file_bytes(value, key, i, max_file_bytes),
                    "path": value.get("path"),
                }
                rows[i][meta_key] = {k: value.get(k) for k in features[meta_key]}
                rows[i][meta_key]["external_locations"] = dumps(
                    value.get("external_locations")
                )
            elif encoding in ("json", "string"):
                nested = check_nested_files(value, key, i, max_file_bytes) or nested
                try:
                    encoded = dumps(value, coerce)
                except HFSchemaError as exc:
                    raise HFSchemaError(f"Column {key!r}, row {i}: {exc}") from exc
                if encoding == "json":
                    rows[i][key] = encoded
                else:
                    rows[i][key] = str(value)
                    # Preserve values whose str() is not reversibly parseable,
                    # including containers and literal strings like 'True'.
                    originals[i][key] = json.loads(encoded)
            elif encoding == "numeric":
                rows[i][key] = float(value)
                if type(value) is int:
                    originals[i][key] = value
        if nested:
            logger.warning(
                "Column %r contains nested FileStore attachments; base64 remains inline in JSON and may be large",
                key,
            )
    if any(originals):
        features["_edsl_originals"] = hf.Value("string")
        for row, original in zip(rows, originals):
            row["_edsl_originals"] = json.dumps(original, ensure_ascii=False)
    nulls = [[k for k, v in r.items() if v is None] for r in records]
    if any(nulls):
        features["_edsl_explicit_nulls"] = hf.Sequence(hf.Value("string"))
        for row, explicit in zip(rows, nulls):
            row["_edsl_explicit_nulls"] = explicit
    return rows, features, columns


def decode_fields(row, columns):
    explicit = row.get("_edsl_explicit_nulls") or []
    originals = json.loads(row.get("_edsl_originals") or "{}")
    fields = {}
    for key, spec in columns.items():
        value = row[key]
        if value is None and key not in explicit:
            continue
        if key in originals:
            value = unpack(originals[key])
        elif value is not None and spec["edsl_type"] == "filestore":
            meta = dict(row[spec.get("meta_column", key + "__meta")])
            meta["external_locations"] = loads(meta["external_locations"])
            meta["base64_string"] = base64.b64encode(value["bytes"]).decode("ascii")
            value = restore_file(meta)
        elif value is not None and (
            spec.get("encoding") == "json" or spec["edsl_type"] == "json"
        ):
            value = loads(value)
        fields[spec.get("original_key", key)] = value
    return fields
