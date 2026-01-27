#!/bin/bash
# Monitor the Phase 3 test and report progress

OUTPUT_FILE="/private/tmp/claude/-Users-randallbennington-Documents-GitHub-edsl-wwil-two-truths-lie-study/tasks/bc4f0de.output"

while true; do
    if [ -f "$OUTPUT_FILE" ]; then
        # Count successful completions
        COMPLETIONS=$(grep -c "✅ Round completed successfully" "$OUTPUT_FILE" 2>/dev/null || echo "0")
        FAILURES=$(grep -c "❌ FAILED:" "$OUTPUT_FILE" 2>/dev/null || echo "0")
        TOTAL=$((COMPLETIONS + FAILURES))

        if [ $TOTAL -gt 0 ]; then
            echo "[$(date +%H:%M:%S)] Progress: $COMPLETIONS/8 successful, $FAILURES failures"

            # Show latest completion or failure
            tail -20 "$OUTPUT_FILE" | grep -E "TESTING:|as JUDGE|as STORYTELLER|✅ Round|❌ FAILED" | tail -5
        fi

        # Check if test is complete
        if grep -q "ALL MODELS READY FOR PHASE 3!" "$OUTPUT_FILE" 2>/dev/null; then
            echo "[$(date +%H:%M:%S)] ✅ TEST COMPLETE - All models working!"
            break
        fi

        if grep -q "SOME MODELS HAVE ISSUES" "$OUTPUT_FILE" 2>/dev/null; then
            echo "[$(date +%H:%M:%S)] ❌ TEST COMPLETE - Some models failed"
            break
        fi

        # Check if 50% complete (4 rounds)
        if [ $COMPLETIONS -ge 4 ] && [ ! -f "/tmp/phase3_started" ]; then
            echo "[$(date +%H:%M:%S)] 🎯 50% COMPLETE - Ready to start Phase 3!"
            touch /tmp/phase3_started
            break
        fi
    fi

    sleep 10
done

echo ""
echo "Final status:"
tail -30 "$OUTPUT_FILE" | grep -E "SUMMARY|Judge:|Storyteller:|READY|ISSUES"
