# Repository instructions

## Python

Use `uv` to manage Python dependencies. If the project is not configured for `uv`, access `pip`
through `uv` and use a virtual environment configured via `uv`.

## Node.js

Prefer `pnpm` for package management unless the repository is configured for `npm` or `yarn`.

## Worktrees

When working on an issue or feature, prefer subagent-driven development on a Git worktree.

## Writing

Do not use em dashes in responses. Use commas, periods, semicolons, parentheses, or colons instead.

## Agent skills

### Issue tracker

Issues and specs are tracked in GitHub Issues. See `docs/agents/issue-tracker.md`.

### Triage labels

Use the default five-role triage vocabulary. See `docs/agents/triage-labels.md`.

### Domain docs

This repository uses the single-context layout. See `docs/agents/domain.md`.
