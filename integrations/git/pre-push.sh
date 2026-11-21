#!/usr/bin/env bash
# Git pre-push hook for AI Auto-Review
# Place this in .git/hooks/pre-push and make it executable: chmod +x .git/hooks/pre-push

set -e

echo "[auto-review] Running AI code review on outgoing commits..."

# Run review on outgoing commits (origin/main..HEAD or default to HEAD~1)
TARGET="origin/main..HEAD"
if ! git rev-parse --verify origin/main >/dev/null 2>&1; then
    TARGET="HEAD~1"
fi

if auto-review review --git "$TARGET" --min-confidence 8; then
    echo "[auto-review] Pre-push check complete."
    exit 0
else
    echo "[auto-review] Identified issues. Review findings before pushing."
    # Change to exit 1 if you want to strictly block pushes on review findings
    exit 0
fi
