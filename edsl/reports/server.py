from fastapi import FastAPI, HTTPException, File, UploadFile, Query
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Dict, Tuple, Optional
from pathlib import Path
import io, contextlib, uuid, yaml

from edsl import Results
from reports.research import Research
from reports.report import Report
from reports.preferences import ReportPreferences

app = FastAPI(title="Reports Configurator")

# In-memory cache for demo purposes
results_cache: Optional[Results] = None


# Helper to load Results from bytes (raw JSON or gzip)
def _load_results_from_bytes(data: bytes) -> Results:
    import json, gzip

    # First, attempt gzip
    try:
        decompressed = gzip.decompress(data)
        data_json = decompressed
    except (OSError, gzip.BadGzipFile):
        data_json = data
    results_dict = json.loads(data_json.decode())
    return Results.from_dict(results_dict)


@app.on_event("startup")
def load_results():
    # No need to load example results on startup
    pass


class PreferencesModel(BaseModel):
    include_questions: Optional[List[str]] = None
    exclude_questions: Optional[List[str]] = None
    analyses: Optional[List[List[str]]] = None
    analysis_output_filters: Optional[
        Dict[str, List[str]]
    ] = None  # keys will be pipe-joined tuples
    analysis_writeup_filters: Optional[
        Dict[str, bool]
    ] = None  # keys will be pipe-joined tuples

    # New interaction filtering options
    include_interactions: Optional[List[List[str]]] = None
    exclude_interactions: Optional[List[List[str]]] = None

    # Report section toggles
    lorem_ipsum: Optional[bool] = None
    include_questions_table: Optional[bool] = None
    include_respondents_section: Optional[bool] = None
    include_scenario_section: Optional[bool] = None
    include_overview: Optional[bool] = None

    # Free text sampling configuration
    free_text_sample_config: Optional[Dict[str, int]] = None


@app.get("/questions")
def get_questions():
    if results_cache is None:
        return []  # Return empty list instead of error
    return [q.question_name for q in results_cache.survey.questions]


@app.get("/possible_outputs")
def get_possible_outputs(question: List[str] = Query(...)):
    if results_cache is None:
        raise HTTPException(500, "Results not loaded")
    return Research.get_possible_output_names(results_cache, question)


@app.post("/generate")
def generate_report(prefs: PreferencesModel):
    if results_cache is None:
        raise HTTPException(500, "Results not loaded")

    # Convert analysis_output_filters keys back to tuple form (split by |)
    filters_dict: Dict[Tuple[str, ...], List[str]] = {}
    if prefs.analysis_output_filters:
        for key, value in prefs.analysis_output_filters.items():
            filters_dict[tuple(key.split("|"))] = value

    # Convert analysis_writeup_filters keys back to tuple form (split by |)
    writeup_filters_dict: Dict[Tuple[str, ...], bool] = {}
    if prefs.analysis_writeup_filters:
        for key, value in prefs.analysis_writeup_filters.items():
            writeup_filters_dict[tuple(key.split("|"))] = value

    rp = ReportPreferences(
        include_questions=prefs.include_questions or [],
        exclude_questions=prefs.exclude_questions or [],
        analyses=prefs.analyses,
        analysis_output_filters=filters_dict,
        analysis_writeup_filters=writeup_filters_dict,
    )

    # Capture stdout prints during report generation
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        report = Report(
            results_cache,
            include_questions=rp.include_questions,
            exclude_questions=rp.exclude_questions,
            analyses=rp.analyses,
            analysis_output_filters=rp.analysis_output_filters,
            analysis_writeup_filters=rp.analysis_writeup_filters,
            include_interactions=prefs.include_interactions,
            exclude_interactions=prefs.exclude_interactions,
            lorem_ipsum=prefs.lorem_ipsum,
            include_questions_table=prefs.include_questions_table,
            include_respondents_section=prefs.include_respondents_section,
            include_scenario_section=prefs.include_scenario_section,
            include_overview=prefs.include_overview,
            free_text_sample_config=prefs.free_text_sample_config,
        )

        # Ensure generated directory exists under static_dir
        gen_dir = static_dir / "generated"
        gen_dir.mkdir(parents=True, exist_ok=True)

        output_file = gen_dir / f"report_{uuid.uuid4().hex}.html"
        report.generate_html(str(output_file))

    logs = buf.getvalue()

    # The file is available via static mount under /generated/...
    file_url = f"/generated/{output_file.name}"
    return {"status": "ok", "file": file_url, "logs": logs}


# Serve the simple React front-end (resolve path relative to this file)
static_dir = Path(__file__).resolve().parent / "web"

# Ensure directory exists
static_dir.mkdir(exist_ok=True)


@app.post("/upload_results")
async def upload_results(file: UploadFile = File(...)):
    global results_cache
    data = await file.read()
    results_cache = _load_results_from_bytes(data)
    return {
        "status": "ok",
        "questions": [q.question_name for q in results_cache.survey.questions],
    }


@app.post("/export_config")
def export_config(prefs: PreferencesModel):
    """Export current configuration as YAML"""
    if results_cache is None:
        raise HTTPException(500, "Results not loaded")

    # Create a Report object to generate the YAML configuration
    report = Report(results_cache)

    # Build configuration dictionary
    config = {
        "report_settings": {
            "lorem_ipsum": prefs.lorem_ipsum or False,
            "include_questions_table": prefs.include_questions_table or True,
            "include_respondents_section": prefs.include_respondents_section or True,
            "include_scenario_section": prefs.include_scenario_section or True,
            "include_overview": prefs.include_overview or True,
        },
        "question_filters": {
            "include_questions": prefs.include_questions or [],
            "exclude_questions": prefs.exclude_questions or [],
        },
        "interaction_filters": {
            "include_interactions": prefs.include_interactions or [],
            "exclude_interactions": prefs.exclude_interactions or [],
        },
        "free_text_sample_config": prefs.free_text_sample_config or {},
    }

    # Add analyses configuration if present
    if prefs.analyses:
        config["analyses"] = {}
        for analysis in prefs.analyses:
            analysis_key = "|".join(analysis)
            config["analyses"][analysis_key] = {
                "outputs": prefs.analysis_output_filters.get(analysis_key, [])
                if prefs.analysis_output_filters
                else [],
                "writeup": prefs.analysis_writeup_filters.get(analysis_key, True)
                if prefs.analysis_writeup_filters
                else True,
            }

    yaml_content = yaml.dump(config, default_flow_style=False)
    return {"status": "ok", "yaml": yaml_content}


@app.post("/import_config")
async def import_config(file: UploadFile = File(...)):
    """Import configuration from YAML file"""
    if results_cache is None:
        raise HTTPException(500, "Results not loaded")

    content = await file.read()
    try:
        config = yaml.safe_load(content.decode())
    except Exception as e:
        raise HTTPException(400, f"Invalid YAML: {str(e)}")

    # Extract preferences from YAML
    prefs = PreferencesModel()

    # Report settings
    report_settings = config.get("report_settings", {})
    prefs.lorem_ipsum = report_settings.get("lorem_ipsum")
    prefs.include_questions_table = report_settings.get("include_questions_table")
    prefs.include_respondents_section = report_settings.get(
        "include_respondents_section"
    )
    prefs.include_scenario_section = report_settings.get("include_scenario_section")
    prefs.include_overview = report_settings.get("include_overview")

    # Question filters
    question_filters = config.get("question_filters", {})
    prefs.include_questions = question_filters.get("include_questions")
    prefs.exclude_questions = question_filters.get("exclude_questions")

    # Interaction filters
    interaction_filters = config.get("interaction_filters", {})
    prefs.include_interactions = interaction_filters.get("include_interactions")
    prefs.exclude_interactions = interaction_filters.get("exclude_interactions")

    # Free text sampling
    prefs.free_text_sample_config = config.get("free_text_sample_config")

    # Analyses
    analyses_config = config.get("analyses", {})
    if analyses_config:
        prefs.analyses = []
        prefs.analysis_output_filters = {}
        prefs.analysis_writeup_filters = {}

        for analysis_key, analysis_config in analyses_config.items():
            analysis_questions = analysis_key.split("|")
            prefs.analyses.append(analysis_questions)
            prefs.analysis_output_filters[analysis_key] = analysis_config.get(
                "outputs", []
            )
            prefs.analysis_writeup_filters[analysis_key] = analysis_config.get(
                "writeup", True
            )

    return {"status": "ok", "config": prefs.dict()}


# ---- Mount static after all routes ----

app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")
