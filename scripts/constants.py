# ABOUTME: Defines the repository scope and header convention for source audits.
# ABOUTME: Keeps validation settings alongside the scripts that consume them.
"""Shared configuration for repository validation scripts."""

from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOTS = ("src", "tests", "scripts")
HEADER_PREFIX = "# ABOUTME: "
HEADER_LINE_COUNT = 2
SKIP_DIRECTORIES = frozenset({"build", "dist", "__pycache__"})
