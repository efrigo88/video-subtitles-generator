# ABOUTME: Audits the two-line ABOUTME convention in maintained Python files.
# ABOUTME: Fails local hooks and CI when source file purpose is undocumented.
"""Audit maintained Python files for their required purpose headers."""

import sys
from pathlib import Path

from scripts.constants import (
    HEADER_LINE_COUNT,
    HEADER_PREFIX,
    REPOSITORY_ROOT,
    SKIP_DIRECTORIES,
    SOURCE_ROOTS,
)


def check_file(path: Path) -> bool:
    """Check that a Python file starts with two nonempty ABOUTME comments.

    Parameters
    ----------
    path : Path
        Source file to inspect.

    Returns
    -------
    bool
        Whether both purpose lines satisfy the repository convention.
    """
    lines = path.read_text(encoding="utf-8").splitlines()[:HEADER_LINE_COUNT]
    return len(lines) == HEADER_LINE_COUNT and all(
        line.startswith(HEADER_PREFIX) and line[len(HEADER_PREFIX) :].strip()
        for line in lines
    )


def main() -> int:
    """Report missing purpose headers across maintained source directories.

    Returns
    -------
    int
        Zero when every file passes, otherwise one.
    """
    missing: list[str] = []
    for root in SOURCE_ROOTS:
        for path in sorted((REPOSITORY_ROOT / root).rglob("*.py")):
            if SKIP_DIRECTORIES.intersection(path.relative_to(REPOSITORY_ROOT).parts):
                continue
            if not check_file(path):
                missing.append(str(path.relative_to(REPOSITORY_ROOT)))
    if missing:
        print("Missing or malformed ABOUTME header:", file=sys.stderr)
        for path_string in missing:
            print(f"  {path_string}", file=sys.stderr)
        return 1
    print("All maintained Python files have ABOUTME headers.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
