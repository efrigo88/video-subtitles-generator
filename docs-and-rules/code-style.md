<!-- ABOUTME: Defines source documentation, typing, and configuration conventions. -->
<!-- ABOUTME: Keeps the local subtitle pipeline readable and machine-checkable. -->
# Code style

Follow the Zen of Python, KISS, YAGNI, and DRY. Keep changes focused on the requested behavior and preserve working interfaces when practical. One function has one job; split a flow at real processing stages or validation boundaries, and avoid chains of tiny helpers with no independent purpose. Keep modules organized by concern and comfortably below 800 lines.

Every Python file begins with two lines starting with `# ABOUTME:` followed by a space. The first explains the purpose; the second explains the mechanism or reason. YAML and TOML need only an intent comment where it helps; Markdown may use an HTML comment header.

Every function, method, and class has a docstring and explicit type annotations. Public Python APIs use numpydoc-style `Parameters`, `Returns`, and `Raises` sections as applicable. Document behavior and contracts rather than repeating the implementation. Use typed cue structures internally and validate external JSON/media metadata at the boundary. Strict mypy is required; do not weaken it to accommodate a change.

Put configuration constants, supported values, model identifiers, thresholds, and defaults in `constants.py` at the same package level as their consumers. Keep the main pipeline's values in `src/constants.py` and standalone maintenance-script values in `scripts/constants.py`. Keep test fixtures readable inline; test-specific input values are not shared runtime configuration.

Comments explain a constraint or intent that code cannot express clearly. Keep them brief and evergreen. Avoid historical narration and names such as “improved” or “new.” Match surrounding style. Do not use implementation assertions or add lint, type, security-scanner, or formatter suppressions; validate inputs and fix the underlying issue.

Formatting, linting, documentation/annotation checks, and strict typing are enforced by the hooks and CI described in [workflow.md](workflow.md). No source module should import a heavy inference library merely to show CLI help or inspect metadata.
