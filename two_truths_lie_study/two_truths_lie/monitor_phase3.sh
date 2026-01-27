#!/bin/bash
# Monitor Phase 3 experiment progress

RESULTS_DIR="results/phase3_flagship/rounds"
TOTAL_ROUNDS=240
LAST_COUNT=0

echo "========================================================================"
echo "PHASE 3 MONITORING - FLAGSHIP MODELS"
echo "========================================================================"
echo ""
echo "Models being tested:"
echo "  1. claude-opus-4-5-20251101 (Direct API)"
echo "  2. claude-sonnet-4-20250514 (EDSL Proxy)"
echo "  3. gpt-5-2025-08-07 (EDSL Proxy)"
echo "  4. o3-2025-04-16 (EDSL Proxy)"
echo ""
echo "Total rounds: $TOTAL_ROUNDS (4 models × 2 roles × 30 rounds)"
echo "========================================================================"
echo ""

while true; do
    if [ -d "$RESULTS_DIR" ]; then
        CURRENT_COUNT=$(ls -1 "$RESULTS_DIR" 2>/dev/null | wc -l | tr -d ' ')

        if [ "$CURRENT_COUNT" -gt "$LAST_COUNT" ]; then
            PROGRESS=$(echo "scale=1; $CURRENT_COUNT / $TOTAL_ROUNDS * 100" | bc)
            CONDITION=$((CURRENT_COUNT / 30))
            ROUND_IN_CONDITION=$((CURRENT_COUNT % 30))

            if [ $ROUND_IN_CONDITION -eq 0 ]; then
                ROUND_IN_CONDITION=30
                CONDITION=$((CONDITION - 1))
            fi

            echo "[$(date +%H:%M:%S)] Round $CURRENT_COUNT/$TOTAL_ROUNDS ($PROGRESS%) - Condition $CONDITION, Round $ROUND_IN_CONDITION/30"

            LAST_COUNT=$CURRENT_COUNT

            # Report milestones
            if [ $CURRENT_COUNT -eq 60 ]; then
                echo "  🎯 MILESTONE: 1 model complete (60 rounds)"
            elif [ $CURRENT_COUNT -eq 120 ]; then
                echo "  🎯 MILESTONE: 2 models complete (120 rounds)"
            elif [ $CURRENT_COUNT -eq 180 ]; then
                echo "  🎯 MILESTONE: 3 models complete (180 rounds)"
            elif [ $CURRENT_COUNT -eq 240 ]; then
                echo "  ✅ PHASE 3 COMPLETE!"
                break
            fi
        fi
    fi

    # Check every 30 seconds
    sleep 30
done

echo ""
echo "========================================================================"
echo "Phase 3 monitoring complete"
echo "========================================================================

"
