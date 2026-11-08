# ABOUTME: Verifies audio stream selection and timeline-preserving extraction.
# ABOUTME: Combines inference doubles with synthetic FFmpeg containers to expose offset loss.
"""Regression coverage for media selection and alignment configuration."""

import array
import shutil
import subprocess
import sys
import types
import wave
from pathlib import Path
from typing import Any

import pytest

from src.helpers import (
    extract_audio,
    media_playback_duration,
    probe_video,
    select_audio_stream,
    transcribe_audio,
)
from src.models import JsonDict
from src.subtitles import quality_warnings


def test_select_language_then_default_and_allow_explicit_index() -> None:
    """Prefer the spoken language while honoring an explicit absolute stream index."""
    probe = {
        "streams": [
            {
                "codec_type": "audio",
                "index": 1,
                "tags": {"language": "spa"},
                "disposition": {"default": 1},
            },
            {"codec_type": "audio", "index": 2, "tags": {"language": "eng"}},
        ]
    }
    assert select_audio_stream(probe, "en")["index"] == 2
    assert select_audio_stream(probe, "en", 1)["index"] == 1
    with pytest.raises(ValueError, match="does not exist"):
        select_audio_stream(probe, "en", 8)


def test_whisper_requests_word_alignment_and_silence_protection(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Request source speech alignment and avoid cross-window repetition by default."""
    captured: JsonDict = {}

    def transcribe(path: str, **kwargs: Any) -> JsonDict:
        """Record transcription options without importing a speech model."""
        captured.update(kwargs)
        return {"segments": []}

    monkeypatch.setitem(
        sys.modules,
        "whisper",
        types.SimpleNamespace(
            load_model=lambda *a, **kw: types.SimpleNamespace(transcribe=transcribe)
        ),
    )
    transcribe_audio(tmp_path / "audio.wav")
    assert captured["word_timestamps"] is True
    assert captured["condition_on_previous_text"] is False
    assert captured["task"] == "transcribe"
    assert captured["fp16"] is False
    assert captured["hallucination_silence_threshold"] == 2


@pytest.mark.skipif(
    not shutil.which("ffmpeg") or not shutil.which("ffprobe"), reason="FFmpeg required"
)
@pytest.mark.parametrize("origin", [-1, 0, 5])
def test_extract_keeps_delayed_audio_at_container_playback_origin(
    tmp_path: Path, origin: int
) -> None:
    """Preserve an audio delay even when the container starts at a nonzero time."""
    video = tmp_path / "delayed.mkv"
    subprocess.run(
        [
            "ffmpeg",
            "-nostdin",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            "color=s=32x32:d=3.5:r=10",
            "-itsoffset",
            "1.25",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:duration=1:sample_rate=16000",
            "-map",
            "0:v",
            "-map",
            "1:a",
            "-c:v",
            "ffv1",
            "-c:a",
            "pcm_s16le",
            "-avoid_negative_ts",
            "disabled",
            "-output_ts_offset",
            str(origin),
            str(video),
        ],
        check=True,
    )
    probe = probe_video(video)
    assert float(probe["format"]["start_time"]) == origin
    assert float(probe["format"]["duration"]) == pytest.approx(3.5 + origin)
    duration = media_playback_duration(video, probe)
    assert duration == pytest.approx(3.5)
    assert (
        quality_warnings([{"start": 3.0, "end": 3.4, "text": "Yes."}], duration) == []
    )
    with pytest.raises(ValueError, match="beyond the media duration"):
        quality_warnings([{"start": 3.4, "end": 4.0, "text": "No."}], duration)
    audio = tmp_path / "audio.wav"
    extract_audio(video, audio, select_audio_stream(probe, "en")["index"])
    with wave.open(str(audio)) as wav:
        assert wav.getframerate() == 16000
        samples = array.array("h", wav.readframes(wav.getnframes()))
    first_signal = next(i for i, value in enumerate(samples) if abs(value) > 100)
    assert first_signal / 16000 == pytest.approx(1.25, abs=0.01)
    # A pre-existing destination never triggers FFmpeg's interactive overwrite prompt.
    with pytest.raises(FileExistsError, match="already exists"):
        extract_audio(video, audio, 1)


@pytest.mark.skipif(
    not shutil.which("ffmpeg") or not shutil.which("ffprobe"), reason="FFmpeg required"
)
@pytest.mark.parametrize("origin, expected", [(-1, 2.5), (0, 3.5), (5, 3.5)])
def test_mp4_stream_duration_is_a_length_not_an_absolute_endpoint(
    tmp_path: Path, origin: int, expected: float
) -> None:
    """Respect MP4 edit lists and preserve valid positive-origin playback bounds."""
    video = tmp_path / "offset.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-nostdin",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            "color=s=32x32:d=3.5:r=10",
            "-itsoffset",
            "1.25",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:duration=1:sample_rate=16000",
            "-c:v",
            "mpeg4",
            "-c:a",
            "aac",
            "-avoid_negative_ts",
            "disabled",
            "-output_ts_offset",
            str(origin),
            str(video),
        ],
        check=True,
    )
    probe = probe_video(video)
    # MP4 reports a length even when presentation starts five seconds later.
    assert float(probe["format"]["duration"]) == pytest.approx(expected)
    assert media_playback_duration(video, probe) == pytest.approx(expected, abs=0.07)


@pytest.mark.parametrize("failure", ["packet_limit", "missing_duration", "probe_error"])
def test_unreliable_tail_cannot_supply_a_media_bound(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, failure: str
) -> None:
    """Leave validation explicitly unbounded when a capped tail is inconclusive."""
    import json

    from src.constants import MEDIA_DURATION_MAX_PACKETS

    probe: JsonDict = {
        "format": {"start_time": "5", "duration": "8.5"},
        "streams": [{"index": 0, "codec_type": "video", "start_time": "5"}],
    }

    def inspect_tail(command: list[str]) -> str:
        """Return incomplete packet metadata without reading an actual movie."""
        if failure == "probe_error":
            raise RuntimeError("Unseekable input")
        packet = {"stream_index": 0, "pts_time": "8.4"}
        if failure == "packet_limit":
            return json.dumps({"packets": [packet] * MEDIA_DURATION_MAX_PACKETS})
        return json.dumps({"packets": [packet]})

    monkeypatch.setattr("src.helpers.run_media_command", inspect_tail)
    assert media_playback_duration(tmp_path / "unreliable.mkv", probe) is None


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="FFmpeg required")
def test_extract_preserves_internal_timestamp_gaps(tmp_path: Path) -> None:
    """Fill missing audio intervals rather than shifting later speech earlier."""
    video = tmp_path / "gap.mkv"
    subprocess.run(
        [
            "ffmpeg",
            "-nostdin",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            "color=s=32x32:d=3:r=10",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:duration=3:sample_rate=16000",
            "-af",
            "aselect='not(between(t,0.5,1.5))'",
            "-c:v",
            "ffv1",
            "-c:a",
            "pcm_s16le",
            str(video),
        ],
        check=True,
    )
    audio = tmp_path / "gap.wav"
    extract_audio(video, audio, 1)
    with wave.open(str(audio)) as wav:
        samples = array.array("h", wav.readframes(wav.getnframes()))
    assert max(abs(v) for v in samples[16000:20000]) < 100
    assert max(abs(v) for v in samples[32000:36000]) > 1000
