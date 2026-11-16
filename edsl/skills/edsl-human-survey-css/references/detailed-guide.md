# Human Survey CSS

Custom CSS is applied via `humanize_schema["survey"]["custom_css"]`. All question components use `edsl-*` CSS classes. All text is Markdown — no HTML tags in question text.

```python
schema = {
    "survey": {
        "custom_css": """
            .edsl-question { margin-bottom: 2rem; }
            .edsl-question-text { font-size: 1.2rem; font-weight: 600; }
            .edsl-option-label { font-size: 1rem; }
            .edsl-textarea { min-height: 120px; }
        """
    }
}
info = survey.humanize(human_survey_name="Styled Study", humanize_schema=schema)
```

Always target EDSL's own classes. Avoid broad global selectors like `html` or `body`.

Iterate on CSS before deployment by re-rendering a runway preview after each
change; see `edsl:edsl-human-survey-preview`.

## Key CSS classes

| Class | Targets |
|---|---|
| `.edsl-survey-container` | Outermost container — use to set survey background color |
| `.edsl-survey-banner` | Logo banner at the top; present only when the survey has a logo |
| `.edsl-survey-banner-content` | Column inside the banner holding the logo |
| `.edsl-logo` | Logo `<img>`, 40px tall by default |
| `.edsl-survey-content` | Column holding the page's questions and navigation |
| `.edsl-survey-item` | Wrapper around each question or instruction on the page |
| `.edsl-instruction` | Instruction text |
| `.edsl-survey-nav` / `.edsl-next-button` | Navigation row / Next button (`:disabled` while submitting) |
| `.edsl-question` | Every question container |
| `.edsl-question-text` | Question text element |
| `.edsl-question-image` | Images embedded in question text |
| `.edsl-options` | Options wrapper (MC, checkbox, linear scale, etc.) |
| `.edsl-option` | Individual option (a `<label>`, so the whole row is clickable) |
| `.edsl-option-label` | Option labels |
| `.edsl-radio-control` / `.edsl-checkbox-control` | Drawn radio circle / checkbox; carries `data-checked` or `data-unchecked` |
| `.edsl-radio-indicator` / `.edsl-checkbox-indicator` | Radio dot / checkbox tick |
| `.edsl-select` | `<select>` for the `dropdown` format |
| `.edsl-textarea` | Textareas (free text, list, edit) |
| `.edsl-input` | Single-line inputs (numerical, email, url) |
| `.edsl-error` | Error messages |

The `.edsl-radio` and `.edsl-checkbox` inputs are hidden; style the `-control`
spans instead. Style a selected row with `.edsl-option:has(.edsl-radio:checked)`.

Question-type-specific containers: `.edsl-free-text-question`, `.edsl-multiple-choice-question`, `.edsl-multiple-choice-with-other-question`, `.edsl-linear-scale-question`, `.edsl-numerical-question`, `.edsl-checkbox-question`, `.edsl-checkbox-with-other-question`, `.edsl-budget-question`, `.edsl-distribution-question`, `.edsl-rank-question`, `.edsl-matrix-question`, `.edsl-likert-question`, `.edsl-yes-no-question`, `.edsl-top-k-question`, `.edsl-list-question`, `.edsl-file-upload-question`, `.edsl-demand-question`, `.edsl-dict-question`, `.edsl-dropdown-question`, `.edsl-edit-question`, `.edsl-email-question`, `.edsl-url-question`, `.edsl-object-question`, `.edsl-survey-message-question`.

## Targeting one question or page

`.edsl-survey-item` carries `data-question-name` or `data-instruction-name`.
Under group presentation, `.edsl-survey-container` carries `data-group-name`.

```css
.edsl-survey-item[data-question-name="age"] .edsl-question-text { font-weight: 700; }
.edsl-survey-container[data-group-name="demographics"] { background: #f8fafc; }
```

## Logo and banner

Set the logo in the humanize schema (`survey.branding.logo`; see
**edsl:edsl-human-survey**). CSS controls its size and backdrop. Set `height` and
let the width follow the image:

```css
.edsl-logo { height: 80px; }
.edsl-survey-banner { background: #2e7d32; }
```

The banner spans the screen and the logo lines up with the questions; restyle
`.edsl-survey-banner-content` (e.g. `width: auto; padding: 0 24px;`) to move it
toward the edge.

## Progress steps

Step markers carry `data-status` (`complete`, `current`, `upcoming`) on each
`.edsl-progress-step`, and each half-line `.edsl-progress-connector` carries its
own `data-status`. Color the filled line with
`.edsl-progress-connector[data-status="complete"]`, not through the step's status.

## File upload classes

`file_upload` has an extended set of classes for its dropzone, file list, and upload status:

| Class | Element |
|---|---|
| `edsl-file-upload-dropzone` | Drop zone + file list container |
| `edsl-file-upload-dragging` | Added to dropzone while a drag is in progress |
| `edsl-file-upload-target` | Clickable/draggable drop target |
| `edsl-file-upload-icon-wrapper` | Upload icon wrapper |
| `edsl-file-upload-icon` | Upload SVG icon |
| `edsl-file-upload-title` | "Upload files" heading |
| `edsl-file-upload-subtitle` | "Drag & drop or click to browse" subtext |
| `edsl-file-upload-hints` | Constraint hints (accepted types, size limit) |
| `edsl-file-upload-errors` | Error banner for browser-side check failures |
| `edsl-file-list` | Container wrapping file count header + cards/table |
| `edsl-file-list-header` | Row with file count and "Remove all" button |
| `edsl-file-remove-all` | "Remove all" button |
| `edsl-file-cards` | Cards container (small screens only) |
| `edsl-file-item` | Individual file card |
| `edsl-file-item-icon-wrapper` | File-type icon wrapper |
| `edsl-file-item-icon` | File-type SVG icon |
| `edsl-file-item-name` | File name |
| `edsl-file-item-size` | File size |
| `edsl-file-item-status` | Upload status wrapper (cards only) |
| `edsl-file-status-uploading` | "Uploading…" status |
| `edsl-file-status-done` | "Done" status |
| `edsl-file-status-error` | "Failed" status |
| `edsl-file-progress-track` | Progress bar background |
| `edsl-file-progress-fill` | Progress bar fill |
| `edsl-file-item-remove` | Per-file remove button (cards and table) |
| `edsl-file-table-wrapper` | Table outer div (medium+ screens only) |
| `edsl-file-table` | Files table |
| `edsl-file-table-header` | `<thead>` |
| `edsl-file-table-header-row` | Header `<tr>` |
| `edsl-file-table-header-cell` | Each `<th>` (Name, Size, Upload Status, Actions) |
| `edsl-file-table-row` | File `<tr>` in table body |

## Programmatic CSS with SurveyCSS

```python
from edsl.surveys.survey_css import SurveyCSS, CSSRule

css = SurveyCSS.default_style()
css = css.update_style(".edsl-question-text", "font-size", "1.3rem")
css = css.update_style(".edsl-option-label", "color", "#333")

schema = {
    "survey": {"custom_css": css.generate_css()}
}
```

## Updating CSS after deployment

Use the CLI to update or clear a live survey's CSS without redeploying:

```bash
ep humanize css patch <human-survey-uuid> --file custom.css
ep humanize css patch <human-survey-uuid> --clear
```

This patches only the CSS field — all other schema settings (optional flags, formats, etc.) are untouched.
