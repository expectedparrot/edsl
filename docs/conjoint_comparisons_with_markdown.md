# Conjoint comparisons with Markdown and Humanize

Humanize renders EDSL question text as Markdown. You can use this to present a conjoint or discrete-choice task as two styled product cards while keeping the respondent's answer as a normal multiple-choice response.

The basic pattern is:

1. Put each alternative in its own one-column Markdown table.
2. Use a `multiple_choice` question for `Option A`, `Option B`, and optionally `Neither`.
3. Add survey-level `custom_css` through the Humanize schema.
4. Use scenarios and Jinja variables when the attributes vary between tasks.

This approach requires no custom JavaScript or changes to the Humanize frontend.

## Static example

The question text below creates two separate tables. Using separate tables is important: it lets CSS give each alternative its own border, background, padding, and rounded corners.

```markdown
## Which option would you choose?

| **Option A** |
|:---|
| • Pretzel bun |
| • Veggie sausage |
| • Slaw |
| • Fast casual |
| **$9** |

| **Option B** |
|:---|
| • Classic bun |
| • Beef sausage |
| • Onions |
| • Street cart |
| **$7** |

One comparison scenario. Prices vary independently across tasks.
```

Use ordinary Markdown rows rather than HTML tags such as `<br>` or `<hr>`. Humanize escapes raw HTML in question text, so those tags may appear literally to respondents.

Create the multiple-choice survey with the CLI:

```bash
ep surveys create \
  --question-type multiple_choice \
  --question-name product_choice \
  --question-text '## Which option would you choose?

| **Option A** |
|:---|
| • Pretzel bun |
| • Veggie sausage |
| • Slaw |
| • Fast casual |
| **$9** |

| **Option B** |
|:---|
| • Classic bun |
| • Beef sausage |
| • Onions |
| • Street cart |
| **$7** |

One comparison scenario. Prices vary independently across tasks.' \
  --option 'Option A' \
  --option 'Option B' \
  --option 'Neither' \
  --no-include-comment \
  --output conjoint-survey.ep
```

## Humanize schema and CSS

Save the following as `humanize.json`:

```json
{
  "questions": {
    "product_choice": {
      "optional": false,
      "format": {
        "type": "radio"
      }
    }
  },
  "survey": {
    "custom_css": ".edsl-question-text { white-space: normal !important; }\ntable { display: inline-table; width: calc(50% - 16px); box-sizing: border-box; border-collapse: separate; border-spacing: 0; vertical-align: top; margin: 1.25rem 0 1.5rem; table-layout: fixed; border: 2px solid #b9cdbf; border-radius: 14px; overflow: hidden; background: #fbfcfb; }\ntable + table { margin-left: 24px; }\ntable th, table td { text-align: left; vertical-align: top; background: #fbfcfb; border: 0; }\ntable th { color: #24543b; font-size: 1.35rem; padding: 1.5rem 2rem .75rem; }\ntable td { font-size: 1.1rem; line-height: 1.5; padding: .25rem 2rem; }\ntable tbody tr:last-child td { position: relative; padding-top: 1.5rem; padding-bottom: 1.5rem; font-size: 1.4rem; }\ntable tbody tr:last-child td::before { content: ''; position: absolute; top: .65rem; left: 2rem; right: 2rem; border-top: 1px solid #ddd; }\ninput[type='radio'] { accent-color: #24543b; }\n@media (max-width: 700px) { table { display: table; width: 100%; margin: .75rem 0; } table + table { margin-left: 0; } table th { padding: 1.1rem 1.25rem .6rem; } table td { padding-left: 1.25rem; padding-right: 1.25rem; font-size: .95rem; } table tbody tr:last-child td::before { left: 1.25rem; right: 1.25rem; } }"
  }
}
```

The key rule is:

```css
.edsl-question-text {
  white-space: normal !important;
}
```

Humanize normally applies `white-space: pre-wrap` to question text. Because the tables are inline elements after styling, preserving the newline between them forces the second table onto the next line. Resetting whitespace to `normal` allows both tables to share a row.

The responsive rule deliberately stacks the cards when the viewport is narrower than 700 pixels. Remove that media query if the cards must remain side by side on narrow screens, though doing so may create horizontal scrolling or cramped text.

## Validate and preview

Validate the schema against the materialized Survey package:

```bash
ep humanize schema validate \
  --survey conjoint-survey.ep \
  --schema humanize.json
```

Create a temporary preview URL without creating a human survey:

```bash
ep humanize preview \
  --survey conjoint-survey.ep \
  --schema humanize.json
```

Or create the Humanize survey:

```bash
ep humanize create \
  --survey conjoint-survey.ep \
  --name "Conjoint product comparison" \
  --schema humanize.json
```

Always parse the command's stdout as JSON. The created survey response includes `admin_url`, `respondent_url`, and `preview_url` in `data`.

## Varying attributes with scenarios

For an actual conjoint experiment, use Jinja variables in the Markdown and supply the attributes through a `ScenarioList`.

```markdown
## Which option would you choose?

| **Option A** |
|:---|
| • {{ a_bun }} |
| • {{ a_sausage }} |
| • {{ a_topping }} |
| • {{ a_setting }} |
| **${{ a_price }}** |

| **Option B** |
|:---|
| • {{ b_bun }} |
| • {{ b_sausage }} |
| • {{ b_topping }} |
| • {{ b_setting }} |
| **${{ b_price }}** |

Choose the option you prefer, or select Neither.
```

Example `scenarios.csv`:

```csv
a_bun,a_sausage,a_topping,a_setting,a_price,b_bun,b_sausage,b_topping,b_setting,b_price
Pretzel bun,Veggie sausage,Slaw,Fast casual,9,Classic bun,Beef sausage,Onions,Street cart,7
Classic bun,Chicken sausage,Relish,Food hall,8,Brioche bun,Veggie sausage,Sauerkraut,Restaurant,10
```

Create the scenario package:

```bash
ep scenarios create \
  --from-csv scenarios.csv \
  --output conjoint-scenarios.ep
```

Then create Humanize from the survey and scenarios. Select the assignment method appropriate for the study design:

```bash
ep humanize create \
  --survey conjoint-survey.ep \
  --scenario_list conjoint-scenarios.ep \
  --scenario_method randomize \
  --name "Conjoint product comparison" \
  --schema humanize.json
```

`randomize` assigns scenarios randomly. Other supported methods include `loop`, `single_scenario`, and `ordered`. The correct choice depends on whether each respondent should see one task or a sequence of tasks.

## Reusing the layout across questions

Survey-level CSS applies to the whole Humanize survey. If the survey contains unrelated Markdown tables, the broad `table` rules will style those too. For a conjoint-only survey this is usually acceptable.

For a mixed survey, scope the selectors to a stable parent class when one is available, or keep conjoint questions in a separate survey. The question container exposes classes such as `.edsl-question-text`, but CSS cannot select an individual question reliably unless its rendered markup provides a unique identifier.

Each conjoint question still needs a Humanize schema entry:

```json
{
  "questions": {
    "choice_1": {"format": {"type": "radio"}},
    "choice_2": {"format": {"type": "radio"}},
    "choice_3": {"format": {"type": "radio"}}
  },
  "survey": {
    "custom_css": "...same CSS as above..."
  }
}
```

## Common problems

### The second card appears below the first on a wide screen

Confirm both of these rules are present:

```css
.edsl-question-text { white-space: normal !important; }
table { display: inline-table; width: calc(50% - 16px); }
```

Also check that the browser viewport is wider than the responsive breakpoint.

### HTML tags appear as text

Use Markdown rows instead of `<br>` and use the CSS pseudo-element divider instead of `<hr>`.

### A centered `OR` breaks the layout

Do not add a narrow third table column solely for `OR`. Markdown's table sizing can make that column collide visually with the alternatives. The answer buttons already communicate that Option A and Option B are alternatives.

### The cards have unequal heights

Give both tables the same number of rows. If an attribute is absent, provide a visible placeholder such as `—` so corresponding rows remain aligned.

### The CSS does not appear

Validate the Humanize schema, ensure the CSS is stored under `survey.custom_css`, and create or update the Humanize survey with that schema. A local Survey package does not contain the Humanize CSS by itself.

## Design recommendations

- Keep the attribute order identical between alternatives.
- Keep labels short enough to fit at the target screen size.
- Randomize attribute levels in the scenario data, not in CSS or Markdown.
- Include `Neither` only when the experimental design calls for an outside option.
- Test both desktop and mobile layouts before collecting responses.
- Keep the recorded answers simple (`Option A`, `Option B`, or `Neither`); the scenario columns preserve the attribute levels used for analysis.
