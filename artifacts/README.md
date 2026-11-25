# Local artifacts

This directory is for generated run state and rendered outputs. Keep source
examples, tests, and maintained documentation in their normal source
directories. Outputs produced here are local and are generally ignored by Git.

- `shared-state-acceptance/` is the output root for the shared-state coopr
  acceptance scripts. The tracked `.gitignore` keeps run-specific Results,
  reports, and databases local.
- The shared-state case-study builders, workflow gallery, Humanize example, and
  path-dependence report write rendered pages, SQLite state, and report files
  here.

Use a fresh output directory for each run when the script supports `--output`
or `--output-dir`. Historical acceptance reports are not archived in this
repository; the runbook records outcomes and commands for reproducing them.
