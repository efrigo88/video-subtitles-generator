<!-- ABOUTME: Explains the subtitle timing failures and their remedies. -->
<!-- ABOUTME: Separates reproduced software bugs from input-dependent and model limitations. -->
# Synchronization analysis

## Confirmed timestamp precision bug

In the original implementation at commit `e833205`, `src/helpers.py:18` constructed a `timedelta`, discarded its fractional part, and appended `,000`. Reproducing the formatter without loading Whisper gave:

```text
12.980   -> 00:00:12,000
12.990   -> 00:00:12,000
0.120    -> 00:00:00,000
0.840    -> 00:00:00,000
3661.234 -> 01:01:01,000
```

Every nonintegral boundary was moved early by up to almost one second. A cue from `0.120` to `0.840` became a zero-duration cue. This damages synchronization even when Whisper's own timing is correct. The error is bounded at each boundary; it does **not** accumulate through the movie and cannot by itself explain a steadily increasing offset of many seconds.

The formatter now rounds to integer milliseconds and decomposes hours, minutes, seconds, and milliseconds arithmetically. Tests cover subsecond cues, minute carry, hour carry, invalid numbers, and long durations. Output validation refuses nonpositive intervals at millisecond precision.

## Alignment and cue boundaries

The original `model.transcribe` call supplied the language but did not request word timestamps. Its writer copied each model segment directly into a cue. These are estimated segment intervals and can span pauses or show too much dialogue at once.

The pipeline now requests word timestamps, builds cues from those words, and splits at actual word boundaries using duration, text-length, and pause limits. It leaves long pauses between cues rather than assigning text evenly across a segment. Missing word alignment is reported rather than described as precise alignment. This is Whisper's cross-attention/dynamic-time-warping alignment, not an independent phoneme aligner. See the [pinned Whisper transcription implementation](https://github.com/openai/whisper/blob/v20250625/whisper/transcribe.py).

Whisper's previous-text conditioning can propagate repetition and timing failure loops. The local defaults now disable it, retain a CLI option for continuity-sensitive material, and enable Whisper's word-based hallucination/silence safeguard. These measures reduce failure risk; they do not establish that every movie scene is transcribed correctly.

## Audio timeline and track selection

The original FFmpeg invocation used automatic audio selection and converted to WAV without preserving the container's common playback origin. WAV samples begin at their own zero. For files whose audio starts after video playback begins, independently rebasing audio loses that delay and makes all subtitles early. Audio timestamp discontinuities can cause a similar mismatch later in a file.

The extraction stage now selects an explicit audio stream and preserves the common origin with `-copyts -start_at_zero`; its resampler pads/trims to the origin and accounts for internal timestamp gaps. FFprobe metadata is available through `--list-audio`, and the selected absolute stream index is saved in the report.

Synthetic FFmpeg integration tests cover a 1.25-second audio delay with zero, positive, and negative container origins, plus an internal audio timestamp gap. Playback-end validation uses stream presentation endpoints or a bounded tail-packet probe because Matroska and MP4 differ in how container duration relates to a nonzero origin. An inconclusive probe produces an explicit warning instead of an incorrect bound. These are real media tests, not mocks of the extraction command. The provided movie's single 5.1 track starts at zero, so a delayed-track offset is not established as the cause for that specific file.

Converting to mono 16 kHz is appropriate for Whisper and does not inherently speed up or slow down playback. There is no frame-rate conversion in this pipeline. A global shift should only be applied after measuring a real constant offset; changing frame rates or adding an arbitrary offset would hide the evidence.

## Bilingual generation and reliable operation

The original language argument means the language spoken in the recording. Setting it to `es` for an English movie does not ask Whisper to translate to Spanish. The original output path also had no language suffix and could replace the previous track.

For English audio, English and Spanish are now the default outputs: speech is transcribed once, and Spanish is translated from the resulting English cues using a local English-to-Spanish model. Both SRTs keep identical cue boundaries and have distinct language suffixes. Translation does not need a second speech-recognition pass and cannot introduce an independent set of estimated speech timestamps.

The unattended workflow also addresses collisions and retry behavior: argument parsing has real help, outputs refuse replacement by default, temporary WAVs cannot collide with user audio, failures clean up temporary media, completed inference is checkpointed, and JSON results expose output paths and warnings. Docker has been removed in favor of the documented local `uv` workflow.

## Validation limits

Unit and synthetic-media tests establish timestamp arithmetic, cue ordering and duration, timeline preservation, track selection, translation timing invariants, cleanup, collision handling, and checkpoint identity. A real-model smoke run also exercised Whisper word timing and local Spanish translation on this machine. A full-length movie run produced matching English/Spanish cue counts and identical timing lines; the quality report still flagged difficult alignment/readability cases.

They cannot establish perfect audiovisual sync for every scene. Music, overlapping dialogue, whispered speech, silence hallucinations, names, and translations that read too quickly still need review. Inspect the report's warnings and sample dialogue across the movie before calling the subtitles ready for viewing.

If residual alignment errors remain on difficult scenes, compare a separate phoneme-alignment stage such as [WhisperX](https://github.com/m-bain/whisperX) against the current word alignment using the same audio. That would add language-specific models and dependencies. It is an escalation for measured residual errors, not a substitute for correcting the precision and extraction defects above.
