# ABOUTME: Builds subtitle cues from aligned words and validates SRT timing.
# ABOUTME: Preserves millisecond boundaries and publishes complete files without accidental replacement.
"""Build readable cues from aligned words and write validated SRT files."""

import json
import math
import os
import tempfile
import textwrap
from pathlib import Path
from typing import Optional

from src.constants import (
    ATOMIC_TEMP_PREFIX,
    LONG_CUE_WARNING_SECONDS,
    MAX_CUE_CHARACTERS,
    MAX_CUE_DURATION,
    MAX_SRT_LINES,
    MAX_WORD_GAP,
    MEDIA_DURATION_TOLERANCE,
    MILLISECONDS_PER_SECOND,
    MINUTES_PER_HOUR,
    READING_SPEED_WARNING,
    SECONDS_PER_MINUTE,
    SRT_LINE_WIDTH,
    TIMESTAMP_DECIMAL_PLACES,
)
from src.models import Cue, JsonDict


def format_timestamp(seconds: float) -> str:
    """Format nonnegative seconds as a millisecond-precision SRT timestamp.

    Parameters
    ----------
    seconds : float
        Time on the video playback timeline.

    Returns
    -------
    str
        Timestamp in ``HH:MM:SS,mmm`` format, with rounding carried across units.
    """
    if not math.isfinite(seconds) or seconds < 0:
        raise ValueError(f"Invalid timestamp: {seconds}")
    scaled = seconds * MILLISECONDS_PER_SECOND
    if not math.isfinite(scaled):
        raise ValueError(
            f"Timestamp exceeds representable millisecond precision: {seconds}"
        )
    milliseconds = round(scaled)
    hours, remainder = divmod(
        milliseconds, MILLISECONDS_PER_SECOND * SECONDS_PER_MINUTE * MINUTES_PER_HOUR
    )
    minutes, remainder = divmod(remainder, MILLISECONDS_PER_SECOND * SECONDS_PER_MINUTE)
    whole_seconds, milliseconds = divmod(remainder, MILLISECONDS_PER_SECOND)
    return f"{hours:02}:{minutes:02}:{whole_seconds:02},{milliseconds:03}"


def atomic_write(path: Path, content: str, overwrite: bool = False) -> None:
    """Publish a complete UTF-8 file with atomic replacement or no-clobber creation.

    Parameters
    ----------
    path : Path
        Destination whose parent directory will be created as needed.
    content : str
        Entire file contents.
    overwrite : bool
        Whether replacing an existing destination is explicitly authorized.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=ATOMIC_TEMP_PREFIX, dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as output:
            output.write(content)
        if overwrite:
            os.replace(temporary, path)
        else:
            os.link(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def write_json(path: Path, value: JsonDict, overwrite: bool = False) -> None:
    """Publish a JSON object, rejecting nonfinite values rather than corrupting it.

    Parameters
    ----------
    path : Path
        Destination JSON file.
    value : dict[str, Any]
        Serializable metadata or transcript object.
    overwrite : bool
        Whether replacing an existing destination is authorized.
    """
    atomic_write(
        path,
        json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        overwrite,
    )


def validate_cues(cues: list[Cue]) -> None:
    """Require nonempty, ordered cues with positive millisecond durations.

    Parameters
    ----------
    cues : list[Cue]
        Cues to validate before reporting or publication.

    Raises
    ------
    ValueError
        If a cue is empty, nonfinite, negative, overlapping, or has no duration.
    """
    if not cues:
        raise ValueError("No speech cues were generated; no SRT will be written.")
    previous_end = 0
    for index, cue in enumerate(cues, 1):
        start, end = cue["start"], cue["end"]
        format_timestamp(start)
        format_timestamp(end)
        if round(end * MILLISECONDS_PER_SECOND) <= round(
            start * MILLISECONDS_PER_SECOND
        ):
            raise ValueError(
                f"Cue {index} has no positive duration at millisecond precision."
            )
        if round(start * MILLISECONDS_PER_SECOND) < previous_end:
            raise ValueError(f"Cue {index} overlaps the previous cue.")
        if not isinstance(cue["text"], str) or not cue["text"].strip():
            raise ValueError(f"Cue {index} has no text.")
        previous_end = round(end * MILLISECONDS_PER_SECOND)


def build_cues(
    segments: list[JsonDict],
    max_duration: float = MAX_CUE_DURATION,
    max_chars: int = MAX_CUE_CHARACTERS,
    max_gap: float = MAX_WORD_GAP,
) -> tuple[list[Cue], list[str]]:
    """Group aligned words without assigning speech times from character counts.

    Parameters
    ----------
    segments : list[dict[str, Any]]
        Whisper segments containing text, timing, and optional aligned words.
    max_duration : float
        Preferred maximum cue duration, split only between aligned words.
    max_chars : int
        Preferred maximum cue text length.
    max_gap : float
        Largest silence interval retained inside a cue.

    Returns
    -------
    tuple[list[Cue], list[str]]
        Validated cues and warnings for timing fallbacks or reconciled overlaps.
    """
    if max_duration <= 0 or max_chars <= 0 or max_gap < 0:
        raise ValueError(
            "Cue duration and character limits must be positive; gap must be nonnegative."
        )
    cues: list[Cue] = []
    warnings: list[str] = []
    for index, segment in enumerate(segments, 1):
        segment_text = segment.get("text", "")
        if not isinstance(segment_text, str):
            raise ValueError(f"Segment {index} text must be a string.")
        words = segment.get("words")
        if words is None:
            words = []
        if not isinstance(words, list) or any(
            not isinstance(word, dict) for word in words
        ):
            raise ValueError(f"Segment {index} words must be a list of objects.")
        group: list[Cue] = []
        segment_cues: list[Cue] = []
        aligned_parts: list[str] = []

        def flush() -> None:
            """Finish the current group without extending its speech interval."""
            if group:
                segment_cues.append(
                    {
                        "start": group[0]["start"],
                        "end": max(word["end"] for word in group),
                        "text": "".join(word["text"] for word in group).strip(),
                    }
                )
                group.clear()

        previous_start = 0.0
        for word in words:
            text = word.get("word", "")
            if not isinstance(text, str):
                raise ValueError(f"Segment {index} has a non-string aligned word.")
            if not text.strip():
                continue
            aligned_parts.append(text)
            start, end = float(word["start"]), float(word["end"])
            format_timestamp(start)
            format_timestamp(end)
            if end < start or start < previous_start:
                raise ValueError(
                    f"Segment {index} contains invalid or unordered word timings."
                )
            previous_start = start
            if group and (
                start - group[-1]["end"] > max_gap
                or end - group[0]["start"] > max_duration
                or len("".join(item["text"] for item in group) + text) > max_chars
            ):
                flush()
            group.append({"start": start, "end": end, "text": text})
        flush()
        aligned_text = " ".join("".join(aligned_parts).split())
        normalized_text = " ".join(segment_text.split())
        missing_text = bool(normalized_text) and normalized_text != aligned_text
        zero_duration = any(
            round(cue["end"] * MILLISECONDS_PER_SECOND)
            <= round(cue["start"] * MILLISECONDS_PER_SECOND)
            for cue in segment_cues
        )
        if not segment_cues or missing_text or zero_duration:
            if not normalized_text:
                if zero_duration:
                    raise ValueError(f"Segment {index} has no usable speech duration.")
                cues.extend(segment_cues)
                continue
            segment_cues = [
                {
                    "start": float(segment["start"]),
                    "end": float(segment["end"]),
                    "text": normalized_text,
                }
            ]
            warnings.append(
                f"Segment {index} has incomplete word alignment; used segment timing."
            )
        cues.extend(segment_cues)
    reconciled: list[Cue] = []
    for cue in cues:
        if reconciled:
            previous = reconciled[-1]
            if cue["start"] < previous["start"]:
                raise ValueError(
                    "Subtitle segments are not ordered on the playback timeline."
                )
            if cue["start"] == previous["start"]:
                previous["text"] = f"{previous['text']} {cue['text']}"
                previous["end"] = max(previous["end"], cue["end"])
                warnings.append("Merged cues sharing the same model start time.")
                continue
            if previous["end"] > cue["start"]:
                previous["end"] = cue["start"]
                warnings.append("Trimmed an overlapping cue to the next cue's start.")
        reconciled.append(cue)
    for cue in reconciled:
        cue["start"] = round(cue["start"], TIMESTAMP_DECIMAL_PLACES)
        cue["end"] = round(cue["end"], TIMESTAMP_DECIMAL_PLACES)
        cue["text"] = " ".join(cue["text"].split())
    validate_cues(reconciled)
    return reconciled, warnings


def quality_warnings(cues: list[Cue], duration: Optional[float] = None) -> list[str]:
    """Report suspicious readability and reject cues beyond the media duration.

    Parameters
    ----------
    cues : list[Cue]
        Generated or translated cues.
    duration : float, optional
        Reliable playback endpoint in seconds, when known.

    Returns
    -------
    list[str]
        Human-readable quality warnings requiring playback review.
    """
    validate_cues(cues)
    warnings = []
    for index, cue in enumerate(cues, 1):
        length = cue["end"] - cue["start"]
        if len(cue["text"]) / length > READING_SPEED_WARNING:
            warnings.append(
                f"Cue {index} exceeds {READING_SPEED_WARNING} characters/second; review readability."
            )
        if length > LONG_CUE_WARNING_SECONDS:
            warnings.append(
                f"Cue {index} exceeds {LONG_CUE_WARNING_SECONDS:g} seconds; review alignment."
            )
        wrapped = textwrap.wrap(
            cue["text"],
            width=SRT_LINE_WIDTH,
            break_long_words=False,
            break_on_hyphens=False,
        )
        if len(wrapped) > MAX_SRT_LINES:
            warnings.append(
                f"Cue {index} exceeds two subtitle lines; review readability."
            )
        if duration is not None and cue["end"] > duration + MEDIA_DURATION_TOLERANCE:
            raise ValueError(f"Cue {index} ends beyond the media duration.")
    return warnings


def write_srt(segments: list[Cue], output_path: Path, overwrite: bool = False) -> None:
    """Write validated cues as UTF-8 SRT with word-preserving line wrapping.

    Parameters
    ----------
    segments : list[Cue]
        Ordered subtitle cues on the playback timeline.
    output_path : Path
        Language-specific SRT destination.
    overwrite : bool
        Whether replacing an existing destination is authorized.
    """
    validate_cues(segments)
    lines = []
    for index, cue in enumerate(segments, 1):
        text = " ".join(cue["text"].split()).replace("-->", "->")
        text = textwrap.fill(
            text, width=SRT_LINE_WIDTH, break_long_words=False, break_on_hyphens=False
        )
        lines.append(
            f"{index}\n{format_timestamp(cue['start'])} --> "
            f"{format_timestamp(cue['end'])}\n{text}\n\n"
        )
    atomic_write(output_path, "".join(lines), overwrite)
