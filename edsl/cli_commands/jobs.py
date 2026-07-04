"""Remote job commands for the EDSL CLI."""

from __future__ import annotations

from pathlib import Path

import click

from edsl.cli_shared import (
    EXIT_NOT_FOUND,
    EXIT_REMOTE,
    EXIT_USAGE,
    EXIT_VALIDATION,
    error,
    jsonable,
    load_git_object,
    load_openable_json,
    output,
    save_results,
)


def register(jobs_group: click.Group) -> None:
    @jobs_group.command("list")
    @click.option("--status", "statuses", multiple=True, help="Filter by status. Can be repeated.")
    @click.option("--query", "-q", default=None, help="Search by description.")
    @click.option("--page", default=1, type=int, help="Page number.")
    @click.option("--page_size", default=10, type=int, help="Results per page (max 100).")
    @click.option("--sort_ascending", is_flag=True, default=False, help="Sort oldest first.")
    def jobs_list(statuses, query, page, page_size, sort_ascending):
        """List remote jobs."""
        try:
            from edsl.coop import Coop

            status_filter = list(statuses) or None
            result = Coop().remote_inference_list(
                status=status_filter,
                search_query=query,
                page=page,
                page_size=page_size,
                sort_ascending=sort_ascending,
            )
            jobs_data = jsonable(list(result))
            data = {
                "jobs": jobs_data,
                "page": page,
                "page_size": page_size,
                "returned_count": len(jobs_data),
                "status": status_filter,
                "query": query,
                "sort_ascending": sort_ascending,
            }
            for attr in ("current_page", "total_pages", "total_count"):
                if hasattr(result, attr):
                    data[attr] = getattr(result, attr)
            output(data)
        except SystemExit:
            raise
        except Exception as e:
            error(
                "JOBS_ERROR",
                str(e),
                suggestion="Check your filters and Expected Parrot API key.",
                exit_code=EXIT_REMOTE,
            )

    @jobs_group.command("status")
    @click.argument("job_uuid", required=False)
    @click.option("--results", "results_uuid", default=None, help="Results UUID associated with the job.")
    @click.option("--include_json", is_flag=True, default=False, help="Include serialized job JSON when available.")
    def jobs_status(job_uuid, results_uuid, include_json):
        """Get remote job status."""
        if not job_uuid and not results_uuid:
            error("USAGE_ERROR", "Provide JOB_UUID or --results <uuid>.", exit_code=EXIT_USAGE)
        try:
            from edsl.coop import Coop

            result = Coop().new_remote_inference_get(
                job_uuid=job_uuid,
                results_uuid=results_uuid,
                include_json_string=include_json,
            )
            output(jsonable(result))
        except SystemExit:
            raise
        except Exception as e:
            error(
                "JOBS_ERROR",
                str(e),
                suggestion="Check the job/results UUID and Expected Parrot API key.",
                exit_code=EXIT_REMOTE,
            )

    @jobs_group.command("results")
    @click.argument("job_uuid", required=False)
    @click.option("--results", "results_uuid", default=None, help="Results UUID to fetch directly.")
    @click.option("--output", "-o", "output_path", default=None, help="Save Results to a JSON file or .ep package.")
    def jobs_results(job_uuid, results_uuid, output_path):
        """Fetch results for a completed remote job."""
        if not job_uuid and not results_uuid:
            error("USAGE_ERROR", "Provide JOB_UUID or --results <uuid>.", exit_code=EXIT_USAGE)
        try:
            from edsl.coop import Coop

            coop = Coop()
            status = None
            if not results_uuid:
                status = coop.new_remote_inference_get(job_uuid=job_uuid)
                results_uuid = status.get("results_uuid")
                if not results_uuid:
                    error(
                        "RESULTS_NOT_AVAILABLE",
                        f"No results UUID is available for job: {job_uuid}",
                        suggestion="Use 'edsl jobs status <job_uuid>' to check whether the job has completed.",
                        exit_code=EXIT_NOT_FOUND,
                    )

            results_obj = coop.pull(results_uuid, expected_object_type="results")
            data = {
                "job_uuid": job_uuid,
                "results_uuid": results_uuid,
                "status": status.get("status") if status else None,
                "result_count": len(results_obj) if hasattr(results_obj, "__len__") else None,
            }
            if output_path:
                data["saved"] = save_results(results_obj, output_path)
            output(data)
        except SystemExit:
            raise
        except Exception as e:
            error(
                "JOBS_ERROR",
                str(e),
                suggestion="Check the job/results UUID, output path, and Expected Parrot API key.",
                exit_code=EXIT_REMOTE,
            )

    @jobs_group.command("errors")
    @click.argument("job_uuid")
    @click.option("--output", "-o", "output_path", default=None, help="Write markdown error report to this path.")
    def jobs_errors(job_uuid, output_path):
        """Fetch the latest remote job error report as markdown."""
        try:
            from edsl.coop import Coop

            report = Coop().get_error_report_markdown(job_uuid)
            data = {"job_uuid": job_uuid, "markdown": report, "saved_to": None}
            if output_path:
                path = Path(output_path)
                path.write_text(report, encoding="utf-8")
                data["saved_to"] = str(path)
            output(data)
        except SystemExit:
            raise
        except Exception as e:
            error(
                "JOBS_ERROR",
                str(e),
                suggestion="Check the job UUID and Expected Parrot API key.",
                exit_code=EXIT_REMOTE,
            )

    @jobs_group.command("manifest")
    @click.argument("job_uuid")
    @click.option("--page_size", default=100, type=int, help="Results page size for manifest calculation.")
    def jobs_manifest(job_uuid, page_size):
        """Fetch the paginated results manifest for a remote job."""
        try:
            from edsl.coop import Coop

            output(jsonable(Coop().remote_inference_results_manifest(job_uuid, page_size=page_size)))
        except SystemExit:
            raise
        except Exception as e:
            error(
                "JOBS_ERROR",
                str(e),
                suggestion="Check the job UUID, page size, and Expected Parrot API key.",
                exit_code=EXIT_REMOTE,
            )

    @jobs_group.command("page")
    @click.argument("job_uuid")
    @click.option("--page", "page_number", default=0, type=int, help="Zero-based results page number.")
    @click.option("--page_size", default=100, type=int, help="Results per page.")
    def jobs_page(job_uuid, page_number, page_size):
        """Fetch one raw paginated results page for a remote job."""
        try:
            from edsl.coop import Coop

            output(
                jsonable(
                    Coop().remote_inference_results_page(
                        job_uuid,
                        page=page_number,
                        page_size=page_size,
                    )
                )
            )
        except SystemExit:
            raise
        except Exception as e:
            error(
                "JOBS_ERROR",
                str(e),
                suggestion="Check the job UUID, page arguments, and Expected Parrot API key.",
                exit_code=EXIT_REMOTE,
            )

    @jobs_group.command("cancel")
    @click.argument("job_uuid")
    @click.option("--yes", is_flag=True, default=False, help="Confirm cancellation.")
    def jobs_cancel(job_uuid, yes):
        """Cancel a queued or running remote job."""
        if not yes:
            error(
                "CONFIRMATION_REQUIRED",
                "Cancelling a remote job requires --yes.",
                suggestion="Re-run with --yes if you intend to cancel this job.",
                exit_code=EXIT_USAGE,
            )
        try:
            from edsl.coop import Coop

            output(jsonable(Coop().cancel_remote_inference_job(job_uuid)))
        except SystemExit:
            raise
        except Exception as e:
            error(
                "JOBS_ERROR",
                str(e),
                suggestion="Check the job UUID and Expected Parrot API key.",
                exit_code=EXIT_REMOTE,
            )

    @jobs_group.command("cost")
    @click.argument("object_path", type=click.Path(exists=True))
    @click.option("--iterations", default=1, type=int, help="Number of iterations.")
    def jobs_cost(object_path, iterations):
        """Estimate remote run cost for a local Jobs or Survey object."""
        try:
            from edsl.coop import Coop
            from edsl.jobs import Jobs
            from edsl.surveys import Survey

            obj = _load_costable_object(Path(object_path))
            if not isinstance(obj, (Jobs, Survey)):
                error(
                    "UNSUPPORTED_OBJECT",
                    f"Cost estimation requires a Jobs or Survey object, got {type(obj).__name__}.",
                    exit_code=EXIT_VALIDATION,
                )
            output(jsonable(Coop().remote_inference_cost(obj, iterations=iterations)))
        except SystemExit:
            raise
        except Exception as e:
            error(
                "JOBS_ERROR",
                str(e),
                suggestion="Check the object path, iterations, and Expected Parrot API key.",
                exit_code=EXIT_REMOTE,
            )


def _load_costable_object(path: Path):
    if path.is_dir() or path.suffix == ".ep":
        return load_git_object(path)
    return load_openable_json(path)
