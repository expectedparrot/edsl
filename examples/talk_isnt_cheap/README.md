# Talk Isn't Always Cheap replication

This directory implements a serializable design replication of Wynn, Satija,
and Hadfield (2025), *Talk Isn't Always Cheap: Understanding Failure Modes in
Multi-Agent Debate* (`arXiv:2509.05396v2`). Object construction and tests make
no model calls.

`debate_experiment.py` provides:

- a three-stage workflow: independent round 0, debate round 1, debate round 2;
- an append-only shared-state ledger of identified answers and reasoning;
- the paper's ten homogeneous/heterogeneous three-model compositions;
- base and correctness-payoff treatments;
- the paper's five-seed, 100-item-per-dataset execution manifest; and
- deterministic majority and answer-transition analysis.

The workflow is intentionally item-level. A study runner should sample 100 items
from each of CSQA, MMLU, and GSM8K for each seed, create one workflow instance
per item/composition/treatment, and bind each participant to the model named in
its `model` trait. Remote execution and dataset acquisition are deliberately not
performed by this design module.

The prior-round prompt uses a serialized participant-relative submission view.
Each recipient receives its own prior response as `self_response` and the other
two submissions as `peer_responses`, while the workflow retains participant
identities for auditing and analysis.

Run the local design checks with:

```bash
pytest -q tests/examples/test_talk_isnt_cheap.py
```

Print the serialized example design with:

```bash
python -m examples.talk_isnt_cheap.debate_experiment
```

Run the nine-response CSQA pilot through the local EDSL/OpenAI path with:

```bash
python -m examples.talk_isnt_cheap.run_openai_pilot \
  --model gpt-4o-mini \
  --output-dir examples/talk_isnt_cheap/runs/my-fresh-pilot
```

`disable_remote_inference=True` means EDSL calls the configured model provider
from this process rather than Expected Parrot remote inference. The command
therefore requires local OpenAI credentials. Use a fresh output directory for
each run so immutable workflow and state histories are never mixed.

The standalone write-up is available as
[`report/talk_isnt_cheap_edsl_report.pdf`](report/talk_isnt_cheap_edsl_report.pdf),
with its LaTeX source beside it. It shows the EDSL syntax and setup, reports the
local pilot results, and distinguishes this small design check from the paper's
full experiment.
