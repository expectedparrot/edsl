#!/usr/bin/env python3
"""
Reports CLI - Generate reports from EDSL Results objects
"""

import typer
from pathlib import Path
from typing import Optional, List
import gzip
import json
import sys
import os
import textwrap
import yaml

from edsl import Results
from reports.report import Report
from reports.research import Research
from reports.warning_utils import (
    print_info,
    print_success,
    setup_warning_capture,
)

# Optional interactive dependency
try:
    import questionary  # type: ignore
except ImportError:  # pragma: no cover
    questionary = None

app = typer.Typer(help="Generate reports from EDSL Results objects")


@app.command()
def generate(
    json_gz_file: Optional[str] = typer.Option(
        None, "--json-gz-file", help="Path to results.json.gz file"
    ),
    coop_uuid: Optional[str] = typer.Option(
        None, "--coop-uuid", help="UUID to fetch results using Results.pull()"
    ),
    output: Optional[str] = typer.Option(
        None,
        "--output",
        "-o",
        help="Output file path (extension determines format: .html, .docx, .pptx, .pdf, .ipynb)",
    ),
    format: Optional[str] = typer.Option(
        None,
        "--format",
        "-f",
        help="Output format: html, docx, pptx, pdf, notebook, or all",
    ),
    execute: bool = typer.Option(
        False,
        "--execute",
        "-e",
        help="Execute notebook after generation (only for .ipynb format)",
    ),
    include_questions: Optional[str] = typer.Option(
        None,
        "--include-questions",
        "-i",
        help=(
            "Comma-separated list of question names to include in the report. "
            "If omitted, all questions are considered."
        ),
    ),
    exclude_questions: Optional[str] = typer.Option(
        None,
        "--exclude-questions",
        "-x",
        help=(
            "Comma-separated list of question names to exclude from the report. "
            "Applied after include filtering."
        ),
    ),
    include_interactions: Optional[str] = typer.Option(
        None,
        "--include-interactions",
        help=(
            "Comma-separated list of 2-way interactions to include in the report. "
            "Format: 'question1:question2,question3:question4'. "
            "If omitted, all possible interactions are considered."
        ),
    ),
    exclude_interactions: Optional[str] = typer.Option(
        None,
        "--exclude-interactions",
        help=(
            "Comma-separated list of 2-way interactions to exclude from the report. "
            "Format: 'question1:question2,question3:question4'. "
            "Applied after include filtering."
        ),
    ),
    no_interactions: bool = typer.Option(
        False,
        "--no-interactions",
        is_flag=True,
        help="Disable all interaction analysis in the report.",
    ),
    interactive: bool = typer.Option(
        False,
        "--interactive",
        "-I",
        is_flag=True,
        help="Launch interactive prompt to choose questions at runtime. Overrides --include-questions/--exclude-questions.",
    ),
    lorem_ipsum: bool = typer.Option(
        False,
        "--lorem-ipsum",
        is_flag=True,
        help="Use lorem ipsum text instead of LLM-generated analysis writeups.",
    ),
    include_questions_table: bool = typer.Option(
        True,
        "--include-questions-table/--no-questions-table",
        help="Include the questions summary table in the report.",
    ),
    include_respondents_section: bool = typer.Option(
        True,
        "--include-respondents-section/--no-respondents-section",
        help="Include the respondents overview section in the report.",
    ),
    include_scenario_section: bool = typer.Option(
        True,
        "--include-scenario-section/--no-scenario-section",
        help="Include the scenario overview section in the report.",
    ),
    include_overview: bool = typer.Option(
        True,
        "--include-overview/--no-overview",
        help="Include the survey overview section in the report.",
    ),
    sample: Optional[int] = typer.Option(
        None,
        "--sample",
        help="Number of Result objects to randomly sample (without replacement) for the report.",
    ),
    seed: Optional[int] = typer.Option(
        None,
        "--seed",
        help="Random seed for reproducible sampling when using --sample.",
    ),
    free_text_sample_size: Optional[str] = typer.Option(
        None,
        "--free-text-sample-size",
        help=(
            "Sample size for free text questions to reduce compute overhead. "
            "Can be global (e.g., '100') or question-specific (e.g., 'question1:50,question2:100'). "
            "Global setting applies to all free text questions unless overridden."
        ),
    ),
    exclude_question_types: Optional[str] = typer.Option(
        None,
        "--exclude-question-types",
        help=(
            "Comma-separated list of question types to exclude from analysis. "
            "Supported types: free_text, multiple_choice, linear_scale, checkbox, numerical. "
            "Example: --exclude-question-types 'free_text,checkbox'"
        ),
    ),
):
    """
    Generate a report from a Results object.

    Input sources (in order of precedence):
    1. --json-gz-file: Path to a gzipped JSON file
    2. --coop-uuid: UUID to fetch from remote
    3. stdin: JSON piped to the command (automatic if no other options specified)
    """

    # Validate input arguments
    if json_gz_file is not None and coop_uuid is not None:
        typer.echo(
            "Error: Cannot specify both --json-gz-file and --coop-uuid", err=True
        )
        raise typer.Exit(1)

    # Determine input source
    use_stdin = json_gz_file is None and coop_uuid is None

    # Load results
    if json_gz_file is not None:
        print_info(f"Loading results from file: {json_gz_file}")
        if not Path(json_gz_file).exists():
            typer.echo(f"Error: File not found: {json_gz_file}", err=True)
            raise typer.Exit(1)
        try:
            with gzip.open(json_gz_file, "rt") as f:
                results_data = json.load(f)
            results = Results.from_dict(results_data)
        except Exception as e:
            typer.echo(f"Error loading results file: {e}", err=True)
            raise typer.Exit(1)
    elif coop_uuid is not None:
        print_info(f"Fetching results with UUID: {coop_uuid}")
        try:
            results = Results.pull(coop_uuid)
        except Exception as e:
            typer.echo(f"Error fetching results: {e}", err=True)
            raise typer.Exit(1)
    else:
        # use_stdin is True
        print_info("Reading JSON from stdin...")
        try:
            stdin_data = sys.stdin.read()
            if not stdin_data.strip():
                typer.echo("Error: No data received from stdin", err=True)
                raise typer.Exit(1)
            results_data = json.loads(stdin_data)
            results = Results.from_dict(results_data)
        except json.JSONDecodeError as e:
            typer.echo(f"Error parsing JSON from stdin: {e}", err=True)
            raise typer.Exit(1)
        except Exception as e:
            typer.echo(f"Error loading results from stdin: {e}", err=True)
            raise typer.Exit(1)

    # Apply sampling if requested
    if sample is not None:
        if sample <= 0:
            typer.echo("Error: --sample must be a positive integer", err=True)
            raise typer.Exit(1)

        total_results = len(results)
        if sample >= total_results:
            print_info(
                f"Sample size ({sample}) >= total results ({total_results}). Using all results."
            )
        else:
            print_info(
                f"Sampling {sample} results from {total_results} total results..."
            )

            # Use Results.sample() method with seed if provided
            seed_str = str(seed) if seed is not None else None
            if seed is not None:
                print_info(f"Using random seed: {seed}")

            # Sample without replacement
            results = results.sample(n=sample, with_replacement=False, seed=seed_str)
            print_info(f"Successfully sampled {len(results)} results.")

    # Parse free text sample size configuration
    free_text_sample_config = {}
    if free_text_sample_size is not None:
        if "," in free_text_sample_size or ":" in free_text_sample_size:
            # Question-specific format: "question1:50,question2:100"
            for item in free_text_sample_size.split(","):
                item = item.strip()
                if ":" in item:
                    question_name, size_str = item.split(":", 1)
                    try:
                        size = int(size_str.strip())
                        if size <= 0:
                            typer.echo(
                                f"Error: Sample size must be positive for question '{question_name.strip()}'",
                                err=True,
                            )
                            raise typer.Exit(1)
                        free_text_sample_config[question_name.strip()] = size
                    except ValueError:
                        typer.echo(
                            f"Error: Invalid sample size '{size_str}' for question '{question_name.strip()}'",
                            err=True,
                        )
                        raise typer.Exit(1)
                else:
                    typer.echo(
                        f"Error: Invalid format '{item}'. Expected 'question:size' or global number.",
                        err=True,
                    )
                    raise typer.Exit(1)
        else:
            # Global format: "100"
            try:
                global_size = int(free_text_sample_size.strip())
                if global_size <= 0:
                    typer.echo(
                        "Error: Global free text sample size must be positive", err=True
                    )
                    raise typer.Exit(1)
                free_text_sample_config["_global"] = global_size
                print_info(f"Using global free text sample size: {global_size}")
            except ValueError:
                typer.echo(
                    f"Error: Invalid global sample size '{free_text_sample_size}'",
                    err=True,
                )
                raise typer.Exit(1)

        if free_text_sample_config:
            print_info(f"Free text sampling configured: {free_text_sample_config}")

    # Parse exclude question types configuration
    exclude_question_types_list = None
    if exclude_question_types is not None and exclude_question_types.strip():
        valid_types = {
            "free_text",
            "multiple_choice",
            "linear_scale",
            "checkbox",
            "numerical",
        }
        exclude_question_types_list = []
        for q_type in exclude_question_types.split(","):
            q_type = q_type.strip()
            if q_type:
                if q_type not in valid_types:
                    typer.echo(
                        f"Error: Invalid question type '{q_type}'. Supported types: {', '.join(sorted(valid_types))}",
                        err=True,
                    )
                    raise typer.Exit(1)
                exclude_question_types_list.append(q_type)

        if exclude_question_types_list:
            print_info(
                f"Excluding question types: {', '.join(exclude_question_types_list)}"
            )
        else:
            exclude_question_types_list = None

    # Create report
    print_info("Creating report...")

    # ------------------------------------------------------------------
    # Determine question filters (interactive overrides CLI parameters)
    # ------------------------------------------------------------------

    def _interactive_select_questions(
        res: "Results",
    ) -> tuple[Optional[List[str]], Optional[List[str]]]:
        """Return include_list, exclude_list chosen interactively."""

        question_names = [q.question_name for q in res.survey.questions]

        stdin_is_tty = sys.stdin.isatty()

        # --------------------------------------------
        # Fancy TUI using questionary if both present:
        #  - library available
        #  - we have a real TTY available for in/out
        # --------------------------------------------
        if questionary is not None and stdin_is_tty:
            selected = questionary.checkbox(
                "Select questions to include in the analysis:",
                choices=question_names,
            ).ask()

            if selected is None:  # User cancelled (Ctrl-C) or similar
                typer.echo("Interactive selection aborted.", err=True)
                raise typer.Exit(1)

            include_lst: Optional[List[str]] = (
                selected if selected else None
            )  # None means all
            return include_lst, None  # Exclude list not gathered interactively

        # -------------------------------------------------------
        # Fallback: simple comma-separated prompt via /dev/tty.
        # (works even when stdin is being used for piped data).
        # -------------------------------------------------------

        # Try opening the controlling TTY for input/output
        try:
            tty_path = os.ctermid() if hasattr(os, "ctermid") else "/dev/tty"
            with open(tty_path, "r") as tty_in, open(tty_path, "w") as tty_out:
                # Display choices
                tty_out.write("Available questions:\n")
                for idx, name in enumerate(question_names, 1):
                    tty_out.write(f"  {idx}: {name}\n")
                tty_out.write(
                    textwrap.dedent(
                        """
                    Enter comma-separated numbers or names to include (blank for all): """
                    )
                )
                tty_out.flush()

                selection_str = tty_in.readline().strip()

        except Exception:
            # As a last resort, use a non-interactive default (all questions)
            typer.echo(
                "Warning: Unable to open a TTY for interactive selection – including all questions by default."
            )
            return None, None

        if not selection_str:
            return None, None  # include all questions

        tokens = [s.strip() for s in selection_str.split(",") if s.strip()]
        include_lst: List[str] = []
        for token in tokens:
            if token.isdigit():
                index = int(token) - 1
                if 0 <= index < len(question_names):
                    include_lst.append(question_names[index])
                else:
                    typer.echo(f"Ignoring invalid index: {token}", err=True)
            else:
                if token in question_names:
                    include_lst.append(token)
                else:
                    typer.echo(f"Ignoring invalid name: {token}", err=True)

        if not include_lst:
            return None, None

        return include_lst, None

    # Use interactive mode if requested
    if interactive:
        include_list, exclude_list = _interactive_select_questions(results)

        # Interactive mode doesn't support interaction filtering yet
        include_interactions_list = None
        exclude_interactions_list = None

        # --------------------------------------------------------------
        # Determine analyses (single / pairwise combos) to include
        # --------------------------------------------------------------

        def _generate_combinations(qs: List[str]) -> List[List[str]]:
            from itertools import combinations

            singles = [[q] for q in qs]
            pairs = [list(c) for c in combinations(qs, 2)]
            return singles + pairs

        # Reproduce filtered question list logic (same as Report)
        all_question_names = [q.question_name for q in results.survey.questions]
        filtered_questions = (
            include_list if include_list is not None else all_question_names
        )
        if exclude_list:
            filtered_questions = [
                q for q in filtered_questions if q not in exclude_list
            ]

        available_combos = _generate_combinations(filtered_questions)

        analyses_list: Optional[List[List[str]]]
        analysis_output_filters: dict[tuple[str, ...], List[str]] = {}

        # -------------------------
        # Analyses prompt
        # -------------------------
        if len(available_combos) <= 1:
            analyses_list = available_combos  # single combo or empty
        else:

            def _analysis_label(combo: List[str]) -> str:
                return " & ".join(combo)

            stdin_is_tty = sys.stdin.isatty()

            if questionary is not None and stdin_is_tty:
                combo_choices = [_analysis_label(c) for c in available_combos]
                selected_labels = questionary.checkbox(
                    "Select analyses to include:",
                    choices=combo_choices,
                ).ask()

                if selected_labels is None:
                    typer.echo("Interactive selection aborted.", err=True)
                    raise typer.Exit(1)

                if selected_labels:
                    label_to_combo = {_analysis_label(c): c for c in available_combos}
                    analyses_list = [label_to_combo[l] for l in selected_labels]
                else:
                    analyses_list = None  # none selected means include all
            else:
                # Fallback prompt via /dev/tty
                try:
                    tty_path = os.ctermid() if hasattr(os, "ctermid") else "/dev/tty"
                    with open(tty_path, "r") as tty_in, open(tty_path, "w") as tty_out:
                        tty_out.write(
                            "Available analyses (comma-separated numbers to include, blank for all):\n"
                        )
                        for idx, combo in enumerate(available_combos, 1):
                            tty_out.write(f"  {idx}: {_analysis_label(combo)}\n")
                        tty_out.write("Selection: ")
                        tty_out.flush()
                        selection_str = tty_in.readline().strip()
                except Exception:
                    typer.echo(
                        "Warning: Unable to open TTY for analyses selection – including all analyses."
                    )
                    selection_str = ""

                if not selection_str:
                    analyses_list = None  # include all
                else:
                    tokens = [t.strip() for t in selection_str.split(",") if t.strip()]
                    selected_indices: List[int] = []
                    for tok in tokens:
                        if tok.isdigit():
                            selected_indices.append(int(tok) - 1)
                    analyses_list = [
                        available_combos[i]
                        for i in selected_indices
                        if 0 <= i < len(available_combos)
                    ]
                    if not analyses_list:
                        analyses_list = None  # fallback to all if nothing valid
        # End analyses selection

        # -------------------------
        # Per-analysis output type prompts
        # -------------------------


        # Resolve which analyses we will run (use analyses_list or all combos)
        analyses_to_iterate = (
            analyses_list if analyses_list is not None else available_combos
        )

        for combo in analyses_to_iterate:
            # Instantiate a temporary Research to know available outputs
            available_outputs = Research.get_possible_output_names(results, combo)

            if not available_outputs:
                # Nothing available, skip selection
                continue

            prompt_title = f"Select outputs for {' & '.join(combo)} (blank for all):"

            stdin_is_tty = sys.stdin.isatty()

            selected_for_combo: List[str] | None = None

            if questionary is not None and stdin_is_tty:
                sel = questionary.checkbox(
                    prompt_title, choices=available_outputs
                ).ask()
                if sel is None:
                    typer.echo("Interactive selection aborted.", err=True)
                    raise typer.Exit(1)
                selected_for_combo = sel if sel else None
            else:
                # Fallback tty prompt
                try:
                    tty_path = os.ctermid() if hasattr(os, "ctermid") else "/dev/tty"
                    with open(tty_path, "r") as tty_in, open(tty_path, "w") as tty_out:
                        tty_out.write(
                            f"Available outputs for {' & '.join(combo)} (comma-separated numbers, blank for all):\n"
                        )
                        for idx, name in enumerate(available_outputs, 1):
                            tty_out.write(f"  {idx}: {name}\n")
                        tty_out.write("Selection: ")
                        tty_out.flush()
                        selection_str = tty_in.readline().strip()
                except Exception:
                    selection_str = ""

                if selection_str:
                    tokens = [t.strip() for t in selection_str.split(",") if t.strip()]
                    selected_indices = [int(tok) - 1 for tok in tokens if tok.isdigit()]
                    selected_for_combo = [
                        available_outputs[i]
                        for i in selected_indices
                        if 0 <= i < len(available_outputs)
                    ]
                    if not selected_for_combo:
                        selected_for_combo = None

            if selected_for_combo is not None:
                analysis_output_filters[tuple(combo)] = selected_for_combo
        # End per-analysis output selection
    else:
        # Parse include/exclude question strings into lists
        include_list = (
            [q.strip() for q in include_questions.split(",") if q.strip()]
            if include_questions is not None and include_questions.strip()
            else None
        )
        exclude_list = (
            [q.strip() for q in exclude_questions.split(",") if q.strip()]
            if exclude_questions is not None and exclude_questions.strip()
            else None
        )

        # Parse include/exclude interaction strings into lists
        include_interactions_list = None
        exclude_interactions_list = None

        # If --no-interactions is specified, disable all interactions
        if no_interactions:
            include_interactions_list = []  # Empty list means no interactions
        else:
            if include_interactions is not None and include_interactions.strip():
                include_interactions_list = []
                for interaction_str in include_interactions.split(","):
                    interaction_str = interaction_str.strip()
                    if interaction_str:
                        parts = [part.strip() for part in interaction_str.split(":")]
                        if len(parts) == 2:
                            include_interactions_list.append(parts)
                        else:
                            typer.echo(
                                f"Error: Invalid interaction format '{interaction_str}'. Expected 'question1:question2'",
                                err=True,
                            )
                            raise typer.Exit(1)

            if exclude_interactions is not None and exclude_interactions.strip():
                exclude_interactions_list = []
                for interaction_str in exclude_interactions.split(","):
                    interaction_str = interaction_str.strip()
                    if interaction_str:
                        parts = [part.strip() for part in interaction_str.split(":")]
                        if len(parts) == 2:
                            exclude_interactions_list.append(parts)
                        else:
                            typer.echo(
                                f"Error: Invalid interaction format '{interaction_str}'. Expected 'question1:question2'",
                                err=True,
                            )
                            raise typer.Exit(1)

        analyses_list = None
        analysis_output_filters = {}

    report = Report(
        results,
        include_questions=include_list,
        exclude_questions=exclude_list,
        exclude_question_types=exclude_question_types_list,
        include_interactions=include_interactions_list,
        exclude_interactions=exclude_interactions_list,
        analyses=analyses_list,
        analysis_output_filters=analysis_output_filters,
        lorem_ipsum=lorem_ipsum,
        include_questions_table=include_questions_table,
        include_respondents_section=include_respondents_section,
        include_scenario_section=include_scenario_section,
        include_overview=include_overview,
        free_text_sample_config=free_text_sample_config,
    )

    # Determine output format and filename
    if format is None and output is None:
        # Default to HTML format only
        output_format = "html"
        output_file = "report.html"
    elif format is None and output is not None:
        # Infer format from output file extension
        ext = Path(output).suffix.lower()
        if ext == ".html":
            output_format = "html"
        elif ext == ".docx":
            output_format = "docx"
        elif ext == ".pptx":
            output_format = "pptx"
        elif ext == ".pdf":
            output_format = "pdf"
        elif ext == ".ipynb":
            output_format = "notebook"
        else:
            typer.echo(
                f"Unknown file extension: {ext}. Supported: .html, .docx, .pptx, .pdf, .ipynb",
                err=True,
            )
            raise typer.Exit(1)
        output_file = output
    elif format is not None and output is None:
        # Use format, generate filename
        output_format = format.lower()
        if output_format == "html":
            output_file = "report.html"
        elif output_format == "docx":
            output_file = "report.docx"
        elif output_format == "pptx":
            output_file = "report.pptx"
        elif output_format == "pdf":
            output_file = "report.pdf"
        elif output_format == "notebook":
            output_file = "report.ipynb"
        elif output_format == "all":
            output_format = "all"
            output_file = "report"  # Base filename for all formats
        else:
            typer.echo(
                f"Unknown format: {format}. Supported: html, docx, pptx, pdf, notebook, all",
                err=True,
            )
            raise typer.Exit(1)
    else:
        # Both format and output specified
        output_format = format.lower()
        output_file = output

    # Generate report
    try:
        if output_format == "all":
            print_info("Generating all report formats...")

            # Generate HTML
            html_file = f"{output_file}.html"
            report.generate_html(html_file)
            print_success(f"HTML report generated: {html_file}")

            # Generate DOCX
            docx_file = f"{output_file}.docx"
            report.generate_docx(docx_file)
            print_success(f"DOCX report generated: {docx_file}")

            # Generate PPTX
            pptx_file = f"{output_file}.pptx"
            try:
                report.generate_pptx(pptx_file)
                print_success(f"PPTX presentation generated: {pptx_file}")
            except Exception as e:
                typer.echo(f"Warning: PPTX generation failed: {e}", err=True)
                print_info("PPTX generation requires python-pptx")

            # Generate PDF
            pdf_file = f"{output_file}.pdf"
            try:
                report.generate_pdf(pdf_file)
                print_success(f"PDF report generated: {pdf_file}")
            except Exception as e:
                typer.echo(f"Warning: PDF generation failed: {e}", err=True)
                print_info("PDF generation requires pandoc")

            # Generate Notebook
            notebook_file = f"{output_file}.ipynb"
            report.generate_notebook(notebook_file, execute=execute)
            print_success(f"Notebook generated: {notebook_file}")

            print_success(f"All reports generated with base name: {output_file}")

        else:
            print_info(f"Generating {output_format.upper()} report...")

            if output_format == "html":
                report.generate_html(output_file)
            elif output_format == "docx":
                report.generate_docx(output_file)
            elif output_format == "pptx":
                report.generate_pptx(output_file)
            elif output_format == "pdf":
                report.generate_pdf(output_file)
            elif output_format == "notebook":
                report.generate_notebook(output_file, execute=execute)
            else:
                typer.echo(f"Unsupported format: {output_format}", err=True)
                raise typer.Exit(1)

            print_success(f"Report generated successfully: {output_file}")

    except Exception as e:
        typer.echo(f"Error generating report: {e}", err=True)

        # Show full traceback for debugging
        import traceback

        typer.echo("\nFull traceback:", err=True)
        typer.echo(traceback.format_exc(), err=True)

        raise typer.Exit(1)


@app.command()
def generate_config(
    json_gz_file: Optional[str] = typer.Option(
        None, "--json-gz-file", help="Path to results.json.gz file"
    ),
    coop_uuid: Optional[str] = typer.Option(
        None, "--coop-uuid", help="UUID to fetch results using Results.pull()"
    ),
    output: Optional[str] = typer.Option(
        "report_config.yaml", "--output", "-o", help="Output YAML config file path"
    ),
    include_questions: Optional[str] = typer.Option(
        None,
        "--include-questions",
        "-i",
        help=(
            "Comma-separated list of question names to include in the report. "
            "If omitted, all questions are considered."
        ),
    ),
    exclude_questions: Optional[str] = typer.Option(
        None,
        "--exclude-questions",
        "-x",
        help=(
            "Comma-separated list of question names to exclude from the report. "
            "Applied after include filtering."
        ),
    ),
    include_interactions: Optional[str] = typer.Option(
        None,
        "--include-interactions",
        help=(
            "Comma-separated list of 2-way interactions to include in the report. "
            "Format: 'question1:question2,question3:question4'. "
            "If omitted, all possible interactions are considered."
        ),
    ),
    exclude_interactions: Optional[str] = typer.Option(
        None,
        "--exclude-interactions",
        help=(
            "Comma-separated list of 2-way interactions to exclude from the report. "
            "Format: 'question1:question2,question3:question4'. "
            "Applied after include filtering."
        ),
    ),
    no_interactions: bool = typer.Option(
        False,
        "--no-interactions",
        is_flag=True,
        help="Disable all interaction analysis in the report.",
    ),
    interactive: bool = typer.Option(
        False,
        "--interactive",
        "-I",
        is_flag=True,
        help="Launch interactive prompt to choose questions at runtime. Overrides --include-questions/--exclude-questions.",
    ),
    lorem_ipsum: bool = typer.Option(
        False,
        "--lorem-ipsum",
        is_flag=True,
        help="Use lorem ipsum text instead of LLM-generated analysis writeups.",
    ),
    include_questions_table: bool = typer.Option(
        True,
        "--include-questions-table/--no-questions-table",
        help="Include the questions summary table in the report.",
    ),
    include_respondents_section: bool = typer.Option(
        True,
        "--include-respondents-section/--no-respondents-section",
        help="Include the respondents overview section in the report.",
    ),
    include_scenario_section: bool = typer.Option(
        True,
        "--include-scenario-section/--no-scenario-section",
        help="Include the scenario overview section in the report.",
    ),
    include_overview: bool = typer.Option(
        True,
        "--include-overview/--no-overview",
        help="Include the survey overview section in the report.",
    ),
    sample: Optional[int] = typer.Option(
        None,
        "--sample",
        help="Number of Result objects to randomly sample (without replacement) for the report.",
    ),
    seed: Optional[int] = typer.Option(
        None,
        "--seed",
        help="Random seed for reproducible sampling when using --sample.",
    ),
    free_text_sample_size: Optional[str] = typer.Option(
        None,
        "--free-text-sample-size",
        help=(
            "Sample size for free text questions to reduce compute overhead. "
            "Can be global (e.g., '100') or question-specific (e.g., 'question1:50,question2:100'). "
            "Global setting applies to all free text questions unless overridden."
        ),
    ),
    exclude_question_types: Optional[str] = typer.Option(
        None,
        "--exclude-question-types",
        help=(
            "Comma-separated list of question types to exclude from analysis. "
            "Supported types: free_text, multiple_choice, linear_scale, checkbox, numerical. "
            "Example: --exclude-question-types 'free_text,checkbox'"
        ),
    ),
):
    """
    Generate a YAML configuration file for a report instead of generating the report itself.

    Input sources (in order of precedence):
    1. --json-gz-file: Path to a gzipped JSON file
    2. --coop-uuid: UUID to fetch from remote
    3. stdin: JSON piped to the command (automatic if no other options specified)
    """

    # Validate input arguments
    if json_gz_file is not None and coop_uuid is not None:
        typer.echo(
            "Error: Cannot specify both --json-gz-file and --coop-uuid", err=True
        )
        raise typer.Exit(1)

    # Determine input source
    use_stdin = json_gz_file is None and coop_uuid is None

    # Load results
    if json_gz_file is not None:
        print_info(f"Loading results from file: {json_gz_file}")
        if not Path(json_gz_file).exists():
            typer.echo(f"Error: File not found: {json_gz_file}", err=True)
            raise typer.Exit(1)
        try:
            with gzip.open(json_gz_file, "rt") as f:
                results_data = json.load(f)
            results = Results.from_dict(results_data)
        except Exception as e:
            typer.echo(f"Error loading results file: {e}", err=True)
            raise typer.Exit(1)
    elif coop_uuid is not None:
        print_info(f"Fetching results with UUID: {coop_uuid}")
        try:
            results = Results.pull(coop_uuid)
        except Exception as e:
            typer.echo(f"Error fetching results: {e}", err=True)
            raise typer.Exit(1)
    else:
        # use_stdin is True
        print_info("Reading JSON from stdin...")
        try:
            stdin_data = sys.stdin.read()
            if not stdin_data.strip():
                typer.echo("Error: No data received from stdin", err=True)
                raise typer.Exit(1)
            results_data = json.loads(stdin_data)
            results = Results.from_dict(results_data)
        except json.JSONDecodeError as e:
            typer.echo(f"Error parsing JSON from stdin: {e}", err=True)
            raise typer.Exit(1)
        except Exception as e:
            typer.echo(f"Error loading results from stdin: {e}", err=True)
            raise typer.Exit(1)

    # Apply sampling if requested
    if sample is not None:
        if sample <= 0:
            typer.echo("Error: --sample must be a positive integer", err=True)
            raise typer.Exit(1)

        total_results = len(results)
        if sample >= total_results:
            print_info(
                f"Sample size ({sample}) >= total results ({total_results}). Using all results."
            )
        else:
            print_info(
                f"Sampling {sample} results from {total_results} total results..."
            )

            # Use Results.sample() method with seed if provided
            seed_str = str(seed) if seed is not None else None
            if seed is not None:
                print_info(f"Using random seed: {seed}")

            # Sample without replacement
            results = results.sample(n=sample, with_replacement=False, seed=seed_str)
            print_info(f"Successfully sampled {len(results)} results.")

    # Parse free text sample size configuration (same logic as generate command)
    free_text_sample_config = {}
    if free_text_sample_size is not None:
        if "," in free_text_sample_size or ":" in free_text_sample_size:
            # Question-specific format: "question1:50,question2:100"
            for item in free_text_sample_size.split(","):
                item = item.strip()
                if ":" in item:
                    question_name, size_str = item.split(":", 1)
                    try:
                        size = int(size_str.strip())
                        if size <= 0:
                            typer.echo(
                                f"Error: Sample size must be positive for question '{question_name.strip()}'",
                                err=True,
                            )
                            raise typer.Exit(1)
                        free_text_sample_config[question_name.strip()] = size
                    except ValueError:
                        typer.echo(
                            f"Error: Invalid sample size '{size_str}' for question '{question_name.strip()}'",
                            err=True,
                        )
                        raise typer.Exit(1)
                else:
                    typer.echo(
                        f"Error: Invalid format '{item}'. Expected 'question:size' or global number.",
                        err=True,
                    )
                    raise typer.Exit(1)
        else:
            # Global format: "100"
            try:
                global_size = int(free_text_sample_size.strip())
                if global_size <= 0:
                    typer.echo(
                        "Error: Global free text sample size must be positive", err=True
                    )
                    raise typer.Exit(1)
                free_text_sample_config["_global"] = global_size
                print_info(f"Using global free text sample size: {global_size}")
            except ValueError:
                typer.echo(
                    f"Error: Invalid global sample size '{free_text_sample_size}'",
                    err=True,
                )
                raise typer.Exit(1)

        if free_text_sample_config:
            print_info(f"Free text sampling configured: {free_text_sample_config}")

    # Parse exclude question types configuration
    exclude_question_types_list = None
    if exclude_question_types is not None and exclude_question_types.strip():
        valid_types = {
            "free_text",
            "multiple_choice",
            "linear_scale",
            "checkbox",
            "numerical",
        }
        exclude_question_types_list = []
        for q_type in exclude_question_types.split(","):
            q_type = q_type.strip()
            if q_type:
                if q_type not in valid_types:
                    typer.echo(
                        f"Error: Invalid question type '{q_type}'. Supported types: {', '.join(sorted(valid_types))}",
                        err=True,
                    )
                    raise typer.Exit(1)
                exclude_question_types_list.append(q_type)

        if exclude_question_types_list:
            print_info(
                f"Excluding question types: {', '.join(exclude_question_types_list)}"
            )
        else:
            exclude_question_types_list = None

    # Create configuration
    print_info("Creating configuration...")

    # Use the same logic as the generate command for determining question filters
    if interactive:
        include_list, exclude_list = _interactive_select_questions(results)

        # Interactive mode doesn't support interaction filtering yet
        include_interactions_list = None
        exclude_interactions_list = None

        # Generate combinations and get analyses list
        def _generate_combinations(qs: List[str]) -> List[List[str]]:
            from itertools import combinations

            singles = [[q] for q in qs]
            pairs = [list(c) for c in combinations(qs, 2)]
            return singles + pairs

        all_question_names = [q.question_name for q in results.survey.questions]
        filtered_questions = (
            include_list if include_list is not None else all_question_names
        )
        if exclude_list:
            filtered_questions = [
                q for q in filtered_questions if q not in exclude_list
            ]

        available_combos = _generate_combinations(filtered_questions)
        analyses_list: Optional[List[List[str]]]
        analysis_output_filters: dict[tuple[str, ...], List[str]] = {}

        # Interactive selection for analyses and outputs (reuse logic from generate command)
        if len(available_combos) <= 1:
            analyses_list = available_combos
        else:

            def _analysis_label(combo: List[str]) -> str:
                return " & ".join(combo)

            stdin_is_tty = sys.stdin.isatty()

            if questionary is not None and stdin_is_tty:
                combo_choices = [_analysis_label(c) for c in available_combos]
                selected_labels = questionary.checkbox(
                    "Select analyses to include:",
                    choices=combo_choices,
                ).ask()

                if selected_labels is None:
                    typer.echo("Interactive selection aborted.", err=True)
                    raise typer.Exit(1)

                if selected_labels:
                    label_to_combo = {_analysis_label(c): c for c in available_combos}
                    analyses_list = [label_to_combo[l] for l in selected_labels]
                else:
                    analyses_list = None
            else:
                # Fallback prompt via /dev/tty
                try:
                    tty_path = os.ctermid() if hasattr(os, "ctermid") else "/dev/tty"
                    with open(tty_path, "r") as tty_in, open(tty_path, "w") as tty_out:
                        tty_out.write(
                            "Available analyses (comma-separated numbers to include, blank for all):\n"
                        )
                        for idx, combo in enumerate(available_combos, 1):
                            tty_out.write(f"  {idx}: {_analysis_label(combo)}\n")
                        tty_out.write("Selection: ")
                        tty_out.flush()
                        selection_str = tty_in.readline().strip()
                except Exception:
                    typer.echo(
                        "Warning: Unable to open TTY for analyses selection – including all analyses."
                    )
                    selection_str = ""

                if not selection_str:
                    analyses_list = None
                else:
                    tokens = [t.strip() for t in selection_str.split(",") if t.strip()]
                    selected_indices: List[int] = []
                    for tok in tokens:
                        if tok.isdigit():
                            selected_indices.append(int(tok) - 1)
                    analyses_list = [
                        available_combos[i]
                        for i in selected_indices
                        if 0 <= i < len(available_combos)
                    ]
                    if not analyses_list:
                        analyses_list = None

        # Per-analysis output type prompts
        analyses_to_iterate = (
            analyses_list if analyses_list is not None else available_combos
        )

        for combo in analyses_to_iterate:
            available_outputs = Research.get_possible_output_names(results, combo)

            if not available_outputs:
                continue

            prompt_title = f"Select outputs for {' & '.join(combo)} (blank for all):"
            stdin_is_tty = sys.stdin.isatty()
            selected_for_combo: List[str] | None = None

            if questionary is not None and stdin_is_tty:
                sel = questionary.checkbox(
                    prompt_title, choices=available_outputs
                ).ask()
                if sel is None:
                    typer.echo("Interactive selection aborted.", err=True)
                    raise typer.Exit(1)
                selected_for_combo = sel if sel else None
            else:
                # Fallback tty prompt
                try:
                    tty_path = os.ctermid() if hasattr(os, "ctermid") else "/dev/tty"
                    with open(tty_path, "r") as tty_in, open(tty_path, "w") as tty_out:
                        tty_out.write(
                            f"Available outputs for {' & '.join(combo)} (comma-separated numbers, blank for all):\n"
                        )
                        for idx, name in enumerate(available_outputs, 1):
                            tty_out.write(f"  {idx}: {name}\n")
                        tty_out.write("Selection: ")
                        tty_out.flush()
                        selection_str = tty_in.readline().strip()
                except Exception:
                    selection_str = ""

                if selection_str:
                    tokens = [t.strip() for t in selection_str.split(",") if t.strip()]
                    selected_indices = [int(tok) - 1 for tok in tokens if tok.isdigit()]
                    selected_for_combo = [
                        available_outputs[i]
                        for i in selected_indices
                        if 0 <= i < len(available_outputs)
                    ]
                    if not selected_for_combo:
                        selected_for_combo = None

            if selected_for_combo is not None:
                analysis_output_filters[tuple(combo)] = selected_for_combo
    else:
        # Parse include/exclude question strings into lists
        include_list = (
            [q.strip() for q in include_questions.split(",") if q.strip()]
            if include_questions is not None and include_questions.strip()
            else None
        )
        exclude_list = (
            [q.strip() for q in exclude_questions.split(",") if q.strip()]
            if exclude_questions is not None and exclude_questions.strip()
            else None
        )

        # Parse include/exclude interaction strings into lists
        include_interactions_list = None
        exclude_interactions_list = None

        # If --no-interactions is specified, disable all interactions
        if no_interactions:
            include_interactions_list = []  # Empty list means no interactions
        else:
            if include_interactions is not None and include_interactions.strip():
                include_interactions_list = []
                for interaction_str in include_interactions.split(","):
                    interaction_str = interaction_str.strip()
                    if interaction_str:
                        parts = [part.strip() for part in interaction_str.split(":")]
                        if len(parts) == 2:
                            include_interactions_list.append(parts)
                        else:
                            typer.echo(
                                f"Error: Invalid interaction format '{interaction_str}'. Expected 'question1:question2'",
                                err=True,
                            )
                            raise typer.Exit(1)

            if exclude_interactions is not None and exclude_interactions.strip():
                exclude_interactions_list = []
                for interaction_str in exclude_interactions.split(","):
                    interaction_str = interaction_str.strip()
                    if interaction_str:
                        parts = [part.strip() for part in interaction_str.split(":")]
                        if len(parts) == 2:
                            exclude_interactions_list.append(parts)
                        else:
                            typer.echo(
                                f"Error: Invalid interaction format '{interaction_str}'. Expected 'question1:question2'",
                                err=True,
                            )
                            raise typer.Exit(1)

        analyses_list = None
        analysis_output_filters = {}

    # Generate config dictionary
    config = {
        "report_settings": {
            "lorem_ipsum": lorem_ipsum,
            "include_questions_table": include_questions_table,
            "include_respondents_section": include_respondents_section,
            "include_scenario_section": include_scenario_section,
            "include_overview": include_overview,
        },
        "question_filters": {
            "include_questions": include_list,
            "exclude_questions": exclude_list,
        },
        "analyses": [],
    }

    # Create a temporary report to get the actual analyses and output structure
    temp_report = Report(
        results,
        include_questions=include_list,
        exclude_questions=exclude_list,
        exclude_question_types=exclude_question_types_list,
        include_interactions=include_interactions_list,
        exclude_interactions=exclude_interactions_list,
        analyses=analyses_list,
        analysis_output_filters=analysis_output_filters,
        lorem_ipsum=lorem_ipsum,
        include_questions_table=include_questions_table,
        include_respondents_section=include_respondents_section,
        include_scenario_section=include_scenario_section,
        include_overview=include_overview,
        free_text_sample_config=free_text_sample_config,
    )

    # Build the analyses configuration based on the actual report structure
    for question_names, output_dict in temp_report.items():
        analysis_config = {"questions": list(question_names), "outputs": []}

        for output_name, output_obj in output_dict.items():
            display_name = getattr(output_obj, "pretty_short_name", output_name)
            analysis_config["outputs"].append(
                {"name": output_name, "display_name": display_name, "enabled": True}
            )

        config["analyses"].append(analysis_config)

    # Write YAML configuration
    try:
        with open(output, "w") as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)
        print_success(f"Configuration saved to {output}")
    except Exception as e:
        typer.echo(f"Error writing configuration: {e}", err=True)
        raise typer.Exit(1)


if __name__ == "__main__":
    # Setup warning capture before running the app
    setup_warning_capture()
    app()
