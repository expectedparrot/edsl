#!/bin/bash
#
# Mark a check as complete for the current commit
#

CHECK_NAME=$1
CHECK_FILE=".git/edsl-checks"
CURRENT_COMMIT=$(git rev-parse HEAD 2>/dev/null || echo "no-git")

if [ -z "$CHECK_NAME" ]; then
    echo "Usage: mark_check_complete.sh CHECK_NAME"
    exit 1
fi

# Remove old entries for this check
if [ -f "$CHECK_FILE" ]; then
    grep -v "^${CHECK_NAME}:" "$CHECK_FILE" > "${CHECK_FILE}.tmp" || true
    mv "${CHECK_FILE}.tmp" "$CHECK_FILE"
fi

# Add new entry
echo "${CHECK_NAME}:${CURRENT_COMMIT}" >> "$CHECK_FILE"

echo "✓ Marked $CHECK_NAME as complete for commit ${CURRENT_COMMIT:0:8}"
