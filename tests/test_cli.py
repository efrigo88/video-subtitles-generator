# ABOUTME: Exercises the noninteractive subtitle CLI and artifact safety contracts.
# ABOUTME: Uses bounded inference doubles so failures and recovery need no model downloads.
"""Regression coverage for CLI output, source integrity, and cleanup."""

import json
from pathlib import Path
from typing import Any, NoReturn

import pytest

from src import main as cli
from src.models import JsonDict

Pipeline = tuple[Path, list[Path]]


@pytest.fixture
def pipeline(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Pipeline:
    """Provide a video and record temporary paths through a model-free pipeline."""
    media_directory = tmp_path / "media"
    media_directory.mkdir()
    video = media_directory / "movie with spaces.mp4"
    monkeypatch.setattr(
        cli, "DEFAULT_CACHE_DIRECTORY", tmp_path / "cache", raising=False
    )
    video.write_bytes(b"video fixture")
    probe = {
        "format": {"duration": "10"},
        "streams": [
            {"codec_type": "video", "index": 0},
            {"codec_type": "audio", "index": 1, "tags": {"language": "eng"}},
        ],
    }
    monkeypatch.setattr(cli, "probe_video", lambda path: probe)
    calls: list[Path] = []

    def extract(video_path: Path, audio: Path, index: int) -> None:
        """Write temporary audio while recording the selected stream."""
        calls.append(audio)
        assert index == 1
        audio.write_bytes(b"temporary")

    def transcribe(*args: Any) -> list[JsonDict]:
        """Return aligned speech and simulate third-party progress output."""
        print("Library progress must go to stderr")
        return [
            {
                "start": 0.12,
                "end": 0.84,
                "text": " Hello",
                "words": [{"start": 0.12, "end": 0.84, "word": " Hello"}],
            }
        ]

    monkeypatch.setattr(cli, "extract_audio", extract)
    monkeypatch.setattr(cli, "transcribe_audio", transcribe)
    monkeypatch.setattr(cli.importlib.util, "find_spec", lambda name: object())
    monkeypatch.setattr(
        cli, "translate_cues", lambda cues: [{**c, "text": "Hola"} for c in cues]
    )
    return video, calls


def test_bilingual_outputs_json_protocol_and_safe_temporary_files(
    pipeline: Pipeline, capsys: pytest.CaptureFixture[str]
) -> None:
    """Keep bilingual timings identical and preserve unrelated sibling audio."""
    video, calls = pipeline
    sibling = video.with_suffix(".wav")
    sibling.write_bytes(b"user audio, must survive")
    assert cli.main([str(video), "--subtitle-languages", "en", "es", "--json"]) == 0
    output = capsys.readouterr()
    result = json.loads(output.out)
    assert "Library progress" in output.err
    assert result["cue_count"] == 1
    english = video.with_suffix(".en.srt").read_text()
    spanish = video.with_suffix(".es.srt").read_text()
    assert (
        english.splitlines()[1]
        == spanish.splitlines()[1]
        == "00:00:00,120 --> 00:00:00,840"
    )
    assert "Hello" in english and "Hola" in spanish
    assert sibling.read_bytes() == b"user audio, must survive"
    assert not calls[0].parent.exists()


def test_refuse_overwrite_before_inference(
    pipeline: Pipeline, capsys: pytest.CaptureFixture[str]
) -> None:
    """Reject existing subtitles before spending inference resources."""
    video, calls = pipeline
    output = video.with_suffix(".en.srt")
    output.write_text("existing subtitles")
    assert cli.main([str(video), "--json"]) == 1
    assert "already exists" in json.loads(capsys.readouterr().out)["error"]
    assert not calls
    assert output.read_text() == "existing subtitles"


def test_default_english_run_generates_both_languages_once(
    pipeline: Pipeline, capsys: pytest.CaptureFixture[str]
) -> None:
    """Produce English and Spanish by default from one source transcription."""
    video, calls = pipeline
    assert cli.main([str(video), "--json"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert set(result["outputs"]) == {"en", "es"}
    assert len(calls) == 1


def test_explicit_english_only_skips_translation(
    pipeline: Pipeline,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Allow an explicit single-language output without translation work."""
    video, calls = pipeline

    def unexpected_translation(cues: list[JsonDict]) -> NoReturn:
        """Fail when translation runs despite requesting English alone."""
        raise RuntimeError("Translation must not run")

    monkeypatch.setattr(cli, "translate_cues", unexpected_translation)
    assert cli.main([str(video), "--subtitle-languages", "en", "--json"]) == 0
    assert set(json.loads(capsys.readouterr().out)["outputs"]) == {"en"}
    assert len(calls) == 1


def test_translation_failure_keeps_reusable_english_and_transcript(
    pipeline: Pipeline,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Resume translation from a checkpoint without extracting speech twice."""
    video, calls = pipeline

    def fail(cues: list[JsonDict]) -> NoReturn:
        """Simulate an unavailable translator after transcription completed."""
        raise RuntimeError("translation unavailable")

    monkeypatch.setattr(cli, "translate_cues", fail)
    assert cli.main([str(video), "--subtitle-languages", "en", "es", "--json"]) == 1
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "error"
    assert len(result["completed_files"]) == 2
    assert video.with_suffix(".en.srt").exists()
    assert not video.with_suffix(".es.srt").exists()
    monkeypatch.setattr(
        cli, "translate_cues", lambda cues: [{**c, "text": "Hola"} for c in cues]
    )
    assert (
        cli.main(
            [
                str(video),
                "--subtitle-languages",
                "es",
                "--reuse-transcript",
                str(Path(result["completed_files"][0])),
                "--json",
            ]
        )
        == 0
    )
    assert len(calls) == 1
    assert json.loads(capsys.readouterr().out)["status"] == "ok"


def test_reject_transcript_from_modified_video(
    pipeline: Pipeline, capsys: pytest.CaptureFixture[str]
) -> None:
    """Prevent cached speech from being applied to a different input movie."""
    video, calls = pipeline
    assert cli.main([str(video), "--json"]) == 0
    checkpoint_path = Path(json.loads(capsys.readouterr().out)["transcript"])
    video.write_bytes(b"different movie")
    assert (
        cli.main(
            [
                str(video),
                "--reuse-transcript",
                str(checkpoint_path),
                "--overwrite",
                "--json",
            ]
        )
        == 1
    )
    assert "does not match" in json.loads(capsys.readouterr().out)["error"]
    assert len(calls) == 1


def test_malformed_checkpoint_returns_structured_failure(
    pipeline: Pipeline, capsys: pytest.CaptureFixture[str]
) -> None:
    """Reject malformed reusable segments without rerunning recognition."""
    video, calls = pipeline
    assert cli.main([str(video), "--json"]) == 0
    checkpoint_path = Path(json.loads(capsys.readouterr().out)["transcript"])
    checkpoint = json.loads(checkpoint_path.read_text())
    checkpoint["segments"] = ["not a segment object"]
    checkpoint_path.write_text(json.dumps(checkpoint))
    assert (
        cli.main(
            [
                str(video),
                "--reuse-transcript",
                str(checkpoint_path),
                "--overwrite",
                "--json",
            ]
        )
        == 1
    )
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "error"
    assert "list of objects" in result["error"]
    assert len(calls) == 1


def test_cleanup_on_inference_failure(
    pipeline: Pipeline,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Remove temporary audio even when the recognizer raises an error."""
    video, calls = pipeline

    def fail(*args: Any) -> NoReturn:
        """Simulate inference failing before a transcript exists."""
        raise RuntimeError("inference failed")

    monkeypatch.setattr(cli, "transcribe_audio", fail)
    assert cli.main([str(video), "--json"]) == 1
    assert json.loads(capsys.readouterr().out)["status"] == "error"
    assert not calls[0].parent.exists()


def test_invalid_destination_fails_before_inference(
    pipeline: Pipeline, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    """Reject a file used as an output-directory ancestor before model work."""
    video, calls = pipeline
    obstacle = tmp_path / "regular-file"
    obstacle.write_text("preserve me")
    assert (
        cli.main([str(video), "--output-dir", str(obstacle / "child"), "--json"]) == 1
    )
    assert json.loads(capsys.readouterr().out)["status"] == "error"
    assert not calls
    assert obstacle.read_text() == "preserve me"


def test_long_input_basename_uses_short_cache_filenames(
    pipeline: Pipeline, capsys: pytest.CaptureFixture[str]
) -> None:
    """Keep valid long media names usable by hashing metadata cache paths."""
    video, calls = pipeline
    long_video = video.with_name("m" * 240 + ".mp4")
    video.rename(long_video)
    assert cli.main([str(long_video), "--json"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "ok"
    assert len(Path(result["transcript"]).name) < 40
    assert len(calls) == 1


@pytest.mark.parametrize("words", [[None], ["bad"], "bad", {"word": "Hello"}])
def test_malformed_nested_words_return_structured_failure(
    pipeline: Pipeline, capsys: pytest.CaptureFixture[str], words: Any
) -> None:
    """Validate nested alignment data rather than leaking an attribute traceback."""
    video, calls = pipeline
    assert cli.main([str(video), "--json"]) == 0
    path = Path(json.loads(capsys.readouterr().out)["transcript"])
    checkpoint = json.loads(path.read_text())
    checkpoint["segments"][0]["words"] = words
    path.write_text(json.dumps(checkpoint))
    assert (
        cli.main([str(video), "--reuse-transcript", str(path), "--overwrite", "--json"])
        == 1
    )
    assert json.loads(capsys.readouterr().out)["status"] == "error"
    assert len(calls) == 1


@pytest.mark.parametrize(
    "arguments", [[], ["missing.mp4"], ["movie.mp4", "--bad-option"]]
)
def test_json_errors_have_nonzero_exit_and_one_result(
    arguments: list[str], capsys: pytest.CaptureFixture[str]
) -> None:
    """Return one parseable failure result for invalid or missing CLI inputs."""
    assert cli.main(arguments + ["--json"]) == 1
    assert json.loads(capsys.readouterr().out)["status"] == "error"


def test_help_does_not_attempt_transcription(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Expose CLI help successfully without loading speech models."""
    with pytest.raises(SystemExit) as exc:
        cli.main(["--help"])
    assert exc.value.code == 0
    assert "--source-language" in capsys.readouterr().out


def test_movie_folder_receives_only_two_subtitles(
    pipeline: Pipeline, capsys: pytest.CaptureFixture[str]
) -> None:
    """Keep all transcripts and reports outside the media directory."""
    video, calls = pipeline
    assert cli.main([str(video), "--json"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert set(video.parent.iterdir()) == {
        video,
        video.with_suffix(".en.srt"),
        video.with_suffix(".es.srt"),
    }
    assert not Path(result["transcript"]).is_relative_to(video.parent)
    assert not Path(result["report"]).is_relative_to(video.parent)
    assert len(calls) == 1


def test_cached_transcript_is_reused_across_output_directories(
    pipeline: Pipeline, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    """Avoid repeating speech recognition when writing the same movie elsewhere."""
    video, calls = pipeline
    assert cli.main([str(video), "--json"]) == 0
    first = json.loads(capsys.readouterr().out)
    destination = tmp_path / "subtitles"
    assert cli.main([str(video), "--output-dir", str(destination), "--json"]) == 0
    second = json.loads(capsys.readouterr().out)
    assert first["transcript"] == second["transcript"]
    assert len(calls) == 1
    assert set(destination.iterdir()) == {
        destination / video.with_suffix(".en.srt").name,
        destination / video.with_suffix(".es.srt").name,
    }


def test_refresh_transcript_runs_recognition_again(
    pipeline: Pipeline, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    """Allow intentional cache refresh without weakening SRT overwrite protection."""
    video, calls = pipeline
    assert cli.main([str(video), "--json"]) == 0
    first = json.loads(capsys.readouterr().out)
    assert (
        cli.main(
            [
                str(video),
                "--output-dir",
                str(tmp_path / "fresh"),
                "--refresh-transcript",
                "--json",
            ]
        )
        == 0
    )
    second = json.loads(capsys.readouterr().out)
    assert first["transcript"] == second["transcript"]
    assert len(calls) == 2


@pytest.mark.parametrize(
    "options",
    [
        ["--model", "small"],
        ["--source-language", "es"],
        ["--condition-on-previous-text"],
    ],
)
def test_cache_identity_includes_transcription_settings(
    pipeline: Pipeline,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
    options: list[str],
) -> None:
    """Invalidate cached speech when its model, language, or decoding context changes."""
    video, calls = pipeline
    assert cli.main([str(video), "--json"]) == 0
    first = json.loads(capsys.readouterr().out)
    assert (
        cli.main(
            [str(video), "--output-dir", str(tmp_path / "changed"), *options, "--json"]
        )
        == 0
    )
    second = json.loads(capsys.readouterr().out)
    assert first["transcript"] != second["transcript"]
    assert len(calls) == 2


@pytest.mark.parametrize("relative", [".", "cache/inside-movie-folder"])
def test_cache_cannot_pollute_movie_directory(
    pipeline: Pipeline, capsys: pytest.CaptureFixture[str], relative: str
) -> None:
    """Reject cache locations equal to or inside the movie directory."""
    video, calls = pipeline
    cache = video.parent / relative
    assert cli.main([str(video), "--cache-dir", str(cache), "--json"]) == 1
    result = json.loads(capsys.readouterr().out)
    assert "cache" in result["error"].lower()
    assert not calls
    assert set(video.parent.iterdir()) == {video}


def test_list_audio_does_not_create_cache(
    pipeline: Pipeline, capsys: pytest.CaptureFixture[str]
) -> None:
    """Keep metadata inspection read-only without creating application cache files."""
    video, calls = pipeline
    assert cli.main([str(video), "--list-audio", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["audio_streams"]
    assert not cli.DEFAULT_CACHE_DIRECTORY.exists()
    assert not calls


def test_corrupted_automatic_cache_returns_structured_error(
    pipeline: Pipeline, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    """Preserve a damaged checkpoint for inspection without silently rerunning ASR."""
    video, calls = pipeline
    assert cli.main([str(video), "--json"]) == 0
    transcript = Path(json.loads(capsys.readouterr().out)["transcript"])
    transcript.write_text("invalid JSON")
    assert (
        cli.main([str(video), "--output-dir", str(tmp_path / "retry"), "--json"]) == 1
    )
    assert json.loads(capsys.readouterr().out)["status"] == "error"
    assert transcript.read_text() == "invalid JSON"
    assert len(calls) == 1


def test_cached_reuse_does_not_require_inference_backend(
    pipeline: Pipeline,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    """Reuse CPU or MLX speech results without importing the original backend."""
    video, calls = pipeline
    assert cli.main([str(video), "--json"]) == 0
    capsys.readouterr()
    monkeypatch.setattr(
        cli.importlib.util,
        "find_spec",
        lambda name: None if name == "mlx_whisper" else object(),
    )
    assert (
        cli.main(
            [
                str(video),
                "--device",
                "mlx",
                "--output-dir",
                str(tmp_path / "mlx-retry"),
                "--json",
            ]
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out)["status"] == "ok"
    assert len(calls) == 1


def test_cache_directory_preflight_fails_before_inference(
    pipeline: Pipeline, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    """Validate cache publication as well as SRT publication before model work."""
    video, calls = pipeline
    obstacle = tmp_path / "cache-file"
    obstacle.write_text("preserve me")
    assert cli.main([str(video), "--cache-dir", str(obstacle / "child"), "--json"]) == 1
    assert json.loads(capsys.readouterr().out)["status"] == "error"
    assert obstacle.read_text() == "preserve me"
    assert not calls


def test_same_basename_movies_have_distinct_cache_namespaces(
    pipeline: Pipeline, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    """Keep separate media sources from sharing a basename-derived transcript."""
    video, calls = pipeline
    assert cli.main([str(video), "--json"]) == 0
    first = json.loads(capsys.readouterr().out)
    other = tmp_path / "different-media" / video.name
    other.parent.mkdir()
    other.write_bytes(video.read_bytes())
    assert cli.main([str(other), "--json"]) == 0
    second = json.loads(capsys.readouterr().out)
    assert first["transcript"] != second["transcript"]
    assert len(calls) == 2


def test_source_file_change_invalidates_automatic_cache(
    pipeline: Pipeline, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    """Run recognition again when source bytes change at the same media path."""
    video, calls = pipeline
    assert cli.main([str(video), "--json"]) == 0
    first = json.loads(capsys.readouterr().out)
    video.write_bytes(b"a different source movie")
    assert (
        cli.main(
            [str(video), "--output-dir", str(tmp_path / "changed-source"), "--json"]
        )
        == 0
    )
    second = json.loads(capsys.readouterr().out)
    assert first["transcript"] != second["transcript"]
    assert len(calls) == 2


def test_conflicting_explicit_reuse_and_refresh_are_rejected(
    pipeline: Pipeline, capsys: pytest.CaptureFixture[str]
) -> None:
    """Reject ambiguous recovery instructions before reading or generating speech."""
    video, calls = pipeline
    assert (
        cli.main(
            [
                str(video),
                "--reuse-transcript",
                "checkpoint.json",
                "--refresh-transcript",
                "--json",
            ]
        )
        == 1
    )
    assert "cannot be combined" in json.loads(capsys.readouterr().out)["error"]
    assert not calls
