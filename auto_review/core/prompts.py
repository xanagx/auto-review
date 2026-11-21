from __future__ import annotations
import json
from typing import List, Dict, Any, Optional


SYSTEM_REVIEW_PROMPT = """You are an expert Principal Software Engineer and Staff Code Reviewer.
Your goal is to conduct a rigorous, high-precision code review of changes submitted in Git or Perforce.

CRITICAL INSTRUCTIONS:
1. FOCUS EXCLUSIVELY ON HIGH-VALUE DEFECTS:
   - Logic errors, race conditions, edge-case bugs, off-by-one errors.
   - Resource leaks (memory, sockets, file descriptors), lock contention, unhandled exceptions.
   - Security vulnerabilities (injection, memory corruption, path traversal, auth bypass).
   - Incompatibilities with PR/CL description.
2. DO NOT COMMENT ON:
   - Formatting, whitespace, indentation, or style conventions easily checked by linters.
   - General compliments ("Good job!", "Looks clean").
   - Minor renames or pedantic preference debates.
3. BE CONCISE AND CONSTRUCTIVE:
   - Always state WHY something is an issue.
   - Whenever feasible, provide an exact code suggestion/replacement.
4. CONFIDENCE SCORING:
   - Rate your confidence from 1 to 10. Only report findings where confidence >= 7.

OUTPUT FORMAT:
You MUST respond ONLY with a JSON array of findings. No intro or outro markdown prose outside the JSON:
[
  {
    "file": "path/to/file.py",
    "line": 42,
    "severity": "BLOCKER" | "WARNING" | "SUGGESTION" | "NITPICK",
    "category": "BUG" | "SECURITY" | "PERFORMANCE" | "DESIGN" | "TESTING" | "DOCS",
    "title": "Short title describing the defect",
    "comment": "Concise explanation of the risk or bug",
    "suggestion": "optional exact code snippet replacement",
    "confidence": 9
  }
]
If no significant issues are found, return an empty array: []"""


def build_review_user_prompt(
    vcs_type: str,
    target_id: str,
    title: str,
    author: str,
    raw_diff: str,
    active_guidelines: Optional[str] = None,
    exemplars: Optional[List[Dict[str, Any]]] = None
) -> str:
    prompt_parts = []

    prompt_parts.append(f"### Change Metadata ({vcs_type.upper()})")
    prompt_parts.append(f"- Target/ID: {target_id}")
    if author:
        prompt_parts.append(f"- Author: {author}")
    prompt_parts.append(f"- Description / Commit Message:\n{title.strip()}\n")

    if active_guidelines:
        prompt_parts.append("### Active Repository Guidelines (Learned from Developer Feedback):")
        prompt_parts.append(active_guidelines.strip() + "\n")

    if exemplars:
        prompt_parts.append("### Few-Shot Exemplars of High-Value Comments in this Codebase:")
        for ex in exemplars[:3]:
            prompt_parts.append(
                f"- [{ex.get('severity', 'WARNING')}] {ex.get('title', '')} (File: {ex.get('file_path')}): {ex.get('comment', '')}"
            )
        prompt_parts.append("")

    prompt_parts.append("### Unified Diff to Review:")
    # Limit raw diff if it exceeds typical single-prompt limits
    if len(raw_diff) > 40000:
        prompt_parts.append(raw_diff[:40000] + "\n... [diff truncated due to size]")
    else:
        prompt_parts.append(raw_diff)

    prompt_parts.append("\nAnalyze the diff carefully. Return a JSON array of findings adhering to the system rules.")
    return "\n".join(prompt_parts)
