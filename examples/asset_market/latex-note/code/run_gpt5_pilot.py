"""Run a bounded prefix of a 30-round market, with concurrent sealed decisions."""

from __future__ import annotations

import argparse
import asyncio
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys
import time

from edsl import AgentList, Model, Results
from edsl.results import Result
from edsl.sharedstate import SQLiteStateBackend
from edsl.workflows import (
    SQLiteWorkflowStore,
    WorkflowCoordinator,
    ExecutionPlan,
    role,
    llm,
    scripted,
)

from .experiment import ROOT, market_runtime, metrics
from .run import ScriptedTrader, write_json, write_tables
from .speculative_prompts import COMPOSITION, VERSION, build_experiment


def source_hashes():
    names = ["experiment.py", "run.py", "speculative_prompts.py", "run_gpt5_pilot.py"]
    return {
        name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in names
    }


async def deliver_until(
    coordinator, backend, agents, model, output, stop_after, stop_on_excursion
):
    """Open a complete round before querying models; commit on one event loop."""
    store, instance = coordinator.store, output.name
    while True:
        market = backend.snapshot("session").state["market"]
        if len(market["tape"]) >= stop_after:
            return "round_limit"
        if (
            stop_on_excursion
            and len(market["tape"]) >= 2
            and all(
                r["price"] is not None and r["price"] >= 17.5
                for r in market["tape"][-2:]
            )
        ):
            return "two_consecutive_trades_at_or_above_17_50"
        pending = store.pending_outbox(instance)
        if not pending:
            raise RuntimeError(
                "No deliverable work before the requested observation limit"
            )
        opened_items = []
        for row in pending:
            item = store.item(row["work_item_id"])
            store.mark_delivered(row["id"])
            if item["status"] not in {"ready", "in_progress"}:
                continue
            attempt = store.start_attempt(item["id"], lease_seconds=600)
            opened = coordinator.open(item["id"])
            opened_items.append((opened, attempt))

        async def answer(opened, attempt):
            agent = agents[opened.participant_id]
            if agent.traits["role"] == "exchange":
                answer_dict = {"settlement": "clear"}
                store.record_executor(
                    opened.id, "scripted", {"purpose": "atomic call-market settlement"}
                )
            elif model is None:
                answer_dict = ScriptedTrader().answer(agent, opened)
                store.record_executor(
                    opened.id, "scripted", {"purpose": "prefix mechanism check"}
                )
            else:
                store.record_executor(
                    opened.id, "llm", {"model": model.model, "service": "openai"}
                )
                store.record_model(opened.id, model.to_dict())
                start = time.monotonic()
                results = (
                    await opened.survey.by(agent)
                    .by(model)
                    .run_async(
                        disable_remote_inference=True,
                        disable_remote_cache=True,
                        cache=False,
                        stop_on_exceptions=True,
                    )
                )
                if len(results) != 1:
                    raise RuntimeError("Expected exactly one trader response")
                result = results[0]
                record = {
                    "work_item_id": opened.id,
                    "step": opened.step_name,
                    "participant": agent.name,
                    "elapsed_seconds": time.monotonic() - start,
                    "state_versions": dict(opened.state_versions),
                    "result": result.to_dict(),
                }
                with (output / "model-calls.jsonl").open("a") as handle:
                    handle.write(json.dumps(record, allow_nan=False) + "\n")
                raw = record["result"]["raw_model_response"][
                    "decision_raw_model_response"
                ]
                if raw["choices"][0]["finish_reason"] != "stop":
                    raise RuntimeError(
                        "Incomplete model response; refusing to submit it"
                    )
                answer_dict = dict(result.answer)
            coordinator.submit(
                opened.id,
                answer_dict,
                idempotency_key=f"pilot:{opened.id}",
                attempt_id=attempt["id"],
            )

        outcomes = await asyncio.gather(
            *(answer(opened, attempt) for opened, attempt in opened_items),
            return_exceptions=True,
        )
        failures = []
        for (opened, attempt), outcome in zip(opened_items, outcomes):
            if not isinstance(outcome, BaseException):
                continue
            if store.item(opened.id)["status"] == "committing":
                failures.append(f"{opened.id}: accepted response needs recovery")
                continue
            store.finish_attempt(
                attempt["id"],
                status="failed",
                error_kind="exception",
                error_message=str(outcome)[:1000],
            )
            if attempt["number"] < 3:
                store.retry_item(opened.id, reason="retry failed model delivery")
            else:
                store.fail_item(opened.id, reason=str(outcome)[:1000])
                failures.append(str(outcome))
        if failures:
            raise RuntimeError("; ".join(failures))
        new_market = backend.snapshot("session").state["market"]
        if len(new_market["tape"]) > len(market["tape"]):
            last = new_market["tape"][-1]
            print(
                json.dumps(
                    {
                        "settled_period": last["period"],
                        "price": last["price"],
                        "volume": last["volume"],
                    }
                ),
                file=sys.stderr,
                flush=True,
            )


def run(
    output,
    *,
    stop_after=12,
    seed=140926,
    backend_kind="llm",
    resume=False,
    stop_on_excursion=True,
):
    if not 1 <= stop_after < 30:
        raise ValueError(
            "Observation limit must be 1–29; the economic horizon remains 30"
        )
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    config = {
        "treatment": COMPOSITION,
        "prompt_variant": VERSION,
        "seed": seed,
        "periods": 30,
        "backend": backend_kind,
        "model": "gpt-5-mini" if backend_kind == "llm" else None,
        "service": "openai" if backend_kind == "llm" else None,
        "temperature": 1,
        "reasoning_effort": "medium",
        "max_tokens": 8000,
        "source_sha256": source_hashes(),
    }
    if (output / "config.json").exists():
        if not resume:
            raise FileExistsError("Use --resume to continue this saved market")
        if json.loads((output / "config.json").read_text()) != config:
            raise ValueError("Configuration/code changed; cannot resume")
    elif resume:
        raise FileNotFoundError("No saved market to resume")
    else:
        write_json(output / "config.json", config)
    workflow, states, agents_list = build_experiment(
        COMPOSITION, periods=30, seed=seed, state_id=output.name
    )
    store = SQLiteWorkflowStore(output / "workflow.sqlite")
    backend = SQLiteStateBackend(
        states, output / "shared-state.sqlite", runtime=market_runtime()
    )
    if resume:
        coordinator = WorkflowCoordinator.restore(
            output.name, store, state_backends={states.state_id: backend}
        )
        workflow = coordinator.workflow
        coordinator.recover(output.name, max_attempts=3)
    else:
        coordinator = WorkflowCoordinator(
            workflow, store, state_backends={states.state_id: backend}
        )
        write_json(output / "workflow.json", workflow.to_dict())
        write_json(output / "shared-state-definition.json", states.to_dict())
        AgentList(agents_list[:-1]).save(str(output / "traders.ep"))
        coordinator.launch(agents_list, instance_id=output.name, random_seed=seed)
    model = None
    if backend_kind == "llm":
        from dotenv import load_dotenv

        load_dotenv()
        model = Model(
            "gpt-5-mini",
            service_name="openai",
            temperature=1,
            reasoning_effort="medium",
            max_tokens=8000,
        )
    plan = ExecutionPlan().bind(
        role("trader"),
        llm(model="gpt-5-mini", service="openai")
        if model
        else scripted(purpose="mechanism check"),
    )
    plan = plan.bind(role("exchange"), scripted(purpose="atomic settlement"))
    write_json(output / "execution-plan.json", plan.to_dict())
    stop_reason = "error"
    started = time.monotonic()
    try:
        stop_reason = asyncio.run(
            deliver_until(
                coordinator,
                backend,
                {a.name: a for a in agents_list},
                model,
                output,
                stop_after,
                stop_on_excursion,
            )
        )
    finally:
        state = backend.snapshot("session").state["market"]
        items = store.items(output.name)
        summary = {
            "config": config,
            "complete": state["finished"],
            "observation_complete": stop_reason != "error",
            "stop_reason": stop_reason,
            "observation_limit": stop_after,
            "observed_periods": len(state["tape"]),
            "stop_on_excursion": stop_on_excursion,
            "elapsed_seconds_this_invocation": time.monotonic() - started,
            "work_items": dict(Counter(item["status"] for item in items)),
            "metrics": metrics(state["tape"]),
            "tape": state["tape"],
            "accounts": state["accounts"],
            "persona_assignment": workflow.metadata["persona_assignment"],
            "order_rejections": sum(
                o["rejection"] is not None for o in state["order_log"]
            ),
            "quantity_reductions": sum(
                o["accepted_quantity"] < o["decision"]["quantity"]
                for o in state["order_log"]
                if o["rejection"] is None
            ),
        }
        write_json(output / "summary.json", summary)
        write_json(output / "orders.json", state["order_log"])
        write_json(output / "workflow-events.json", store.events(output.name))
        calls_path = output / "model-calls.jsonl"
        if calls_path.exists():
            by_item = {
                c["work_item_id"]: c
                for line in calls_path.read_text().splitlines()
                for c in [json.loads(line)]
            }
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
        "observation_complete": summary["observation_complete"],
        "observed_periods": summary["observed_periods"],
        "stop_reason": stop_reason,
        "metrics": summary["metrics"],
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--stop-after", type=int, default=12)
    parser.add_argument("--seed", type=int, default=140926)
    parser.add_argument("--backend", choices=["llm", "scripted"], default="llm")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--no-early-stop", action="store_true")
    args = parser.parse_args()
    result = run(
        args.output,
        stop_after=args.stop_after,
        seed=args.seed,
        backend_kind=args.backend,
        resume=args.resume,
        stop_on_excursion=not args.no_early_stop,
    )
    print(json.dumps({"status": "ok", "data": result, "warnings": []}))
