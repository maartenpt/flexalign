"""Optional flexipipe-based segmentation (``Document.from_plain_text``)."""

from __future__ import annotations


def flexipipe_available() -> bool:
    try:
        import flexipipe.doc  # noqa: F401

        return True
    except ImportError:
        return False


def plain_to_sentences_and_tokens_flexipipe(text: str, *, level: str) -> tuple[list[str], list[list[str]] | None]:
    """
    Use flexipipe's unicode sentence + token segmentation.

    Requires ``flexipipe`` installed in the same environment.
    """
    from flexipipe.doc import Document

    doc = Document.from_plain_text(
        text,
        doc_id="plain",
        tokenize=True,
        segment=True,
    )
    sents: list[str] = []
    token_rows: list[list[str]] = []
    for sent in doc.sentences:
        t = (sent.text or "").strip()
        if not t and sent.tokens:
            t = " ".join(tok.form for tok in sent.tokens).strip()
        if not t:
            continue
        sents.append(t)
        token_rows.append([(tok.form or "").strip() for tok in sent.tokens if (tok.form or "").strip()])
    if level != "tok":
        return sents, None
    return sents, token_rows
