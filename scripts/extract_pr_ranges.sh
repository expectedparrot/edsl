#!/bin/bash
# EDSL PR Range Extraction Script
# 
# This script extracts pull request information for specified version ranges from the EDSL repository.
# It uses the GitHub CLI to fetch PR data.
#
# Usage:
#   ./scripts/extract_pr_ranges.sh <start_pr> <end_pr> <output_file>
#
# Examples:
#   ./scripts/extract_pr_ranges.sh 2057 2103 /tmp/v1_0_1_prs.json
#   ./scripts/extract_pr_ranges.sh 2104 2172 /tmp/v1_0_2_prs.json
#   ./scripts/extract_pr_ranges.sh 1969 2011 /tmp/v0_1_61_prs.json

# Check if correct number of arguments provided
if [ $# -ne 3 ]; then
    echo "Usage: $0 <start_pr> <end_pr> <output_file>"
    echo ""
    echo "Examples:"
    echo "  $0 2057 2103 /tmp/v1_0_1_prs.json"
    echo "  $0 2104 2172 /tmp/v1_0_2_prs.json" 
    echo "  $0 1969 2011 /tmp/v0_1_61_prs.json"
    exit 1
fi

START_PR=$1
END_PR=$2
OUTPUT_FILE=$3

echo "Extracting PRs #$START_PR to #$END_PR from expectedparrot/edsl..."

# Execute the GitHub CLI command
gh pr list --repo expectedparrot/edsl --state merged --limit 300 --json number,title,body,mergedAt,baseRefName,author,url --jq ".[] | select(.baseRefName == \"main\" and .number >= $START_PR and .number <= $END_PR)" > "$OUTPUT_FILE"

# Check if the command was successful
if [ $? -eq 0 ]; then
    # Count the number of PRs extracted
    PR_COUNT=$(wc -l < "$OUTPUT_FILE")
    echo "✅ Successfully extracted $PR_COUNT PRs"
    echo "📄 Data saved to: $OUTPUT_FILE"
else
    echo "❌ Error: Failed to extract PRs"
    exit 1
fi
