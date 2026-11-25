# Human Survey Notifications — Emailing Respondents via Coop

**Prerequisite:** The survey must already be deployed via `.humanize()` with an `AgentList` attached (`survey.by(agents)`) whose traits include an email address, and a `delivery_map` mapping the email channel to that trait. See `edsl:edsl-human-survey` ("With agents") for deployment.

`HumanSurveyNotificationHandler` manages the full email notification lifecycle for a human survey: triggered sends, scheduled campaigns, completion callbacks, and delivery monitoring.

For CLI workflows, use `ep humanize deliveries`, `ep humanize schedules`, and
`ep humanize callbacks`. Routes and respondent filters can be supplied as JSON
files; the examples below use the Python API for operations that need its richer
helper methods.

```bash
# Send a configured email route now
ep humanize deliveries create <human-survey-uuid> --name "Initial outreach" --respondent-email-template respondent_invitation

# Schedule a reminder or create an event callback
ep humanize schedules create-one-time <human-survey-uuid> --name "Reminder" --run_at 2026-12-01T09:00:00Z --template_file reminder.html --subject "A reminder"
ep humanize callbacks create <human-survey-uuid> --name "Completion thanks" --type human_survey_respondent.completed --respondent-email-template respondent_transcript

# Inspect deliveries and their respondent tasks
ep humanize deliveries list <human-survey-uuid>
ep humanize deliveries tasks <human-survey-uuid> <delivery-uuid>
```

Run each subcommand with `--help` for route, template, and filter-file options.
The CLI exposes schedule/callback activation and route editing as separate
subcommands; the Python handler examples below are useful when composing those
operations programmatically.

## Setup

```python
from edsl.coop import HumanSurveyNotificationHandler

handler = HumanSurveyNotificationHandler("your-human-survey-uuid")
```



## Default subject and template

The server provides defaults that are appropriate for **initial survey invitations only**:

- **Subject:** `"Expected Parrot Surveys: {survey_name}"` (falls back to `"A message from Expected Parrot Surveys"` if no name)
- **Template:** An invitation-framed email — "You've been invited to take a survey" — with a "Take Survey" button linking to `{{ url }}`

Default subjects and templates use invitation framing; delivery configuration accepts custom values.

## Immediate delivery

For an initial invitation, the server defaults are fine:

```python
result = handler.send_respondent_email(name="Initial outreach")
# {"delivery_uuid": "...", "routes": [...]}
```

For reminders, thank-yous, or any non-invitation send, provide custom content:

```python
result = handler.send_respondent_email(
    name="Reminder to non-starters",
    subject="Don't forget to complete our survey",
    delivery_template="<p>Hi! Just a reminder to complete {{ survey_name }}: <a href='{{ url }}'>take survey</a></p>",
)
```

### Parameters

| Parameter | Required | Description |
|-----------|----------|-------------|
| `name` | yes | Label for this delivery job |
| `subject` | no | Email subject (1–200 chars); server default used if omitted (invitation-framed) |
| `delivery_template` | no | HTML body; supports `{{ survey_name }}` and `{{ url }}`; server default used if omitted (invitation-framed) |
| `respondent_filter` | no | `HumanizeRespondentFilter` to target a subset of respondents (see below) |

## Scheduling

Scheduled sends use the configured subject and delivery template; defaults use invitation framing.

### One-time schedule

`run_at` must be a timezone-aware datetime or an ISO 8601 string.

```python
from datetime import datetime, timezone

schedule = handler.create_one_time_schedule(
    name="June 1st reminder",
    run_at=datetime(2026, 6, 1, 9, 0, tzinfo=timezone.utc),
    subject="Reminder: survey still open",
    delivery_template="<p>Just a reminder to complete {{ survey_name }}: <a href='{{ url }}'>take survey</a></p>",
)
print(schedule["schedule_uuid"])
```

Update the time before it fires:

```python
handler.update_one_time_schedule(
    schedule_uuid=schedule["schedule_uuid"],
    run_at="2026-06-02T09:00:00+00:00",
)
```

### Recurring cron schedule

Provide either `max_jobs` or `deadline` as the termination condition (at least one required).

```python
# Every Monday at 9 AM Eastern, up to 4 times
schedule = handler.create_cron_schedule(
    name="Weekly Monday reminder",
    cron_expression="0 9 * * MON",
    timezone="America/New_York",
    max_jobs=4,
    subject="Weekly reminder",
    delivery_template="<p>Still time to complete {{ survey_name }}: <a href='{{ url }}'>take survey</a></p>",
)
```

With a deadline instead:

```python
schedule = handler.create_cron_schedule(
    name="Daily reminders through end of month",
    cron_expression="0 8 * * *",
    timezone="America/Chicago",
    deadline=datetime(2026, 6, 30, 23, 59, tzinfo=timezone.utc),
    subject="Daily reminder",
    delivery_template="<p>Please complete {{ survey_name }}: <a href='{{ url }}'>take survey</a></p>",
)
```

Use `start_at` to delay when the schedule begins firing. Without it, the first run is calculated from the current time.

```python
schedule = handler.create_cron_schedule(
    name="Post-launch reminders",
    cron_expression="0 9 * * MON",
    timezone="America/New_York",
    max_jobs=4,
    start_at=datetime(2026, 7, 1, 0, 0, tzinfo=timezone.utc),
    subject="Reminder: survey is open",
    delivery_template="<p>Please complete {{ survey_name }}: <a href='{{ url }}'>take survey</a></p>",
)
```

Pause and resume:

```python
handler.deactivate_schedule(schedule["schedule_uuid"])
handler.activate_schedule(schedule["schedule_uuid"])
```

## Event callbacks

Callbacks use the configured subject and delivery template; defaults use invitation framing.

Two respondent event types are supported:

| Event | When it fires |
|-------|--------------|
| `"human_survey_respondent.completed"` | When a respondent's status is set to completed |
| `"human_survey_respondent.response_submitted"` | Each time a respondent submits a response |

A **respondent** is a person with a corresponding entry in the survey's agent list. Submissions from people outside the agent list (e.g. anonymous links) are not associated with a respondent.

Fire an email when a respondent completes the survey:

```python
callback = handler.create_callback(
    name="Completion thank-you",
    callback_type="human_survey_respondent.completed",
    subject="Thank you for completing our survey!",
    delivery_template="<p>Thanks for completing {{ survey_name }}.</p>",
)
print(callback["callback_uuid"])
```

Limit how many times the callback fires:

```python
callback = handler.create_callback(
    name="First 100 completions",
    callback_type="human_survey_respondent.completed",
    max_fires=100,
    subject="Thank you!",
    delivery_template="<p>Thanks for completing {{ survey_name }}.</p>",
)
```

### Notify the owner on every new response

`create_owner_response_callback` emails the survey owner each time a response is submitted. This fires for **all** responses, including anonymous ones — not just respondents in the agent list.

```python
callback = handler.create_owner_response_callback(name="New response notification")
print(callback["callback_uuid"])
```

### Send a transcript after each submission

`create_transcript_callback` automatically emails a transcript each time a response is submitted. Pass `recipient` to control who receives it:

- `"respondent"` (default) — emails each respondent a copy of their own answers.
- `"owner"` — emails the survey owner a copy of the answers. Fires for all submissions, including anonymous ones.

```python
# Email the respondent their own transcript
callback = handler.create_transcript_callback(
    name="Send respondent transcript on submission",
    recipient="respondent",
)

# Email the owner a transcript on every submission
callback = handler.create_transcript_callback(
    name="Send owner transcript on submission",
    recipient="owner",
)

print(callback["callback_uuid"])
```

Toggle callbacks:

```python
handler.deactivate_callback(callback["callback_uuid"])
handler.activate_callback(callback["callback_uuid"])
```

## Filtering respondents

```python
from edsl.coop.coop_humanize_notifications import (
    HumanizeRespondentFilter,
    RespondentCondition,
    DeliveryStatus,
    DispatchStatus,
    ResponseStatus,
    FilterOperator,
)

# Only email respondents who haven't started yet
filt = HumanizeRespondentFilter(
    conditions=[RespondentCondition(response_status=[ResponseStatus.not_started])]
)

handler.send_respondent_email(
    name="Reminder to non-starters",
    subject="Reminder: survey not yet started",
    delivery_template="<p>Please complete {{ survey_name }}: <a href='{{ url }}'>take survey</a></p>",
    respondent_filter=filt,
)
```

Combine conditions with AND / OR:

```python
# Never contacted OR previously bounced
filt = HumanizeRespondentFilter(
    operator=FilterOperator.or_,
    conditions=[
        RespondentCondition(never_contacted=True),
        RespondentCondition(most_recent_delivery_status=[DeliveryStatus.bounced]),
    ],
)
```

### Available condition fields

| Field | Type | Filters to respondents where… |
|-------|------|-------------------------------|
| `respondent_uuids` | `list[str]` | UUID is in the provided list |
| `response_status` | `list[ResponseStatus]` | Survey response status matches |
| `never_contacted` | `bool` | Has never received a delivery |
| `any_dispatch_status` | `list[DispatchStatus]` | Any past task has this dispatch status |
| `any_delivery_status` | `list[DeliveryStatus]` | Any past task has this delivery status |
| `most_recent_dispatch_status` | `list[DispatchStatus]` | Most recent task has this dispatch status |
| `most_recent_delivery_status` | `list[DeliveryStatus]` | Most recent task has this delivery status |

## Monitoring delivery

```python
# All delivery jobs for this survey
deliveries = handler.list_deliveries()
for d in deliveries["deliveries"]:
    print(d["delivery_uuid"], d["status"], d["sent_count"], d["failed_count"])

# Details for one job
delivery = handler.get_delivery(delivery_uuid="...")

# Per-respondent breakdown
tasks = handler.list_delivery_tasks(delivery_uuid="...")
for task in tasks["tasks"]:
    print(task["identifier"], task["dispatch_status"], task["delivery_status"])

# Details for one respondent's task
task = handler.get_delivery_task(task_uuid="...")
```

### Status tracks

Each delivery task carries three independent status fields:

| Track | What it measures | States |
|-------|-----------------|--------|
| Dispatch | Whether the platform handed the message off to the email provider | `pending` → `dispatched` / `failed` |
| Delivery | What the email provider reports back after dispatch | `pending` → `sent` → `delivered` / `bounced` / `failed` |
| Response | Whether the respondent has engaged with the survey itself | `not_started` → `completed` |

## Updating a route's subject or template

For a route on a schedule:

```python
handler.patch_schedule_respondent_email_route(
    schedule_uuid="...",
    route_uuid="...",
    subject="A quick reminder about our survey",
    delivery_template="<p>Hi! Please take a moment to complete our survey.</p>",
)
```

For a route on a callback:

```python
handler.patch_callback_respondent_email_route(
    callback_uuid="...",
    route_uuid="...",
    subject="Thanks for completing our survey",
    delivery_template="<p>Hi! Thank you for completing <strong>{{ survey_name }}</strong>.</p>",
)
```

## Respondent and agent list management

```python
# List all respondents with their response status
respondents = handler.get_respondents()
for r in respondents["respondents"]:
    print(r["respondent_uuid"], r["response_status"])

# View delivery channel configuration
config = handler.get_agent_list()
print(config["agent_list_config"])

# Update the email column mapping
from edsl.coop.coop_humanize_notifications import ChannelConfig, DeliveryMap

handler.patch_agent_list(
    delivery_map=DeliveryMap(email=ChannelConfig(col_name="email_address"))
)
```

## Quick reference

| Task | Code |
|------|------|
| Send immediately (server defaults) | `handler.send_respondent_email(name="...")` |
| Send with custom subject/template | `handler.send_respondent_email(name=..., subject=..., delivery_template=...)` |
| Schedule one-time send | `handler.create_one_time_schedule(name=..., run_at=..., subject=..., delivery_template=...)` |
| Update a schedule | `handler.update_one_time_schedule(schedule_uuid=..., run_at=...)` |
| Create cron schedule | `handler.create_cron_schedule(name=..., cron_expression=..., timezone=..., max_jobs=N, ...)` |
| Pause/resume schedule | `handler.deactivate_schedule(schedule_uuid)` / `handler.activate_schedule(schedule_uuid)` |
| On-completion callback | `handler.create_callback(name=..., callback_type="human_survey_respondent.completed", ...)` |
| On-response-submitted callback | `handler.create_callback(name=..., callback_type="human_survey_respondent.response_submitted", ...)` |
| Notify owner on every response | `handler.create_owner_response_callback(name=...)` |
| Send respondent a transcript | `handler.create_transcript_callback(name=..., recipient="respondent")` |
| Send owner a transcript on every submission | `handler.create_transcript_callback(name=..., recipient="owner")` |
| Toggle callback | `handler.deactivate_callback(callback_uuid)` / `handler.activate_callback(callback_uuid)` |
| Email only non-starters | filter with `RespondentCondition(response_status=[ResponseStatus.not_started])` |
| Email never-contacted | filter with `RespondentCondition(never_contacted=True)` |
| Check delivery status | `handler.list_deliveries()` / `handler.list_delivery_tasks(delivery_uuid=...)` |
| View respondent list | `handler.get_respondents()` |
| Update schedule route subject/template | `handler.patch_schedule_respondent_email_route(schedule_uuid=..., route_uuid=..., ...)` |
| Update callback route subject/template | `handler.patch_callback_respondent_email_route(callback_uuid=..., route_uuid=..., ...)` |
