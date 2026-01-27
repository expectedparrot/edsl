#!/bin/bash
# Monitor Phase 2 experiment and report milestones

OUTPUT_FILE="/private/tmp/claude/-Users-randallbennington-Documents-GitHub-edsl-wwil-two-truths-lie-study/tasks/b9fb145.output"
RESULTS_DIR="results/phase2_small/rounds"
MILESTONE_FILE="/tmp/phase2_milestones.txt"

# Initialize milestone tracking
echo "0" > "$MILESTONE_FILE"

while true; do
    if [ -d "$RESULTS_DIR" ]; then
        ROUNDS=$(ls -1 "$RESULTS_DIR" 2>/dev/null | wc -l | tr -d ' ')
        LAST_MILESTONE=$(cat "$MILESTONE_FILE" 2>/dev/null || echo "0")

        # Check for condition completions (every 30 rounds)
        CURRENT_CONDITION=$((ROUNDS / 30))
        LAST_CONDITION=$((LAST_MILESTONE / 30))

        if [ $CURRENT_CONDITION -gt $LAST_CONDITION ]; then
            echo "[MILESTONE] Condition $CURRENT_CONDITION completed! ($ROUNDS/240 rounds)"
            echo "$ROUNDS" > "$MILESTONE_FILE"

            # Check current condition from output
            tail -50 "$OUTPUT_FILE" | grep -E "Condition:|complete" | tail -3
        fi

        # Check for gemini rounds (starts at round 60)
        if [ $ROUNDS -ge 60 ] && [ $LAST_MILESTONE -lt 60 ]; then
            echo "[MILESTONE] 🔥 Gemini-2.5-flash testing has begun!"
            echo "$ROUNDS" > "$MILESTONE_FILE"
        fi

        # Check for completion
        if [ $ROUNDS -ge 240 ]; then
            echo "[MILESTONE] ✅ Phase 2 COMPLETE! All 240 rounds finished."
            break
        fi

        # Report progress every 30 rounds
        if [ $((ROUNDS % 30)) -eq 0 ] && [ $ROUNDS -gt $LAST_MILESTONE ]; then
            PROGRESS=$(echo "scale=1; $ROUNDS / 240 * 100" | bc)
            echo "[UPDATE] Progress: $ROUNDS/240 ($PROGRESS%)"
            echo "$ROUNDS" > "$MILESTONE_FILE"
        fi
    fi

    sleep 120  # Check every 2 minutes
done

echo "[COMPLETE] Phase 2 monitoring finished."
