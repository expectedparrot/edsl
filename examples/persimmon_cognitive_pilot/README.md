# Persimmon cognitive pilot

This small pilot runs four classic judgment questions with twelve fictional
personas using Persimmon's conversation API. It makes paid model calls.

The Makefile uses the repository's existing `.venv`; it does not require a
separate `uv.lock` for this example. From the repository root:

```bash
cd examples/persimmon_cognitive_pilot
make env-check
make qa
```

Set `PERSIMMON_API_KEY` in the environment before running the pilot:

```bash
make run-pilot
```

Results are written under `results/`, with answer counts saved to
`analysis/summary.json`. `make qa` validates the personas defined in
`run_pilot.py`; it does not require a separate CSV or provenance file.
