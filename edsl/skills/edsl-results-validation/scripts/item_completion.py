"""Audit numeric ratings in studies with a known complete exposure_order."""
import argparse
import csv
from collections import defaultdict
from pathlib import Path

from edsl import Results


def audit(results, wave_field, items, minimum, maximum):
    """Yield one row per wave and requested item, including empty cells."""
    exposed = defaultdict(int)
    answered = defaultdict(int)
    total = defaultdict(float)
    waves = set()
    for interview in results:
        wave = interview.scenario[wave_field]
        shown = interview["randomization"].get("exposure_order")
        if not isinstance(shown, list):
            raise ValueError(f"Missing exposure_order in wave {wave!r}")
        waves.add(wave)
        for item in items:
            if item not in shown:
                continue
            key = (wave, item)
            exposed[key] += 1
            value = interview.answer.get(item)
            if type(value) in (int, float) and minimum <= value <= maximum:
                answered[key] += 1
                total[key] += value

    for wave in sorted(waves):
        for item in items:
            key = (wave, item)
            count = answered[key]
            mean = round(total[key] / count, 2) if count else None
            yield wave, item, exposed[key], count, mean


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("results", type=Path)
    parser.add_argument("--wave-field", required=True, help="Scenario field identifying the wave.")
    parser.add_argument("--item", action="append", required=True, help="Rated question name. Repeat in output order.")
    parser.add_argument("--min-score", type=float, required=True)
    parser.add_argument("--max-score", type=float, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if len(set(args.item)) != len(args.item) or args.min_score > args.max_score:
        parser.error("Supply distinct items and an ordered score range.")
    if args.output.resolve() == args.results.resolve():
        parser.error("Choose a CSV destination separate from the Results package.")
    results = Results.git.load(args.results, sync_coop=False)
    unknown = set(args.item) - set(results.survey.question_names)
    if unknown:
        parser.error(f"Unknown survey items: {sorted(unknown)}")
    rows = list(audit(results, args.wave_field, args.item, args.min_score, args.max_score))
    with args.output.open("w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["wave", "item", "exposed", "answered", "mean"])
        writer.writerows(rows)


if __name__ == "__main__":
    main()
