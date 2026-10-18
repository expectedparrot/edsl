"""Shared local and Hub reader/writer for the v1 interchange format."""

from __future__ import annotations

import logging
import math
import tempfile
from pathlib import Path

from .card import (
    FORMAT_VERSION,
    config_for,
    generated_prose,
    merge_card,
    object_metadata,
    read_card,
    write_card,
)
from .dependencies import require
from .exceptions import HFSchemaError
from .schema import decode_fields, dumps, encode_columns, loads

logger = logging.getLogger(__name__)
SHARD_BYTES = 500_000_000
AGENT_SETTINGS = (
    "instruction",
    "traits_presentation_template",
    "codebook",
    "trait_categories",
)
JSON_SETTINGS = {"codebook", "trait_categories"}


def _class_name(value):
    from edsl.agents.agent_list import AgentList

    cls = value if isinstance(value, type) else type(value)
    return "AgentList" if issubclass(cls, AgentList) else "ScenarioList"


def _encode_names(obj, rows, features, hf):
    features["_edsl_name"] = hf.Value("string")
    preserve_types = any(
        item.name is not None and not isinstance(item.name, str) for item in obj
    )
    if preserve_types:
        features["_edsl_name_original"] = hf.Value("string")
    for row, item in zip(rows, obj):
        name = item.name
        row["_edsl_name"] = None if name is None else str(name)
        if preserve_types:
            row["_edsl_name_original"] = dumps(name)


def _decode_name(row):
    original = row.get("_edsl_name_original")
    return loads(original) if original is not None else row.get("_edsl_name")


def _build_table(obj, coerce, max_file_bytes):
    hf, pa = require("datasets"), require("pyarrow")
    class_name = _class_name(obj)
    metadata = {"class": class_name, "n": len(obj)}
    if class_name == "AgentList":
        agents = [a.to_dict(add_edsl_version=False) for a in obj]
        # Agent codebooks are dict subclasses; store portable plain mappings.
        for agent in agents:
            for setting in JSON_SETTINGS:
                if setting in agent:
                    agent[setting] = dict(agent[setting])
        records = [a["traits"] for a in agents]
        lost = sum(
            bool(a.dynamic_traits_function) or hasattr(a, "answer_question_directly")
            for a in obj
        )
        if lost:
            logger.warning(
                "HF export omits dynamic-trait or direct-answering functions on %d agent(s)",
                lost,
            )
        subclasses = sorted(
            {type(a).__name__ for a in obj if type(a).__name__ != "Agent"}
        )
        if subclasses:
            metadata["agent_subclasses"] = subclasses
    else:
        records = [dict(s) for s in obj]
        if obj.codebook:
            metadata["codebook"] = dict(obj.codebook)
    rows, features, columns = encode_columns(
        records,
        "trait" if class_name == "AgentList" else "field",
        coerce,
        max_file_bytes,
        hf,
    )
    metadata["columns"] = columns
    if class_name == "ScenarioList" and any(s.name is not None for s in obj):
        _encode_names(obj, rows, features, hf)
    if class_name == "AgentList":
        _encode_names(obj, rows, features, hf)
        for setting in AGENT_SETTINGS:
            if agents and all(
                setting in a and a[setting] == agents[0].get(setting) for a in agents
            ):
                metadata[setting] = agents[0][setting]
            elif any(setting in a for a in agents):
                col = "_edsl_" + setting
                features[col] = hf.Value("string")
                for row, agent in zip(rows, agents):
                    value = agent.get(setting)
                    row[col] = (
                        dumps(value)
                        if value is not None and setting in JSON_SETTINGS
                        else value
                    )
    if not features:
        # Arrow cannot represent the row count of a zero-column Parquet table.
        features["_edsl_row"] = hf.Value("int64")
        for index, row in enumerate(rows):
            row["_edsl_row"] = index
    features = hf.Features(features)
    try:
        table = pa.Table.from_pylist(rows, schema=features.arrow_schema)
    except (pa.ArrowException, OverflowError, TypeError) as exc:
        raise HFSchemaError(f"Cannot encode HF columns: {exc}") from exc
    return table, features, metadata


def _install_config(staging, path, config):
    """Keep the previous shards until the new shards and card are installed."""
    path.mkdir(parents=True, exist_ok=True)
    config_path = path / config
    if config_path.is_symlink():
        raise HFSchemaError(
            f"Refusing to overwrite symlink config directory {config_path}"
        )
    config_path.mkdir(exist_ok=True)
    backup = staging / ".previous"
    backup.mkdir()
    moved, installed = [], []
    try:
        for old in sorted(config_path.glob("train-*-of-*.parquet")):
            saved = old.replace(backup / old.name)
            moved.append((saved, old))
        for shard in sorted((staging / config).iterdir()):
            installed.append(shard.replace(config_path / shard.name))
        (staging / "README.md").replace(path / "README.md")
    except BaseException:
        try:
            for shard in installed:
                shard.unlink()
            for saved, old in moved:
                saved.replace(old)
        except BaseException as rollback_error:
            # Preserve backups outside TemporaryDirectory's cleanup if the
            # filesystem also refuses the rollback (e.g. permissions changed).
            recovery = staging.with_name(staging.name + "-recovery")
            staging.rename(recovery)
            raise RuntimeError(
                f"HF dataset overwrite and rollback failed; recover files from {recovery}"
            ) from rollback_error
        raise


def save_hf(obj, path, *, config_name=None, coerce="error", max_file_bytes=50_000_000):
    """Write a standard HF Parquet config, retaining other configs and prose."""
    if coerce not in ("error", "string", "json"):
        raise ValueError("coerce must be 'error', 'string', or 'json'")
    if type(max_file_bytes) is not int or max_file_bytes < 0:
        raise ValueError("max_file_bytes must be a non-negative integer")
    config = config_for(_class_name(obj), config_name)
    path = Path(path)
    existing, prose = read_card(path / "README.md")
    table, features, metadata = _build_table(obj, coerce, max_file_bytes)
    from edsl import __version__

    hf = require("datasets")
    pq = require("pyarrow.parquet")
    info = hf.DatasetInfo(features=features)._to_yaml_dict()
    info.update(
        config_name=config,
        splits=[
            {
                "name": "train",
                "num_bytes": table.nbytes,
                "num_examples": len(obj),
            }
        ],
    )
    generated = {
        "configs": [
            {
                "config_name": config,
                "data_files": [{"split": "train", "path": f"{config}/*.parquet"}],
            }
        ],
        "dataset_info": [info],
        "edsl": {
            "format_version": FORMAT_VERSION,
            "edsl_version": __version__,
            "objects": {config: metadata},
        },
    }
    card = merge_card(existing, generated, config)
    if not (path / "README.md").exists():
        prose = generated_prose(config, metadata)
    # Validate and finish serialization before replacing the prior config.
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="edsl-hf-", dir=path.parent) as tmp:
        staging = Path(tmp)
        target = staging / config
        target.mkdir()
        shards = min(max(1, len(obj)), max(1, math.ceil(table.nbytes / SHARD_BYTES)))
        rows_per_shard = math.ceil(len(obj) / shards)
        for i in range(shards):
            shard_path = target / f"train-{i:05d}-of-{shards:05d}.parquet"
            if len(obj):
                pq.write_table(
                    table.slice(i * rows_per_shard, rows_per_shard), shard_path
                )
            else:
                # An empty row group makes datasets infer a zero batch size.
                # A schema-only file remains readable with its streaming API.
                with pq.ParquetWriter(shard_path, table.schema):
                    pass
        write_card(staging / "README.md", card, prose)
        _install_config(staging, path, config)
    return path


def _fallback(cls, path, config_name, **kwargs):
    hf = require("datasets")
    dataset = hf.load_dataset(
        str(path), name=config_name, split="train", trust_remote_code=False, **kwargs
    )
    from edsl.agents.agent import Agent
    from edsl.scenarios.scenario import Scenario

    factory = Agent if _class_name(cls) == "AgentList" else Scenario
    return cls(factory(dict(row)) for row in dataset)


def load_hf(cls, path, *, config_name=None):
    path = Path(path)
    if not path.is_dir():
        raise FileNotFoundError(f"HF dataset folder not found: {path}")
    config = config_for(_class_name(cls), config_name)
    card, _ = read_card(path / "README.md")
    metadata = object_metadata(card, config, _class_name(cls))
    if metadata is None:
        return _fallback(cls, path, config_name)
    require("datasets")
    pq = require("pyarrow.parquet")
    from edsl.agents.agent import Agent
    from edsl.scenarios.scenario import Scenario

    files = sorted((path / config).glob("train-*-of-*.parquet"))
    if not files:
        raise HFSchemaError(f"No Parquet shards for config {config!r}")
    items = []
    for file in files:
        # Read Arrow directly so Image/Audio decoders never open paths or URLs.
        for batch in pq.ParquetFile(file).iter_batches():
            for row in batch.to_pylist():
                fields = decode_fields(row, metadata["columns"])
                if metadata["class"] == "AgentList":
                    agent = {"traits": fields, "name": _decode_name(row)}
                    for setting in AGENT_SETTINGS:
                        if setting in metadata:
                            agent[setting] = metadata[setting]
                        elif row.get("_edsl_" + setting) is not None:
                            value = row["_edsl_" + setting]
                            agent[setting] = (
                                loads(value) if setting in JSON_SETTINGS else value
                            )
                    items.append(Agent.from_dict(agent))
                else:
                    items.append(Scenario(fields, name=_decode_name(row)))
    if len(items) != metadata["n"]:
        raise HFSchemaError(
            f"Config {config!r}: card declares {metadata['n']} rows, found {len(items)}"
        )
    if metadata["class"] == "ScenarioList":
        return cls(items, codebook=metadata.get("codebook"))
    return cls(items)


def to_hf(
    obj,
    repo_id,
    *,
    config_name=None,
    private=True,
    token=None,
    commit_message=None,
    coerce="error",
    max_file_bytes=50_000_000,
):
    hub = require("huggingface_hub")
    config = config_for(_class_name(obj), config_name)
    with tempfile.TemporaryDirectory(prefix="edsl-hf-") as tmp:
        path = save_hf(
            obj,
            Path(tmp) / "dataset",
            config_name=config,
            coerce=coerce,
            max_file_bytes=max_file_bytes,
        )
        api = hub.HfApi(token=token)
        repo_url = api.create_repo(
            repo_id, repo_type="dataset", private=private, exist_ok=True
        )
        head = api.repo_info(repo_id, repo_type="dataset").sha
        try:
            existing_path = hub.hf_hub_download(
                repo_id, "README.md", repo_type="dataset", token=token, revision=head
            )
        except hub.errors.EntryNotFoundError:
            pass
        else:
            existing, prose = read_card(existing_path)
            generated, _ = read_card(path / "README.md")
            write_card(
                path / "README.md", merge_card(existing, generated, config), prose
            )
        hub.upload_folder(
            repo_id=repo_id,
            repo_type="dataset",
            folder_path=str(path),
            token=token,
            commit_message=commit_message or f"Export EDSL {config}",
            parent_commit=head,
            allow_patterns=["README.md", f"{config}/*.parquet"],
            delete_patterns=[f"{config}/train-*-of-*.parquet"],
        )
    return str(repo_url)


def from_hf(cls, repo_id, *, config_name=None, revision=None, token=None):
    hub = require("huggingface_hub")
    config = config_for(_class_name(cls), config_name)
    # Resolve once so card and shards come from the same commit, even when main moves.
    head = (
        hub.HfApi(token=token)
        .repo_info(repo_id, repo_type="dataset", revision=revision)
        .sha
    )
    try:
        card_path = hub.hf_hub_download(
            repo_id, "README.md", repo_type="dataset", token=token, revision=head
        )
    except hub.errors.EntryNotFoundError:
        card = {}
    else:
        card, _ = read_card(card_path)
    if object_metadata(card, config, _class_name(cls)) is None:
        return _fallback(cls, repo_id, config_name, revision=head, token=token)
    folder = hub.snapshot_download(
        repo_id,
        repo_type="dataset",
        token=token,
        revision=head,
        allow_patterns=["README.md", f"{config}/*.parquet"],
    )
    return load_hf(cls, folder, config_name=config)
