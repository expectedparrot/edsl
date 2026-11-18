## Editing a survey after `.humanize()`

A humanized survey is live as soon as `.humanize()` returns. When the
researcher asks to change it, decide first whether the change can be patched
onto the existing survey or needs a new deployment. Patching keeps the same
UUID, links, and collected responses. Redeploying creates a separate survey
with new links, and responses stay split between the two.

### Patch in place

These settings live outside the survey structure and can change on the live
survey. Respondents keep the same links.

| Change | CLI |
|---|---|
| Optional flags, formats, preselection, time limits, attention checks, submitting indicators, intro screens | `ep humanize schema patch <uuid> --schema schema-patch.json` |
| `QuestionInterview` settings: interviewer name, checklist, end policy, end message, language, voice (how the AI sounds) | `ep humanize schema set <uuid> --interviewer-name ...` and related interview flags, or use `--schema` for other fields |
| `QuestionInterview` mode (text, voice, or both) | `ep humanize schema set <uuid> --interview-mode question=voice` |
| Progress display, logo | `ep humanize schema patch <uuid> --schema schema-patch.json`; logos can use `ep humanize schema set <uuid> --logo-file ...` |
| Custom CSS | `ep humanize css patch <uuid> --file custom.css` — see `edsl:edsl-human-survey-css` |
| Question JavaScript | `ep humanize schema set <uuid> --javascript question:hook=file.js`; see `edsl:edsl-human-survey-javascript` |
| Agent-list delivery map, anonymity, resubmission | `ep humanize agent-list patch <uuid> --help` |
| Whether AI agents may take the survey | see `edsl:edsl-human-survey-agent-access` |
| Emails, reminders, follow-ups | see `edsl:edsl-human-survey-notifications` |

Schema patches are deep-merged, and lists replace the existing value (see
"Updating the schema on a live survey" in `references/humanize-schema.md`).
Read the current schema with `ep humanize schema get <uuid> --out schema.json`
before patching a list such as checklist items, and send the full new list.

### Redeploy with `.humanize()`

Anything stored in the survey, scenario list, or agent list needs a new
deployment:

- question text, options, question type, or `question_name`
- adding, removing, or reordering questions
- skip logic and piping
- a `QuestionInterview`'s `interview_guide`
- scenarios or `scenario_list_method`
- respondents in the agent list, or their traits

If a single request mixes both kinds of change, put everything in the new
deployment, since the new survey starts from its own `humanize_schema`.

### Pulling a deployed survey

Pull a deployed survey to reuse or inspect it, and before every change, so
the work starts from what is deployed and not from a local file that may have
drifted. A human survey links to separate Coop objects:

```python
from edsl import Coop, Survey, ScenarioList, AgentList

coop = Coop()
info = coop.get_human_survey(uuid)
survey = Survey.pull(info["survey_uuid"])
scenarios = (
    ScenarioList.pull(info["scenario_list_uuid"])
    if info["scenario_list_uuid"]
    else None
)

agent_config = coop.get_human_survey_agent_list(uuid)["agent_list_config"]
agents = AgentList.pull(agent_config["uuid"]) if agent_config else None

humanize_schema = coop.get_human_survey_humanize_schema(uuid)
agent_access = coop.get_human_survey_agent_access(uuid)
```

`info["agent_list_uuid"]` is always `None`; take the agent list's UUID from
`get_human_survey_agent_list()`. That call also returns the `delivery_map`,
`anonymous`, and `allow_resubmit` settings.

The API does not return `scenario_list_method`; preserve it from the deployment configuration when recreating a deployment.

To create a new deployment with updated survey structure, include the survey, scenarios, agents, and schema settings that should carry forward:

```python
new_info = survey.by(scenarios).by(agents).humanize(
    human_survey_name=f"{info['name']} v2",
    scenario_list_method=scenario_list_method,
    humanize_schema=humanize_schema,
    delivery_map=agent_config["delivery_map"],
)
new_uuid = new_info["uuid"]

coop.patch_human_survey_agent_list(
    new_uuid,
    anonymous=agent_config["anonymous"],
    allow_resubmit=agent_config["allow_resubmit"],
)
if agent_access["configured"]:
    coop.patch_human_survey_agent_access(
        new_uuid,
        {
            key: agent_access[key]
            for key in ("enabled", "participation_mode", "instructions", "question_settings")
        },
        survey=survey,
    )
```

Leave out `.by(scenarios)` and `scenario_list_method` when the survey has no
scenarios, and `.by(agents)`, `delivery_map`, and the agent-list patch when it
has no agent list. If the edit renamed or removed a question, update its
entries in `humanize_schema` and `question_settings` to match.
