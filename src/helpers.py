"""
Video Subtitles Generator - A tool for generating SRT subtitles
from video files.

This module provides helper functions for:
- Extract audio from video files
- Transcribe speech to text using OpenAI's Whisper model
- Generate properly formatted SRT subtitle files
"""
import subprocess
from datetime import timedelta
from pathlib import Path

import whisper


def format_timestamp(seconds: float) -> str:
    """Formats seconds into SRT timestamp."""
    td = timedelta(seconds=seconds)
    hours_mins_secs = str(td).split(".", maxsplit=1)[0].zfill(8)
    return hours_mins_secs.replace(".", ",") + ",000"


def extract_audio(video_path: Path, audio_path: Path) -> None:
    """Extracts mono 16kHz WAV audio using ffmpeg."""
    command = [
        "ffmpeg",
        "-i",
        str(video_path),
        "-vn",  # no video
        "-acodec",
        "pcm_s16le",  # uncompressed PCM
        "-ar",
        "16000",  # 16 kHz
        "-ac",
        "1",  # mono
        "-loglevel", "error",  # only show errors
        str(audio_path),
    ]
    subprocess.run(command, check=True, capture_output=True)


def transcribe_audio(
        audio_path: Path,
        model_size="base",
        language="en",
        ) -> list:
    """Transcribes the audio using Whisper + Metal (MPS) if available."""
    # Force CPU usage to avoid MPS compatibility issues
    device = "cpu"
    print(f"Loading {model_size} model...")
    model = whisper.load_model(model_size, device=device)
    print(f"Transcribing audio in {language} "
          f"(this may take a while)...")
    result = model.transcribe(
        str(audio_path),
        language=language,
        verbose=False,
    )
    return result["segments"]


def write_srt(segments: list, output_path: Path) -> None:
    """Writes transcribed segments to an SRT file."""
    with open(output_path, "w", encoding="utf-8") as f:
        for i, segment in enumerate(segments):
            start = format_timestamp(segment["start"])
            end = format_timestamp(segment["end"])
            text = segment["text"].strip()
            f.write(f"{i + 1}\n{start} --> {end}\n{text}\n\n")
