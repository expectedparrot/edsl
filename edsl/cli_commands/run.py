"""Run command for the EDSL CLI."""

from __future__ import annotations

import json
import sys
import time
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from typing import Optional

import click

from edsl.cli_shared import (
    EXIT_ERROR,
    EXIT_USAGE,
    EXIT_VALIDATION,
    error,
    jsonable,
    output,
    raw_output_written,
    read_json_file,
    save_results,
)


def register(app: click.Group) -> None:
    # ---------------------------------------------------------------------------
    # ep run
    # ---------------------------------------------------------------------------

    @app.command("run")
    @click.option("--jobs", default=None, help="Path to serialized Jobs JSON.")
    @click.option("--survey", default=None, help="Path to serialized Survey JSON.")
    @click.option("--json", "--json_data", "json_data", default=None, help="Inline JSON.")
    @click.option("--question", "-q", default=None, help="Question text.")
    @click.option("--agent_list", default=None, help="Path to AgentList JSON.")
    @click.option("--scenario_list", default=None, help="Path to ScenarioList JSON.")
    @click.option("--model_list", default=None, help="Path to ModelList JSON.")
    @click.option("--model", "-m", default=None, help="Model name.")
    @click.option("--type", "-t", "qtype", default="free_text", help="Question type.")
    @click.option("--options", default=None, help="JSON array for MC/checkbox.")
    @click.option("--name", default=None, help="Question name.")
    @click.option("--progress/--no_progress", default=False, help="Show progress bar on stderr.")
    @click.option("--background", is_flag=True, default=False, help="Submit remote job and return immediately.")
    @click.option("--wait", is_flag=True, default=False, help="With --background, poll until the remote job reaches a terminal status.")
    @click.option("--poll_interval", default=10.0, type=float, help="Seconds between status checks with --wait.")
    @click.option("--timeout", default=None, type=float, help="Maximum seconds to wait with --wait.")
    @click.option("--remote_inference_description", default=None, help="Description for the remote job.")
    @click.option("--remote_inference_results_visibility", default="private", type=click.Choice(["private", "public", "unlisted"]), help="Visibility for remote results.")
    @click.option("--results_description", default=None, help="Description for the remote results object.")
    @click.option("--fresh", is_flag=True, default=False, help="Ignore cache.")
    @click.option("--n", "-n", "iterations", default=1, type=int, show_default=True, help="Number of iterations per question/scenario/agent/model combination.")
    @click.option("--local", is_flag=True, default=False, help="Disable remote inference and run locally.")
    @click.option("--save", default=None, help="Save Results JSON to file.")
    @click.option("--output", "-o", "output_path", default=None, help="Save Results to a file or .ep package.")
    @click.argument("input_path", required=False, type=click.Path(exists=True))
    def run(jobs, survey, json_data, question, agent_list, scenario_list,
            model_list, model, qtype, options, name, progress, background,
            wait, poll_interval, timeout, remote_inference_description,
            remote_inference_results_visibility, results_description, fresh,
            iterations, local, save, output_path, input_path):
        """Run question(s) and get results.

        \b
        Examples:
          ep run --question "What is 2+2?" --model gpt-4o
          ep run --question "Pick one." --type multiple_choice --options '["A","B"]' --name choice
          ep run --survey survey.ep --agent_list agents.ep --scenario_list scenarios.ep --model gpt-4o --output results.ep
          ep run --jobs jobs.ep --local --output results.ep
          ep run --jobs jobs.ep --background
          ep run --jobs jobs.ep --background --wait --timeout 600 --output results.ep
          cat jobs.json | ep run --output results.json
        """
        from edsl.jobs import Jobs
        from edsl.agents import AgentList as AgentListClass
        from edsl.scenarios import ScenarioList as ScenarioListClass
        from edsl.language_models import Model as ModelClass
        from edsl.language_models.model_list import ModelList as ModelListClass

        # Check mutually exclusive model flags
        if model and model_list:
            error("USAGE_ERROR", "--model and --model_list are mutually exclusive.",
                   exit_code=EXIT_USAGE)
        if wait and not background:
            error("USAGE_ERROR", "--wait requires --background.",
                   exit_code=EXIT_USAGE)
        if poll_interval <= 0:
            error("USAGE_ERROR", "--poll_interval must be greater than 0.",
                   exit_code=EXIT_USAGE)
        if timeout is not None and timeout <= 0:
            error("USAGE_ERROR", "--timeout must be greater than 0.",
                   exit_code=EXIT_USAGE)
        if iterations <= 0:
            error("USAGE_ERROR", "--n must be greater than 0.",
                   exit_code=EXIT_USAGE)

        # Step 1: Determine base input source
        sources = []
        if input_path:
            sources.append("path")
        if jobs:
            sources.append("jobs")
        if survey:
            sources.append("survey")
        if json_data:
            sources.append("json")
        if question:
            sources.append("question")

        stdin_data = _read_stdin() if not sources else None
        if stdin_data:
            sources.append("stdin")

        if len(sources) > 1:
            error("USAGE_ERROR",
                   f"Multiple input sources provided: {', '.join(sources)}. Only one allowed.",
                   suggestion="Use exactly one of: INPUT_PATH, --jobs, --survey, --json_data, --question, or stdin.",
                   exit_code=EXIT_USAGE)

        input_mode = sources[0] if sources else None
        if not input_mode:
            error("USAGE_ERROR", "No input provided.",
                   suggestion="Use INPUT_PATH, --jobs, --survey, --json_data, --question, or pipe JSON via stdin.",
                   exit_code=EXIT_USAGE)

        # Step 2: Build the Jobs object
        try:
            job = _build_job(
                input_mode=input_mode,
                input_path=input_path, jobs_path=jobs, survey_path=survey, json_str=json_data,
                stdin_data=stdin_data, question_text=question,
                question_type=qtype, question_options=options, question_name=name,
            )
        except SystemExit:
            raise
        except Exception as e:
            error("RUN_ERROR", f"Failed to build job: {e}",
                   suggestion="Use 'ep validate' to check your input.",
                   exit_code=EXIT_ERROR)

        # Step 3: Apply component overrides
        try:
            if agent_list:
                data = read_json_file(agent_list)
                job = Jobs(
                    survey=job.survey,
                    agents=AgentListClass.from_dict(data),
                    models=job.models,
                    scenarios=job.scenarios,
                )
            if scenario_list:
                data = read_json_file(scenario_list)
                job = Jobs(
                    survey=job.survey,
                    agents=job.agents,
                    models=job.models,
                    scenarios=ScenarioListClass.from_dict(data),
                )
            if model_list:
                data = read_json_file(model_list)
                job = Jobs(
                    survey=job.survey,
                    agents=job.agents,
                    models=ModelListClass.from_dict(data),
                    scenarios=job.scenarios,
                )
            if model:
                job = Jobs(
                    survey=job.survey,
                    agents=job.agents,
                    models=[ModelClass(model)],
                    scenarios=job.scenarios,
                )
        except SystemExit:
            raise
        except Exception as e:
            error("RUN_ERROR", f"Failed to apply overrides: {e}", exit_code=EXIT_ERROR)

        # Step 4: Execute
        if save and output_path:
            error("USAGE_ERROR", "--save and --output are mutually exclusive.",
                   exit_code=EXIT_USAGE)

        if not background and not (save or output_path):
            error(
                "USAGE_ERROR",
                "Completed run results must be written to a file.",
                suggestion="Use '--output results.ep' or '--output results.json'. Use '--background' to submit a remote job and return metadata without waiting for results.",
                exit_code=EXIT_USAGE,
            )

        if background and not wait and (save or output_path):
            error("USAGE_ERROR", "Background jobs cannot be saved before completion.",
                   suggestion="Use 'ep jobs results <job_uuid> --output results.ep' after the job completes.",
                   exit_code=EXIT_USAGE)

        envelope_warnings = []
        try:
            stdout_buffer = StringIO()
            with redirect_stdout(stdout_buffer):
                results_obj = job.run(
                    progress_bar=progress,
                    background=background,
                    remote_inference_description=remote_inference_description,
                    remote_inference_results_visibility=remote_inference_results_visibility,
                    results_description=results_description,
                    fresh=fresh,
                    n=iterations,
                    disable_remote_inference=local,
                    verbose=False,
                )
            captured_stdout = stdout_buffer.getvalue().strip()
            if captured_stdout:
                envelope_warnings.append(
                    {
                        "code": "SUPPRESSED_STDOUT",
                        "message": "Output emitted during job execution was captured to keep stdout as a single JSON envelope.",
                        "output": captured_stdout,
                    }
                )
        except Exception as e:
            error("RUN_ERROR", f"Job execution failed: {e}", exit_code=EXIT_ERROR)

        saved = None
        result_count = 0 if background else _safe_len(results_obj)

        # Save if requested
        if (save or output_path) and not background:
            try:
                saved = save_results(results_obj, output_path or save)
                if raw_output_written(saved):
                    return
            except SystemExit:
                raise
            except Exception as e:
                error("RUN_ERROR", f"Failed to save results: {e}", exit_code=EXIT_ERROR)

        meta = {
            "input_mode": input_mode,
            "model_count": len(job.models) if hasattr(job, 'models') else 0,
            "agent_count": len(job.agents) if hasattr(job, 'agents') else 0,
            "scenario_count": len(job.scenarios) if hasattr(job, 'scenarios') else 0,
            "result_count": result_count,
            "n": iterations,
            "local": local,
        }
        if background:
            meta["remote_job"] = _remote_job_meta_from_results(results_obj)
            if wait:
                wait_data = _wait_for_remote_job(
                    meta["remote_job"].get("job_uuid"),
                    poll_interval=poll_interval,
                    timeout=timeout,
                    output_path=output_path or save,
                )
                meta["remote_job"]["wait"] = wait_data
                if wait_data.get("saved") is not None:
                    meta["saved"] = wait_data["saved"]
                    if raw_output_written(wait_data["saved"]):
                        return
        if saved is not None:
            meta["saved"] = saved

        output({"results": [], "meta": meta}, warnings=envelope_warnings)


    def _wait_for_remote_job(
        job_uuid: str,
        poll_interval: float,
        timeout: Optional[float],
        output_path: Optional[str],
    ) -> dict:
        if not job_uuid:
            error(
                "RUN_ERROR",
                "Background job did not return a job UUID.",
                exit_code=EXIT_ERROR,
            )

        from edsl.coop import Coop

        coop = Coop()
        terminal_statuses = {
            "completed",
            "failed",
            "partial_failed",
            "partially_failed",
            "cancelled",
            "canceled",
        }
        started_at = time.monotonic()
        polls = 0

        while True:
            status_data = coop.new_remote_inference_get(job_uuid=job_uuid)
            polls += 1
            last_status = status_data.get("status")
            normalized_status = str(last_status or "").lower()
            if normalized_status in terminal_statuses:
                break
            if timeout is not None and time.monotonic() - started_at >= timeout:
                return {
                    "completed": False,
                    "timed_out": True,
                    "polls": polls,
                    "elapsed_seconds": round(time.monotonic() - started_at, 3),
                    "last_status": last_status,
                    "status": jsonable(status_data),
                }
            time.sleep(poll_interval)

        data = {
            "completed": normalized_status == "completed",
            "timed_out": False,
            "polls": polls,
            "elapsed_seconds": round(time.monotonic() - started_at, 3),
            "last_status": last_status,
            "status": jsonable(status_data),
        }

        results_uuid = status_data.get("results_uuid") if status_data else None
        if normalized_status == "completed" and results_uuid:
            results_obj = coop.pull(results_uuid, expected_object_type="results")
            data["results_uuid"] = results_uuid
            data["result_count"] = len(results_obj) if hasattr(results_obj, "__len__") else None
            if output_path:
                data["saved"] = save_results(results_obj, output_path)
        elif normalized_status in {"failed", "partial_failed", "partially_failed"}:
            data["commands"] = {
                "errors": f"ep jobs errors {job_uuid} --output error.md",
            }

        return data




    def _remote_job_meta_from_results(results_obj) -> dict:
        job_info = getattr(results_obj, "job_info", None)
        if job_info is None:
            return {"background": True}

        creation_data = getattr(job_info, "creation_data", None)
        logger = getattr(job_info, "logger", None)
        jobs_info = getattr(logger, "jobs_info", None)
        meta = {
            "background": True,
            "job_uuid": getattr(job_info, "job_uuid", None),
            "creation_data": jsonable(creation_data) if creation_data is not None else None,
            "new_format": getattr(job_info, "new_format", None),
        }
        for field in (
            "progress_bar_url",
            "remote_inference_url",
            "remote_cache_url",
            "results_uuid",
            "results_url",
            "error_report_url",
        ):
            value = getattr(jobs_info, field, None) if jobs_info is not None else None
            if value is not None:
                meta[field] = value
        meta["commands"] = {
            "status": f"ep jobs status {meta['job_uuid']}" if meta.get("job_uuid") else None,
            "results": f"ep jobs results {meta['job_uuid']} --output results.ep" if meta.get("job_uuid") else None,
            "errors": f"ep jobs errors {meta['job_uuid']} --output error.md" if meta.get("job_uuid") else None,
        }
        return meta


    def _safe_len(obj) -> Optional[int]:
        try:
            return len(obj)
        except Exception:
            return None


    def _build_job(input_mode, input_path, jobs_path, survey_path, json_str, stdin_data,
                   question_text, question_type, question_options, question_name):
        """Build a Jobs object from the determined input source."""
        from edsl.jobs import Jobs
        from edsl.surveys import Survey as SurveyClass
        from edsl.questions.register_questions_meta import RegisterQuestionsMeta


        if input_mode == "path":
            return _load_jobs_from_path(input_path)

        if input_mode == "jobs":
            return _load_jobs_from_path(jobs_path)

        if input_mode == "survey":
            data = read_json_file(survey_path)
            sv = SurveyClass.from_dict(data)
            return Jobs(survey=sv)

        if input_mode in ("json", "stdin"):
            raw_str = json_str if input_mode == "json" else stdin_data
            try:
                data = json.loads(raw_str)
            except json.JSONDecodeError as e:
                error("INVALID_JSON", f"Failed to parse JSON: {e}", exit_code=EXIT_USAGE)
            return _build_job_from_json(data)

        if input_mode == "question":
            qname = question_name or "q0"
            type_map = RegisterQuestionsMeta.question_types_to_classes()
            if question_type not in type_map:
                error("UNKNOWN_QUESTION_TYPE", f"Unknown type: '{question_type}'",
                       suggestion=f"Available: {', '.join(sorted(type_map.keys()))}",
                       exit_code=EXIT_USAGE)
            kwargs = {"question_name": qname, "question_text": question_text}
            if question_options:
                try:
                    kwargs["question_options"] = json.loads(question_options)
                except json.JSONDecodeError:
                    error("INVALID_JSON", "Failed to parse --options as JSON array.",
                           exit_code=EXIT_USAGE)
            cls = type_map[question_type]
            q = cls(**kwargs)
            sv = SurveyClass(questions=[q])
            return Jobs(survey=sv)

        error("USAGE_ERROR", f"Unknown input mode: {input_mode}", exit_code=EXIT_USAGE)


    def _load_jobs_from_path(path: str):
        path_obj = Path(path)
        if path_obj.suffix == ".ep":
            from edsl.jobs import Jobs

            return Jobs.git.load(path_obj)
        data = read_json_file(path)
        from edsl.jobs import Jobs

        return Jobs.from_dict(data)


    def _build_job_from_json(data: dict):
        """Build a Jobs from parsed JSON, auto-detecting shape."""
        from edsl.jobs import Jobs
        from edsl.surveys import Survey as SurveyClass
        from edsl.agents import Agent
        from edsl.scenarios import Scenario
        from edsl.language_models import Model as ModelClass
        from edsl.questions.register_questions_meta import RegisterQuestionsMeta

        # Shape 1: serialized Jobs (has "survey" key)
        if "survey" in data and isinstance(data["survey"], dict):
            return Jobs.from_dict(data)

        # Shape 2: lightweight job spec (has "questions" array)
        if "questions" in data and isinstance(data["questions"], list):
            type_map = RegisterQuestionsMeta.question_types_to_classes()
            questions = []
            for i, qd in enumerate(data["questions"]):
                qtype = qd.pop("type", qd.pop("question_type", "free_text"))
                if "question_name" not in qd:
                    qd["question_name"] = f"q{i}"
                if qtype not in type_map:
                    error("UNKNOWN_QUESTION_TYPE", f"Unknown type in questions[{i}]: '{qtype}'",
                           exit_code=EXIT_VALIDATION)
                questions.append(type_map[qtype](**qd))

            sv = SurveyClass(questions=questions)
            agents = [Agent(traits=a.get("traits", a)) for a in data.get("agents", [])]
            scenarios = [Scenario(s) for s in data.get("scenarios", [])]
            models_list = [ModelClass(m) if isinstance(m, str) else ModelClass(**m) for m in data.get("models", [])]

            return Jobs(
                survey=sv,
                agents=agents or None,
                models=models_list or None,
                scenarios=scenarios or None,
            )

        # Shape 3: single question shorthand
        if "type" in data and "question_text" in data:
            type_map = RegisterQuestionsMeta.question_types_to_classes()
            qtype = data.pop("type", data.pop("question_type", "free_text"))
            if "question_name" not in data:
                data["question_name"] = "q0"
            if qtype not in type_map:
                error("UNKNOWN_QUESTION_TYPE", f"Unknown type: '{qtype}'",
                       exit_code=EXIT_VALIDATION)
            q = type_map[qtype](**{k: v for k, v in data.items() if k != "question_type"})
            sv = SurveyClass(questions=[q])
            return Jobs(survey=sv)

        error("VALIDATION_ERROR",
               "Could not determine JSON shape. Expected serialized Jobs, lightweight job spec, or single question.",
               suggestion="Use 'ep schema survey' to see accepted shapes.",
               exit_code=EXIT_VALIDATION)


    def _read_stdin() -> Optional[str]:
        if sys.stdin.isatty():
            return None
        return sys.stdin.read()
