#!/usr/bin/env python3
"""
Helix Swarm Webhook / Automated Test Integration Worker.

When configured as a Swarm Automated Test, Swarm calls this script
(or POSTs to this webhook) when a review is updated or shelved:
  python3 swarm_worker.py --review {review} --change {change}

It fetches the changelist via P4Adapter, runs the review engine,
and posts inline comments directly into Swarm's review thread via the Swarm REST API.
"""

import sys
import argparse
import subprocess
import os


def main():
    parser = argparse.ArgumentParser(description="Helix Swarm Automated Review Worker")
    parser.add_argument("--review", required=True, help="Swarm Review ID")
    parser.add_argument("--change", required=True, help="Shelved Changelist Number")
    parser.add_argument("--swarm-url", default=os.environ.get("SWARM_URL"), help="Helix Swarm URL")
    parser.add_argument("--swarm-token", default=os.environ.get("SWARM_TOKEN"), help="Helix Swarm API Token")
    args = parser.parse_args()

    env = os.environ.copy()
    if args.swarm_url:
        env["SWARM_URL"] = args.swarm_url
    if args.swarm_token:
        env["SWARM_TOKEN"] = args.swarm_token

    print(f"Triggering auto-review for Swarm Review #{args.review} (CL: {args.change})...")

    # Run auto-review with --post to send findings to Swarm API
    cmd = [
        "auto-review",
        "review",
        "--p4", args.change,
        "--format", "swarm",
        "--post"
    ]

    res = subprocess.run(cmd, env=env)
    sys.exit(res.returncode)


if __name__ == "__main__":
    main()
