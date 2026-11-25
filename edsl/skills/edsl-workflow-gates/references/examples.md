# Gate setup and verification

Initialize a workflow and define its ordered gates in one command:

```bash
ep workflow setup --name color-survey --root . \
  --spec workflow-gates.json \
  --evidence "Approved plan and gate set from the project brief"
```

For example, `workflow-gates.json` can contain:

```json
{
  "gates": [
    {
      "name": "plan-approved",
      "description": "The user approved the study plan",
      "verification": { "type": "user-approval" }
    },
    {
      "name": "report-rendered",
      "description": "The promised report exists",
      "verification": { "type": "file-exists", "path": "writeup/report.html" }
    }
  ]
}
```

Record the approval, verify the file gate, and inspect status:

```bash
ep workflow gate attest plan-approved --by user \
  --evidence "Approved in the project conversation"
ep workflow gate verify report-rendered
ep workflow status
```

For incremental setup, use `ep workflow init`, `ep workflow gate set`, and
`ep workflow freeze`. Gate setup validates the full set atomically. Gates pass
in order; changing an earlier gate invalidates downstream passes. See
`ep workflow --help` for the installed CLI's full command set.
