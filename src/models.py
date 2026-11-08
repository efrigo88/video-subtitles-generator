# ABOUTME: Defines shared subtitle data types for the generation pipeline.
# ABOUTME: Keeps cue timing and text contracts explicit across transcription and translation.
"""Data contracts shared by subtitle processing stages."""

from typing import Any, TypedDict

JsonDict = dict[str, Any]


class Cue(TypedDict):
    """A subtitle interval expressed in seconds on the video playback timeline.

    Attributes
    ----------
    start : float
        Inclusive start time in seconds.
    end : float
        Exclusive end time in seconds, greater than ``start``.
    text : str
        Subtitle text without SRT numbering or timing syntax.
    """

    start: float
    end: float
    text: str
