"""Segmentation projection from pivot to target."""

from __future__ import annotations

from pathlib import Path
import re
import subprocess
import tempfile
import sys

from lxml import etree


def _split_sentences(text: str, count_hint: int | None = None) -> list[str]:
    cleaned = " ".join(text.split()).strip()
    if not cleaned:
        return []
    if count_hint and count_hint > 1:
        tokens = cleaned.split()
        chunk = max(1, len(tokens) // count_hint)
        pieces: list[str] = []
        for index in range(count_hint):
            start = index * chunk
            end = len(tokens) if index == count_hint - 1 else min(len(tokens), (index + 1) * chunk)
            if start < len(tokens):
                pieces.append(" ".join(tokens[start:end]).strip())
        return [piece for piece in pieces if piece]
    parts = [part.strip() for part in re.split(r"(?<=[.!?])\s+", cleaned) if part.strip()]
    return parts or [cleaned]


def _tokenize(text: str) -> list[str]:
    return re.findall(r"\w+|[^\w\s]", text, flags=re.UNICODE)


def _tokenize_with_flexipipe(text: str, language: str | None = None) -> list[str]:
    """Tokenize text via flexipipe CoNLL-U output.

    Falls back to regex tokenization if flexipipe is not available or fails.
    """
    cleaned = " ".join(text.split()).strip()
    if not cleaned:
        return []
    with tempfile.NamedTemporaryFile("w", suffix=".txt", encoding="utf-8", delete=False) as handle:
        handle.write(cleaned)
        input_path = handle.name
    cmd = [sys.executable, "-m", "flexipipe", "process", "--input", input_path, "--output-format", "conllu"]
    if language:
        cmd.extend(["--language", language])
    try:
        run = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if run.returncode != 0:
            return _tokenize(cleaned)
        tokens: list[str] = []
        for line in run.stdout.splitlines():
            if not line or line.startswith("#"):
                continue
            cols = line.split("\t")
            if len(cols) < 2:
                continue
            token_id = cols[0]
            if "-" in token_id or "." in token_id:
                continue
            if token_id.isdigit():
                tokens.append(cols[1])
        return tokens or _tokenize(cleaned)
    except Exception:
        return _tokenize(cleaned)
    finally:
        try:
            Path(input_path).unlink(missing_ok=True)
        except Exception:
            pass


def _parent_units(tree: etree._ElementTree) -> list[etree._Element]:
    root = tree.getroot()
    return list(root.xpath(".//*[local-name()='ab' and @tuid]"))


def _remove_children(element: etree._Element) -> None:
    element.text = None
    for child in list(element):
        element.remove(child)


def _write_sentence_structure(parent: etree._Element, parent_tuid: str, sentences: list[str], with_tokens: bool = False) -> None:
    _remove_children(parent)
    for index, sentence_text in enumerate(sentences, start=1):
        s_node = etree.SubElement(parent, "s")
        s_tuid = f"{parent_tuid}:s{index}"
        s_node.set("tuid", s_tuid)
        if with_tokens:
            tokens = _tokenize(sentence_text)
            for token_index, token in enumerate(tokens, start=1):
                tok_node = etree.SubElement(s_node, "tok")
                tok_node.set("tuid", f"{s_tuid}:w{token_index}")
                tok_node.text = token
                if token_index < len(tokens):
                    tok_node.tail = " "
            if index < len(sentences):
                s_node.tail = " "
        else:
            s_node.text = sentence_text
            if index < len(sentences):
                s_node.tail = " "


def project_sentences_from_pivot(pivot_path: str, target_path: str, output_path: str | None = None) -> None:
    parser = etree.XMLParser(remove_blank_text=False, recover=True)
    pivot_tree = etree.parse(str(Path(pivot_path)), parser)
    target_source = Path(target_path)
    target_tree = etree.parse(str(target_source), parser)
    pivot_units = _parent_units(pivot_tree)
    target_units = _parent_units(target_tree)
    count = min(len(pivot_units), len(target_units))
    for index in range(count):
        pivot_parent = pivot_units[index]
        target_parent = target_units[index]
        parent_tuid = target_parent.get("tuid") or pivot_parent.get("tuid")
        if not parent_tuid:
            continue
        pivot_sentences = list(pivot_parent.xpath("./*[local-name()='s']"))
        if pivot_sentences:
            sentence_texts = [" ".join(node.itertext()).strip() for node in pivot_sentences]
        else:
            sentence_texts = _split_sentences(" ".join(pivot_parent.itertext()).strip())
        target_text = " ".join(target_parent.itertext()).strip()
        projected = _split_sentences(target_text, count_hint=len(sentence_texts) if sentence_texts else None)
        if not projected and sentence_texts:
            projected = ["" for _ in sentence_texts]
        _write_sentence_structure(target_parent, parent_tuid, projected or sentence_texts, with_tokens=False)
    destination = Path(output_path) if output_path else target_source
    destination.write_bytes(etree.tostring(target_tree, pretty_print=True, xml_declaration=True, encoding="utf-8"))


def project_tokens_from_pivot(pivot_path: str, target_path: str, output_path: str | None = None) -> None:
    parser = etree.XMLParser(remove_blank_text=False, recover=True)
    pivot_tree = etree.parse(str(Path(pivot_path)), parser)
    target_source = Path(target_path)
    target_tree = etree.parse(str(target_source), parser)
    target_lang_nodes = target_tree.getroot().xpath(".//*[local-name()='text'][1]")
    target_lang = target_lang_nodes[0].get("lang") if target_lang_nodes else None
    pivot_sentences = list(pivot_tree.getroot().xpath(".//*[local-name()='s' and @tuid]"))
    target_sentences = list(target_tree.getroot().xpath(".//*[local-name()='s' and @tuid]"))
    count = min(len(pivot_sentences), len(target_sentences))
    for index in range(count):
        pivot_s = pivot_sentences[index]
        target_s = target_sentences[index]
        s_tuid = target_s.get("tuid") or pivot_s.get("tuid")
        if not s_tuid:
            continue
        pivot_toks = list(pivot_s.xpath("./*[local-name()='tok']"))
        token_count_hint = len(pivot_toks) if pivot_toks else None
        target_text = " ".join(target_s.itertext()).strip()
        tokens = _tokenize_with_flexipipe(target_text, target_lang)
        if token_count_hint and token_count_hint > 0 and len(tokens) > token_count_hint:
            tokens = tokens[:token_count_hint]
        target_s.text = None
        for child in list(target_s):
            target_s.remove(child)
        for token_index, token in enumerate(tokens, start=1):
            tok_node = etree.SubElement(target_s, "tok")
            tok_node.set("tuid", f"{s_tuid}:w{token_index}")
            tok_node.text = token
            if token_index < len(tokens):
                tok_node.tail = " "
    destination = Path(output_path) if output_path else target_source
    destination.write_bytes(etree.tostring(target_tree, pretty_print=True, xml_declaration=True, encoding="utf-8"))


def project_paragraphs(*_: object) -> None:
    raise NotImplementedError("scheduled for v2")


def project_divs(*_: object) -> None:
    raise NotImplementedError("scheduled for v2")


def project_text(*_: object) -> None:
    raise NotImplementedError("scheduled for v2")


def segment_from_pivot(level: str, pivot_path: str, target_path: str, output_path: str | None = None) -> None:
    if level == "s":
        project_sentences_from_pivot(pivot_path, target_path, output_path)
        return
    if level == "tok":
        project_tokens_from_pivot(pivot_path, target_path, output_path)
        return
    if level == "p":
        project_paragraphs()
    elif level == "div":
        project_divs()
    elif level == "text":
        project_text()
    else:
        raise ValueError(f"Unsupported level for segmentation projection: {level}")

