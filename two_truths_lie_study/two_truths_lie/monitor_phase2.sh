#!/bin/bash
# Monitor Phase 2 experiment progress

OUTPUT_FILE="/private/tmp/claude/-Users-randallbennington-Documents-GitHub-edsl-wwil-two-truths-lie-study/tasks/b9fb145.output"
RESULTS_DIR="results/phase2_small/rounds"

while true; do
    clear
    echo "======================================================================"
    echo "PHASE 2 PROGRESS MONITOR"
    echo "======================================================================"
    echo
    echo "Time: $(date '+%Y-%m-%d %H:%M:%S')"
    echo

    # Count completed rounds
    if [ -d "$RESULTS_DIR" ]; then
        ROUND_COUNT=$(ls -1 "$RESULTS_DIR" 2>/dev/null | wc -l | tr -d ' ')
        PROGRESS=$(echo "scale=1; $ROUND_COUNT / 240 * 100" | bc)
        echo "Completed Rounds: $ROUND_COUNT / 240 ($PROGRESS%)"
    else
        echo "Completed Rounds: 0 / 240 (0.0%)"
    fi

    echo
    echo "Latest Output (last 20 lines):"
    echo "----------------------------------------------------------------------"
    tail -20 "$OUTPUT_FILE" 2>/dev/null || echo "No output yet..."

    echo
    echo "----------------------------------------------------------------------"
    echo "Press Ctrl+C to stop monitoring"
    echo

    sleep 60  # Update every minute
done
