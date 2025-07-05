# Video Subtitles Generator

A Python tool for automatically generating SRT subtitle files from video files using OpenAI's Whisper speech recognition model.

## Features

- 🎬 **Video Support**: Works with MP4 and MKV video files
- 🎵 **Audio Extraction**: Automatically extracts and converts audio to optimal format for transcription
- 🗣️ **Speech Recognition**: Uses OpenAI's Whisper model for accurate speech-to-text conversion
- 📝 **SRT Format**: Generates properly formatted SRT subtitle files
- 🚀 **Performance**: Optimized for speed with minimal verbose output
- 🍎 **macOS Optimized**: Works great on Apple Silicon Macs (with CPU fallback for compatibility)

## Requirements

- Python 3.9-3.12
- ffmpeg (for audio extraction)
- OpenAI Whisper model

## Installation

### Option 1: Docker (Recommended for Easy Setup)

The easiest way to run this application is using Docker, which handles all dependencies automatically.

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd video-subtitles-generator
   ```

2. **Run with Docker**:
   ```bash
   # Quick start with convenience script
   ./scripts/docker-run.sh video.mp4
   
   # For different languages
   ./scripts/docker-run.sh video.mp4 es  # Spanish
   ./scripts/docker-run.sh video.mp4 fr  # French
   ```

The script will automatically:
- Check if Docker and Docker Compose are installed
- Build the Docker image if needed
- Copy your video to the working directory
- Run the subtitle generation
- Copy the SRT file back to your original video location
- Clean up temporary files

### Option 2: Local Installation

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd video-subtitles-generator
   ```

2. **Install dependencies** (using uv):
   ```bash
   uv sync
   ```

3. **Install ffmpeg** (if not already installed):
   ```bash
   # macOS (using Homebrew)
   brew install ffmpeg
   
   # Ubuntu/Debian
   sudo apt update && sudo apt install ffmpeg
   
   # Windows (using Chocolatey)
   choco install ffmpeg
   ```

## Usage

### Basic Usage

```bash
python -m src.main "/path/to/your/video.mp4"
```

### Language-Specific Usage

```bash
# English (default)
python -m src.main "/path/to/your/video.mp4"

# Spanish
python -m src.main "/path/to/your/video.mp4" es

# French
python -m src.main "/path/to/your/video.mp4" fr

# German
python -m src.main "/path/to/your/video.mp4" de

# Italian
python -m src.main "/path/to/your/video.mp4" it

# Portuguese
python -m src.main "/path/to/your/video.mp4" pt

# Russian
python -m src.main "/path/to/your/video.mp4" ru

# Chinese
python -m src.main "/path/to/your/video.mp4" zh
```

### Example

```bash
python -m src.main "/Volumes/SANDISK256/movies/MyMovie.mp4"
```

This will:
1. Extract audio from the video file
2. Transcribe the audio using Whisper
3. Generate a `.srt` subtitle file in the same directory
4. Clean up temporary audio files

### Output

The script generates an SRT file with the same name as your video file:
- Input: `MyMovie.mp4`
- Output: `MyMovie.srt`

## Configuration

### Language Support

Currently supported languages:
- `en` - English (default)
- `es` - Spanish
- `fr` - French
- `de` - German
- `it` - Italian
- `pt` - Portuguese
- `ru` - Russian
- `zh` - Chinese

Note: While Whisper supports many more languages, these are the ones currently configured in this project. For a complete list of Whisper's supported languages, see [Whisper's supported languages](https://github.com/openai/whisper/blob/main/whisper/tokenizer.py).

### Model Size

You can change the Whisper model size in `src/main.py`:

```python
segments = transcribe_audio(audio_path, model_size="medium")  # Options: tiny, base, small, medium, large
```

**Model Size Comparison**:
- `tiny`: Fastest, least accurate (~39MB)
- `base`: Good balance (~74MB)
- `small`: Better accuracy (~244MB)
- `medium`: High accuracy (~769MB) - **Default**
- `large`: Best accuracy (~1550MB)

### Supported Video Formats

- MP4 (`.mp4`)
- MKV (`.mkv`)

## Project Structure

```
video-subtitles-generator/
├── src/
│   ├── __init__.py
│   ├── main.py          # Main script entry point
│   ├── helpers.py       # Helper functions for audio extraction and transcription
│   └── constants.py     # Language constants
├── scripts/
│   └── docker-run.sh    # Docker convenience script
├── videos/              # Mounted volume for Docker (created automatically)
├── Dockerfile           # Docker configuration
├── docker-compose.yml   # Docker Compose configuration
├── .dockerignore        # Docker ignore file
├── pyproject.toml       # Project dependencies and configuration
├── uv.lock             # Locked dependency versions
└── README.md           # This file
```

## How It Works

1. **Audio Extraction**: Uses ffmpeg to extract mono 16kHz WAV audio from the video
2. **Speech Recognition**: Loads the Whisper model and transcribes the audio
3. **SRT Generation**: Converts transcription segments to SRT format with proper timestamps
4. **Cleanup**: Removes temporary audio files

## Troubleshooting

### MPS/GPU Issues

If you encounter MPS (Metal Performance Shaders) errors on macOS, the script automatically falls back to CPU processing. This is slower but more reliable.

### Memory Issues

For very long videos, consider using a smaller model size:
```python
segments = transcribe_audio(audio_path, model_size="base")
```

### ffmpeg Not Found

Make sure ffmpeg is installed and available in your PATH:
```bash
ffmpeg -version
```

## Performance Tips

- **Shorter videos**: Use `medium` or `large` models for better accuracy
- **Longer videos**: Use `base` or `small` models for faster processing
- **Batch processing**: Process multiple videos in sequence
- **SSD storage**: Use fast storage for better I/O performance

## License

This project is open source. See the LICENSE file for details.

### Troubleshooting

- **"Docker is not installed"**: Install Docker Desktop or Docker Engine
- **"Docker is not running"**: Start Docker Desktop or Docker service
- **"Permission denied"**: Run `chmod +x scripts/docker-run.sh`
- **"No space left"**: Run `docker system prune -a` to clean up

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
