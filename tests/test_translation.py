# ABOUTME: Tests local translation contracts without loading model weights.
# ABOUTME: Ensures translated text cannot silently lose cues, timing, or completion markers.
"""Regression coverage for translation integrity and generation limits."""

import contextlib
import sys
import types
from typing import Any

import pytest

from src.models import Cue, JsonDict
from src.translation import translate_cues


class TokenRow:
    """Represent the generated token tail inspected for translation completion."""

    def __init__(self, token_ids: list[int]) -> None:
        """Store the generated tokens following the decoder start marker."""
        self.token_ids = token_ids

    def __getitem__(self, item: slice) -> "TokenRow":
        """Expose the generated tail while keeping a tensor-like list method."""
        return self

    def tolist(self) -> list[int]:
        """Return generated token identifiers for completion checks."""
        return self.token_ids


class Tokenizer:
    """Provide deterministic tokenization and translation responses."""

    def __init__(self, state: JsonDict) -> None:
        """Share response controls with the test that configures the backend."""
        self.state = state

    def __call__(self, texts: list[str], **kwargs: Any) -> JsonDict:
        """Record source text and return token dimensions without truncation."""
        self.state["batches"].append(texts)
        self.state["truncation"] = kwargs.get("truncation")
        self.state["batch_count"] = len(texts)
        return {
            "input_ids": types.SimpleNamespace(
                shape=(len(texts), self.state["token_count"])
            )
        }

    def batch_decode(self, tokens: list[TokenRow], **kwargs: Any) -> list[str]:
        """Return a configured failure response or one translation per input cue."""
        if self.state["decoded"] is not None:
            return list(self.state["decoded"])
        return ["Hola" for _ in tokens]


@pytest.fixture
def translation_backend(monkeypatch: pytest.MonkeyPatch) -> JsonDict:
    """Install in-memory inference doubles so translation tests need no ML packages."""
    state: JsonDict = {
        "batches": [],
        "batch_count": 0,
        "token_count": 12,
        "token_ids": [5, 0],
        "decoded": None,
        "force_limit": False,
    }
    tokenizer = Tokenizer(state)

    def generate(**kwargs: Any) -> list[TokenRow]:
        """Generate one completed or truncated token row per source cue."""
        if state["force_limit"]:
            token_ids = (
                [5, 0] if kwargs.get("forced_eos_token_id", 0) is not None else [5, 9]
            )
            return [TokenRow(token_ids) for _ in range(state["batch_count"])]
        return [TokenRow(state["token_ids"]) for _ in range(state["batch_count"])]

    model = types.SimpleNamespace(
        config=types.SimpleNamespace(eos_token_id=0, max_position_embeddings=512),
        eval=lambda: None,
        generate=generate,
    )
    monkeypatch.setitem(
        sys.modules,
        "torch",
        types.SimpleNamespace(inference_mode=contextlib.nullcontext),
    )
    monkeypatch.setitem(
        sys.modules,
        "transformers",
        types.SimpleNamespace(
            MarianTokenizer=types.SimpleNamespace(
                from_pretrained=lambda *args, **kwargs: tokenizer
            ),
            MarianMTModel=types.SimpleNamespace(
                from_pretrained=lambda *args, **kwargs: model
            ),
        ),
    )
    return state


def test_translation_preserves_timing_and_order_across_batches(
    translation_backend: JsonDict,
) -> None:
    """Preserve each source interval when translation crosses a batch boundary."""
    cues: list[Cue] = [
        {"start": 1.12, "end": 1.84, "text": "Hello"},
        {"start": 5.51, "end": 6.87, "text": "Goodbye"},
    ]
    translated = translate_cues(cues, batch_size=1)
    assert [(cue["start"], cue["end"]) for cue in translated] == [
        (1.12, 1.84),
        (5.51, 6.87),
    ]
    assert [cue["text"] for cue in cues] == ["Hello", "Goodbye"]
    assert [cue["text"] for cue in translated] == ["Hola", "Hola"]
    assert translation_backend["batches"] == [["Hello"], ["Goodbye"]]
    assert translation_backend["truncation"] is False


@pytest.mark.parametrize("decoded", [[], [""], [" "]])
def test_reject_empty_or_missing_translations(
    translation_backend: JsonDict, decoded: list[str]
) -> None:
    """Fail explicitly if the translator omits or blanks a source cue."""
    translation_backend["decoded"] = decoded
    with pytest.raises(RuntimeError, match="missing or empty"):
        translate_cues([{"start": 0.12, "end": 0.84, "text": "Hello"}])


def test_reject_generation_without_end_token(translation_backend: JsonDict) -> None:
    """Do not publish a translation that stopped at the generation limit."""
    translation_backend["token_ids"] = [5, 9]
    with pytest.raises(RuntimeError, match="token limit"):
        translate_cues([{"start": 0.12, "end": 0.84, "text": "Hello"}])


def test_forced_end_marker_cannot_hide_generation_limit(
    translation_backend: JsonDict,
) -> None:
    """Reject an exhausted decoder even when the model normally forces a final EOS."""
    translation_backend["force_limit"] = True
    with pytest.raises(RuntimeError, match="token limit"):
        translate_cues([{"start": 0.12, "end": 0.84, "text": "Hello"}])


def test_reject_source_too_long_without_truncating(
    translation_backend: JsonDict,
) -> None:
    """Reject an oversized source cue rather than silently translating a prefix."""
    translation_backend["token_count"] = 513
    with pytest.raises(ValueError, match="too long"):
        translate_cues([{"start": 0.12, "end": 0.84, "text": "Hello"}])
