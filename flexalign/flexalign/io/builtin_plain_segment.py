"""Lightweight sentence / token segmentation for plain text (no external NLP)."""

from __future__ import annotations

import re

# Rough sentence boundaries (paragraph + punctuation).
_SENT_SPLIT = re.compile(r"(?<=[.!?؟।])\s+|\n\s*\n+")


def segment_sentences_builtin(text: str) -> list[str]:
    """Split plain text into sentence-like chunks."""
    text = (text or "").strip()
    if not text:
        return []
    parts: list[str] = []
    for block in re.split(r"\n\s*\n+", text):
        block = block.strip()
        if not block:
            continue
        for piece in _SENT_SPLIT.split(block):
            p = piece.strip()
            if p:
                parts.append(p)
    if not parts:
        return [text] if text else []
    return parts


def tokenize_sentence_builtin(sentence: str) -> list[str]:
    """Whitespace tokenization (preserves tokens as alignable units)."""
    return [t for t in sentence.split() if t]


def plain_to_sentences_and_tokens(text: str, *, level: str) -> tuple[list[str], list[list[str]] | None]:
    """
    Return (sentence_texts, token_rows or None).

    If level is ``tok``, ``token_rows`` is one token list per sentence; otherwise ``None``.
    """
    sents = segment_sentences_builtin(text)
    if level == "tok":
        return sents, [tokenize_sentence_builtin(s) for s in sents]
    return sents, None
