"""Read and merge dataset cards without replacing user-written prose."""

from __future__ import annotations

import copy
import re
from pathlib import Path

import yaml

from .exceptions import HFClassMismatchError, HFFormatVersionError, HFSchemaError

FORMAT_VERSION = 1


def config_for(class_name, config_name):
    name = (
        config_name
        if config_name is not None
        else {"AgentList": "agents", "ScenarioList": "scenarios"}[class_name]
    )
    if not isinstance(name, str) or not re.fullmatch(
        r"[A-Za-z0-9][A-Za-z0-9_.-]*", name
    ):
        raise HFSchemaError(
            "config_name must start with a letter or digit and contain only letters, digits, '_', '-' or '.'"
        )
    return name


def read_card(path):
    path = Path(path)
    if not path.exists():
        return {}, ""
    text = path.read_text(encoding="utf-8")
    match = re.match(r"\A---\r?\n(.*?)\r?\n---(?:\r?\n|$)", text, re.DOTALL)
    if not match:
        return {}, text
    data = yaml.safe_load(match.group(1)) or {}
    if not isinstance(data, dict):
        raise HFSchemaError("Dataset card metadata must be a YAML mapping")
    check_version(data)
    return data, text[match.end() :]


def check_version(card):
    if "edsl" not in card:
        return
    metadata = card["edsl"]
    if not isinstance(metadata, dict):
        raise HFSchemaError("Dataset card 'edsl' metadata must be a mapping")
    version = metadata.get("format_version", 1)
    if not isinstance(version, int) or version < 1:
        raise HFSchemaError(f"Invalid EDSL format_version: {version!r}")
    if version > FORMAT_VERSION:
        raise HFFormatVersionError(
            f"EDSL HF format version {version} is newer than supported version {FORMAT_VERSION}. Upgrade EDSL."
        )


def object_metadata(card, config, class_name):
    check_version(card)
    if "edsl" not in card:
        return None
    objects = card["edsl"].get("objects", {})
    if config not in objects:
        # A repo may also contain configs that were not written by EDSL.
        configs = card.get("configs", [])
        if any(c.get("config_name") == config for c in configs):
            return None
        if len(objects) == 1:
            actual = next(iter(objects.values())).get("class")
            if actual != class_name:
                raise HFClassMismatchError(
                    f"Dataset contains {actual}, requested {class_name}"
                )
        raise HFSchemaError(
            f"No EDSL config {config!r}; available configs: {list(objects)}"
        )
    metadata = objects[config]
    if metadata.get("class") != class_name:
        raise HFClassMismatchError(
            f"Config {config!r} contains {metadata.get('class')}, requested {class_name}"
        )
    return metadata


def merge_card(existing, generated, config):
    """Replace only one config's metadata, retaining unrelated card keys."""
    check_version(existing)
    result = copy.deepcopy(existing)
    for key in ("configs", "dataset_info"):
        entries = result.get(key, [])
        if isinstance(entries, dict):
            entries = [entries]
        # Unnamed dataset_info refers to HF's default config.
        entries = [e for e in entries if e.get("config_name", "default") != config]
        result[key] = entries + [
            e for e in generated[key] if e["config_name"] == config
        ]
    edsl = result.setdefault("edsl", {})
    edsl.update({k: v for k, v in generated["edsl"].items() if k != "objects"})
    edsl.setdefault("objects", {})[config] = generated["edsl"]["objects"][config]
    return result


def generated_prose(config, metadata):
    prose = (
        "\n# EDSL dataset\n\n"
        "Created with [EDSL](https://docs.expectedparrot.com). "
        "Each config contains a Parquet `train` split, usable without EDSL.\n\n"
        "```python\nfrom datasets import load_dataset\n"
        f'data = load_dataset("REPO_ID_OR_LOCAL_FOLDER", name="{config}", split="train")\n```\n'
    )
    if metadata.get("codebook"):

        def cell(value):
            return str(value).replace("|", "\\|").replace("\n", "<br>")

        prose += "\n| Field | Description |\n| --- | --- |\n"
        for field, description in metadata["codebook"].items():
            prose += f"| {cell(field)} | {cell(description)} |\n"
    return prose


def write_card(path, metadata, prose):
    Path(path).write_text(
        "---\n"
        + yaml.safe_dump(metadata, sort_keys=False, allow_unicode=True)
        + "---\n"
        + prose,
        encoding="utf-8",
    )
