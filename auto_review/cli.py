from __future__ import annotations
import sys
import argparse
import os
from typing import Optional

from auto_review.config import Config
from auto_review.models import get_model_backend
from auto_review.vcs.git_adapter import GitAdapter
from auto_review.vcs.p4_adapter import P4Adapter
from auto_review.core.reviewer import CodeReviewer
from auto_review.core.formatter import OutputFormatter
from auto_review.rsi.feedback_store import FeedbackStore
from auto_review.rsi.rule_synthesizer import RuleSynthesizer


def main():
    parser = argparse.ArgumentParser(
        prog="auto-review",
        description="AI-powered code review tool for Git and Perforce with Recursive Self-Improvement (RSI)."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # 1. Review Command
    review_parser = subparsers.add_parser("review", help="Execute AI code review on Git or Perforce changes")
    vcs_group = review_parser.add_mutually_exclusive_group(required=True)
    vcs_group.add_argument("--git", nargs="?", const="auto", help="Review Git change (e.g. staged, HEAD~1, main...HEAD, or auto-detect)")
    vcs_group.add_argument("--p4", nargs="?", const="default", help="Review Perforce change (e.g. 123456, shelved:123456, or default opened files)")

    review_parser.add_argument("--provider", choices=["gemini", "openai", "ollama", "anthropic", "mock"], help="LLM backend provider")
    review_parser.add_argument("--model", help="Specific model identifier")
    review_parser.add_argument("--format", choices=["terminal", "markdown", "json", "swarm"], default="terminal", help="Output format")
    review_parser.add_argument("--no-critic", action="store_true", help="Disable adversarial critic verification pass")
    review_parser.add_argument("--min-confidence", type=int, default=7, help="Minimum confidence threshold (1-10)")
    review_parser.add_argument("--post", action="store_true", help="Publish comments to review platform (Helix Swarm / PR)")

    # 2. Feedback Command (RSI Loop)
    feedback_parser = subparsers.add_parser("feedback", help="Manage developer feedback on review comments (RSI Loop)")
    fb_sub = feedback_parser.add_subparsers(dest="feedback_cmd", required=True)

    fb_sub.add_parser("list", help="List recent pending review comments")
    fb_sub.add_parser("metrics", help="Display reviewer precision and feedback metrics")

    record_parser = fb_sub.add_parser("record", help="Record feedback for a specific comment")
    record_parser.add_argument("comment_id", help="Comment ID (from review output)")
    record_parser.add_argument("status", choices=["ACCEPTED", "DISMISSED", "FALSE_POSITIVE"], help="Developer action")
    record_parser.add_argument("--notes", default="", help="Optional notes on why this was accepted/dismissed")

    # 3. RSI Command (Self-Improvement & Optimization)
    rsi_parser = subparsers.add_parser("rsi", help="Recursive Self-Improvement controls")
    rsi_sub = rsi_parser.add_subparsers(dest="rsi_cmd", required=True)

    opt_parser = rsi_sub.add_parser("optimize", help="Synthesize guidelines and prompt rules from feedback history")
    opt_parser.add_argument("--provider", default="gemini", help="Model to use for guideline distillation")
    rsi_sub.add_parser("show", help="Display currently active learned guidelines")

    # 4. Config Command
    config_parser = subparsers.add_parser("config", help="View or update default configuration")
    config_parser.add_argument("--set-provider", help="Set default LLM provider")
    config_parser.add_argument("--set-gemini-model", help="Set default Gemini model")
    config_parser.add_argument("--set-openai-model", help="Set default OpenAI model")
    config_parser.add_argument("--set-swarm-url", help="Set default Helix Swarm URL")

    args = parser.parse_args()

    cfg = Config.load()
    store = FeedbackStore()

    if args.command == "review":
        handle_review(args, cfg, store)
    elif args.command == "feedback":
        handle_feedback(args, store)
    elif args.command == "rsi":
        handle_rsi(args, cfg, store)
    elif args.command == "config":
        handle_config(args, cfg)


def handle_review(args, cfg: Config, store: FeedbackStore):
    # Determine Provider and Backend
    provider = args.provider or cfg.default_provider
    model_name = args.model
    if not model_name:
        if provider == "gemini":
            model_name = cfg.gemini_model
        elif provider in ("openai", "ollama"):
            model_name = cfg.openai_model
        elif provider == "anthropic":
            model_name = cfg.anthropic_model

    try:
        backend = get_model_backend(
            provider=provider,
            model_name=model_name,
            base_url=cfg.openai_base_url if provider in ("openai", "ollama") else None
        )
    except Exception as e:
        sys.stderr.write(f"\033[31mError initializing model backend: {e}\033[0m\n")
        sys.exit(1)

    # Initialize VCS Adapter
    if args.git is not None:
        adapter = GitAdapter()
        target = None if args.git == "auto" else args.git
        try:
            changeset = adapter.get_changeset(target)
        except Exception as e:
            sys.stderr.write(f"\033[31mError extracting Git changes: {e}\033[0m\n")
            sys.exit(1)
    else:
        adapter = P4Adapter(
            p4port=cfg.p4port,
            p4client=cfg.p4client,
            p4user=cfg.p4user,
            swarm_url=cfg.swarm_url
        )
        target = args.p4
        try:
            changeset = adapter.get_changeset(target)
        except Exception as e:
            sys.stderr.write(f"\033[31mError extracting Perforce changes: {e}\033[0m\n")
            sys.exit(1)

    if not changeset.files or not changeset.raw_diff.strip():
        print(f"No code changes found for {changeset.vcs_type.upper()} target '{changeset.target_id}'. Nothing to review.")
        return

    reviewer = CodeReviewer(
        backend=backend,
        store=store,
        enable_critic=not args.no_critic and cfg.enable_critic,
        min_confidence=args.min_confidence or cfg.min_confidence,
    )

    print(f"Analyzing {len(changeset.files)} file(s) from {changeset.vcs_type.upper()} ({changeset.target_id}) using {provider} [{model_name}]...")
    comments = reviewer.review(changeset, adapter=adapter)

    # Format output
    if args.format == "terminal":
        output = OutputFormatter.to_terminal(changeset, comments)
        print(output)
    elif args.format == "markdown":
        output = OutputFormatter.to_markdown(changeset, comments)
        print(output)
    elif args.format == "json":
        output = OutputFormatter.to_json(changeset, comments)
        print(output)
    elif args.format == "swarm":
        import json
        swarm_payloads = OutputFormatter.to_swarm_comments(changeset, comments)
        print(json.dumps(swarm_payloads, indent=2))

    # Optional post to platform
    if args.post and comments:
        print("Publishing comments to platform...")
        success = adapter.post_comments(changeset, comments)
        if success:
            print("Successfully published comments.")
        else:
            print("Warning: Failed to publish comments to platform.")


def handle_feedback(args, store: FeedbackStore):
    if args.feedback_cmd == "list":
        pending = store.get_pending_comments(limit=15)
        if not pending:
            print("No pending comments in feedback store.")
            return
        print(f"\n--- Recent Pending Review Comments ({len(pending)}) ---")
        for p in pending:
            print(f"ID: {p['comment_id']} | File: {p['file_path']}:{p['line_number']} | [{p['severity']}] {p['title']}")
            print(f"    Comment: {p['comment'][:140]}...")
            print("")
    elif args.feedback_cmd == "record":
        success = store.record_feedback(args.comment_id, args.status, args.notes)
        if success:
            print(f"Recorded feedback for '{args.comment_id}' -> {args.status}")
        else:
            print(f"Comment ID '{args.comment_id}' not found.")
    elif args.feedback_cmd == "metrics":
        m = store.get_metrics()
        print("\n=== Reviewer RSI Metrics ===")
        print(f"Total Comments Generated : {m['total_generated']}")
        print(f"Accepted by Engineers     : {m['accepted']}")
        print(f"Dismissed / False Positive: {m['dismissed']}")
        print(f"Pending Evaluation        : {m['pending']}")
        print(f"Precision Rate            : {m['precision_rate']}%\n")


def handle_rsi(args, cfg: Config, store: FeedbackStore):
    synth = RuleSynthesizer(
        backend=get_model_backend(args.provider or cfg.default_provider),
        store=store
    )
    if args.rsi_cmd == "optimize":
        print("Running RSI Rule Synthesizer to distill feedback into guidelines...")
        res = synth.optimize_guidelines()
        print(res)
    elif args.rsi_cmd == "show":
        g = synth.load_active_guidelines()
        if g:
            print(g)
        else:
            print("No active guidelines synthesized yet. Run 'auto-review rsi optimize' after recording feedback.")


def handle_config(args, cfg: Config):
    modified = False
    if args.set_provider:
        cfg.default_provider = args.set_provider
        modified = True
    if args.set_gemini_model:
        cfg.gemini_model = args.set_gemini_model
        modified = True
    if args.set_openai_model:
        cfg.openai_model = args.set_openai_model
        modified = True
    if args.set_swarm_url:
        cfg.swarm_url = args.set_swarm_url
        modified = True

    if modified:
        cfg.save()
        print("Configuration updated and saved to .auto_review/config.json.")
    else:
        import json
        from dataclasses import asdict
        print("Current Configuration:")
        print(json.dumps(asdict(cfg), indent=2))


if __name__ == "__main__":
    main()
