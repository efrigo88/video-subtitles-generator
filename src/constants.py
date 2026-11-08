# ABOUTME: Collects the subtitle generator's configuration and supported values.
# ABOUTME: Gives inference, formatting, and CLI stages one source of defaults.
"""Shared configuration for media extraction and subtitle generation."""

import errno
from typing import Final

from platformdirs import user_cache_path

LANGUAGE_DESCRIPTION: Final[dict[str, str]] = {
    "en": "English",
    "es": "Spanish",
    "fr": "French",
    "de": "German",
    "it": "Italian",
    "pt": "Portuguese",
    "ru": "Russian",
    "zh": "Chinese",
}
LANGUAGE_TAGS: Final[dict[str, set[str]]] = {
    "en": {"en", "eng"},
    "es": {"es", "spa"},
    "fr": {"fr", "fra", "fre"},
    "de": {"de", "deu", "ger"},
    "it": {"it", "ita"},
    "pt": {"pt", "por"},
    "ru": {"ru", "rus"},
    "zh": {"zh", "zho", "chi"},
}
DEFAULT_SOURCE_LANGUAGE: Final = "en"
DEFAULT_SUBTITLE_LANGUAGES: Final = ("en", "es")
DEFAULT_MODEL: Final = "medium"
DEFAULT_DEVICE: Final = "cpu"
DEFAULT_CACHE_DIRECTORY: Final = user_cache_path("video-subtitle-generator")
CACHE_TRANSCRIPT_NAME: Final = "transcript.json"
CACHE_REPORT_NAME: Final = "report.json"
CONDITION_ON_PREVIOUS_TEXT: Final = False
SUPPORTED_FORMATS: Final = (".mp4", ".mkv")
SUPPORTED_MODELS: Final = (
    "tiny",
    "base",
    "small",
    "medium",
    "large",
    "large-v3",
    "turbo",
)
SUPPORTED_DEVICES: Final = ("cpu", "cuda", "mlx")
MLX_MODEL_REPOSITORIES: Final = {
    "tiny": "mlx-community/whisper-tiny-mlx",
    "base": "mlx-community/whisper-base-mlx",
    "small": "mlx-community/whisper-small-mlx",
    "medium": "mlx-community/whisper-medium-mlx",
    "large": "mlx-community/whisper-large-v3-mlx",
    "large-v3": "mlx-community/whisper-large-v3-mlx",
    "turbo": "mlx-community/whisper-turbo",
}
TRANSLATION_PAIR: Final = ("en", "es")
TRANSLATION_MODEL: Final = "Helsinki-NLP/opus-mt-en-es"
TRANSLATION_MODEL_REVISION: Final = "5bc4493d463cf000c1f0b50f8d56886a392ed4ab"
TRANSLATION_BATCH_SIZE: Final = 8
TRANSLATION_MAX_TOKENS: Final = 512
TRANSLATION_PROGRESS_BATCHES: Final = 25
AUDIO_SAMPLE_RATE: Final = 16000
AUDIO_CHANNELS: Final = 1
AUDIO_CODEC: Final = "pcm_s16le"
TEMP_DIRECTORY_PREFIX: Final = "video-subtitles-"
TEMP_AUDIO_NAME: Final = "audio.wav"
PREFLIGHT_DIRECTORY_PREFIX: Final = ".subtitle-preflight-"
ATOMIC_TEMP_PREFIX: Final = ".subtitle-output-"
OUTPUT_FILE_PERMISSIONS: Final = 0o600
HARD_LINK_UNSUPPORTED_ERRORS: Final = frozenset(
    {errno.EOPNOTSUPP, errno.ENOTSUP, errno.ENOSYS, errno.EXDEV, errno.EPERM}
)
HALLUCINATION_SILENCE_SECONDS: Final = 2.0
MAX_CUE_DURATION: Final = 6.0
MAX_CUE_CHARACTERS: Final = 84
MAX_WORD_GAP: Final = 0.8
SRT_LINE_WIDTH: Final = 42
MAX_SRT_LINES: Final = 2
TIMESTAMP_DECIMAL_PLACES: Final = 3
SRT_SUFFIX: Final = ".srt"
READING_SPEED_WARNING: Final = 25
LONG_CUE_WARNING_SECONDS: Final = 7.0
MEDIA_DURATION_TOLERANCE: Final = 0.1
MEDIA_DURATION_TAIL_SECONDS: Final = 30.0
MEDIA_DURATION_MAX_PACKETS: Final = 4096
MILLISECONDS_PER_SECOND: Final = 1000
SECONDS_PER_MINUTE: Final = 60
MINUTES_PER_HOUR: Final = 60
TRANSCRIPT_SCHEMA_VERSION: Final = 1
TIMELINE_DESCRIPTION: Final = "container playback origin, preserved during extraction"
