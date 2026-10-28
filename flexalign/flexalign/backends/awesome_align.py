"""awesome-align's extraction (Dou & Neubig 2021): word pairs from one layer of a multilingual BERT.

Each word is split into subwords; both sentences go through the model separately; the dot products of the
subword vectors at `layer` are normalised by a softmax in both directions, and a subword pair is aligned when both
directions exceed `threshold`. Word pairs are the subword pairs mapped back to their words (n:m allowed).
Defaults as in awesome-align and the NTREX project: model `aneuraz/awesome-align-with-co`, layer 8, threshold 1e-3.
"""

from __future__ import annotations

import os
from typing import List, Set, Tuple

DEFAULT_MODEL = "aneuraz/awesome-align-with-co"
DEFAULT_LAYER = 8
DEFAULT_THRESHOLD = 1e-3


class AwesomeAligner:
    def __init__(self, model_name: str = DEFAULT_MODEL, *, layer: int = DEFAULT_LAYER,
                 threshold: float = DEFAULT_THRESHOLD) -> None:
        self.model_name = model_name
        self.layer = layer
        self.threshold = threshold
        self._model = None
        self._tokenizer = None

    def _ensure_model(self) -> None:
        if self._model is not None:
            return
        os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
        import torch
        from transformers import AutoModel, AutoTokenizer

        self._torch = torch
        self._tokenizer = AutoTokenizer.from_pretrained(self.model_name)
        self._model = AutoModel.from_pretrained(self.model_name)
        self._model.eval()

    def _encode(self, words: List[str]):
        """The subword ids of a sentence (with the model's special tokens) and each subword's word index."""
        tok = self._tokenizer
        pieces = [tok.tokenize(w) or [tok.unk_token] for w in words]
        sub2word = [i for i, p in enumerate(pieces) for _ in p]
        limit = min(tok.model_max_length, 512) - 2
        sub_ids = [t for p in pieces for t in tok.convert_tokens_to_ids(p)][:limit]
        ids = self._torch.tensor([tok.cls_token_id, *sub_ids, tok.sep_token_id])   # BERT: [CLS] … [SEP]
        return ids, sub2word[: len(sub_ids)]

    def _layer(self, ids):
        out = self._model(ids.unsqueeze(0), output_hidden_states=True)
        return out.hidden_states[self.layer][0, 1:-1]

    def word_pairs(self, src: List[str], tgt: List[str]) -> Set[Tuple[int, int]]:
        """The aligned (source word index, target word index) pairs of one sentence pair."""
        if not src or not tgt:
            return set()
        self._ensure_model()
        torch = self._torch
        ids_s, s2w_s = self._encode(src)
        ids_t, s2w_t = self._encode(tgt)
        with torch.no_grad():
            dot = torch.matmul(self._layer(ids_s), self._layer(ids_t).transpose(-1, -2))
            both = (torch.nn.Softmax(dim=-1)(dot) > self.threshold) * (torch.nn.Softmax(dim=-2)(dot) > self.threshold)
        return {(s2w_s[i], s2w_t[j]) for i, j in torch.nonzero(both, as_tuple=False).tolist()}
