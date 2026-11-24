# Fetchable workflow examples

These complete source files ship with the matching EDSL version and can be
retrieved through `ep`:

```bash
ep skills list --routing
ep skills show edsl-orchestration --example workflows/workflow_weekend_activity_revision.py
```

The weekend-activity examples run locally with scripted respondents. The stress
gallery exercises many workflow shapes and writes its results under the
current directory's `artifacts/`. `workflow_schelling_claims_humanize.py`
requires two explicit email addresses when creating a run; it can send
Humanize invitations.
