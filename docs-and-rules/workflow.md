<!-- ABOUTME: Defines the repository's Git, validation, and delivery workflow. -->
<!-- ABOUTME: Makes local hooks and CI consistent without adding deployment infrastructure. -->
# Workflow

## Git and delivery

Create a descriptive feature branch before editing. Use `fix/`, `feat/`, `refactor/`, `docs/`, `test/`, or `chore/` as appropriate. For parallel or long-lived changes, use an isolated worktree when it avoids interfering with the user's active checkout. Preserve existing user work; never switch away from or discard unrelated edits.

Use Conventional Commits and keep one logical change per commit. Leave implementation and review work unstaged until preparing the authorized final commits, so the working-tree diff remains visible. Do not skip Git hooks or force-push without explicit user authorization. Open requested PRs as drafts using [.github/PULL_REQUEST_TEMPLATE.md](../.github/PULL_REQUEST_TEMPLATE.md). The user reviews and merges; never merge on their behalf unless they explicitly revise that instruction.

Carry an authorized request through implementation, validation, and the requested PR. If the user requests a diff review before committing, honor that checkpoint. Do not introduce extra approval questions for work already authorized in the conversation.

## Installed hooks

Follow the exact setup and install commands in [README.md](../README.md). Both commit and push hooks must be installed in the current checkout, including after a fresh clone. Hook installation is local Git state; a checked-in configuration alone does not activate it. Check that both hook files exist and are executable when setup is part of the task.

Commit hooks enforce file hygiene, parseability, conflict/private-key checks, large-file protection, Markdown/YAML rules, formatting, documented and annotated APIs, `ABOUTME` headers, strict typing, and security scanning. Tests run at the push stage. Use the existing locked environment for hook commands so optional inference packages remain available. A failing hook is a defect to investigate, not a reason to bypass it.

## Tests and CI

For behavioral changes, first reproduce the failure with a focused test or concrete input. Prefer a failing regression test, then the smallest useful fix, then passing validation. Use meaningful tests at processing boundaries rather than tests that merely repeat implementation details. Documentation-only changes need their applicable documentation/hygiene checks.

The automated suite must not download model weights, depend on the user's movie, or invoke real inference. Mock inference at its boundary and exercise timeline behavior with small synthetic FFmpeg files. Keep a real-model smoke run and full-video verification separate from CI.

CI runs code-quality hooks, supported-Python regression tests, and PR-description validation. Workflows use locked development dependencies, read-only permissions, and cancellation of superseded runs. A local CLI does not need Docker build, deployment, Terraform, or production-data jobs. Keep the supported Python range aligned across project metadata, tests, and CI.

## Documentation and completion

After review fixes, sweep every Markdown file and update anything made stale. README is the landing page: setup, hooks/checks, one basic command, and links to all guides/rules in `docs-and-rules/`. Keep each fact in one authoritative home and use links elsewhere.

Report what changed, which checks actually ran, and any material limitations. Successful programmatic checks are evidence of file validity; they do not prove every line of dialogue is synchronized. See [synchronization.md](synchronization.md).
