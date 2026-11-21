# 🤖 Auto-Review

An intelligent, multi-backend AI code review tool built for both **Git** and **Perforce (Helix Core & Swarm)**, designed around **Recursive Self-Improvement (RSI)** principles.

---

## 🌟 Key Features

1. **Dual VCS Engine**:
   - **Git**: Reviews uncommitted changes, staged changes, commit hashes (`HEAD~1`), or branch ranges (`origin/main...HEAD`).
   - **Perforce (P4)**: Reviews pending workspace diffs (`p4 diff -du`), shelved changelists (`p4 describe -S -du <cl>`), or submitted changes.
   - **Helix Swarm Ready**: Formats and publishes inline review comments directly via the Swarm REST API (`/api/v11/comments`).

2. **Pluggable Model Backends**:
   - **Google Gemini**: High speed & deep context (`gemini-2.5-flash`, `gemini-2.5-pro`).
   - **OpenAI & OpenAI-Compatible**: OpenAI (`gpt-4o`), local **Ollama** (`http://localhost:11434/v1`), **vLLM**, **DeepSeek**, or **Groq**.
   - **Anthropic**: Claude models (`claude-3-5-sonnet`).
   - **Mock / Offline**: Zero-token testing and dry-run mode.

3. **RSI (Recursive Self-Improvement) Loops**:
   - **Phase 1: Generator**: High-recall candidate proposal of critical bugs, vulnerabilities, and scale risks.
   - **Phase 2: Adversarial Critic**: Self-verifying pass that evaluates candidate findings against full file context to eliminate false positives and trivial linters/formatting nitpicks.
   - **Phase 3: Feedback Store**: Local SQLite database tracking developer acceptances, dismissals, and notes.
   - **Phase 4: Dynamic Rule Synthesizer**: Periodically synthesizes negative constraints and codebase idioms into `.auto_review/guidelines.md` from developer feedback, injecting them into future review prompts.

---

## 🚀 Quickstart & Installation

```bash
# Clone and create virtual environment
git clone <repo-url> auto-review
cd auto-review
python3 -m venv .venv
source .venv/bin/activate

# Install in editable mode
pip install -e .
```

Verify installation:
```bash
auto-review --help
```

---

## ⚙️ Model Provider Configuration

Set environment variables for your chosen backend:

### Google Gemini (Default)
```bash
export GEMINI_API_KEY="your-api-key"
export GEMINI_MODEL="gemini-2.5-flash"   # optional, defaults to gemini-2.5-flash
```

### Local Models via Ollama (Zero Cloud API Costs)
```bash
export LLM_PROVIDER="ollama"
export OPENAI_API_BASE="http://localhost:11434/v1"
export OPENAI_MODEL="qwen2.5-coder:14b"
```

### OpenAI / DeepSeek
```bash
export LLM_PROVIDER="openai"
export OPENAI_API_KEY="your-api-key"
export OPENAI_MODEL="gpt-4o"
```

### Anthropic Claude
```bash
export LLM_PROVIDER="anthropic"
export ANTHROPIC_API_KEY="your-api-key"
export ANTHROPIC_MODEL="claude-3-5-sonnet-20241022"
```

---

## 🛠️ Usage Guide

### 1. Reviewing Git Changes

```bash
# Review uncommitted working changes (auto-detects staged vs unstaged)
auto-review review --git

# Review staged changes only
auto-review review --git staged

# Review latest commit
auto-review review --git HEAD~1

# Review a feature branch against main
auto-review review --git "main...HEAD"

# Output in Markdown format (e.g., for PR comments)
auto-review review --git staged --format markdown

# Output JSON for CI pipelines
auto-review review --git staged --format json
```

### 2. Reviewing Perforce (P4) Changes

```bash
# Review default changelist in current client workspace
auto-review review --p4

# Review a specific shelved changelist (p4 describe -S -du 123456)
auto-review review --p4 123456

# Export comments in Helix Swarm JSON format
auto-review review --p4 123456 --format swarm

# Automatically post comments to Helix Swarm (requires SWARM_URL and SWARM_TOKEN)
auto-review review --p4 123456 --post
```

---

## 🔄 The RSI Feedback & Improvement Loop

### 1. View Generated Comments & Metrics
```bash
# List recent review comments awaiting human review
auto-review feedback list

# Check reviewer precision and acceptance rates
auto-review feedback metrics
```

### 2. Record Developer Feedback
When an engineer accepts, dismisses, or marks a finding as a false positive:
```bash
# Record acceptance
auto-review feedback record <COMMENT_ID> ACCEPTED --notes "Great catch on the missing lock"

# Record false positive
auto-review feedback record <COMMENT_ID> FALSE_POSITIVE --notes "In this service, missing items return sentinel -1, not exceptions"
```

### 3. Synthesize Learned Guidelines
Run the optimizer to distill all recorded feedback into repository-specific rules:
```bash
auto-review rsi optimize
```
This updates `.auto_review/guidelines.md`. The reviewer automatically injects these rules into subsequent prompt contexts.

To view currently active learned guidelines:
```bash
auto-review rsi show
```

---

## 🔌 Integrations

### Git Integration
* **Local Pre-Push Hook**: Copy `integrations/git/pre-push.sh` into your `.git/hooks/pre-push` and `chmod +x .git/hooks/pre-push`.
* **GitHub Actions**: See `integrations/git/github_action.yml` for automatic PR reviews and inline commenting.

### Perforce & Helix Swarm Integration
* **Perforce Server Trigger**: Add `integrations/p4/p4_trigger.sh` to your Perforce `p4 triggers` table for automated checks on `change-shelf`.
* **Helix Swarm Automated Test**: Configure `integrations/p4/swarm_worker.py` in Swarm's "Automated Tests" panel for reviews.
