"""Run speculative-v1 without modifying the archived original implementation.

Uses the same runner protocol and shared-state exchange as the original pilot.
Both the original mechanism and the new prompt/runner code are fingerprinted.
"""

from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
import hashlib
import json
from pathlib import Path
import time

from edsl import AgentList, Model, Results
from edsl.results import Result
from edsl.sharedstate import SQLiteStateBackend
from edsl.workflows import (
    ExecutionPlan,
    RetryPolicy,
    SQLiteWorkflowStore,
    WorkflowCoordinator,
    WorkflowSimulation,
    llm,
    role,
    scripted,
)

from .experiment import ROOT, market_runtime, metrics
from .run import (
    ExchangeAnswerer,
    RecordedLLMAnswerer,
    ScriptedRouter,
    ScriptedTrader,
    write_json,
    write_tables,
)
from .speculative_prompts import COMPOSITION, VERSION, build_experiment


def prompt_hash():
    return hashlib.sha256(
        b"".join(
            (ROOT / name).read_bytes()
            for name in ["speculative_prompts.py", "run_speculative.py"]
        )
    ).hexdigest()


def run_session(config):
    output = Path(config["output"])
    resume = config.pop("resume", False)
    output.mkdir(parents=True, exist_ok=True)
    code_files = [
        ROOT / "experiment.py",
        ROOT / "run.py",
        *sorted((ROOT / "personas").glob("*.txt")),
    ]
    config["implementation_sha256"] = hashlib.sha256(
        b"".join(p.read_bytes() for p in code_files)
    ).hexdigest()
    config["prompt_variant"] = VERSION
    config["prompt_implementation_sha256"] = prompt_hash()
    existing = output / "config.json"
    if existing.exists():
        if not resume:
            raise FileExistsError(
                f"Existing run {output}; use --resume or a fresh directory"
            )
        if json.loads(existing.read_text()) != config:
            raise ValueError(
                "Resume requires the same configuration, code, and persona texts"
            )
    elif resume:
        raise FileNotFoundError(f"Cannot resume missing run {output}")
    else:
        write_json(existing, config)
    workflow, states, agents = build_experiment(
        config["treatment"],
        periods=config["periods"],
        seed=config["seed"],
        state_id=output.name,
    )
    store = SQLiteWorkflowStore(output / "workflow.sqlite")
    backend = SQLiteStateBackend(
        states, output / "shared-state.sqlite", runtime=market_runtime()
    )
    instance = output.name
    coordinator = (
        WorkflowCoordinator.restore(
            instance, store, state_backends={states.state_id: backend}
        )
        if resume
        else WorkflowCoordinator(
            workflow, store, state_backends={states.state_id: backend}
        )
    )
    if not resume:
        write_json(output / "workflow.json", workflow.to_dict())
        write_json(output / "shared-state-definition.json", states.to_dict())
        AgentList(agents[:-1]).save(str(output / "traders.ep"))
        coordinator.launch(agents, instance_id=instance, random_seed=config["seed"])
    if config["backend"] == "llm":
        from dotenv import load_dotenv

        load_dotenv()
        params = {"temperature": config["temperature"], "max_tokens": 650}
        if config.get("base_url"):
            params["base_url"] = config["base_url"]
        if config["service"] in {"openai_compatible", "ollama"}:
            import os

            os.environ.setdefault("OPENAI_COMPATIBLE_API_KEY", "local")
            os.environ.setdefault("OLLAMA_API_KEY", "local")
        model = Model(config["model"], service_name=config["service"], **params)
        answerer = RecordedLLMAnswerer(model, output)
        plan = ExecutionPlan().bind(
            role("trader"), llm(model=config["model"], service=config["service"])
        )
    else:
        answerer = ScriptedTrader()
        plan = ExecutionPlan().bind(role("trader"), scripted(purpose="mechanism test"))
    plan = plan.bind(
        role("exchange"), scripted(purpose="atomic call-market settlement")
    )
    write_json(output / "execution-plan.json", plan.to_dict())
    start = time.monotonic()
    try:
        WorkflowSimulation(
            coordinator,
            {agent.name: agent for agent in agents},
            answerer,
            execution_plan=plan,
            answerers={
                "llm": answerer,
                "scripted": ExchangeAnswerer()
                if config["backend"] == "llm"
                else ScriptedRouter(),
            },
        ).run(instance, resume=resume, retry_policy=RetryPolicy(max_attempts=3))
    finally:
        state = backend.snapshot("session").state["market"]
        items = store.items(instance)
        summary = {
            "config": config,
            "complete": state["finished"],
            "elapsed_seconds_this_invocation": time.monotonic() - start,
            "work_items": dict(Counter(item["status"] for item in items)),
            "metrics": metrics(state["tape"]),
            "tape": state["tape"],
            "accounts": state["accounts"],
            "persona_assignment": workflow.metadata["persona_assignment"],
            "order_rejections": sum(
                order["rejection"] is not None for order in state["order_log"]
            ),
            "quantity_reductions": sum(
                order["accepted_quantity"] < order["decision"]["quantity"]
                for order in state["order_log"]
                if order["rejection"] is None
            ),
        }
        write_json(output / "summary.json", summary)
        write_json(output / "orders.json", state["order_log"])
        write_json(output / "workflow-events.json", store.events(instance))
        calls_file = output / "model-calls.jsonl"
        if calls_file.exists():
            calls = [json.loads(line) for line in calls_file.read_text().splitlines()]
            # Use the final call for each completed item; retain every attempt in JSONL.
            by_item = {call["work_item_id"]: call for call in calls}
            records = [
                Result.from_dict(by_item[item["id"]]["result"])
                for item in items
                if item["status"] == "completed" and item["id"] in by_item
            ]
            if records:
                Results(survey=workflow.steps[0].survey, data=records).save(
                    str(output / "results.ep")
                )
        write_tables(output, state)
    return {
        "output": str(output),
        "complete": summary["complete"],
        "metrics": summary["metrics"],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--replicates", type=int, default=3)
    parser.add_argument("--periods", type=int, default=30)
    parser.add_argument("--seed", type=int, default=140926)
    parser.add_argument("--backend", choices=["scripted", "llm"], default="scripted")
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    if args.replicates < 1 or args.workers < 1:
        parser.error("replicates and workers must be positive")
    configs = [
        {
            "output": str(args.output.resolve() / f"{VERSION}-s{args.seed + rep}"),
            "treatment": COMPOSITION,
            "periods": args.periods,
            "seed": args.seed + rep,
            "backend": args.backend,
            "model": "gpt-4o-mini" if args.backend == "llm" else None,
            "service": "openai" if args.backend == "llm" else None,
            "base_url": None,
            "temperature": 0.7,
            "resume": args.resume,
        }
        for rep in range(args.replicates)
    ]
    if args.workers == 1:
        summaries = [run_session(c) for c in configs]
    else:
        with ProcessPoolExecutor(max_workers=args.workers) as pool:
            summaries = list(pool.map(run_session, configs))
    write_json(args.output / "manifest.json", summaries)
    print(json.dumps({"status": "ok", "data": summaries, "warnings": []}))


if __name__ == "__main__":
    main()
