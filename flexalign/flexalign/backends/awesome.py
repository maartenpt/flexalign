"""awesome backend: token pairs within sentences that share a sentence tuid.

Methods (option `method`):
  awesome     awesome-align's extraction (awesome_align.py; options `model`, `layer`, `threshold`); the default
  similarity  mutual nearest neighbours of frequency-weighted word vectors from a small sentence encoder
              (option `threshold`, default 0.4)
"""

from __future__ import annotations

import os
import re
from collections import defaultdict
from dataclasses import dataclass
from math import sqrt

from ..align.rollup import chunk_sentence_windows
from ..align.segment_adapter import segment_views_from_align_doc
from ..backend_spec import BackendSpec, StepSpec


@dataclass
class _TokenUnit:
    unit_id: str
    text: str
    tuid: str | None


class AwesomeBackend:
    name = "awesome"
    supported_steps = (
        StepSpec("p", "s", "rollup", via="tok", needs_pretokenized=True),
        StepSpec("s", "tok", "direct", needs_pretokenized=True),
    )

    def __init__(self) -> None:
        # Smaller multilingual encoder to reduce memory pressure and crashes.
        self._model_name = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
        self._tokenizer = None
        self._model = None

    def _ensure_model(self):
        if self._tokenizer is not None and self._model is not None:
            return
        os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
        try:
            import torch
            from transformers import AutoModel, AutoTokenizer
        except Exception as exc:  # pragma: no cover - optional dependency path
            missing_pkg = None
            if isinstance(exc, ModuleNotFoundError):
                missing_pkg = exc.name
            missing_hint = f" Missing package: {missing_pkg}." if missing_pkg else ""
            raise RuntimeError(
                "Awesome backend dependencies are not installed."
                f"{missing_hint}\n"
                "Install one of:\n"
                '  - pip install "flexalign[awesome]"\n'
                '  - pip install -e ".[awesome]"   # from the flexalign repo root'
            ) from exc
        self._torch = torch
        try:
            torch.set_num_threads(1)
            torch.set_num_interop_threads(1)
        except Exception:
            pass
        self._tokenizer = AutoTokenizer.from_pretrained(self._model_name)
        self._model = AutoModel.from_pretrained(self._model_name, low_cpu_mem_usage=True)
        self._model.eval()

    @staticmethod
    def _split_tuids(raw: str | None) -> list[str]:
        if not raw:
            return []
        return [part for part in re.split(r"[|\s]+", str(raw).strip()) if part]

    @staticmethod
    def _sentence_tuids_for_token(elem) -> list[str]:
        cur = elem
        while cur is not None:
            tag = str(getattr(cur, "tag", "") or "")
            if tag.endswith("}s") or tag == "s":
                tuids = AwesomeBackend._split_tuids(cur.get("tuid"))
                if tuids:
                    return tuids
            cur = cur.getparent() if hasattr(cur, "getparent") else None
        return []

    @staticmethod
    def _sentence_key(token_id: str, tuid: str | None) -> str:
        source = tuid or token_id
        if ":w" in source:
            return source.rsplit(":w", 1)[0]
        if ":" in source:
            return source.rsplit(":", 1)[0]
        return "global"

    def _collect_tokens(self, doc) -> dict[str, list[_TokenUnit]]:
        grouped: dict[str, list[_TokenUnit]] = defaultdict(list)
        for view in segment_views_from_align_doc(doc, "tok"):
            token = _TokenUnit(unit_id=view.anchor_id, text=view.text, tuid=view.tuid)
            el = view.element
            sentence_tuids = self._sentence_tuids_for_token(el) if el is not None else []
            if sentence_tuids:
                for sentence_tuid in sentence_tuids:
                    grouped[sentence_tuid].append(token)
                continue
            grouped[self._sentence_key(view.anchor_id, token.tuid)].append(token)
        return grouped

    @staticmethod
    def _norm_token(text: str) -> str:
        return "".join(ch for ch in text.lower().strip() if ch.isalnum())

    def _build_frequency(self, grouped_tokens: dict[str, list[_TokenUnit]]) -> dict[str, int]:
        freq: dict[str, int] = defaultdict(int)
        for tokens in grouped_tokens.values():
            for token in tokens:
                norm = self._norm_token(token.text)
                if norm:
                    freq[norm] += 1
        return freq

    def _token_weight(self, text: str, freq_map: dict[str, int]) -> float:
        norm = self._norm_token(text)
        if not norm:
            return 0.0
        freq = max(freq_map.get(norm, 1), 1)
        # Penalize frequent tokens to reduce spurious function-word matches.
        return 1.0 / sqrt(float(freq))

    def _embed_words(self, words: list[str]):
        self._ensure_model()
        if not words:
            return []
        encoded = self._tokenizer(
            [words],
            is_split_into_words=True,
            return_tensors="pt",
            truncation=True,
            max_length=512,
        )
        with self._torch.no_grad():
            outputs = self._model(**encoded)
        hidden = outputs.last_hidden_state[0]
        word_ids = encoded.word_ids(batch_index=0)
        by_word: dict[int, list] = defaultdict(list)
        for idx, word_id in enumerate(word_ids):
            if word_id is None:
                continue
            by_word[word_id].append(hidden[idx])
        vectors = []
        for i in range(len(words)):
            pieces = by_word.get(i)
            if not pieces:
                vectors.append(None)
                continue
            stacked = self._torch.stack(pieces)
            vectors.append(stacked.mean(dim=0))
        return vectors

    def _cosine(self, a, b) -> float:
        denom = (a.norm() * b.norm()).item()
        if denom <= 1e-9:
            return -1.0
        return float((a @ b).item() / denom)

    def _align_sentence_tokens(
        self,
        src_tokens: list[_TokenUnit],
        tgt_tokens: list[_TokenUnit],
        *,
        src_freq: dict[str, int],
        tgt_freq: dict[str, int],
        threshold: float = 0.4,
    ):
        src_words = [token.text for token in src_tokens]
        tgt_words = [token.text for token in tgt_tokens]
        src_vecs = self._embed_words(src_words)
        tgt_vecs = self._embed_words(tgt_words)
        if not src_vecs or not tgt_vecs:
            return []
        sim = [[-1.0 for _ in range(len(tgt_vecs))] for _ in range(len(src_vecs))]
        for i, svec in enumerate(src_vecs):
            if svec is None:
                continue
            for j, tvec in enumerate(tgt_vecs):
                if tvec is None:
                    continue
                base = self._cosine(svec, tvec)
                weighted = base * self._token_weight(src_tokens[i].text, src_freq) * self._token_weight(
                    tgt_tokens[j].text, tgt_freq
                )
                sim[i][j] = weighted

        src_best = [max(range(len(tgt_vecs)), key=lambda j: sim[i][j]) if tgt_vecs else -1 for i in range(len(src_vecs))]
        tgt_best = [max(range(len(src_vecs)), key=lambda i: sim[i][j]) if src_vecs else -1 for j in range(len(tgt_vecs))]
        pairs = []
        for i, j in enumerate(src_best):
            if j < 0:
                continue
            if tgt_best[j] != i:
                continue
            score = sim[i][j]
            if score < threshold:
                continue
            pairs.append((i, j, score))
        return pairs

    def align(self, src, tgt, *, step=None, parent_pairs=None, options=None):
        options = options or {}
        level = step.level if step else "s"
        # Demonstrate chunking behavior on long text spans for rollup paths.
        windows = chunk_sentence_windows(
            [u.text for u in segment_views_from_align_doc(src, level)],
            subtoken_cap=options.get("subtoken_cap", 480),
        )
        _ = windows

        if level != "tok":
            from .identity import IdentityBackend

            return IdentityBackend().align(src, tgt, step=step, parent_pairs=parent_pairs, options=options)

        method = str(options.get("method", "awesome"))
        if method not in ("awesome", "similarity"):
            raise ValueError(f"awesome backend: unknown method {method!r} (awesome, similarity)")
        src_by_sentence = self._collect_tokens(src)
        tgt_by_sentence = self._collect_tokens(tgt)
        if method == "awesome":
            from .awesome_align import DEFAULT_LAYER, DEFAULT_MODEL, DEFAULT_THRESHOLD, AwesomeAligner

            aligner = AwesomeAligner(str(options.get("model", DEFAULT_MODEL)),
                                     layer=int(options.get("layer", DEFAULT_LAYER)),
                                     threshold=float(options.get("threshold", DEFAULT_THRESHOLD)))
            basis = "awesome:softmax-intersection"

            def sentence_pairs(src_tokens, tgt_tokens):
                found = aligner.word_pairs([t.text for t in src_tokens], [t.text for t in tgt_tokens])
                return [(i, j, 1.0) for i, j in sorted(found)]
        else:
            threshold = float(options.get("threshold", 0.4))
            src_freq = self._build_frequency(src_by_sentence)
            tgt_freq = self._build_frequency(tgt_by_sentence)
            basis = "awesome:mutual-nearest-weighted"

            def sentence_pairs(src_tokens, tgt_tokens):
                return self._align_sentence_tokens(src_tokens, tgt_tokens, src_freq=src_freq, tgt_freq=tgt_freq,
                                                   threshold=threshold)
        rows = []
        seen = set()
        for sentence_key in sorted(set(src_by_sentence).intersection(tgt_by_sentence)):
            src_tokens = src_by_sentence[sentence_key]
            tgt_tokens = tgt_by_sentence[sentence_key]
            for i, j, score in sentence_pairs(src_tokens, tgt_tokens):
                source = src_tokens[i]
                target = tgt_tokens[j]
                if (source.unit_id, target.unit_id) in seen:   # a sentence with several tuids is in several groups
                    continue
                seen.add((source.unit_id, target.unit_id))
                rows.append(
                    {
                        "id1": [source.unit_id],
                        "id2": [target.unit_id],
                        "text1": source.text,
                        "text2": target.text,
                        "score": round(score, 6),
                        "edit": "auto",
                        "alignment_basis": basis,
                        "tuid_at_write_1": source.tuid,
                        "tuid_at_write_2": target.tuid,
                    }
                )
        return rows


BACKEND_SPEC = BackendSpec(
    name="awesome",
    description="Token pairs within aligned sentences (awesome-align; or a similarity method)",
    factory=AwesomeBackend,
    supported_steps=AwesomeBackend.supported_steps,
    install_instructions='Install extras with: pip install "flexalign[awesome]"',
)

