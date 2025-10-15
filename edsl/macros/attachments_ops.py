from __future__ import annotations
from typing import Callable, Any

from .head_attachments import HeadAttachments


class AttachmentOps:
    """Registry of named, serializable attachment operations.

    Each op has signature: (attachments: HeadAttachments, params: dict, **kwargs) -> HeadAttachments
    Ops MUST be pure with respect to inputs (may mutate a copy or mutate and return same instance consistently).
    """

    _ops: dict[str, Callable[..., HeadAttachments]] = {}

    @classmethod
    def register(cls, name: str, fn: Callable[..., HeadAttachments]) -> None:
        cls._ops[name] = fn

    @classmethod
    def get(cls, name: str) -> Callable[..., HeadAttachments]:
        if name not in cls._ops:
            raise ValueError(f"Attachment op '{name}' is not registered")
        return cls._ops[name]

    @classmethod
    def list_ops(cls) -> list[str]:
        return sorted(cls._ops.keys())


# ---- Built-in ops ----

def op_clear(attachments: HeadAttachments, params: dict, *, dest: str) -> HeadAttachments:
    if dest == "scenario":
        attachments.scenario = None
    elif dest == "survey":
        attachments.survey = None
    elif dest == "agent_list":
        attachments.agent_list = None
    else:
        raise ValueError(f"Unknown dest '{dest}'")
    return attachments


def op_move(attachments: HeadAttachments, params: dict, *, src: str, dest: str) -> HeadAttachments:
    value = None
    if src == "scenario":
        value = attachments.scenario
        attachments.scenario = None
    elif src == "survey":
        value = attachments.survey
        attachments.survey = None
    elif src == "agent_list":
        value = attachments.agent_list
        attachments.agent_list = None
    else:
        raise ValueError(f"Unknown src '{src}'")

    if dest == "scenario":
        attachments.scenario = value
    elif dest == "survey":
        attachments.survey = value
    elif dest == "agent_list":
        attachments.agent_list = value
    else:
        raise ValueError(f"Unknown dest '{dest}'")
    return attachments


def op_set_from_param(attachments: HeadAttachments, params: dict, *, dest: str, param: str) -> HeadAttachments:
    if param not in params:
        raise ValueError(f"Param '{param}' not found for set_from_param")
    value = params[param]
    if dest == "scenario":
        attachments.scenario = value
    elif dest == "survey":
        attachments.survey = value
    elif dest == "agent_list":
        attachments.agent_list = value
    else:
        raise ValueError(f"Unknown dest '{dest}'")
    return attachments


def op_filestore_to_scenario_list(attachments: HeadAttachments, params: dict, *, path_param: str) -> HeadAttachments:
    from ..scenarios import FileStore

    if path_param not in params:
        raise ValueError(f"Param '{path_param}' not found for filestore_to_scenario_list")
    fs = FileStore(path=params[path_param])
    attachments.scenario = fs.to_scenario_list()
    return attachments


def op_question_to_survey(attachments: HeadAttachments, params: dict, *, param: str) -> HeadAttachments:
    if param not in params:
        raise ValueError(f"Param '{param}' not found for question_to_survey")
    q = params[param]
    attachments.survey = q.to_survey()
    return attachments


# Register built-ins
AttachmentOps.register("clear", op_clear)
AttachmentOps.register("move", op_move)
AttachmentOps.register("set_from_param", op_set_from_param)
AttachmentOps.register("filestore_to_scenario_list", op_filestore_to_scenario_list)
AttachmentOps.register("question_to_survey", op_question_to_survey)


