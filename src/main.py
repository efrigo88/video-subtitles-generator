"""
Video Subtitles Generator - A tool for generating SRT subtitles from
video files.
"""

import sys
from pathlib import Path

from .constants import LANGUAGE_DESCRIPTION
from .helpers import extract_audio, transcribe_audio, write_srt


def main():
    """Main function to execute the subtitle generation process."""
    if len(sys.argv) < 2:
        print("Usage: python -m src.main <video_file> [language]")
        print("Language codes:")
        for code, description in LANGUAGE_DESCRIPTION.items():
            print(f"  {code}: {description}")
        print("Example: python -m src.main video.mp4 es")
        sys.exit(1)

    video_path = Path(sys.argv[1])

    # Debug information
    print(f"Checking file: {video_path}")
    print(f"File exists: {video_path.exists()}")
    print(f"File suffix: {video_path.suffix.lower()}")

    if not video_path.exists():
        print(f"Error: File does not exist: {video_path}")
        sys.exit(1)

    if video_path.suffix.lower() not in [".mp4", ".mkv"]:
        print(f"Error: Unsupported file format: {video_path.suffix}")
        print("Supported formats: .mp4, .mkv")
        sys.exit(1)

    # Get language from command line argument (default to English)
    language = sys.argv[2] if len(sys.argv) > 2 else "en"

    if language not in LANGUAGE_DESCRIPTION:
        print(f"Error: Unsupported language: {language}")
        print("Supported languages:")
        for code, description in LANGUAGE_DESCRIPTION.items():
            print(f"  {code}: {description}")
        sys.exit(1)

    audio_path = video_path.with_suffix(".wav")
    srt_path = video_path.with_suffix(".srt")

    print(f"[1/4] Extracting audio from {video_path.name}...")
    extract_audio(video_path, audio_path)

    print("[2/4] Loading Whisper model...")
    segments = transcribe_audio(
        audio_path, model_size="medium", language=language
    )  # base, small, medium, large

    print(f"[3/4] Writing subtitles to {srt_path.name}...")
    write_srt(segments, srt_path)

    print(f"[4/4] Done! Subtitles saved to {srt_path}")
    audio_path.unlink()  # optional: delete temp audio


if __name__ == "__main__":
    main()
