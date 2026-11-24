# Previewing a Human Survey with Runway

`runway` turns a saved survey into a self-contained HTML file: the same markup,
stylesheet, and font a respondent is served. It runs locally, creates nothing on
Expected Parrot, and fills in scenario values and images. This is the draft
preview to give the researcher before deployment. After `.humanize()`, the live
`preview_url` covers what runway cannot (see "What a preview cannot show").

Runway is a standalone CLI, not an `ep` subcommand. `runway guide` prints its
full reference.

## Workflow

### 1. Save the inputs

Runway reads files. The humanize schema is not part of a survey, so save it
separately:

```python
import json
from pathlib import Path

survey.git.save("survey.ep")
Path("humanize_schema.json").write_text(json.dumps(humanize_schema, indent=2))
scenarios.git.save("scenarios.ep")
```

Save the real `Survey` object. Runway refuses a hand-written survey file. If the
survey is built in a deploy script, save `survey.ep` and the schema from that
script rather than rebuilding them separately.

### 2. Validate and check

Runway accepts schema keys that `.humanize()` rejects, so validate the schema
first and fix any errors before rendering:

```bash
ep humanize schema validate --survey survey.ep --schema humanize_schema.json
```

`check` writes nothing and reports what each question will render as:

```bash
runway check survey.ep --schema humanize_schema.json --scenarios scenarios.ep
```

| Status | Meaning | Action |
|---|---|---|
| `drawn` | Previews with its real control | None |
| `automatic` | Thinking question, `compute`, or image generation; no respondent sees it | None |
| `note` | Runway has no control for this type yet; the page shows the text and a note | Tell the researcher which questions show a note |
| `warning` | No respondent can be served this question | Fix the survey |

A `warning` means a question type that humanize cannot show, or a question
left out of every question group under group presentation. It exits 1. Fix the
survey and check again before rendering. With `--scenarios`, `check` also names
scenario keys the list does not carry, which render as blank on the live page.

### 3. Render

Write the preview into the study directory:

```bash
runway render survey.ep --schema humanize_schema.json --scenarios scenarios.ep \
  -o <study_dir>/previews
```

This writes one file, `<study_dir>/previews/survey.html`, with a toolbar to move
between pages and, with `--scenarios`, a dropdown to switch scenarios. Omit
`--schema` or `--scenarios` when the survey has none.

- **More than 25 scenarios** are refused. Pick a representative set with
  `--scenario-index 0,4,11`.
- **A logo** in `survey.branding.logo` draws as a placeholder. Add
  `--fetch-assets` to fetch it from Coop and embed it.

## What a preview cannot show

Tell the researcher which of these apply to their survey, and offer the live
`preview_url` after deployment to check them (see `edsl:edsl-human-survey`):

- **Agent traits and prior answers.** `{{ agent.x }}` and `{{ q.answer }}` show
  as written. An `image_generation` answer piped into a later question shows a
  placeholder image.
- **Skip logic and randomization.** Pages follow authored order, and options
  are not shuffled.
- **Behaviour.** The Next button, validation, and selection limits do nothing.
  Checkbox Select all and exclusive options do work.
- **Custom JavaScript.** Question scripts don't run. Test them through the live
  `preview_url` (see `edsl:edsl-human-survey-javascript`).
- **Some formats.** A `numerical` slider shows a note. A matrix carousel is
  drawn but cannot be swiped; test it on a phone through the live link.
- **Math.** `$$…$$` shows as TeX source.

Types runway does not draw yet (for example `rank`, `budget`, `top_k`, `list`,
`file_upload`, and `interview`) still get a full page with their question text,
so wording and position can be reviewed. `runway types` lists the current set.

## Quick reference

| Task | Command |
|---|---|
| See what each question will render as | `runway check survey.ep --schema humanize_schema.json` |
| Render a preview | `runway render survey.ep --schema humanize_schema.json -o <study_dir>/previews` |
| Render with scenarios | add `--scenarios scenarios.ep` |
| Render selected scenarios | add `--scenario-index 0,4,11` |
| Draw the real logo | add `--fetch-assets` |
| List supported question types | `runway types` |
| Full CLI reference | `runway guide` |
