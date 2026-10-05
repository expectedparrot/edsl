# Study contracts and cost reconciliation

Survey scaffolds now create `study-contract.json`. Before `make prepare`, edit
its jobs, expected row counts, required answers, protected sources, and
deliverables to match the approved plan. Include every planned job and output
format. `prepare` snapshots the specification, plan, and protected source
hashes into `.study-contract/0001.json`. `qa` verifies results against that
snapshot; `report-check` also checks required deliverables.

For an existing or neutral scaffold, use the commands directly:

```bash
ep study contract freeze --root study --spec study/study-contract.json \
  --approval-evidence "Approved protocol in conversation turn 8"
ep study contract verify --root study --phase results
ep study contract verify --root study --phase complete
```

The version 1 specification has this shape:

```json
{
  "schema_version": 1,
  "plan_path": "plan.md",
  "jobs": [{
    "id": "job_a",
    "jobs_path": "edsl_jobs/job_a/jobs.ep",
    "results_path": "data/results.ep",
    "expected_rows": 100,
    "required_answers": ["preference"]
  }],
  "deliverables": ["writeup/report.html", "writeup/report.pdf"],
  "protected_sources": ["analysis/validate_results.py"]
}
```

The `jobs` list may be empty for a document-only study. All paths are relative
to the study root. Add construction sources to `protected_sources`. A mutable
spec edit or an edited validator does not replace the frozen expectation.
Amendments require a reason and new approval evidence and preserve earlier
revisions:

```bash
ep study contract amend --root study --spec study/study-contract.json \
  --reason "Researcher accepted one missing response; report missingness" \
  --approval-evidence "Approved amendment in conversation turn 15"
```

These checks detect accidental workflow drift. They do not authenticate human
approval in an agent-writable workspace, establish scientific validity, or
enforce a spending ceiling. Existing generated Makefiles are not silently
rewritten: use the explicit checks when maintaining an older study.

`Results.reconcile_job_cost(remote_status)` compares Results' uncached costs
with supplied finalized remote accounting. It performs no network calls and
returns `matched`, `mismatch`, or `not_comparable`. Remote retrieval also runs
this check. `ep jobs results JOB_UUID --output results.ep` exposes the
diagnostic and any discrepancy in its JSON envelope.

The tolerance is the greater of $0.0001 and 1% of the remote cost. Missing cost
or cache metadata, incomplete row coverage, pending jobs, and known separately
billed retries are not comparable. A mismatch does not establish which ledger
is correct. It emits `RemoteCostMismatchWarning` while preserving answers;
even warning-as-error configuration does not turn it into an inference retry.
