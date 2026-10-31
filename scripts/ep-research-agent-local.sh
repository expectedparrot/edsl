#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
EDSL_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"

# EDSL's default dotenv loading overwrites shell values. development-testrun
# keeps the localhost URL below and requires explicit rate-limit defaults.
export EDSL_RUN_MODE=development-testrun
export EDSL_SERVICE_RPM_BASELINE="${EDSL_SERVICE_RPM_BASELINE:-1000}"
export EDSL_SERVICE_TPM_BASELINE="${EDSL_SERVICE_TPM_BASELINE:-2000000}"
export EXPECTED_PARROT_URL="${EXPECTED_PARROT_URL:-http://localhost:1234}"

if (($# == 0)); then
    set -- sessions --filter all
fi

exec uv run --project "$EDSL_ROOT" ep research-agent "$@"
