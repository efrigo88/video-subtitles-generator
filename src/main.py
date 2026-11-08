# ABOUTME: Runs noninteractive subtitle generation and optional local Spanish translation.
# ABOUTME: Exposes safe output handling, reusable transcripts, and machine-readable results to AI callers.
"""Noninteractive CLI for local and AI-driven subtitle generation."""

import argparse
import contextlib
import importlib.util
import json
import sys
import tempfile
from pathlib import Path
from typing import NoReturn, Optional, cast

from src.cache import transcript_cache_paths
from src.constants import (
    DEFAULT_CACHE_DIRECTORY,
    DEFAULT_DEVICE,
    DEFAULT_MODEL,
    DEFAULT_SOURCE_LANGUAGE,
    DEFAULT_SUBTITLE_LANGUAGES,
    LANGUAGE_DESCRIPTION,
    PREFLIGHT_DIRECTORY_PREFIX,
    SRT_SUFFIX,
    SUPPORTED_DEVICES,
    SUPPORTED_FORMATS,
    SUPPORTED_MODELS,
    TEMP_AUDIO_NAME,
    TEMP_DIRECTORY_PREFIX,
    TIMELINE_DESCRIPTION,
    TRANSCRIPT_SCHEMA_VERSION,
    TRANSLATION_MODEL,
    TRANSLATION_PAIR,
)
from src.helpers import (
    extract_audio,
    media_playback_duration,
    probe_video,
    select_audio_stream,
    transcribe_audio,
)
from src.models import JsonDict
from src.subtitles import (
    atomic_write,
    build_cues,
    quality_warnings,
    validate_cues,
    write_json,
    write_srt,
)
from src.translation import translate_cues


class Parser(argparse.ArgumentParser):
    """Argument parser that lets the CLI publish usage failures as JSON."""

    def error(self, message: str) -> NoReturn:
        """Raise a validation error instead of exiting before JSON reporting.

        Parameters
        ----------
        message : str
            Argument validation failure supplied by argparse.
        """
        raise ValueError(message)


def parser() -> argparse.ArgumentParser:
    """Build the supported noninteractive command-line interface.

    Returns
    -------
    argparse.ArgumentParser
        Parser for media inspection, generation, and transcript reuse.
    """
    result = Parser(
        description="Generate aligned SRT subtitles without interactive prompts."
    )
    result.add_argument("video", type=Path, help="MP4 or MKV input path")
    result.add_argument(
        "legacy_language",
        nargs="?",
        choices=LANGUAGE_DESCRIPTION,
        help="Source language (legacy positional form)",
    )
    result.add_argument("--source-language", choices=LANGUAGE_DESCRIPTION)
    result.add_argument(
        "--subtitle-languages",
        nargs="+",
        choices=LANGUAGE_DESCRIPTION,
        help="Output languages; defaults to English and Spanish for English audio",
    )
    result.add_argument(
        "--output-dir", type=Path, help="Defaults to the video directory"
    )
    result.add_argument(
        "--cache-dir",
        type=Path,
        help="External application cache for transcripts and reports",
    )
    result.add_argument("--model", default=DEFAULT_MODEL, choices=SUPPORTED_MODELS)
    result.add_argument("--device", choices=SUPPORTED_DEVICES, default=DEFAULT_DEVICE)
    result.add_argument(
        "--audio-stream", type=int, help="Absolute ffprobe stream index"
    )
    result.add_argument(
        "--list-audio", action="store_true", help="Inspect audio tracks and exit"
    )
    result.add_argument(
        "--reuse-transcript", type=Path, help="Reuse this video's saved transcription"
    )
    result.add_argument(
        "--refresh-transcript",
        action="store_true",
        help="Run speech recognition again instead of reusing the matching cache",
    )
    result.add_argument(
        "--condition-on-previous-text",
        action="store_true",
        help="Enable context across Whisper windows (may increase repetition)",
    )
    result.add_argument(
        "--overwrite", action="store_true", help="Replace existing generated files"
    )
    result.add_argument(
        "--json", action="store_true", help="Print a single JSON result to stdout"
    )
    return result


def fingerprint(video: Path) -> JsonDict:
    """Identify the source file for conservative transcript-cache reuse.

    Parameters
    ----------
    video : Path
        Resolved input video path.

    Returns
    -------
    dict[str, Any]
        Absolute path, byte size, and nanosecond modification timestamp.
    """
    stat = video.stat()
    return {"path": str(video), "size": stat.st_size, "mtime_ns": stat.st_mtime_ns}


def load_transcript(
    args: argparse.Namespace,
    video: Path,
    source: str,
    stream_index: int,
    reuse: Optional[Path],
) -> JsonDict:
    """Read a matching transcript or extract and transcribe source audio.

    Parameters
    ----------
    args : argparse.Namespace
        Parsed model, device, and decoding settings.
    video : Path
        Resolved video source.
    source : str
        Spoken language code.
    stream_index : int
        Absolute selected audio stream index.
    reuse : Path, optional
        Existing checkpoint whose source identity must match.

    Returns
    -------
    dict[str, Any]
        A source-validated checkpoint containing raw aligned segments.
    """
    source_file = fingerprint(video)
    if reuse is not None:
        checkpoint = json.loads(reuse.read_text(encoding="utf-8"))
        if not isinstance(checkpoint, dict) or (
            checkpoint.get("schema_version") != TRANSCRIPT_SCHEMA_VERSION
            or checkpoint.get("source_file") != source_file
            or checkpoint.get("source_language") != source
            or checkpoint.get("audio_stream") != stream_index
            or checkpoint.get("model") != args.model
            or checkpoint.get("condition_on_previous_text")
            != args.condition_on_previous_text
        ):
            raise ValueError(
                "Transcript does not match this video, language, audio stream, "
                "model, or decoding settings."
            )
        if not isinstance(checkpoint.get("segments"), list) or not all(
            isinstance(segment, dict) for segment in checkpoint["segments"]
        ):
            raise ValueError("Transcript segments must be a list of objects.")
        if not isinstance(checkpoint.get("model"), str):
            raise ValueError("Transcript is missing its source model name.")
        return cast(JsonDict, checkpoint)
    print(f"Extracting audio stream {stream_index}...", file=sys.stderr)
    with tempfile.TemporaryDirectory(prefix=TEMP_DIRECTORY_PREFIX) as temporary:
        audio = Path(temporary) / TEMP_AUDIO_NAME
        extract_audio(video, audio, stream_index)
        with contextlib.redirect_stdout(sys.stderr):
            segments = transcribe_audio(
                audio, args.model, source, args.device, args.condition_on_previous_text
            )
    return {
        "schema_version": TRANSCRIPT_SCHEMA_VERSION,
        "source_file": source_file,
        "source_language": source,
        "audio_stream": stream_index,
        "model": args.model,
        "device": args.device,
        "condition_on_previous_text": args.condition_on_previous_text,
        "timeline": TIMELINE_DESCRIPTION,
        "segments": segments,
    }


def generate(args: argparse.Namespace, completed: list[str]) -> JsonDict:
    """Inspect media or orchestrate transcription and language-specific publication.

    Parameters
    ----------
    args : argparse.Namespace
        Parsed command-line options.
    completed : list[str]
        Mutable record of successfully published files for partial-failure reports.

    Returns
    -------
    dict[str, Any]
        Inspection results or the persisted generation report.
    """
    video = args.video.expanduser().resolve()
    if not video.is_file():
        raise ValueError(f"Video file does not exist: {video}")
    if video.suffix.lower() not in SUPPORTED_FORMATS:
        raise ValueError(f"Supported input formats: {', '.join(SUPPORTED_FORMATS)}")
    probe = probe_video(video)
    if args.list_audio:
        return {
            "status": "ok",
            "video": str(video),
            "audio_streams": [
                {
                    "index": stream["index"],
                    "codec": stream.get("codec_name"),
                    "channels": stream.get("channels"),
                    "tags": stream.get("tags", {}),
                    "default": bool(stream.get("disposition", {}).get("default")),
                    "start_time": stream.get("start_time"),
                }
                for stream in probe["streams"]
                if stream["codec_type"] == "audio"
            ],
        }
    if (
        args.source_language
        and args.legacy_language
        and args.source_language != args.legacy_language
    ):
        raise ValueError("Conflicting positional and --source-language values.")
    source = args.source_language or args.legacy_language or DEFAULT_SOURCE_LANGUAGE
    default_languages = (
        DEFAULT_SUBTITLE_LANGUAGES if source == DEFAULT_SOURCE_LANGUAGE else (source,)
    )
    languages = list(dict.fromkeys(args.subtitle_languages or default_languages))
    if any(
        language != source and (source, language) != TRANSLATION_PAIR
        for language in languages
    ):
        raise ValueError(
            "Translation currently supports English audio to Spanish only."
        )
    needs_translation = (
        TRANSLATION_PAIR[1] in languages and source == TRANSLATION_PAIR[0]
    )
    if needs_translation and importlib.util.find_spec("transformers") is None:
        raise RuntimeError(
            "Spanish translation requires the standard dependencies: uv sync --locked"
        )
    if args.reuse_transcript and args.refresh_transcript:
        raise ValueError(
            "--reuse-transcript and --refresh-transcript cannot be combined."
        )
    stream = select_audio_stream(probe, source, args.audio_stream)
    output_dir = (args.output_dir or video.parent).expanduser().resolve()
    if output_dir.exists() and not output_dir.is_dir():
        raise ValueError(f"Output directory is not a directory: {output_dir}")
    outputs = {
        language: output_dir / f"{video.stem}.{language}{SRT_SUFFIX}"
        for language in languages
    }
    transcript_path, report_path = transcript_cache_paths(
        args.cache_dir or DEFAULT_CACHE_DIRECTORY,
        fingerprint(video),
        source,
        stream["index"],
        args.model,
        args.condition_on_previous_text,
        output_dir,
    )
    reuse = (
        args.reuse_transcript.expanduser().resolve() if args.reuse_transcript else None
    )
    if reuse is None and not args.refresh_transcript and transcript_path.exists():
        reuse = transcript_path
    if (
        reuse is None
        and args.device == "mlx"
        and importlib.util.find_spec("mlx_whisper") is None
    ):
        raise RuntimeError("Apple acceleration requires: uv sync --extra apple")
    planned = list(outputs.values())
    cached = [transcript_path, report_path]
    for path in planned + cached:
        if path.is_dir():
            raise IsADirectoryError(f"Output path is a directory: {path}")
    if not args.overwrite:
        for path in planned:
            if path.exists() or path.is_symlink():
                raise FileExistsError(
                    f"Output already exists: {path}. Use --overwrite to replace it."
                )
    # Validate the actual publication operation before paying for model inference.
    for directory, paths, overwrite in [
        (output_dir, planned, args.overwrite),
        (transcript_path.parent, cached, True),
    ]:
        directory.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(
            prefix=PREFLIGHT_DIRECTORY_PREFIX, dir=directory
        ) as temporary:
            for path in paths:
                atomic_write(Path(temporary) / path.name, "", overwrite)
    checkpoint = load_transcript(args, video, source, stream["index"], reuse)
    # Raw inference survives subsequent formatting or translation failures.
    if reuse != transcript_path:
        write_json(transcript_path, checkpoint, overwrite=True)
    completed.append(str(transcript_path))
    cues, warnings = build_cues(checkpoint["segments"])
    duration = media_playback_duration(video, probe)
    if duration is None:
        warnings.append(
            "Media playback duration could not be established; "
            "cue endpoints were not checked against the media end."
        )
    warnings.extend(quality_warnings(cues, duration))
    if source in outputs:
        write_srt(cues, outputs[source], args.overwrite)
        completed.append(str(outputs[source]))
    if needs_translation:
        print("Translating aligned English cues to Spanish locally...", file=sys.stderr)
        with contextlib.redirect_stdout(sys.stderr):
            translated = translate_cues(cues)
        validate_cues(translated)
        warnings.extend(
            f"Spanish: {warning}" for warning in quality_warnings(translated, duration)
        )
        write_srt(translated, outputs[TRANSLATION_PAIR[1]], args.overwrite)
        completed.append(str(outputs[TRANSLATION_PAIR[1]]))
    warnings = list(dict.fromkeys(warnings))
    report = {
        "status": "ok",
        "video": str(video),
        "source_language": source,
        "audio_stream": stream["index"],
        "model": checkpoint["model"],
        "outputs": {language: str(path) for language, path in outputs.items()},
        "transcript": str(transcript_path),
        "report": str(report_path),
        "cue_count": len(cues),
        "warnings": warnings,
        "translation_model": TRANSLATION_MODEL if needs_translation else None,
    }
    write_json(report_path, report, overwrite=True)
    return report


def main(argv: Optional[list[str]] = None) -> int:
    """Execute the CLI and report failures without contaminating JSON stdout.

    Parameters
    ----------
    argv : list[str], optional
        Arguments excluding the executable; defaults to the process arguments.

    Returns
    -------
    int
        Zero on success, one on a handled failure.
    """
    argv = sys.argv[1:] if argv is None else argv
    completed: list[str] = []
    try:
        args = parser().parse_args(argv)
        report = generate(args, completed)
    except (ValueError, OSError, RuntimeError, KeyError, TypeError, ImportError) as exc:
        report = {"status": "error", "error": str(exc), "completed_files": completed}
        if "--json" in argv:
            print(json.dumps(report, ensure_ascii=False))
        else:
            print(f"Error: {exc}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(report, ensure_ascii=False))
    elif args.list_audio:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        for language, path in report["outputs"].items():
            print(f"{language}: {path}")
        print(f"Report: {report['report']}")
        for warning in report["warnings"]:
            print(f"Warning: {warning}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
