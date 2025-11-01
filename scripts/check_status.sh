#!/bin/bash
#
# Show status of pre-push checks for current commit
#

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

CHECK_FILE=".git/edsl-checks"
CURRENT_COMMIT=$(git rev-parse HEAD 2>/dev/null || echo "no-git")

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}EDSL Pre-Push Check Status${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo "Current commit: ${CURRENT_COMMIT:0:8}"
echo ""

REQUIRED_CHECKS=("BLACK" "RUFF" "TESTS" "DOCTESTS" "BENCHMARKS")

if [ ! -f "$CHECK_FILE" ]; then
    echo -e "${RED}No checks have been run yet${NC}"
    echo ""
    for check in "${REQUIRED_CHECKS[@]}"; do
        echo -e "  ${RED}✗${NC} $check"
    done
else
    ALL_COMPLETE=true
    for check in "${REQUIRED_CHECKS[@]}"; do
        if grep -q "^${check}:${CURRENT_COMMIT}$" "$CHECK_FILE"; then
            echo -e "  ${GREEN}✓${NC} $check"
        else
            echo -e "  ${RED}✗${NC} $check"
            ALL_COMPLETE=false
        fi
    done

    echo ""
    if [ "$ALL_COMPLETE" = true ]; then
        echo -e "${GREEN}All checks complete! You can push.${NC}"
    else
        echo -e "${YELLOW}Some checks still needed before you can push.${NC}"
    fi
fi

echo -e "${BLUE}========================================${NC}"
