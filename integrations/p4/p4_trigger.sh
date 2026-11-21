#!/usr/bin/env bash
# Perforce trigger script for AI Auto-Review
#
# Configure in 'p4 triggers':
#   ai-review-shelve change-shelf //... "/path/to/p4_trigger.sh %change% %user%"
#
# This script inspects the shelved changelist using p4 describe -S -du,
# executes auto-review, and outputs findings or pushes to Helix Swarm.

set -e

CHANGELIST="$1"
USER="$2"

if [ -z "$CHANGELIST" ]; then
    echo "Usage: $0 <changelist_number> [user]"
    exit 1
fi

echo "[auto-review] Reviewing shelved changelist $CHANGELIST for user $USER..."

# Run auto-review on the shelved changelist
# If SWARM_URL and SWARM_TOKEN are exported, --post pushes comments into Swarm
auto-review review --p4 "$CHANGELIST" --format swarm --post

exit 0
