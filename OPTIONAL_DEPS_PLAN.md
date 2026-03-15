# Plan: Make Heavy Dependencies Optional

## Context
The edsl package has many required dependencies that are only used in specific features (visualization, reporting, ML, file format handling). Making them optional reduces install size and avoids dependency conflicts for users who only need core functionality.

## Approach
For each dependency: (1) move it to `optional = true` in pyproject.toml, (2) wrap all imports with lazy try/except ImportError patterns, (3) add to appropriate extras groups.

We'll follow the existing codebase pattern (see `edsl/runner/storage_redis.py`, `edsl/surveys/textual_interactive_survey.py`):
```python
try:
    import foo
except ImportError:
    foo = None

# At usage site:
if foo is None:
    raise ImportError("foo is required for X. Install with: pip install edsl[group]")
```

## Dependency Analysis & Plan

### Tier 1: Zero/Unused imports - just remove from required deps
| Package | Usage | Action |
|---------|-------|--------|
| **markdown2** | No imports found anywhere | Remove entirely from dependencies |
| **pluggy** | No imports found anywhere | Remove entirely from dependencies |

### Tier 2: Scripts/tests only - move to dev or optional
| Package | Usage | Action |
|---------|-------|--------|
| **memory-profiler** | Only in `scripts/memory_line_profiler.py`, `tests/memory/` (2 files) | Move to dev dependencies |

### Tier 3: Narrow usage - make optional with lazy imports
| Package | Files | Extras Group |
|---------|-------|-------------|
| **pygments** | 3 files: `scenarios/handlers/sql_file_store.py`, `scenarios/handlers/py_file_store.py`, `questions/question_base.py` | `viz` |
| **rank-bm25** | 1 file: `questions/question_dropdown.py` | `full` |
| **mammoth** | 1 file: `scenarios/handlers/docx_file_store.py` | `docs` (new) |
| **anywidget** | 1 file: `widgets/base_widget.py` | `notebook` |
| **textual** | 1 file: `surveys/textual_interactive_survey.py` (already lazy!) | `full` |
| **pydot** | 3 files: `jobs/job_flow_visualization.py`, `surveys/extras/survey_flow_visualization.py`, `macros/composite_macro_visualization.py` | `viz` (already there) |

### Tier 4: Moderate usage - make optional with lazy imports
| Package | Files | Extras Group |
|---------|-------|-------------|
| **python-docx** | ~9 files across reports, datasets, scenarios, surveys | `docs` (new) |
| **openpyxl** | 2 files: `assistants/survey_assistant.py`, `dataset/file_exports.py` | `docs` (new) |
| **pypdf2** | 1 file: `scenarios/handlers/pdf_file_store.py` | `docs` (new) |
| **python-pptx** | 2 files: `reports/report_pptx.py`, `scenarios/handlers/pptx_file_store.py` | `docs` (new) |
| **scipy** | 4 files: `reports/tables/chi_square*.py` (2), `results/results_weighting.py`, `results/results_weighting_strategies.py` | `ml` (new) |
| **joblib** | 1 file: `scenarios/scenarioml/prediction.py` | `ml` (new) |
| **scikit-learn** | 4 files: `scenarios/scenarioml/model_selector.py`, `scenarios/scenarioml/feature_processor.py`, `embeddings/embeddings_visualization.py`, `embeddings/embeddings_clustering.py` | `ml` (new) |

### Tier 5: Heavy usage - make optional with lazy imports
| Package | Files | Extras Group |
|---------|-------|-------------|
| **matplotlib** | ~20+ files across reports, tasks, buckets, comparisons, scenarios | `viz` |

## New Extras Groups
```toml
docs = ["python-docx", "openpyxl", "pypdf2", "python-pptx", "mammoth"]
ml = ["scikit-learn", "scipy", "joblib"]
```
Update `full` to include all new groups' packages.

## Files to Modify

### pyproject.toml
- Remove: `markdown2`, `pluggy` from `[tool.poetry.dependencies]`
- Move to dev: `memory-profiler`
- Make optional (add `optional = true`): `pygments`, `rank-bm25`, `python-docx`, `matplotlib`, `openpyxl`, `pypdf2`, `python-pptx`, `anywidget`, `textual`, `scipy`, `mammoth`, `joblib`, `scikit-learn`
- Add new extras groups: `docs`, `ml`
- Update `full` extras group with all new optional deps

### Source files requiring lazy import wrappers
Each file gets its top-level import wrapped in try/except with a clear error message. The import moves to either module level (with `= None` fallback) or to the function that uses it (lazy local import).

**Preferred pattern** - local lazy import in the function that uses it (matches existing patterns in `dataset_operations_mixin.py`, `dataset_tree.py`, etc. which already do this for docx):

```python
def some_method(self):
    try:
        from docx import Document
    except ImportError:
        raise ImportError(
            "python-docx is required for DOCX export. "
            "Install with: pip install edsl[docs]"
        )
```

Files already using local/lazy imports (minimal or no changes needed):
- `edsl/surveys/textual_interactive_survey.py` - already lazy
- `edsl/dataset/dataset_tree.py` - docx already local import
- `edsl/dataset/report_from_template.py` - docx already local import
- `edsl/dataset/dataset_operations_mixin.py` - docx already local import
- `edsl/embeddings/embeddings_visualization.py` - sklearn already try/except
- `edsl/embeddings/embeddings_clustering.py` - sklearn already try/except
- `edsl/macros/composite_macro_visualization.py` - pydot already in try/except
- Most matplotlib usages are already in methods (local scope)

Files needing import changes (top-level imports to wrap):
1. `edsl/scenarios/handlers/sql_file_store.py` - pygments (lines 32-34)
2. `edsl/scenarios/handlers/py_file_store.py` - pygments (lines 36-38)
3. `edsl/questions/question_base.py` - pygments (lines 1210-1212, already local)
4. `edsl/questions/question_dropdown.py` - rank_bm25 (line 6)
5. `edsl/scenarios/handlers/docx_file_store.py` - mammoth (line 42, already local), docx (line 11)
6. `edsl/widgets/base_widget.py` - anywidget (line 8)
7. `edsl/reports/report_docx.py` - docx (lines 3-4)
8. `edsl/dataset/file_exports.py` - docx (line 290, already local), openpyxl (line 128, already local)
9. `edsl/assistants/survey_assistant.py` - docx (line 338, already local), openpyxl (line 277, already local)
10. `edsl/surveys/survey_export.py` - docx (line 61, already local)
11. `edsl/scenarios/DocxScenario.py` - docx (line 3)
12. `edsl/scenarios/handlers/pdf_file_store.py` - PyPDF2 (line 11)
13. `edsl/reports/report_pptx.py` - pptx (lines 3-6)
14. `edsl/scenarios/handlers/pptx_file_store.py` - pptx (lines 10, 44, 75, already local)
15. `edsl/reports/tables/chi_square_table.py` - scipy (line 49, already local)
16. `edsl/reports/tables/chi_square.py` - scipy (line 2)
17. `edsl/results/results_weighting.py` - scipy (line 361, already local)
18. `edsl/results/results_weighting_strategies.py` - scipy (line 18)
19. `edsl/scenarios/scenarioml/prediction.py` - joblib (line 9)
20. `edsl/scenarios/scenarioml/model_selector.py` - sklearn (lines 13-22)
21. `edsl/scenarios/scenarioml/feature_processor.py` - sklearn (lines 13-14)
22. `edsl/jobs/job_flow_visualization.py` - pydot (line 29)
23. `edsl/surveys/extras/survey_flow_visualization.py` - pydot (line 41)
24. matplotlib files - all ~20 files (most are already local imports in methods; wrap remaining top-level ones)

## Execution Order
1. Update pyproject.toml (remove/move/make optional)
2. Wrap imports in Tier 1-3 files (simple, few files)
3. Wrap imports in Tier 4 files (moderate)
4. Wrap imports in Tier 5 files (matplotlib - many files but mechanical)
5. Run tests to verify nothing breaks at import time

## Verification
- `python -c "import edsl"` should work without any of the optional deps
- `python -m pytest tests/ -x --ignore=tests/memory` should still pass
- Check that error messages are clear when optional features are used without deps
