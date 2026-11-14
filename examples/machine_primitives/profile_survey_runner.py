"""Local coverage benchmark; --uncached reproduces per-use survey decoding.

Run: python -m examples.machine_primitives.profile_survey_runner [--uncached]
No model calls. Counts are diagnostics, not a stable performance contract.
"""

import argparse
from contextlib import nullcontext
import json
from time import perf_counter
from unittest.mock import patch

from edsl import Survey
from edsl.runner.survey_cache import SurveyCache
from edsl.sharedstate import Machine
from examples.question_coverage import run_demo


def profile(*, agents=5, uncached=False):
    counts = {"survey_decodes": 0, "machine_validations": 0}
    decode, validate = Survey.from_dict, Machine.validate

    def counted_decode(cls, *args, **kwargs):
        counts["survey_decodes"] += 1
        return decode(*args, **kwargs)

    def counted_validate(self, *args, **kwargs):
        counts["machine_validations"] += 1
        return validate(self, *args, **kwargs)

    bypass = (
        patch.object(SurveyCache, "get", lambda self, data: Survey.from_dict(data))
        if uncached
        else nullcontext()
    )
    with (
        patch.object(Survey, "from_dict", classmethod(counted_decode)),
        patch.object(Machine, "validate", counted_validate),
        bypass,
    ):
        start = perf_counter()
        report = run_demo(count=agents)
        seconds = perf_counter() - start
    return {
        "mode": "uncached" if uncached else "cached",
        "seconds": seconds,
        **counts,
        "report": report,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--agents", type=int, default=5)
    parser.add_argument("--uncached", action="store_true")
    args = parser.parse_args()
    print(json.dumps(profile(agents=args.agents, uncached=args.uncached), indent=2))
