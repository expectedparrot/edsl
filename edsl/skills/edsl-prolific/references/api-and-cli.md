# EDSL Prolific API and CLI

Prolific integration is attached to a deployed EDSL human survey by its UUID.
The CLI commands below return the standard EDSL JSON envelope.

## CLI commands

```bash
ep humanize prolific filters
ep humanize prolific cost \
  --participant_payment_cents 200 \
  --num_participants 100 \
  --estimated_completion_time_minutes 10
ep humanize prolific settings
ep humanize prolific create <human_survey_uuid> --config prolific-study.json
ep humanize prolific list <human_survey_uuid>
ep humanize prolific get <human_survey_uuid> <study_id>
ep humanize prolific update <human_survey_uuid> <study_id> --config study-patch.json
ep humanize prolific preflight <human_survey_uuid> <study_id> \
  --survey survey.ep --require-question consent --required-credits 25
ep humanize prolific publish <human_survey_uuid> <study_id> \
  --survey survey.ep --require-question consent --required-credits 25
ep humanize prolific pause <human_survey_uuid> <study_id>
ep humanize prolific resume <human_survey_uuid> <study_id>
ep humanize prolific stop <human_survey_uuid> <study_id> --yes
ep humanize prolific delete <human_survey_uuid> <draft_study_id> --yes
ep humanize prolific responses <human_survey_uuid> <study_id> --output responses.ep
ep humanize prolific demographics <human_survey_uuid> <study_id> --output demographics.csv
```

`update --config` takes a JSON object containing only the fields to change, using
the same field names as the create config. `stop` is permanent and requires
`--yes`; only unpublished drafts can be deleted, and `delete` also requires
`--yes`.

`preflight` performs read-only checks and returns `ready`, `blockers`, study and
survey identifiers, missing questions, recruitment credits, required credits,
balance, and the account key source. A non-ready preflight exits with a
validation error. `publish` performs a fresh preflight before publishing.
`--required-credits` can represent a caller-supplied total, including any
separately estimated EDSL interview runtime; without it, preflight costs only
the Prolific recruitment amount.

The create command accepts a JSON object whose keys match
`Coop.create_prolific_study`, for example:

```json
{
  "name": "Study listing title",
  "description": "Participant-facing study description",
  "num_participants": 100,
  "estimated_completion_time_minutes": 10,
  "participant_payment_cents": 200,
  "device_compatibility": ["desktop", "mobile"],
  "peripheral_requirements": [],
  "filters": [],
  "approval_mode": "automatic"
}
```

`responses` saves an EDSL Results artifact when given `--output`; supported
formats include `.ep`, `.json`, and `.json.gz`.

`demographics` downloads Prolific's demographics for the study's participants as
a CSV, saved to the `--output` path; without it, the command reports the
participant count and the columns. Only the survey's owner can download them.

## Coop API

```python
from edsl import Coop

coop = Coop()
settings = coop.get_prolific_study_settings()
filters = coop.list_prolific_filters()
quote = coop.calculate_prolific_study_cost(
    participant_payment_cents=200,
    num_participants=100,
    estimated_completion_time_minutes=10,
)
```

`settings` reports `key_source` (`"ep"` or `"user_key"`), whether recruitment
is charged in credits, and whether a participant limit applies. A cost quote
returns `cost_cents`, `cost_credits`, `is_underpayment`, and
`underpayment_warning`. EDSL currently validates the Prolific minimum hourly
payment in `Coop`; check the installed version's implementation for its exact
threshold.

`list_prolific_filters()` returns `CoopProlificFilters`. Use `.find(filter_id)`
to inspect a filter and `.create_study_filter(...)` to construct a validated
filter dictionary:

```python
filters = coop.list_prolific_filters()
age = filters.create_study_filter("age", min=25, max=45)
country = filters.create_study_filter(
    "current-country-of-residence", values=["United States", "Canada"]
)
```

Range filters take `min` and `max`; select filters take the displayed option
labels in `values`. The helper maps select labels to Prolific option IDs and
accepts underscore or hyphen variants when looking up filter IDs.

`create_prolific_study(human_survey_uuid, ...)` creates a study associated with
the human survey. It returns `study_id`, `status`, `admin_url`,
`respondent_url`, `preview_url`, configuration fields, and cost. The study
configuration fields are `name`, `description`, `num_participants`,
`estimated_completion_time_minutes`, `participant_payment_cents`,
`device_compatibility`, `peripheral_requirements`, `filters`, and optional
`approval_mode` (`"automatic"` or `"manual"`). The EDSL client rejects a
payment below its implemented minimum.

## Study lifecycle methods

The CLI exposes study listing, inspection, updates, and lifecycle changes. The
same operations are also available on `Coop`:

```python
coop.list_prolific_studies(human_survey_uuid)
coop.get_prolific_study(human_survey_uuid, study_id)
coop.update_prolific_study(human_survey_uuid, study_id, name="Updated title")
coop.pause_prolific_study(human_survey_uuid, study_id)
coop.resume_prolific_study(human_survey_uuid, study_id)
coop.stop_prolific_study(human_survey_uuid, study_id)
coop.get_prolific_study_responses(human_survey_uuid, study_id)
coop.get_prolific_study_demographics(human_survey_uuid, study_id, save_path="demographics.csv")
```

Each result from `get_prolific_study_responses` carries Prolific's submission
fields as agent traits, such as `prolific_submission_id` and
`prolific_submission_status`, but not participants' demographics.
`get_prolific_study_demographics` returns those as Prolific's CSV text, one row
per submission, and also saves it when given `save_path`. Join the two on the
CSV's "Submission id" column and the `prolific_submission_id` trait. The columns
are Prolific's own, such as "Age", "Sex", "Ethnicity simplified",
"Nationality", and "Employment status".

`update_prolific_study` accepts the same configuration fields as creation;
`approval_mode` can only change on an unpublished draft. Pause, resume, and stop
update the study status. Stop is terminal. `delete_prolific_study` applies only
to draft studies. The CLI requires `--yes` for stop and delete so these
irreversible actions are explicit.

Pausing or resuming the study is separate from pausing the human survey
(`coop.pause_human_survey(human_survey_uuid)`). A paused survey tells new
respondents it's closed but doesn't stop Prolific recruiting; pause or stop the
study as well when participation should stop.

`preflight_prolific_study(...)` checks that the study is an unpublished draft,
the deployed survey matches an optional expected `Survey`, required question
names are present, and the relevant balance covers the required credits. It
does not reserve funds or establish that live routing or participant eligibility
works. `publish_prolific_study(...)` runs this preflight again before publishing.

The response method returns EDSL `Results` when conversion succeeds and can
return a `ScenarioList` otherwise. The CLI export records the resulting object
type and count in its JSON envelope.
