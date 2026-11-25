# Repository scripts

Repository maintenance and documentation builders live here; these files are
not part of the installed EDSL API.

- `build_shared_state_case_study_site.py` builds the shared-state case-study
  HTML pages from saved study artifacts under `examples/`.
- `build_systematic_review_case_study.py` builds the systematic-review page
  from saved Results packages under `artifacts/shared_state/systematic_review/`.
- `build_shared_state_path_dependence_report.py` builds the repeated-poll PDF
  from its saved input data under `examples/`.
- `render_economic_games_lab.py` builds the economic-games HTML lab from the
  example source and saved logs.

Run these commands from the repository root. Rendered HTML, PDFs, figures, and
intermediate files go under `artifacts/` and are ignored by Git. Some builders
need saved Results packages or optional plotting/LaTeX dependencies; they do not
launch model runs.
