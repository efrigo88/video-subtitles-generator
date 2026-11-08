<!-- ABOUTME: Introduces the local subtitle generator and its supported workflow. -->
<!-- ABOUTME: Links setup, validation, and operating details for humans and AI agents. -->
# Video Subtitles Generator

Generate aligned SRT subtitles from MP4 or MKV videos using local Whisper inference. English audio produces both English captions and Spanish translations by default, with matching cue timings from one transcription. No API key is required; model weights download on first use.

## Setup

Requires Python 3.9–3.12, [uv](https://docs.astral.sh/uv/), and FFmpeg (`ffmpeg` and `ffprobe` on `PATH`). On macOS, install FFmpeg with `brew install ffmpeg`.

```bash
uv sync --locked
```

On Apple Silicon, add `--extra apple` to that command to enable MLX acceleration. Docker is not part of the supported workflow.

## Generate subtitles

Run from the repository root. For an English-language movie:

```bash
uv run --no-sync python -m src.main "/path/to/movie.mp4" \
  --source-language en --json
```

The default run writes both English and Spanish subtitles, transcribing the audio once. Use `--subtitle-languages en` to generate English only.

Add `--device mlx` on Apple Silicon after installing the `apple` extra. The default device is CPU. The source-language argument describes the spoken audio; Spanish output is produced by translating the aligned English captions.

Outputs are `movie.en.srt`, `movie.es.srt`, a reusable `movie.en.transcript.json`, and `movie.subtitles.json`, beside the video. Existing output files require an explicit `--overwrite`. Model inference runs locally; the original video is left intact.

## Development

Install both Git hooks after setup, and repeat this for every fresh clone:

```bash
uv run --no-sync pre-commit install --install-hooks --hook-type pre-commit --hook-type pre-push
uv run --no-sync pre-commit run --all-files
uv run --no-sync pre-commit run --all-files --hook-stage pre-push
```

The commit hook checks formatting, documented and annotated Python APIs, strict typing, `ABOUTME` headers, file hygiene, Markdown/YAML, and security rules. The push hook also runs the regression suite. Git hooks live in the local checkout and are not installed by cloning. CI repeats the quality checks and runs tests on every supported Python version without downloading inference models.

For a direct regression run, use `uv run --no-sync python -m pytest -q`. Hook commands use the existing environment so optional MLX packages remain installed.

## Documentation

- [AI operating instructions](AGENTS.md): generation workflow, result verification, and repository conventions.
- [Usage](docs-and-rules/usage.md): audio selection, language support, model/device choices, and recovery.
- [Synchronization analysis](docs-and-rules/synchronization.md): identified timing failures, fixes, and validation limits.
- [Code style](docs-and-rules/code-style.md): documentation, typing, constants, and source conventions.
- [Workflow](docs-and-rules/workflow.md): branches, installed hooks, CI, and draft PRs.
- [Data safety](docs-and-rules/data-safety.md): local processing, file preservation, and recovery.
- [Code review](docs-and-rules/code-review.md): review scope, evidence, and agent coordination.

See [LICENSE](LICENSE) for licensing.
