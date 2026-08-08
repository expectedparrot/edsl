#!/usr/bin/env python3
"""Create a study project directory structure."""

import argparse
import json
import os
import re
import shutil
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parent
MAKEFILE_TEMPLATE = (
    SKILL_ROOT / "makefile-template.mk"
).read_text(encoding="utf-8")


COMMON_DIRS = [
    "refs",
    "data/raw",
    "data/cooked",
    "data/uploaded",
    "analysis",
    "computed_objects",
    "writeup/tables",
    "writeup/plots",
    "writeup/numbers",
]

EDSL_DIRS = ["edsl_jobs"]

SIMULATION_DIRS = ["simulations"]

FILES = {
    "Makefile": MAKEFILE_TEMPLATE,
}

SURVEY_SOURCE_TEMPLATE = '''"""Define the approved survey questions."""

from edsl import QuestionFreeText, QuestionMultipleChoice, Survey


# STUDY EDIT: replace these examples with the approved questions.
questions = [
    QuestionMultipleChoice(
        question_name="replace_me",
        question_text="Replace with the approved question.",
        question_options=["Replace me", "Other"],
    ),
    QuestionFreeText(
        question_name="replace_me_reason",
        question_text="Why did you choose {{ replace_me.answer }}?",
    ),
]
survey = Survey(questions)


if __name__ == "__main__":
    survey.git.save("survey.ep")
'''

AGENT_SOURCE_TEMPLATE = '''"""Define the approved simulated respondent panel."""

from edsl import Agent, AgentList


# STUDY EDIT: replace these examples with the approved named personas.
personas = [
    {
        "name": "Replace Me",
        "age": 0,
        "background": "Replace with approved persona traits.",
    },
]

# Keep the reserved name outside traits.
agent_list = AgentList([
    Agent(
        name=persona["name"],
        traits={key: value for key, value in persona.items() if key != "name"},
    )
    for persona in personas
])


if __name__ == "__main__":
    agent_list.git.save("agent_list.ep")
'''

SCENARIO_SOURCE_TEMPLATE = '''"""Define the approved repeated study stimuli."""

from edsl import Scenario, ScenarioList


# STUDY EDIT: replace these examples with the approved stimuli. Keep stable
# identifiers so each Results row can be joined back to the source instrument.
scenarios = [
    {
        "item_id": "replace_me",
        "item_text": "Replace with the approved item or stimulus.",
        "response_type": "Replace with the proposed response type.",
        "response_options": ["Replace me"],
    },
]
scenario_list = ScenarioList([Scenario(values) for values in scenarios])


if __name__ == "__main__":
    scenario_list.git.save("scenario_list.ep")
'''


def create_project(
    root: str,
    jobs: list[str] | None = None,
    study_type: str = "edsl",
    sims: list[str] | None = None,
    template: str | None = None,
    expected_rows: int | None = None,
    required_answers: list[str] | None = None,
    expected_agents: int | None = None,
    required_traits: list[str] | None = None,
    group_trait: str | None = None,
    expected_group_size: int | None = None,
    required_source_domain: str | None = None,
    model: str | None = None,
    run_description: str | None = None,
    with_scenarios: bool = False,
):
    if jobs is None:
        jobs = ["job_a"]
    if sims is None:
        sims = ["sim_a"]
    if required_answers is None:
        required_answers = []
    if required_traits is None:
        required_traits = []
    if template == "survey":
        if study_type != "edsl":
            raise ValueError("the survey template requires --type edsl")
        if expected_rows is None or expected_rows < 1:
            raise ValueError("the survey template requires --expected-rows >= 1")
        if not model or not model.strip():
            raise ValueError("the survey template requires --model")
        if not run_description or not run_description.strip():
            raise ValueError("the survey template requires --run-description")
        if any("\n" in value for value in (model, run_description)):
            raise ValueError("model and run description must be single-line values")
        invalid = [
            name for name in required_answers
            if not re.fullmatch(r"[a-zA-Z][a-zA-Z0-9_]*", name)
        ]
        if invalid:
            raise ValueError(f"invalid answer field names: {invalid}")
    elif with_scenarios:
        raise ValueError("--with-scenarios requires --template survey")
    if template == "agent-list":
        if study_type != "edsl":
            raise ValueError("the agent-list template requires --type edsl")
        if expected_agents is None or expected_agents < 1:
            raise ValueError("the agent-list template requires --expected-agents >= 1")
        names = required_traits + ([group_trait] if group_trait else [])
        invalid = [
            name for name in names
            if not re.fullmatch(r"[a-zA-Z][a-zA-Z0-9_]*", name or "")
        ]
        if invalid:
            raise ValueError(f"invalid trait names: {invalid}")
        if (group_trait is None) != (expected_group_size is None):
            raise ValueError("--group-trait and --expected-group-size must be used together")
        if expected_group_size is not None and expected_group_size < 1:
            raise ValueError("--expected-group-size must be >= 1")
        if required_source_domain and not re.fullmatch(
            r"[a-zA-Z0-9.-]+", required_source_domain
        ):
            raise ValueError("invalid required source domain")

    os.makedirs(root, exist_ok=True)

    # Create common directories
    for d in COMMON_DIRS:
        os.makedirs(os.path.join(root, d), exist_ok=True)

    # Create type-specific directories
    if study_type == "simulation":
        for d in SIMULATION_DIRS:
            os.makedirs(os.path.join(root, d), exist_ok=True)
    else:
        for d in EDSL_DIRS:
            os.makedirs(os.path.join(root, d), exist_ok=True)

    for path, content in FILES.items():
        full = os.path.join(root, path)
        if not os.path.exists(full):
            with open(full, "w") as f:
                f.write(content)

    # Scaffold type-specific sub-directories
    if study_type == "simulation":
        for sim in sims:
            sim_dir = os.path.join(root, "simulations", sim)
            os.makedirs(sim_dir, exist_ok=True)
    else:
        for job in jobs:
            job_dir = os.path.join(root, "edsl_jobs", job)
            os.makedirs(job_dir, exist_ok=True)

    # Copy EP report assets (CSS + LaTeX header + logo + Lua filter) into writeup/
    try:
        from .create_css import create_css, create_latex_header, create_logo, create_lua_filter
        create_css(os.path.join(root, "writeup"))
        create_latex_header(os.path.join(root, "writeup"))
        create_logo(os.path.join(root, "writeup"))
        create_lua_filter(os.path.join(root, "writeup"))
    except Exception:
        pass  # assets are optional

    # Install the versioned plotting API deterministically. Study code imports
    # this local module and never discovers a skill checkout at runtime.
    plot_style = SKILL_ROOT / "plot_style.py"
    destination = Path(root) / "analysis" / "plot_style.py"
    if plot_style.is_file() and not destination.exists():
        shutil.copyfile(plot_style, destination)
    standard_plots = SKILL_ROOT / "build_standard_plots.py"
    standard_plots_destination = Path(root) / "analysis" / "build_standard_plots.py"
    if standard_plots.is_file() and not standard_plots_destination.exists():
        shutil.copyfile(standard_plots, standard_plots_destination)

    if template == "survey":
        job_dir = Path(root) / "edsl_jobs" / "job_a"
        source_templates = {
            job_dir / "study_survey.py": SURVEY_SOURCE_TEMPLATE,
            job_dir / "study_agent_list.py": AGENT_SOURCE_TEMPLATE,
        }
        if with_scenarios:
            source_templates[job_dir / "study_scenario_list.py"] = SCENARIO_SOURCE_TEMPLATE
        for path, content in source_templates.items():
            if not path.exists():
                path.write_text(content, encoding="utf-8")
        workflow_spec = Path(root) / "workflow-gates.json"
        if not workflow_spec.exists():
            workflow_spec.write_text(
                json.dumps(
                    {
                        "gates": [
                            {
                                "name": "plan-approved",
                                "description": "User approved plan.md and its definition of done",
                                "verification": {"type": "user-approval"},
                            },
                            {
                                "name": "results-valid",
                                "description": "Saved results satisfy the planned survey invariants",
                                "verification": {"type": "command", "command": "make qa"},
                            },
                            {
                                "name": "report-validated",
                                "description": "The compiled HTML report passes report checks",
                                "verification": {
                                    "type": "command", "command": "make report-check"
                                },
                            },
                        ]
                    },
                    indent=2,
                ) + "\n",
                encoding="utf-8",
            )

        validator = Path(root) / "analysis" / "validate_results.py"
        if not validator.exists():
            fields = json.dumps(required_answers)
            validator.write_text(
                '''#!/usr/bin/env python3
"""Validate the invariant fields of this survey's saved Results."""

import json
from pathlib import Path

from edsl import Results


EXPECTED_ROWS = %d
REQUIRED_ANSWERS = %s
RESULTS_PATH = Path(__file__).resolve().parents[1] / "data" / "results.ep"


def main() -> int:
    results = Results.git.load(str(RESULTS_PATH))
    errors = []
    if len(results) != EXPECTED_ROWS:
        errors.append(f"expected {EXPECTED_ROWS} rows; found {len(results)}")
    missing = {}
    for field in REQUIRED_ANSWERS:
        count = sum(
            1 for result in results
            if result.answer.get(field) is None or result.answer.get(field) == ""
        )
        if count:
            missing[field] = count
    if missing:
        errors.append(f"missing required answers: {missing}")
    payload = {
        "status": "error" if errors else "ok",
        "data": {
            "result_count": len(results),
            "expected_count": EXPECTED_ROWS,
            "required_answers": REQUIRED_ANSWERS,
            "missing_answers": missing,
        },
        "errors": errors,
    }
    print(json.dumps(payload, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
''' % (expected_rows, fields),
                encoding="utf-8",
            )
        cost_summary = Path(root) / "analysis" / "summarize_run_costs.py"
        if not cost_summary.exists():
            cost_summary.write_text(
                '''#!/usr/bin/env python3
"""Summarize current and archived inference attempts without losing provenance."""

import json
from pathlib import Path

from edsl import Results


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    attempts = []
    for path in sorted((ROOT / "data" / "attempts").glob("*-cost.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        attempts.append({"artifact": path.name, "cost": payload["data"]["cost"]})
    current = ROOT / "data" / "results.ep"
    if current.is_file():
        attempts.append({
            "artifact": "results.ep",
            "cost": Results.git.load(str(current)).compute_job_cost(),
        })
    print(json.dumps({
        "attempt_count": len(attempts),
        "attempts": attempts,
        "total_cost": sum(float(item["cost"]) for item in attempts),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
''',
                encoding="utf-8",
            )
        makefile = Path(root) / "Makefile"
        marker = "# --- Generated survey validation ---"
        makefile_text = makefile.read_text(encoding="utf-8")
        if marker not in makefile_text:
            answer_options = " ".join(
                f"--column answer.{field}" for field in required_answers
            )
            export_options = "--column 'agent.*' --column 'answer.*'"
            scenario_variables = (
                "SCENARIOS := $(JOB_DIR)/scenario_list.ep\n" if with_scenarios else ""
            )
            scenario_rule = (
                "$(SCENARIOS): $(JOB_DIR)/study_scenario_list.py\n"
                "\tcd $(JOB_DIR) && $(STUDY_PYTHON) study_scenario_list.py\n\n"
                if with_scenarios else ""
            )
            scenario_prerequisite = " $(SCENARIOS)" if with_scenarios else ""
            scenario_argument = " --scenarios $(SCENARIOS)" if with_scenarios else ""
            makefile.write_text(
                makefile_text.rstrip() + "\n\n" + marker + "\n"
                f"MODEL_NAME := {model}\n"
                f"RUN_DESCRIPTION := {run_description}\n"
                "REPORT_GROUP_BY ?=\n"
                "JOB_DIR := edsl_jobs/job_a\n"
                "SURVEY := $(JOB_DIR)/survey.ep\n"
                "AGENTS := $(JOB_DIR)/agent_list.ep\n"
                f"{scenario_variables}"
                "MODELS := $(JOB_DIR)/model_list.ep\n"
                "JOBS := $(JOB_DIR)/jobs.ep\n\n"
                ".PHONY: prepare post-run complete estimate inspect report-data plots exports costs retry-data workflow-setup workflow-verify report-check present\n\n"
                "workflow-setup: workflow-gates.json\n"
                "\t@test -n \"$(APPROVAL_EVIDENCE)\" || { echo \"APPROVAL_EVIDENCE is required\" >&2; exit 2; }\n"
                "\t$(EP) workflow setup --name \"$(RUN_DESCRIPTION)\" --root . --spec $< --evidence \"$(APPROVAL_EVIDENCE)\"\n"
                "\t$(EP) workflow gate attest plan-approved --root . --by user --evidence \"$(APPROVAL_EVIDENCE)\"\n\n"
                "prepare: workflow-setup edsl-objects estimate\n\n"
                "edsl-objects: $(JOBS)\n\n"
                "$(SURVEY): $(JOB_DIR)/study_survey.py\n"
                "\tcd $(JOB_DIR) && $(STUDY_PYTHON) study_survey.py\n\n"
                "$(AGENTS): $(JOB_DIR)/study_agent_list.py\n"
                "\tcd $(JOB_DIR) && $(STUDY_PYTHON) study_agent_list.py\n\n"
                f"{scenario_rule}"
                "$(MODELS):\n"
                "\t$(EP) models create --model \"$(MODEL_NAME)\" --output $@\n\n"
                f"$(JOBS): $(SURVEY) $(AGENTS){scenario_prerequisite} $(MODELS)\n"
                f"\t$(EP) jobs build --survey $(SURVEY) --agents $(AGENTS){scenario_argument} --models $(MODELS) --output $@\n\n"
                "estimate: $(JOBS)\n"
                "\t$(EP) jobs cost $(JOBS)\n\n"
                "data: data/results.ep\n\n"
                "data/results.ep: $(JOBS)\n"
                "\t@mkdir -p data\n"
                "\t@if test -s \"$@\"; then \\\n"
                "\t\techo \"Existing results preserved: $@\"; \\\n"
                "\telse \\\n"
                "\t\t$(EP) run $(JOBS) --remote_inference_description \"$(RUN_DESCRIPTION)\" --results_description \"$(RUN_DESCRIPTION)\" --output $@; \\\n"
                "\tfi\n\n"
                "data/report-data.json: data/results.ep\n"
                "\t@mkdir -p data\n"
                "\t$(EP) results review data/results.ep $(if $(REPORT_GROUP_BY),--group-by \"$(REPORT_GROUP_BY)\",) > $@\n\n"
                "report-data: data/report-data.json\n\n"
                "plots: data/report-data.json analysis/build_standard_plots.py\n"
                "\t$(STUDY_PYTHON) analysis/build_standard_plots.py data/report-data.json writeup/plots\n\n"
                "inspect: data/report-data.json\n"
                "\t@cat $<\n\n"
                "retry-data: data/results.ep\n"
                "\t@test -n \"$(RETRY_REASON)\" || { echo \"RETRY_REASON is required\" >&2; exit 2; }\n"
                "\t@mkdir -p data/attempts\n"
                "\t@attempt=$$(date -u +%Y%m%dT%H%M%SZ); \\\n"
                "\t\tcp data/results.ep data/attempts/$${attempt}-results.ep; \\\n"
                "\t\t$(EP) results cost data/results.ep > data/attempts/$${attempt}-cost.json; \\\n"
                "\t\tprintf '%s\\n' \"$(RETRY_REASON)\" > data/attempts/$${attempt}-reason.txt; \\\n"
                "\t\trm -f data/results.ep\n"
                "\t$(MAKE) data\n"
                "\t$(MAKE) costs\n\n"
                "costs: data/results.ep\n"
                "\t$(STUDY_PYTHON) analysis/summarize_run_costs.py > data/run-costs.json\n\n"
                "writeup/tables/results.csv: data/results.ep\n"
                "\t@mkdir -p writeup/tables\n"
                f"\t$(EP) results export data/results.ep {export_options} --format csv --output $@\n\n"
                "writeup/tables/results.json: data/results.ep\n"
                "\t@mkdir -p writeup/tables\n"
                f"\t$(EP) results export data/results.ep {export_options} --format json --output $@\n\n"
                "exports: writeup/tables/results.csv writeup/tables/results.json\n\n"
                "tables: exports\n\n"
                "qa: analysis/validate_results.py data/results.ep\n"
                "\t$(STUDY_PYTHON) analysis/validate_results.py\n\n"
                "post-run: report-data exports costs qa plots\n\n"
                "writeup/report.html: writeup/report.md writeup/report.css writeup/tables/results.csv\n"
                "\tcd writeup && pandoc report.md -o report.html --standalone --embed-resources --css=report.css\n\n"
                "report: writeup/report.html\n\n"
                "report-check: writeup/report.html\n"
                "\t$(EP) report check --root .\n\n"
                "workflow-verify: report-check\n"
                "\t$(EP) workflow verify --root .\n\n"
                "present: writeup/report.html\n"
                "\t$(EP) present $(abspath $<) --title \"$(RUN_DESCRIPTION)\"\n\n"
                "complete: workflow-verify present\n",
                encoding="utf-8",
            )

    if template == "qualitative-analysis":
        qual_root = Path(root) / "analysis" / "bewley_project"
        (qual_root / "corpus").mkdir(parents=True, exist_ok=True)
        workflow_spec = Path(root) / "workflow-gates.json"
        if not workflow_spec.exists():
            workflow_spec.write_text(json.dumps({"gates": [
                {
                    "name": "plan-approved",
                    "description": "User approved the qualitative research question, corpus, and coding approach",
                    "verification": {"type": "user-approval"},
                },
                {
                    "name": "coding-valid",
                    "description": "Bewley event state and indexes pass integrity validation",
                    "verification": {"type": "command", "command": "make qual-validate"},
                },
                {
                    "name": "evidence-browser-built",
                    "description": "Local qualitative evidence browser is non-empty",
                    "verification": {"type": "artifact", "path": "writeup/report.html", "min_bytes": 1000},
                },
            ]}, indent=2) + "\n", encoding="utf-8")
        makefile = Path(root) / "Makefile"
        marker = "# --- Generated qualitative-analysis workflow ---"
        makefile_text = makefile.read_text(encoding="utf-8")
        if marker not in makefile_text:
            makefile.write_text(
                makefile_text.rstrip() + "\n\n" + marker + "\n"
                "QUAL_ROOT := analysis/bewley_project\n\n"
                ".PHONY: workflow-setup prepare bewley-init qual-next qual-validate qual-export workflow-verify present complete\n\n"
                "workflow-setup: workflow-gates.json\n"
                "\t@test -n \"$(APPROVAL_EVIDENCE)\" || { echo \"APPROVAL_EVIDENCE is required\" >&2; exit 2; }\n"
                "\t$(EP) workflow setup --name \"Qualitative analysis\" --root . --spec $< --evidence \"$(APPROVAL_EVIDENCE)\"\n"
                "\t$(EP) workflow gate attest plan-approved --root . --by user --evidence \"$(APPROVAL_EVIDENCE)\"\n\n"
                "bewley-init:\n"
                "\t@mkdir -p $(QUAL_ROOT)/corpus\n"
                "\t@if test -d $(QUAL_ROOT)/.bewley; then echo \"Existing Bewley project preserved\"; else cd $(QUAL_ROOT) && bewley init; fi\n\n"
                "prepare: workflow-setup bewley-init\n\n"
                "qual-next: bewley-init\n"
                "\tcd $(QUAL_ROOT) && bewley next\n\n"
                "qual-validate: bewley-init\n"
                "\tcd $(QUAL_ROOT) && bewley fsck\n\n"
                "qual-export: qual-validate\n"
                "\t@mkdir -p writeup\n"
                "\tcd $(QUAL_ROOT) && bewley export html --output ../../writeup/report.html\n\n"
                "workflow-verify: qual-export\n"
                "\t$(EP) workflow verify --root .\n\n"
                "present: writeup/report.html\n"
                "\t$(EP) present $(abspath $<) --title \"Qualitative analysis\"\n\n"
                "complete: workflow-verify present\n",
                encoding="utf-8",
            )

    if template == "digital-twins":
        twin_root = Path(root) / "data" / "zwill_project"
        twin_root.mkdir(parents=True, exist_ok=True)
        workflow_spec = Path(root) / "workflow-gates.json"
        if not workflow_spec.exists():
            workflow_spec.write_text(json.dumps({"gates": [
                {
                    "name": "plan-approved",
                    "description": "User approved the twin construction or validation design before execution",
                    "verification": {"type": "user-approval"},
                },
                {
                    "name": "zwill-project-readable",
                    "description": "The package-owned Zwill project can report its current state",
                    "verification": {"type": "command", "command": "make twin-status"},
                },
                {
                    "name": "twin-report-built",
                    "description": "The package-owned consolidated local report is non-empty",
                    "verification": {
                        "type": "artifact", "path": "writeup/zwill-report/report.html", "min_bytes": 1000,
                    },
                },
            ]}, indent=2) + "\n", encoding="utf-8")
        makefile = Path(root) / "Makefile"
        marker = "# --- Generated digital-twins workflow ---"
        makefile_text = makefile.read_text(encoding="utf-8")
        if marker not in makefile_text:
            makefile.write_text(
                makefile_text.rstrip() + "\n\n" + marker + "\n"
                "ZWILL_ROOT := data/zwill_project\n"
                "ZWILL_SURVEY ?=\n\n"
                ".PHONY: workflow-setup prepare zwill-init twin-next twin-status twin-report workflow-verify present complete\n\n"
                "workflow-setup: workflow-gates.json\n"
                "\t@test -n \"$(APPROVAL_EVIDENCE)\" || { echo \"APPROVAL_EVIDENCE is required\" >&2; exit 2; }\n"
                "\t$(EP) workflow setup --name \"Digital twins\" --root . --spec $< --evidence \"$(APPROVAL_EVIDENCE)\"\n"
                "\t$(EP) workflow gate attest plan-approved --root . --by user --evidence \"$(APPROVAL_EVIDENCE)\"\n\n"
                "zwill-init:\n"
                "\t@mkdir -p $(ZWILL_ROOT)\n"
                "\t@if test -d $(ZWILL_ROOT)/.zwill; then echo \"Existing Zwill project preserved\"; else cd $(ZWILL_ROOT) && zwill init; fi\n\n"
                "prepare: workflow-setup zwill-init\n\n"
                "twin-next: zwill-init\n"
                "\tcd $(ZWILL_ROOT) && zwill next $(if $(ZWILL_SURVEY),--survey $(ZWILL_SURVEY),)\n\n"
                "twin-status: zwill-init\n"
                "\tcd $(ZWILL_ROOT) && zwill status\n\n"
                "twin-report: twin-status\n"
                "\t@test -n \"$(ZWILL_SURVEY)\" || { echo \"ZWILL_SURVEY is required\" >&2; exit 2; }\n"
                "\t@mkdir -p writeup/zwill-report\n"
                "\tcd $(ZWILL_ROOT) && zwill report build --survey \"$(ZWILL_SURVEY)\" --path \"$(abspath writeup/zwill-report)\"\n\n"
                "workflow-verify: twin-report\n"
                "\t$(EP) workflow verify --root .\n\n"
                "present: writeup/zwill-report/report.html\n"
                "\t$(EP) present $(abspath $<) --title \"Digital twin evidence report\"\n\n"
                "complete: workflow-verify present\n",
                encoding="utf-8",
            )

    if template == "agent-list":
        workflow_spec = Path(root) / "workflow-gates.json"
        if not workflow_spec.exists():
            workflow_spec.write_text(json.dumps({"gates": [
                {
                    "name": "plan-approved",
                    "description": "User approved plan.md and its AgentList invariants",
                    "verification": {"type": "user-approval"},
                },
                {
                    "name": "agent-list-valid",
                    "description": "The requested agent_list.ep package and provenance satisfy every approved invariant",
                    "verification": {"type": "command", "command": "make qa"},
                },
            ]}, indent=2) + "\n", encoding="utf-8")

        validator = Path(root) / "analysis" / "validate_agent_list.py"
        if not validator.exists():
            validator.write_text('''#!/usr/bin/env python3
"""Validate the scaffold-owned AgentList package and source provenance."""

import ast
import hashlib
import json
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse

from edsl import AgentList

ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / "data" / "cooked" / "agent_list.ep"
PROVENANCE = ROOT / "data" / "raw" / "provenance.json"
EXPECTED_AGENTS = %d
REQUIRED_TRAITS = %s
GROUP_TRAIT = %s
EXPECTED_GROUP_SIZE = %s
REQUIRED_SOURCE_DOMAIN = %s


def main() -> int:
    agents = AgentList.git.load(str(ARTIFACT))
    errors = []
    names = [agent.name for agent in agents]
    if len(agents) != EXPECTED_AGENTS:
        errors.append(f"expected {EXPECTED_AGENTS} agents; found {len(agents)}")
    if len(set(names)) != len(names) or any(not name for name in names):
        errors.append("agent names must be non-empty and unique")
    missing = {
        trait: sum(agent.traits.get(trait) in (None, "") for agent in agents)
        for trait in REQUIRED_TRAITS
    }
    missing = {key: value for key, value in missing.items() if value}
    if missing:
        errors.append(f"missing required traits: {missing}")
    groups = Counter(agent.traits.get(GROUP_TRAIT) for agent in agents) if GROUP_TRAIT else Counter()
    bad_groups = {
        str(key): value for key, value in groups.items()
        if key in (None, "") or value != EXPECTED_GROUP_SIZE
    }
    if bad_groups:
        errors.append(f"invalid {GROUP_TRAIT} group sizes: {bad_groups}")
    provenance = json.loads(PROVENANCE.read_text(encoding="utf-8"))
    for field in ("source_url", "retrieval_date", "raw_source_path", "source_sha256"):
        if not provenance.get(field):
            errors.append(f"provenance missing {field}")
    raw_source = (ROOT / provenance.get("raw_source_path", "")).resolve()
    try:
        raw_source.relative_to(ROOT)
    except ValueError:
        errors.append("raw_source_path must stay inside the study root")
    if not raw_source.is_file():
        errors.append(f"raw source not found: {raw_source}")
    elif provenance.get("source_sha256"):
        digest = hashlib.sha256(raw_source.read_bytes()).hexdigest()
        if digest != provenance["source_sha256"]:
            errors.append("raw source SHA-256 does not match provenance")
    embedded = []
    for path in ROOT.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        if any(
            isinstance(node, ast.Constant) and isinstance(node.value, str)
            and len(node.value) > 4096
            for node in ast.walk(tree)
        ):
            embedded.append(str(path.relative_to(ROOT)))
    if embedded:
        errors.append(f"large source payload embedded in Python: {embedded}")
    source_host = urlparse(provenance.get("source_url", "")).hostname or ""
    if REQUIRED_SOURCE_DOMAIN and not (
        source_host == REQUIRED_SOURCE_DOMAIN or
        source_host.endswith("." + REQUIRED_SOURCE_DOMAIN)
    ):
        errors.append(
            f"source must be on {REQUIRED_SOURCE_DOMAIN}; found {source_host or 'none'}"
        )
    print(json.dumps({
        "status": "error" if errors else "ok",
        "data": {
            "agent_count": len(agents), "unique_names": len(set(names)),
            "required_traits": REQUIRED_TRAITS,
            "group_trait": GROUP_TRAIT, "group_count": len(groups),
            "source_url": provenance.get("source_url"),
            "retrieval_date": provenance.get("retrieval_date"),
        },
        "errors": errors,
    }, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
''' % (
                expected_agents,
                json.dumps(required_traits),
                repr(group_trait),
                repr(expected_group_size),
                repr(required_source_domain),
            ), encoding="utf-8")

        makefile = Path(root) / "Makefile"
        makefile_text = makefile.read_text(encoding="utf-8")
        marker = "# --- Generated AgentList workflow ---"
        if marker not in makefile_text:
            makefile.write_text(
                makefile_text.rstrip() + "\n\n" + marker + "\n"
                "AGENT_SOURCE := data/raw/agents.csv\n"
                "AGENT_ARTIFACT := data/cooked/agent_list.ep\n\n"
                ".PHONY: agent-list qa workflow-setup workflow-verify present\n\n"
                "workflow-setup: workflow-gates.json\n"
                "\t@test -n \"$(APPROVAL_EVIDENCE)\" || { echo \"APPROVAL_EVIDENCE is required\" >&2; exit 2; }\n"
                "\t$(EP) workflow setup --name \"AgentList study\" --root . --spec $< --evidence \"$(APPROVAL_EVIDENCE)\"\n"
                "\t$(EP) workflow gate attest plan-approved --root . --by user --evidence \"$(APPROVAL_EVIDENCE)\"\n\n"
                "agent-list: $(AGENT_ARTIFACT)\n\n"
                "$(AGENT_ARTIFACT): $(AGENT_SOURCE)\n"
                "\t@mkdir -p data/cooked\n"
                "\t$(EP) agents create --from-csv $< --name-field name --output $@\n\n"
                "qa: $(AGENT_ARTIFACT) data/raw/provenance.json analysis/validate_agent_list.py\n"
                "\t$(STUDY_PYTHON) analysis/validate_agent_list.py\n\n"
                "workflow-verify: qa\n"
                "\t$(EP) workflow verify --root .\n\n"
                "present: $(AGENT_ARTIFACT)\n"
                "\t$(EP) present $(abspath $<) --title \"Validated AgentList\"\n",
                encoding="utf-8",
            )

    manifest = {
        "status": "ok",
        "data": {
            "root": str(Path(root).resolve()),
            "study_type": study_type,
            "template": template,
            "required_skill": (
                "edsl-surveys" if template == "survey" else
                "edsl-agent-lists" if template == "agent-list" else
                "research-qualitative-data-analysis" if template == "qualitative-analysis" else
                "research-digital-twins" if template == "digital-twins" else None
            ),
            "source_action": (
                "read_then_edit_marked_sections" if template == "survey" else None
            ),
            "next_edits": (
                [
                    "edsl_jobs/job_a/study_survey.py",
                    "edsl_jobs/job_a/study_agent_list.py",
                ] + (["edsl_jobs/job_a/study_scenario_list.py"] if with_scenarios else [])
                if template == "survey" else []
            ),
            "with_scenarios": with_scenarios if template == "survey" else False,
            "next_writes": (
                ["writeup/report.md"] if template == "survey" else
                ["data/raw/agents.csv", "data/raw/provenance.json"]
                if template == "agent-list" else
                ["analysis/bewley_project/corpus/"] if template == "qualitative-analysis" else
                ["data/zwill_project/"] if template == "digital-twins" else []
            ),
            "owned_targets": (
                [
                    "workflow-setup", "prepare", "edsl-objects", "estimate", "data",
                    "report-data", "inspect", "plots", "exports", "costs", "retry-data", "qa",
                    "post-run", "workflow-verify", "present", "complete",
                ]
                if template == "survey" else
                ["workflow-setup", "agent-list", "qa", "workflow-verify", "present"]
                if template == "agent-list" else
                ["workflow-setup", "prepare", "bewley-init", "qual-next", "qual-validate", "qual-export", "workflow-verify", "present", "complete"]
                if template == "qualitative-analysis" else
                ["workflow-setup", "prepare", "zwill-init", "twin-next", "twin-status", "twin-report", "workflow-verify", "present", "complete"]
                if template == "digital-twins" else []
            ),
            "phase_commands": (
                {
                    "after_plan_approval": (
                        f'make -C "{Path(root).resolve()}" prepare '
                        'APPROVAL_EVIDENCE="<approval evidence>"'
                    ),
                    "after_spend_approval": f'make -C "{Path(root).resolve()}" data',
                    "after_inference": f'make -C "{Path(root).resolve()}" post-run',
                    "after_report": f'make -C "{Path(root).resolve()}" complete',
                }
                if template == "survey" else {}
            ),
            "inspect_scaffold": False,
        },
        "warnings": [],
    }
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create a study project structure.")
    parser.add_argument("name", help="Project directory name")
    parser.add_argument(
        "--type",
        choices=["edsl", "simulation"],
        default="edsl",
        help="Study type: 'edsl' (default) or 'simulation'",
    )
    parser.add_argument(
        "--with-scenarios",
        action="store_true",
        help="Create and wire a ScenarioList for repeated survey stimuli",
    )
    parser.add_argument(
        "--template",
        choices=["survey", "agent-list", "qualitative-analysis", "digital-twins"],
        help="Install deterministic boilerplate for this study type",
    )
    parser.add_argument(
        "--expected-rows",
        type=int,
        help="Exact planned result count for the survey validator",
    )
    parser.add_argument(
        "--required-answer",
        action="append",
        default=[],
        help="Required non-null answer field; repeat for multiple fields",
    )
    parser.add_argument("--expected-agents", type=int)
    parser.add_argument("--required-trait", action="append", default=[])
    parser.add_argument("--group-trait")
    parser.add_argument("--expected-group-size", type=int)
    parser.add_argument("--required-source-domain")
    parser.add_argument("--model", help="Confirmed model name for the survey run")
    parser.add_argument(
        "--run-description",
        help="Single-line label used for remote inference, Results, and presentation",
    )
    parser.add_argument(
        "--jobs",
        nargs="+",
        default=["job_a"],
        help="Names of edsl_jobs to create (default: job_a)",
    )
    parser.add_argument(
        "--sims",
        nargs="+",
        default=["sim_a"],
        help="Names of simulations to create (default: sim_a)",
    )
    args = parser.parse_args()
    create_project(
        args.name,
        args.jobs,
        study_type=args.type,
        sims=args.sims,
        template=args.template,
        expected_rows=args.expected_rows,
        required_answers=args.required_answer,
        expected_agents=args.expected_agents,
        required_traits=args.required_trait,
        group_trait=args.group_trait,
        expected_group_size=args.expected_group_size,
        required_source_domain=args.required_source_domain,
        model=args.model,
        run_description=args.run_description,
        with_scenarios=args.with_scenarios,
    )
