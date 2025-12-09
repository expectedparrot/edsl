#!/bin/bash
#
# Install Git Hooks for EDSL
#
# This script installs custom git hooks for the EDSL project.
# Run this after cloning the repository to set up pre-push checks.
#

set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}EDSL Git Hooks Installation${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Get the git root directory
GIT_ROOT=$(git rev-parse --show-toplevel)

if [ -z "$GIT_ROOT" ]; then
    echo -e "${RED}Error: Not in a git repository${NC}"
    exit 1
fi

HOOKS_DIR="$GIT_ROOT/.git/hooks"
TEMPLATES_DIR="$GIT_ROOT/.git-hooks-templates"

# Create templates directory if it doesn't exist
if [ ! -d "$TEMPLATES_DIR" ]; then
    echo -e "${BLUE}Creating .git-hooks-templates directory...${NC}"
    mkdir -p "$TEMPLATES_DIR"
fi

# Copy pre-push hook template
echo -e "${BLUE}Installing pre-push hook...${NC}"

# Check if hook already exists
if [ -f "$HOOKS_DIR/pre-push" ] && [ ! -L "$HOOKS_DIR/pre-push" ]; then
    echo -e "${YELLOW}Warning: pre-push hook already exists${NC}"
    read -p "Overwrite? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Skipping pre-push hook installation"
    else
        # The hook is already in .git/hooks/pre-push
        # We just need to make sure it's executable
        chmod +x "$HOOKS_DIR/pre-push"
        echo -e "${GREEN}✓ Pre-push hook installed${NC}"
    fi
else
    if [ -f "$HOOKS_DIR/pre-push" ]; then
        chmod +x "$HOOKS_DIR/pre-push"
        echo -e "${GREEN}✓ Pre-push hook already installed${NC}"
    else
        echo -e "${YELLOW}Pre-push hook not found at $HOOKS_DIR/pre-push${NC}"
        echo -e "${YELLOW}It should have been created automatically${NC}"
    fi
fi

# Summary
echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${GREEN}Git hooks installation complete!${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo "Installed hooks:"
echo "  • pre-push: Verifies tests, doctests, linting, and benchmarks have been run"
echo ""
echo "Usage:"
echo "  • Check status: make check-status"
echo "  • Skip verification: git push --no-verify"
echo ""
