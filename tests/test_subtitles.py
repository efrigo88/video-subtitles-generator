# ABOUTME: Covers subtitle precision, speech boundaries, and safe SRT publication.
# ABOUTME: Reproduces visible timing failures with deterministic word-level examples.
"""Regression coverage for subtitle timing and cue validation."""

import json
import math
from pathlib import Path

import pytest

from src.subtitles import (
    build_cues,
    format_timestamp,
    validate_cues,
    write_json,
    write_srt,
)
from src.models import Cue


@pytest.mark.parametrize(
    "value, expected",
    [
        (0.12, "00:00:00,120"),
        (0.84, "00:00:00,840"),
        (12.98, "00:00:12,980"),
        (59.9996, "00:01:00,000"),
        (3661.234, "01:01:01,234"),
        (86401.01, "24:00:01,010"),
    ],
)
def test_timestamp_preserves_milliseconds_and_carries(
    value: float, expected: str
) -> None:
    """Preserve millisecond precision across second, hour, and day boundaries."""
    assert format_timestamp(value) == expected


@pytest.mark.parametrize("value", [-1, math.nan, math.inf, 1e308])
def test_invalid_timestamp(value: float) -> None:
    """Reject negative and nonfinite subtitle times."""
    with pytest.raises(ValueError):
        format_timestamp(value)


def test_short_cue_keeps_positive_duration_and_existing_output(tmp_path: Path) -> None:
    """Keep short cues visible and refuse to replace an existing output file."""
    output = tmp_path / "movie.en.srt"
    cues = [{"start": 0.12, "end": 0.84, "text": "Hello"}]
    write_srt(cues, output)
    assert "00:00:00,120 --> 00:00:00,840" in output.read_text()
    with pytest.raises(FileExistsError):
        write_srt([{**cues[0], "text": "Changed"}], output)
    assert "Hello" in output.read_text()
    assert list(tmp_path.iterdir()) == [output]


def test_long_valid_destination_name_does_not_overflow_temporary_name(
    tmp_path: Path,
) -> None:
    """Publish a valid long basename without adding that name to its temporary prefix."""
    output = tmp_path / ("m" * 230 + ".en.transcript.json")
    write_json(output, {"text": "Hello"})
    assert json.loads(output.read_text()) == {"text": "Hello"}
    assert list(tmp_path.iterdir()) == [output]


def test_cues_follow_words_and_leave_silence_unsubtitled() -> None:
    """Use actual word boundaries rather than broad recognition segments."""
    cues, warnings = build_cues(
        [
            {
                "start": 0,
                "end": 10,
                "text": "Hello world. Goodbye.",
                "words": [
                    {"start": 1.12, "end": 1.4, "word": " Hello"},
                    {"start": 1.5, "end": 1.9, "word": " world."},
                    {"start": 5.2, "end": 5.8, "word": " Goodbye."},
                ],
            }
        ]
    )
    assert cues == [
        {"start": 1.12, "end": 1.9, "text": "Hello world."},
        {"start": 5.2, "end": 5.8, "text": "Goodbye."},
    ]
    assert not warnings


def test_duration_split_uses_word_boundaries() -> None:
    """Split long speech on known word boundaries without losing text."""
    words = [{"start": i, "end": i + 0.5, "word": f" word{i}"} for i in range(8)]
    cues, _ = build_cues([{"text": "", "words": words}], max_duration=3)
    assert [(cue["start"], cue["end"]) for cue in cues] == [
        (0, 2.5),
        (3, 5.5),
        (6, 7.5),
    ]
    assert " ".join(cue["text"] for cue in cues) == " ".join(
        w["word"].strip() for w in words
    )


def test_zero_duration_alignment_uses_segment_time_without_losing_text() -> None:
    """Recover a word with unusable alignment from its positive source interval."""
    cues, warnings = build_cues(
        [
            {
                "start": 1.12,
                "end": 1.84,
                "text": "Hello",
                "words": [{"start": 1.12, "end": 1.12, "word": "Hello"}],
            }
        ]
    )
    assert cues == [{"start": 1.12, "end": 1.84, "text": "Hello"}]
    assert any("used segment timing" in warning for warning in warnings)


def test_incomplete_word_alignment_preserves_the_full_source_text() -> None:
    """Do not silently drop transcript words omitted by the aligner."""
    cues, warnings = build_cues(
        [
            {
                "start": 1.12,
                "end": 2.84,
                "text": "Hello world",
                "words": [{"start": 1.12, "end": 1.84, "word": "Hello"}],
            }
        ]
    )
    assert cues == [{"start": 1.12, "end": 2.84, "text": "Hello world"}]
    assert any("used segment timing" in warning for warning in warnings)


def test_identical_start_times_merge_cues_without_losing_text() -> None:
    """Keep both texts when model segments share a start boundary."""
    cues, warnings = build_cues(
        [
            {"start": 1.12, "end": 1.84, "text": "Hello"},
            {"start": 1.12, "end": 2.84, "text": "world"},
        ]
    )
    assert cues == [{"start": 1.12, "end": 2.84, "text": "Hello world"}]
    assert any("Merged cues" in warning for warning in warnings)


def test_chinese_word_alignment_preserves_silence_between_cues() -> None:
    """Retain aligned boundaries when a language uses no interword spaces."""
    cues, warnings = build_cues(
        [
            {
                "start": 0,
                "end": 6,
                "text": "你好世界",
                "words": [
                    {"start": 0, "end": 1, "word": "你好"},
                    {"start": 5, "end": 6, "word": "世界"},
                ],
            }
        ]
    )
    assert [(cue["start"], cue["end"]) for cue in cues] == [(0, 1), (5, 6)]
    assert not warnings


@pytest.mark.parametrize(
    "cues",
    [
        [],
        [{"start": 1, "end": 1, "text": "Hello"}],
        [{"start": 0, "end": 1, "text": ""}],
        [{"start": 0, "end": 2, "text": "A"}, {"start": 1, "end": 3, "text": "B"}],
    ],
)
def test_reject_invalid_cues(cues: list[Cue]) -> None:
    """Reject empty text, overlapping timing, and nonpositive cue duration."""
    with pytest.raises(ValueError):
        validate_cues(cues)
