# ABOUTME: Translates aligned English subtitle cues into Spanish locally.
# ABOUTME: Preserves source cue timing and rejects incomplete model output.
"""Optional local translation that keeps English and Spanish cue boundaries identical."""

import sys

from src.constants import (
    TRANSLATION_BATCH_SIZE,
    TRANSLATION_MAX_TOKENS,
    TRANSLATION_MODEL,
    TRANSLATION_MODEL_REVISION,
    TRANSLATION_PROGRESS_BATCHES,
)
from src.models import Cue
from src.subtitles import validate_cues


def translate_cues(
    cues: list[Cue], batch_size: int = TRANSLATION_BATCH_SIZE
) -> list[Cue]:
    """Translate English text into Spanish without changing cue boundaries.

    Parameters
    ----------
    cues : list[Cue]
        Validated English cues on the video playback timeline.
    batch_size : int
        Maximum number of cues processed together by the local Marian model.

    Returns
    -------
    list[Cue]
        Spanish cues with exactly the original start and end values.

    Raises
    ------
    RuntimeError
        If optional dependencies are absent or translation output is incomplete.
    ValueError
        If input cues or the batch size are invalid, or input exceeds model limits.
    """
    validate_cues(cues)
    if batch_size <= 0:
        raise ValueError("Translation batch size must be positive.")
    try:
        import torch
        from transformers import MarianMTModel, MarianTokenizer
    except ImportError as exc:
        raise RuntimeError(
            "Spanish translation requires the standard dependencies: uv sync --locked"
        ) from exc

    tokenizer = MarianTokenizer.from_pretrained(
        TRANSLATION_MODEL, revision=TRANSLATION_MODEL_REVISION
    )
    model = MarianMTModel.from_pretrained(
        TRANSLATION_MODEL, revision=TRANSLATION_MODEL_REVISION
    )
    model.eval()
    translated: list[Cue] = []
    max_tokens = min(TRANSLATION_MAX_TOKENS, model.config.max_position_embeddings - 1)
    for offset in range(0, len(cues), batch_size):
        batch = cues[offset : offset + batch_size]
        inputs = tokenizer(
            [cue["text"] for cue in batch],
            return_tensors="pt",
            padding=True,
            truncation=False,
        )
        if inputs["input_ids"].shape[1] > model.config.max_position_embeddings:
            raise ValueError(
                "A cue is too long for translation; use shorter source cues."
            )
        with torch.inference_mode():
            tokens = model.generate(
                **inputs, max_new_tokens=max_tokens, forced_eos_token_id=None
            )
        for row in tokens:
            if model.config.eos_token_id not in row[1:].tolist():
                raise RuntimeError(
                    "Translation reached its token limit without completing a cue."
                )
        texts = tokenizer.batch_decode(tokens, skip_special_tokens=True)
        if len(texts) != len(batch) or any(not text.strip() for text in texts):
            raise RuntimeError("Translation returned missing or empty cues.")
        for cue, text in zip(batch, texts):
            translated.append(
                {"start": cue["start"], "end": cue["end"], "text": text.strip()}
            )
        if (offset // batch_size + 1) % TRANSLATION_PROGRESS_BATCHES == 0:
            print(f"Translated {len(translated)}/{len(cues)} cues...", file=sys.stderr)
    return translated
