# ABOUTME: Computes source-specific cache locations outside movie and subtitle folders.
# ABOUTME: Keeps recovery metadata reusable across output locations without basename collisions.
"""Application-cache identity and location validation for subtitle generation."""

import hashlib
import json
from pathlib import Path

from src.constants import (
    CACHE_REPORT_NAME,
    CACHE_TRANSCRIPT_NAME,
    TIMELINE_DESCRIPTION,
    TRANSCRIPT_SCHEMA_VERSION,
)
from src.models import JsonDict


def transcript_cache_paths(
    root: Path,
    source_file: JsonDict,
    source_language: str,
    stream_index: int,
    model: str,
    condition_on_previous_text: bool,
    output_directory: Path,
) -> tuple[Path, Path]:
    """Derive short cache paths without writing into media or SRT directories.

    Parameters
    ----------
    root : Path
        Application cache root selected by platform defaults or the caller.
    source_file : dict[str, Any]
        Source path, size, and modification timestamp used for cache validation.
    source_language : str
        Spoken language used during transcription.
    stream_index : int
        Absolute selected audio stream index.
    model : str
        Whisper model whose aligned output the cache contains.
    condition_on_previous_text : bool
        Whether decoding receives context from previous windows.
    output_directory : Path
        Folder receiving SRT files, which must remain free of metadata files.

    Returns
    -------
    tuple[Path, Path]
        Transcript and report paths under a fingerprinted application namespace.
    """
    identity = {
        "source_file": source_file,
        "source_language": source_language,
        "audio_stream": stream_index,
        "model": model,
        "condition_on_previous_text": condition_on_previous_text,
        "schema_version": TRANSCRIPT_SCHEMA_VERSION,
        "timeline": TIMELINE_DESCRIPTION,
    }
    digest = hashlib.sha256(
        json.dumps(identity, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    root = root.expanduser().resolve()
    directory = (root / digest).resolve()
    protected = [Path(source_file["path"]).parent.resolve(), output_directory.resolve()]
    for folder in protected:
        if root.is_relative_to(folder) or directory.is_relative_to(folder):
            raise ValueError(
                "The cache directory must be outside the movie and subtitle "
                f"output directories: {folder}"
            )
    return directory / CACHE_TRANSCRIPT_NAME, directory / CACHE_REPORT_NAME
