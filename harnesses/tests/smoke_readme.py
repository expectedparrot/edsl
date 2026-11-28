"""Run published README installers in disposable Linux containers.

    python3 harnesses/tests/smoke_readme.py codex pi
    python3 harnesses/tests/smoke_readme.py --all
"""

import argparse
from pathlib import Path
import re
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
IMAGE = "edsl-readme-smoke:local"

# Agent launchers whose executable name differs from the selector in the README.
EXECUTABLE = {
    "claude-code": "claude",
    "cursor": "cursor-agent",
    "antigravity": "agy",
    "kiro": "kiro-cli",
}

CHECK = r"""
set -eu -o pipefail
mkdir study && cd study
if command -v ep || command -v "$2"; then
    echo 'Expected a clean user environment' >&2
    exit 1
fi
# Docker supplies no controlling terminal, so --launch should print next steps.
bash -o pipefail -c "$1"
test -r "$HOME/$3/edsl-harness/SKILL.md"
# Discover the executable and the shared ep launcher in a fresh login shell.
bash -lc 'command -v "$1" && command -v ep' _ "$2"
ep skills show edsl-harness | python3 -c 'import json,sys; r=json.load(sys.stdin); assert r["status"] == "ok" and r["data"]["name"] == "edsl-harness", r'
ep surveys create --question-type free_text --question-name coffee --question-text "How do you make coffee?" --output coffee.ep |
    python3 -c 'import json,sys; r=json.load(sys.stdin); assert r["status"] == "ok", r'
ep surveys questions coffee.ep |
    python3 -c 'import json,sys; r=json.load(sys.stdin); assert r["status"] == "ok" and r["data"]["questions"][0]["question_name"] == "coffee", r'
"""


def main():
    guide = (ROOT / "harnesses/README.md").read_text()
    readmes = (ROOT / "README.md").read_text() + "\n" + guide
    commands = {
        slug: command
        for command, slug in re.findall(
            r"^```bash\n(curl [^\n]+ \| bash -s -- ([\w-]+) --launch)\n```",
            readmes,
            re.MULTILINE,
        )
    }
    skill_dirs = dict(
        re.findall(r"^\| [^|]+ \| `([\w-]+)` \| `~/([^`]+)` \|", guide, re.MULTILINE)
    )
    if commands.keys() != skill_dirs.keys():
        sys.exit(
            f"Missing README command or skill directory for {commands.keys() ^ skill_dirs.keys()}"
        )

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("harnesses", nargs="*", metavar="HARNESS")
    parser.add_argument(
        "--all", action="store_true", help="run each documented installer"
    )
    args = parser.parse_args()
    targets = list(commands) if args.all else args.harnesses
    if not targets or set(targets) - commands.keys() or (args.all and args.harnesses):
        parser.error("choose --all or harness names from " + ", ".join(commands))

    subprocess.run(
        ["docker", "build", "-t", IMAGE, "-"],
        input=(HERE / "Dockerfile").read_bytes(),
        check=True,
    )
    failures = []
    for slug in targets:
        # A synthetic configured key exercises setup without opening a browser.
        # Direct requests to loopback so this test cannot use an EP account.
        result = subprocess.run(
            [
                "docker",
                "run",
                "--rm",
                "--init",
                "-e",
                "EXPECTED_PARROT_API_KEY=smoke-test",
                "-e",
                "EXPECTED_PARROT_URL=https://127.0.0.1:1",
                IMAGE,
                "timeout",
                "--kill-after=10s",
                "15m",
                "bash",
                "-c",
                CHECK,
                "_",
                commands[slug],
                EXECUTABLE.get(slug, slug),
                skill_dirs[slug],
            ]
        )
        print(f"{slug} {'PASS' if result.returncode == 0 else 'FAIL'}", flush=True)
        if result.returncode:
            failures.append(slug)
    if failures:
        sys.exit("Failed installers: " + ", ".join(failures))


if __name__ == "__main__":
    main()
