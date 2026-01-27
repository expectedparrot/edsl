#!/bin/bash
# Helper script for running baseline experiments
# Handles Python version and PYTHONPATH setup

set -e

# Find Python 3.10+ (required for EDSL)
if command -v python3.11 &> /dev/null; then
    PYTHON=python3.11
elif command -v python3.10 &> /dev/null; then
    PYTHON=python3.10
elif command -v python3.12 &> /dev/null; then
    PYTHON=python3.12
else
    echo "Error: Python 3.10+ is required but not found"
    echo "Please install Python 3.10 or later"
    exit 1
fi

echo "Using Python: $PYTHON"
$PYTHON --version

# Get the script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PARENT_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"

# Set PYTHONPATH to include parent directory (for edsl)
export PYTHONPATH="$PARENT_DIR:$PYTHONPATH"

# Change to script directory
cd "$SCRIPT_DIR"

# Run the experiment script with all arguments
$PYTHON run_baseline_experiment.py "$@"
