from __future__ import annotations
from typing import Any, Optional


def jsonify(obj: Any) -> Any:
    """Best-effort conversion of arbitrary objects into JSON-serializable structures.

    - Uses `to_dict()` when available (with optional args fallback).
    - Recursively converts mappings, sequences, and sets.
    - Falls back to `repr(obj)` for unknown objects.
    """
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj

    try:
        to_dict = getattr(obj, "to_dict", None)
        if callable(to_dict):
            try:
                return to_dict()  # type: ignore[misc]
            except TypeError:
                try:
                    return to_dict(add_edsl_version=True)  # type: ignore[misc]
                except Exception:
                    pass
    except Exception:
        pass

    if isinstance(obj, dict):
        return {jsonify(k): jsonify(v) for k, v in obj.items()}

    if isinstance(obj, (set, tuple, list)):
        return [jsonify(v) for v in obj]

    return repr(obj)


def serialize_for_api(result: Any) -> Any:
    """Convert formatter output into a client-friendly JSON-serializable value.

    - If object has to_dict(), return that dict (FileStore dicts pass through).
    - Lists/tuples/sets -> list of serialized items.
    - Dicts -> recursively serialized; FileStore-like dicts preserved.
    - Unknown objects -> str(result).
    """
    try:
        if hasattr(result, 'to_dict') and callable(getattr(result, 'to_dict')):
            try:
                result_dict = result.to_dict()
            except TypeError:
                try:
                    result_dict = result.to_dict(add_edsl_version=True)
                except Exception:
                    result_dict = None
            if isinstance(result_dict, dict):
                if 'base64_string' in result_dict:
                    return result_dict
                return jsonify(result_dict)
    except Exception:
        pass

    if isinstance(result, dict):
        if 'base64_string' in result:
            return result
        return {jsonify(k): serialize_for_api(v) for k, v in result.items()}

    if isinstance(result, (list, tuple, set)):
        return [serialize_for_api(v) for v in result]

    if result is None or isinstance(result, (str, int, float, bool)):
        return result

    return str(result)


def build_api_payload(result: Any, formatter_name: Optional[str], app_instance: Any, params: Optional[dict]) -> dict:
    """Wrap formatted output with metadata and reconstruction hints.

    Payload keys:
    - meta: content_type, formatter, formatter_output_type, optional edsl_class_name, reconstruct
    - data: JSON-serializable payload (EDSL objects via to_dict, FileStore dicts preserved)
    - preview: optional inline string for text-like FileStore
    """
    meta: dict[str, Any] = {}
    preview: Optional[str] = None

    # Formatter metadata
    try:
        formatter_obj = app_instance._select_formatter(formatter_name)
        meta["formatter"] = getattr(formatter_obj, "description", None) or getattr(formatter_obj, "name", None)
        meta["formatter_output_type"] = getattr(formatter_obj, "output_type", "auto")
    except Exception:
        meta["formatter"] = None
        meta["formatter_output_type"] = "auto"

    # EDSL objects
    try:
        if hasattr(result, 'to_dict') and callable(getattr(result, 'to_dict')):
            try:
                obj_dict = result.to_dict()
            except TypeError:
                try:
                    obj_dict = result.to_dict(add_edsl_version=True)
                except Exception:
                    obj_dict = None
            if isinstance(obj_dict, dict):
                edsl_class = obj_dict.get('edsl_class_name') or getattr(result.__class__, '__name__', None)
                meta.update({
                    "content_type": "edsl_object",
                    "edsl_class_name": edsl_class,
                    "reconstruct": {"class": edsl_class, "method": "from_dict"}
                })
                if 'base64_string' in obj_dict:
                    meta["content_type"] = "file"
                    meta["reconstruct"] = {"class": "FileStore", "method": "from_dict"}
                    suffix = obj_dict.get('suffix', '')
                    if not suffix and 'path' in obj_dict:
                        try:
                            from pathlib import Path as _P
                            suffix = _P(obj_dict['path']).suffix
                        except Exception:
                            suffix = ''
                    meta["suffix"] = suffix
                    meta["mime_type"] = obj_dict.get('mime_type')
                    text_suffixes = {'.md', '.markdown', '.txt', '.csv', '.json'}
                    if isinstance(suffix, str) and suffix.lower() in text_suffixes:
                        try:
                            import base64 as _b64
                            preview = _b64.b64decode(obj_dict['base64_string']).decode('utf-8')
                        except Exception:
                            preview = None
                return {"meta": meta, "data": obj_dict, **({"preview": preview} if preview is not None else {})}
    except Exception:
        pass

    # FileStore-like dict
    if isinstance(result, dict) and 'base64_string' in result:
        meta.update({
            "content_type": "file",
            "edsl_class_name": "FileStore",
            "reconstruct": {"class": "FileStore", "method": "from_dict"},
            "suffix": result.get('suffix'),
            "mime_type": result.get('mime_type')
        })
        try:
            suffix = (result.get('suffix') or '').lower()
            text_suffixes = {'.md', '.markdown', '.txt', '.csv', '.json'}
            if suffix in text_suffixes:
                import base64 as _b64
                preview = _b64.b64decode(result['base64_string']).decode('utf-8')
        except Exception:
            preview = None
        return {"meta": meta, "data": result, **({"preview": preview} if preview is not None else {})}

    # Simple types
    if isinstance(result, list) and all(isinstance(x, str) for x in result):
        meta.update({"content_type": "list[string]"})
        return {"meta": meta, "data": result}

    if isinstance(result, str):
        meta.update({"content_type": "string"})
        return {"meta": meta, "data": result}

    # Generic JSON-like
    if isinstance(result, (list, tuple, set, dict)):
        meta.update({"content_type": "json"})
        return {"meta": meta, "data": jsonify(result)}

    meta.update({"content_type": "string"})
    return {"meta": meta, "data": str(result)}


def _resolve_edsl_class(class_name: Optional[str]):
    """Return an EDSL class object by name, or None if unknown."""
    if not class_name or not isinstance(class_name, str):
        return None
    name = class_name.strip()
    lowered = name.lower()
    try:
        # Import locally to avoid heavy imports and cycles
        from edsl.scenarios import Scenario, ScenarioList, FileStore  # type: ignore
        from edsl.surveys import Survey  # type: ignore
        from edsl.dataset import Dataset  # type: ignore
        from edsl.results import Results  # type: ignore
        from edsl.agents import AgentList, Agent  # type: ignore
    except Exception:
        Scenario = ScenarioList = FileStore = Survey = Dataset = Results = AgentList = Agent = None  # type: ignore

    mapping = {
        'scenario': Scenario,
        'scenariolist': ScenarioList,
        'scenario_list': ScenarioList,
        'filestore': FileStore,
        'file_store': FileStore,
        'survey': Survey,
        'dataset': Dataset,
        'results': Results,
        'agentlist': AgentList,
        'agent_list': AgentList,
        'agent': Agent,
    }

    # Direct match first
    if name in {k.capitalize() for k in mapping.keys()}:
        # Not reliable; fall back to lowered mapping
        pass
    return mapping.get(lowered)


def reconstitute_from_api_payload(payload: Any) -> Any:
    """Rebuild original formatted output from an API payload envelope.

    If the payload doesn't look like an API envelope, it's returned unchanged.
    """
    if not isinstance(payload, dict) or 'meta' not in payload or 'data' not in payload:
        return payload

    meta = payload.get('meta') or {}
    data = payload.get('data')

    # If reconstruction hints are provided, prefer them
    reconstruct = meta.get('reconstruct') or {}
    class_name = reconstruct.get('class') if isinstance(reconstruct, dict) else None
    method_name = reconstruct.get('method') if isinstance(reconstruct, dict) else None

    # Attempt class-based reconstruction
    cls = _resolve_edsl_class(class_name)
    if cls is not None and isinstance(method_name, str) and hasattr(cls, method_name):
        try:
            method = getattr(cls, method_name)
            if callable(method):
                return method(data)
        except Exception:
            # Fall through to type-based handling
            pass

    # Heuristics based on content_type
    content_type = meta.get('content_type')
    if content_type == 'string':
        return data
    if content_type == 'list[string]':
        return list(data) if isinstance(data, (list, tuple)) else data
    if content_type == 'file':
        # Try FileStore.from_dict
        cls = _resolve_edsl_class('FileStore')
        try:
            if cls is not None and hasattr(cls, 'from_dict'):
                return cls.from_dict(data)
        except Exception:
            return data
        return data
    if content_type == 'edsl_object':
        # Try to use embedded edsl_class_name from data if not in meta
        if not cls and isinstance(data, dict):
            embedded_name = data.get('edsl_class_name')
            cls = _resolve_edsl_class(embedded_name)
            try:
                if cls is not None and hasattr(cls, 'from_dict'):
                    return cls.from_dict(data)
            except Exception:
                return data
        return data

    # JSON and other generic types
    return data


