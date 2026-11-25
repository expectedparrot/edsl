# Shared-state CLI commands

The CLI operates on a serialized `Machine` JSON file. It is useful for
validation, local transition replay, and saved Results inspection; it does not
provide an interactive Machine builder.

```bash
ep state validate --file machine.json
ep state inspect --file machine.json
ep state simulate --file machine.json --transitions transitions.json
ep results state --file results.ep
ep results state --file results.ep --binding 0
```

`validate` reports structural validity, required capabilities, and whether the
installed built-in runtime can initialize and render the machine. A definition
may be structurally valid while requiring an unregistered custom algorithm.
`inspect` summarizes fields, commands, views, and capability requirements.

`simulate` accepts a JSON array of transitions. Each element has a command name,
an optional `inputs` object, and optional `current` context:

```json
[
  {"command": "vote", "inputs": {"voter": "Amina", "activity": "hike"}},
  {"command": "vote", "inputs": {"voter": "Boris", "activity": "sailing"}}
]
```

The response includes each event, resulting state, rendered view, and completion
status. Simulation is local and does not create a backend or mutate a saved
Results object.

`ep results state` reads the `shared_state` provenance stored with Results. It
returns all bindings by default; `--binding` selects one zero-based binding
index. It does not filter by scope or snapshot type yet. CLI stdout uses the
standard JSON status envelope.
