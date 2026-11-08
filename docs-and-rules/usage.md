<!-- ABOUTME: Documents subtitle generation, audio selection, and recovery. -->
<!-- ABOUTME: Keeps operational details separate from the repository landing page. -->
# Usage

Run commands from the repository root with `uv run --no-sync python -m src.main`. Use `--help` for the current option list. `uv sync --locked` installs transcription, Spanish translation, and development tools; add `--extra apple` for Apple Silicon acceleration. A later plain `uv sync` can remove optional packages, so retain the extras when syncing again.

## Audio and languages

Inspect the available audio tracks before processing a movie:

```bash
uv run --no-sync python -m src.main "/path/to/movie.mkv" --list-audio --json
```

`--audio-stream` accepts the absolute stream index reported by FFprobe, including video streams in the numbering. Without this option, selection prefers matching language tags and then the default track. Tags can be missing or wrong; inspect the track title and confirm the chosen audio if several tracks match. A commentary track may need an explicit override.

`--source-language` defaults to `en`. Supported source codes are `en`, `es`, `fr`, `de`, `it`, `pt`, `ru`, and `zh`. The positional source form (`movie.mp4 es`) remains accepted. It specifies Spanish **audio**, not Spanish translation.

`--subtitle-languages` defaults to **English and Spanish** for English audio, sharing one transcription. For other supported source languages, it defaults to the source language only. Same-language transcription works for every supported source code. Cross-language generation currently supports **English to Spanish** only. The default `--source-language en` run transcribes once and translates those cues. Use `--subtitle-languages en` for English only or `--subtitle-languages es` for Spanish only. This avoids transcribing English speech as if it were Spanish. Unsupported translation pairs fail before inference.

Spanish translation uses the local [Helsinki-NLP/opus-mt-en-es](https://huggingface.co/Helsinki-NLP/opus-mt-en-es) model. Each cue retains its English start and end; translated text can be longer and should be reviewed for reading speed, names, idioms, and dialogue context. Translations are machine-generated and do not add accessibility annotations such as sound effects.

## Outputs and unattended execution

SRT files use the video stem and language code. The movie folder receives exactly `movie.en.srt` and `movie.es.srt` by default. The default destination is always the resolved input video’s parent directory, wherever the movie lives. `--output-dir "/path/to/output"` explicitly changes the SRT destination. Transcription checkpoints and quality reports are stored separately in the platform’s application cache, under a source/settings fingerprint; `--cache-dir` can select another cache root outside the movie/output folder. The final JSON result lists the transcript/report cache paths, selected stream, model, cue count, and quality warnings.

`--json` reserves stdout for one final JSON object; progress and model download messages use stderr. Exit status is zero on success and nonzero on failure. An error result includes any completed files, so a failed translation does not hide a completed English track or transcript.

SRT files and internal cache artifacts are published individually. Publication is atomic when the filesystem supports hard links or authorized replacement. On filesystems such as exFAT, exclusive creation preserves no-clobber behavior; handled write failures remove the partially written file. A process kill or power loss during that fallback can leave a partial file, so inspect an interrupted output before explicitly replacing it. The run does not form a transaction across all tracks: if a later stage fails, earlier completed artifacts remain. Existing outputs are refused before expensive inference unless `--overwrite` is provided. No command waits for input. The extracted WAV lives in a unique temporary directory and is cleaned up after success or failure; an unrelated WAV next to the video is never used or deleted.

## Models and devices

The default Whisper model is `medium`. Available model options are `tiny`, `base`, `small`, `medium`, `large`, `large-v3`, and `turbo`. Model size affects transcription quality, speed, and memory, but cannot replace timestamp preservation or fix an incorrect audio track.

`--device cpu` is portable and uses FP32. `--device cuda` uses the PyTorch CUDA backend when available. On an Apple Silicon Mac, install the `apple` extra and use `--device mlx`; this uses converted Whisper weights with the same word-timing workflow. MPS is not used by the PyTorch backend. GPU availability is not inferred from the language model running the agent.

Whisper and translation weights download to the libraries' user caches. Later runs can reuse them. Video/audio processing stays local. Initial setup and uncached models require network access and free disk space; a full movie can take substantial time. Allow the process to finish rather than treating silent computation as failure.

Whisper context across windows is disabled by default to reduce repetitive decoding and timing failure loops. `--condition-on-previous-text` enables it when continuity is more useful; compare difficult sections before choosing that mode for a movie.

## Reuse a transcription

Raw inference is saved in the application cache before cue formatting or translation. Matching cached transcription is reused automatically, so retrying a translation or writing subtitles into another directory does not run Whisper again. `--refresh-transcript` requests fresh inference when needed. Cached identity includes the resolved video path, size, modification time, spoken language, selected audio stream, model, and decoding settings.

If Spanish translation fails after English output completed, retry only Spanish:

```bash
uv run --no-sync python -m src.main "/path/to/movie.mp4" \
  --source-language en --subtitle-languages es --json
```

An explicit `--reuse-transcript "/path/from-the-json-result/transcript.json"` also remains available. It must match the video’s source identity, language, stream, model, and previous-text decoding setting. Keep the original `--model` and `--condition-on-previous-text` options when retrying or explicitly reusing a transcript. Do not edit provenance to make an unrelated transcript appear valid. Renaming, moving, or modifying the input changes its identity.

Existing SRT files still require `--overwrite`, even when inference is cached. Internal fingerprinted cache files are maintained by the application; they are not additional movie-folder outputs. Keep the cache if you want to reuse compute. Model weight caches are managed separately by the inference libraries.

## Verify the result

Check that every requested output exists and is nonempty, the JSON status is `ok`, and there are no unresolved timing errors. English and Spanish tracks should have the same cue count and identical timestamp lines. Generated timestamps retain milliseconds; positive duration and ordering are validated. Media bounds are checked when stream endpoints or a bounded tail probe establish a reliable playback endpoint; otherwise the report explicitly warns that endpoint validation was skipped.

Read the report's quality warnings. Reading-speed warnings need editorial review, especially after translation. Programmatic validity cannot establish perceptual sync: inspect dialogue near the beginning, middle, and end, and around long silences or music. Automatic speech recognition can still miss words or hallucinate speech in difficult scenes. See [the timing analysis](synchronization.md) for the distinction between corrected software bugs and model limitations.
