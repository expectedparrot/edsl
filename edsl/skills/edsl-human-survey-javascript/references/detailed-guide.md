# Human Survey JavaScript

A question in a human survey can carry a script that runs in the respondent's
browser once the question is on the page. Use it for interactive tasks, timing and
behavioural measures, and logging events with the survey.

## 1. Check access first

Custom JavaScript is available on approved accounts only, and a schema with a
script is rejected when saved from an account that isn't approved. Check before
writing any script:

```bash
ep humanize custom-js-access
```

If it is `False`, tell the researcher to email info@expectedparrot.com to request
access, and don't build the survey around a script until it is approved.

## 2. Attach a script

Scripts go in the humanize schema under `questions[<name>].javascript.hooks`, keyed
by the event that runs them. The only event is `"question.ready"`: the question has
rendered and its inputs are on the page.

```python
time_to_first_answer = """
const container = this.getQuestionContainer();
const shownAt = performance.now();

container.addEventListener("change", () => {
    ep.log("first_answer", { ms: Math.round(performance.now() - shownAt) });
}, { once: true });
"""

humanize_schema = {
    "questions": {
        "choice": {"javascript": {"hooks": {"question.ready": time_to_first_answer}}},
    },
}
info = survey.humanize(human_survey_name="...", humanize_schema=humanize_schema)
```

From the CLI, keep each script in its own `.js` file:

```bash
ep humanize schema create --survey survey.ep --javascript choice:question.ready=choice.js --output humanize.json
ep humanize schema set <human-survey-uuid> --javascript choice:question.ready=choice.js
ep humanize schema set <human-survey-uuid> --clear-javascript choice
```

On a live survey, use `ep humanize schema set` to change or clear a script; see the
CLI examples above.

Every question type supports `javascript`, including survey messages, except
`compute` and `image_generation`, which never appear on the page.

## 3. Write the hook

A hook is the **body** of a function. Write statements; don't wrap them in
`function () { ... }`. Inside it:

| Name | What it is |
|---|---|
| `this.getQuestionContainer()` | The question's element. Find its inputs and add elements inside it. |
| `context.questionName` / `context.questionType` | Which question the hook is running for. |
| `context.isPreview` | `true` on a preview link. Its answers don't appear in results. Its `ep.log` events are kept, and returned only when asked for (`include_previews`), marked `is_preview`. |
| `ep.log(eventName, payload)` | Records an event against the response. |

- The hook runs once each time its question appears. The same script on several
  questions runs once for each; tell them apart with `context.questionName`.
- `context` carries nothing that identifies the respondent.
- `ep.log`: `eventName` is a non-empty string (cut to 200 characters); `payload` is
  optional and must be JSON (no page elements, no objects that refer to themselves),
  at most 4,000 characters as JSON. At most 10,000 events per response. It returns
  nothing; events are sent in the background.

## 4. Rules a script must follow

A script that breaks these can't be saved, and nothing in that schema is saved.

Allowed: building interface within the survey, reading and writing answers,
controlling when respondents can move on, measuring behaviour, randomising
conditions, reading URL parameters, loading images, audio, video and other media to
show, and using the camera, microphone or location for a task the respondent is told
about.

**Libraries:** load a well-known library (d3, Chart.js, lodash, PapaParse, …) only
from **cdnjs**, at a pinned version, e.g.
`https://cdnjs.cloudflare.com/ajax/libs/d3/7.9.0/d3.min.js`. Respondent pages load
scripts from cdnjs only, so a library from any other CDN fails in the respondent's
browser even if the schema saves.

Not allowed:

- Loading code from anywhere else, or from a URL built while the script runs.
- Building code at runtime: `eval`, `new Function`, strings passed to `setTimeout` or
  `setInterval`, or inserting markup that contains a script.
- Any request to Expected Parrot, or sending respondent data anywhere. `ep.log` is how
  data leaves a script.
- Reading cookies, tokens, credentials, or storage the script didn't create.
- Obfuscated or minified code (a loaded library is fine).
- Asking for passwords or payment details, or imitating a login or dialog.
- Collecting anything unrelated to the survey, or using the camera, microphone or
  location covertly.
- Running after the respondent has finished or left, opening popups, preventing them
  from leaving, or hiding the survey's own notices.
- Using the respondent's device for anything else.

Limits: 64,000 characters per hook, 256,000 per question, and at most 25 new
distinct scripts per save (a script reused unchanged counts once; scripts already on
the survey don't count). Save larger surveys in batches.

If a save is refused, nothing in that schema was saved. Fix the script against the
rules above; if the researcher believes it was refused by mistake, they can write to
info@expectedparrot.com.

## 5. Test it

- **Runway previews don't run scripts** (see `edsl:edsl-human-survey-preview`). Check
  layout there, but test behaviour on the live survey.
- After deploying, have the researcher open `info["preview_url"]` with the browser's
  developer console open. Scripts run there exactly as for respondents, script errors
  appear in the console, and logged events are saved marked `is_preview`.
- Then fetch the events with `include_previews=True` (`--include-previews`) to
  confirm each `ep.log` call arrives with the expected payload.

## 6. Agents and handoffs

Scripts run only in a browser. If the survey accepts agent responses (see
`edsl:edsl-human-survey-agent-access`), agent-completed answers have no script
events, except on a page the agent hands to its participant, which runs the page's
scripts like any respondent's. Tell the researcher, since behavioural measures will
be missing for those responses.

## 7. Retrieve the events

`Coop().get_all_human_survey_events(uuid)` or `ep humanize events <uuid> --all
--output events.jsonl`, oldest first, previews left out unless asked for. For the event
fields, batching, catching up with `after`, counting, and the rule for a complete
download, read `references/events.md`.
