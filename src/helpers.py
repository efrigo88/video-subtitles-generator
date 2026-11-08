# ABOUTME: Inspects media streams and transcribes timeline-preserving audio.
# ABOUTME: Keeps subtitle timing relative to video playback across local inference backends.
"""Media inspection, timeline-preserving extraction, and Whisper inference."""

import gc
import json
import math
import subprocess
import sys
from pathlib import Path
from typing import Optional, cast

from src.constants import (
    AUDIO_CHANNELS,
    AUDIO_CODEC,
    AUDIO_SAMPLE_RATE,
    CONDITION_ON_PREVIOUS_TEXT,
    DEFAULT_DEVICE,
    DEFAULT_MODEL,
    DEFAULT_SOURCE_LANGUAGE,
    HALLUCINATION_SILENCE_SECONDS,
    LANGUAGE_TAGS,
    MEDIA_DURATION_MAX_PACKETS,
    MEDIA_DURATION_TAIL_SECONDS,
    MLX_MODEL_REPOSITORIES,
)
from src.models import JsonDict


def run_media_command(command: list[str]) -> str:
    """Run a media utility and turn executable or process failures into errors.

    Parameters
    ----------
    command : list[str]
        Executable and arguments, passed directly without a shell.

    Returns
    -------
    str
        Captured standard output.
    """
    try:
        result = subprocess.run(command, check=True, capture_output=True, text=True)
    except FileNotFoundError as exc:
        raise RuntimeError(f"{command[0]} is required; install FFmpeg first.") from exc
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(f"{command[0]} failed: {exc.stderr.strip()}") from exc
    return result.stdout


def probe_video(video_path: Path) -> JsonDict:
    """Read container metadata and require video and audio streams.

    Parameters
    ----------
    video_path : Path
        Input video to inspect.

    Returns
    -------
    dict[str, Any]
        FFprobe stream and format metadata.
    """
    result = json.loads(
        run_media_command(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_streams",
                "-show_format",
                "-of",
                "json",
                str(video_path),
            ]
        )
    )
    if not any(s["codec_type"] == "video" for s in result["streams"]):
        raise ValueError("The input has no video stream.")
    if not any(s["codec_type"] == "audio" for s in result["streams"]):
        raise ValueError("The input has no audio stream.")
    return cast(JsonDict, result)


def _finite_seconds(value: object) -> Optional[float]:
    """Parse a finite FFprobe timestamp, returning None for absent metadata."""
    if not isinstance(value, (int, float, str)):
        return None
    try:
        seconds = float(value)
    except ValueError:
        return None
    return seconds if math.isfinite(seconds) else None


def media_playback_duration(video_path: Path, probe: JsonDict) -> Optional[float]:
    """Find the media end on the same rebased timeline as extracted audio.

    Parameters
    ----------
    video_path : Path
        Source container to inspect without decoding audio or video.
    probe : dict[str, Any]
        FFprobe stream and format metadata for the source container.

    Returns
    -------
    float or None
        Positive playback endpoint in seconds, or None when metadata and a
        bounded tail inspection cannot establish a reliable endpoint.

    Notes
    -----
    Stream durations are lengths, so their presentation endpoints include their
    start times. Container duration is only a seek hint: muxers disagree about
    whether it includes a nonzero timestamp origin. Missing stream durations
    require a tail packet probe capped at a fixed packet count. Reaching that
    cap cannot establish EOF and therefore leaves the duration unknown.
    """
    origin = _finite_seconds(probe.get("format", {}).get("start_time"))
    if origin is None:
        return None
    streams: list[JsonDict] = [
        stream
        for stream in probe["streams"]
        if stream.get("codec_type") in {"audio", "video"}
        and not stream.get("disposition", {}).get("attached_pic")
    ]
    endpoints: list[float] = []
    missing: set[int] = set()
    for stream in streams:
        start = _finite_seconds(stream.get("start_time"))
        duration = _finite_seconds(stream.get("duration"))
        if start is None or duration is None or duration <= 0:
            missing.add(stream["index"])
        else:
            endpoints.append(start + duration)
    if missing:
        hint = _finite_seconds(probe.get("format", {}).get("duration"))
        if hint is None or hint <= 0:
            return None
        # Seeking past EOF can return the last keyframe or no packets; both are
        # safe. The hint never becomes a validation bound itself.
        seek = max(origin, hint, origin + hint) - MEDIA_DURATION_TAIL_SECONDS
        try:
            tail = json.loads(
                run_media_command(
                    [
                        "ffprobe",
                        "-v",
                        "error",
                        "-read_intervals",
                        f"{seek}%+#{MEDIA_DURATION_MAX_PACKETS}",
                        "-show_packets",
                        "-show_entries",
                        "packet=stream_index,pts_time,duration_time",
                        "-of",
                        "json",
                        str(video_path),
                    ]
                )
            )
        except RuntimeError:
            return None
        packets: list[JsonDict] = tail.get("packets", [])
        if len(packets) >= MEDIA_DURATION_MAX_PACKETS:
            return None
        found: set[int] = set()
        for packet in packets:
            index = packet.get("stream_index")
            if index not in missing:
                continue
            pts = _finite_seconds(packet.get("pts_time"))
            duration = _finite_seconds(packet.get("duration_time"))
            if pts is None or duration is None or duration <= 0:
                return None
            endpoints.append(pts + duration)
            found.add(index)
        if found != missing:
            return None
    if not endpoints:
        return None
    playback_end = max(endpoints) - origin
    return playback_end if playback_end > 0 else None


def select_audio_stream(
    probe: JsonDict, language: str, stream_index: Optional[int] = None
) -> JsonDict:
    """Select an explicit track or prefer a language match and default disposition.

    Parameters
    ----------
    probe : dict[str, Any]
        FFprobe metadata containing audio streams.
    language : str
        Spoken language code used for matching track tags.
    stream_index : int, optional
        Absolute stream index, including non-audio streams in the numbering.

    Returns
    -------
    dict[str, Any]
        Selected audio stream metadata.
    """
    streams: list[JsonDict] = [
        s for s in probe["streams"] if s["codec_type"] == "audio"
    ]
    if not streams:
        raise ValueError("The input has no audio stream.")
    if stream_index is not None:
        for stream in streams:
            if stream["index"] == stream_index:
                return stream
        raise ValueError(
            f"Audio stream {stream_index} does not exist. Use --list-audio."
        )
    matching = [
        s
        for s in streams
        if s.get("tags", {}).get("language", "").lower() in LANGUAGE_TAGS[language]
    ]
    candidates = matching or streams
    return next(
        (s for s in candidates if s.get("disposition", {}).get("default")),
        candidates[0],
    )


def extract_audio(video_path: Path, audio_path: Path, stream_index: int) -> None:
    """Extract mono PCM while preserving the container playback timeline.

    Parameters
    ----------
    video_path : Path
        Source container, whose start time defines playback zero.
    audio_path : Path
        Unused destination for a mono 16 kHz WAV file.
    stream_index : int
        Absolute audio stream index from FFprobe.

    Notes
    -----
    Shared timestamp rebasing preserves delayed audio. Resampling inserts leading
    silence and timestamp gaps instead of collapsing them onto the speech.
    """
    if audio_path.exists():
        raise FileExistsError(f"Audio destination already exists: {audio_path}")
    run_media_command(
        [
            "ffmpeg",
            "-nostdin",
            "-n",
            "-loglevel",
            "error",
            "-copyts",
            "-start_at_zero",
            "-i",
            str(video_path),
            "-map",
            f"0:{stream_index}",
            "-vn",
            "-af",
            f"aresample={AUDIO_SAMPLE_RATE}:async=1:first_pts=0",
            "-acodec",
            AUDIO_CODEC,
            "-ar",
            str(AUDIO_SAMPLE_RATE),
            "-ac",
            str(AUDIO_CHANNELS),
            str(audio_path),
        ]
    )


def _null_nonfinite(value: object) -> object:
    """Replace NaN and infinite floats in nested inference output with None.

    Parameters
    ----------
    value : object
        Whisper output fragment: a mapping, list, or scalar.

    Returns
    -------
    object
        Structurally identical data that strict JSON serialization accepts.
    """
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, dict):
        return {key: _null_nonfinite(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_null_nonfinite(item) for item in value]
    return value


def transcribe_audio(
    audio_path: Path,
    model_size: str = DEFAULT_MODEL,
    language: str = DEFAULT_SOURCE_LANGUAGE,
    device: str = DEFAULT_DEVICE,
    condition_on_previous_text: bool = CONDITION_ON_PREVIOUS_TEXT,
) -> list[JsonDict]:
    """Transcribe source speech with word alignment and silence protection.

    Parameters
    ----------
    audio_path : Path
        Timeline-preserving WAV file.
    model_size : str
        Whisper model name.
    language : str
        Spoken language, rather than a translation target.
    device : str
        ``cpu``, ``cuda``, or Apple Silicon ``mlx``.
    condition_on_previous_text : bool
        Whether decoding uses text from previous windows.

    Returns
    -------
    list[dict[str, Any]]
        Whisper segments including aligned words and confidence diagnostics;
        nonfinite values such as an empty-slice word probability become None.
    """
    print(f"Loading Whisper {model_size} on {device}...", file=sys.stderr)
    options: JsonDict = dict(
        language=language,
        task="transcribe",
        verbose=False,
        word_timestamps=True,
        condition_on_previous_text=condition_on_previous_text,
        hallucination_silence_threshold=HALLUCINATION_SILENCE_SECONDS,
    )
    if device == "mlx":
        try:
            import mlx_whisper
            from mlx_whisper.transcribe import ModelHolder
        except ImportError as exc:
            raise RuntimeError(
                "Apple acceleration requires: uv sync --extra apple"
            ) from exc
        try:
            result = mlx_whisper.transcribe(
                str(audio_path),
                path_or_hf_repo=MLX_MODEL_REPOSITORIES[model_size],
                **options,
            )
            return cast(list[JsonDict], _null_nonfinite(result["segments"]))
        finally:
            # MLX caches its model globally; translation needs that memory back.
            ModelHolder.model = None
            ModelHolder.model_path = None
            gc.collect()
    # Lazy imports keep help, probing, and transcript reuse independent of torch.
    import whisper

    model = whisper.load_model(model_size, device=device)
    try:
        result = model.transcribe(
            str(audio_path),
            fp16=device == "cuda",
            **options,
        )
        return cast(list[JsonDict], _null_nonfinite(result["segments"]))
    finally:
        del model
        gc.collect()
