#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Install EDSL from the harness-guidance branch, authenticate with Expected Parrot,
and install the EDSL harness skill for one coding harness.

Usage: bash harnesses/install.sh <harness>

Harnesses: codex, claude-code, opencode, pi, antigravity, fx

Activate the Python environment you want EDSL installed into before running.
USAGE
}

if [[ $# -ne 1 ]]; then
  usage >&2
  exit 2
fi

harness=$1
case "$harness" in
  codex)
    command_name=codex
    install_kind=codex
    skill_dir="$HOME/.agents/skills"
    ;;
  claude-code)
    command_name=claude
    install_kind=claude-code
    skill_dir="$HOME/.claude/skills"
    ;;
  opencode)
    command_name=opencode
    install_kind=opencode
    skill_dir="$HOME/.config/opencode/skills"
    ;;
  pi)
    command_name=pi
    install_kind=pi
    skill_dir="$HOME/.pi/agent/skills"
    ;;
  antigravity)
    command_name=agy
    install_kind=antigravity
    skill_dir="$HOME/.gemini/config/skills"
    ;;
  fx)
    command_name=fx
    install_kind=fx
    skill_dir="$HOME/.fx/skills"
    ;;
  -h|--help|help)
    usage
    exit 0
    ;;
  *)
    printf 'Unknown harness: %s\n\n' "$harness" >&2
    usage >&2
    exit 2
    ;;
esac

if ! command -v curl >/dev/null 2>&1; then
  printf 'curl is required to install the selected harness.\n' >&2
  exit 1
fi

if ! command -v "$command_name" >/dev/null 2>&1; then
  printf 'Installing %s...\n' "$harness"
  case "$install_kind" in
    codex) curl -fsSL https://chatgpt.com/codex/install.sh | sh ;;
    claude-code) curl -fsSL https://claude.ai/install.sh | bash ;;
    opencode) curl -fsSL https://opencode.ai/v2/install | bash ;;
    pi) curl -fsSL https://pi.dev/install.sh | sh ;;
    antigravity) curl -fsSL https://antigravity.google/cli/install.sh | bash ;;
    fx) curl -fsSL https://fx.sh/setup.sh | bash ;;
  esac
  export PATH="$HOME/.local/bin:$HOME/.bun/bin:$HOME/.cargo/bin:$PATH"
fi

if ! command -v python3 >/dev/null 2>&1; then
  printf 'python3 is required. Install Python 3.10–3.13, activate the environment, and rerun this script.\n' >&2
  exit 1
fi

printf 'Installing EDSL from feat/edsl-harness-guidance...\n'
python3 -m pip install --upgrade \
  'edsl @ git+https://github.com/expectedparrot/edsl.git@feat/edsl-harness-guidance'

run_ep() {
  python3 -m edsl "$@"
}

printf 'Checking Expected Parrot authentication...\n'
if auth_status=$(run_ep auth status); then
  :
else
  printf '%s\n' "$auth_status" >&2
  printf 'Could not check Expected Parrot authentication.\n' >&2
  exit 1
fi
if printf '%s' "$auth_status" | python3 -c '
import json, sys
try:
    result = json.load(sys.stdin)
except Exception:
    raise SystemExit(2)
if result.get("status") != "ok":
    raise SystemExit(2)
raise SystemExit(0 if result.get("data", {}).get("authenticated") else 1)
'; then
  :
else
  auth_rc=$?
  if [[ $auth_rc -eq 2 ]]; then
    printf 'Could not read a successful JSON response from `ep auth status`.\n' >&2
    exit 1
  fi
  printf 'No Expected Parrot key is configured. Starting browser login...\n'
  run_ep auth login
fi

printf 'Installing edsl-harness for %s...\n' "$harness"
if skill_install=$(run_ep skills install --target "$skill_dir" --skill edsl-harness); then
  :
else
  printf '%s\n' "$skill_install" >&2
  printf 'Could not install edsl-harness.\n' >&2
  exit 1
fi
printf '%s' "$skill_install" | python3 -c '
import json, sys
try:
    result = json.load(sys.stdin)
except Exception as exc:
    print(f"Could not parse `ep skills install` JSON output: {exc}", file=sys.stderr)
    raise SystemExit(1)
if result.get("status") != "ok":
    print(result.get("error", {}).get("message", "EDSL skill installation failed"), file=sys.stderr)
    raise SystemExit(1)
'
printf '%s\n' "$skill_install"
printf 'Setup complete. Launching %s in %s...\n' "$command_name" "$PWD"
exec "$command_name"
