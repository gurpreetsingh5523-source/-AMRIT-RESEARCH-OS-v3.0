"""
AMRIT RESEARCH OS v4.0
core/memory/turbovec_memory.py

Low-level vector engine primitives backed by Google Research's TurboQuant
(ICLR 2026, arxiv 2504.19874) via the `turbovec` Rust package.

  16x ਘੱਟ RAM · FAISS ਤੋਂ 12-20% ਤੇਜ਼ · Apple M-series NEON optimized

ਇੰਸਟਾਲ: pip install turbovec

This module only exposes the engine pieces:
  - OllamaEmbedder      → local nomic-embed-text embeddings (768-dim)
  - NumpyFallbackIndex  → pure-numpy cosine search (used if turbovec absent)
  - _make_index()       → returns turbovec IdMapIndex or the numpy fallback
  - TURBOVEC_AVAILABLE  → bool

The high-level store (`VectorMemory`) and the pipeline helper
(`AMRITMemoryBridge`) live in core/memory/vector_memory.py and are built
on top of these primitives.
"""

import json
import logging
import urllib.request
import urllib.error
from typing import Optional

import numpy as np

log = logging.getLogger("AmritTurboVec")

# ─────────────────────────────────────────────────────────────
# TurboVec availability check
# ─────────────────────────────────────────────────────────────
try:
    from turbovec import IdMapIndex
    TURBOVEC_AVAILABLE = True
    log.info("turbovec loaded — Rust SIMD vector search active")
except ImportError:
    TURBOVEC_AVAILABLE = False
    log.warning("turbovec not installed. Run: pip install turbovec")
    log.warning("   Falling back to numpy cosine search (slower)")

OLLAMA_BASE = "http://localhost:11434"
EMBED_MODEL = "nomic-embed-text"   # already in the Ollama stack
EMBED_DIM   = 768                  # nomic-embed-text dimension
BIT_WIDTH   = 4                    # 4-bit quantization (best recall)


# ─────────────────────────────────────────────────────────────
# Ollama Embeddings
# ─────────────────────────────────────────────────────────────
class OllamaEmbedder:
    """Get embeddings from local Ollama (nomic-embed-text)."""

    def __init__(self, model: str = EMBED_MODEL):
        self.model = model

    def embed(self, text: str) -> Optional[np.ndarray]:
        """Single text → 768-dim float32 unit vector (or None on failure)."""
        payload = json.dumps({
            "model": self.model,
            "prompt": (text or "")[:2000],   # truncate long texts
        }).encode()

        req = urllib.request.Request(
            f"{OLLAMA_BASE}/api/embeddings",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                data = json.loads(r.read().decode())
                vec = np.array(data["embedding"], dtype=np.float32)
                norm = np.linalg.norm(vec)
                return vec / norm if norm > 1e-9 else vec
        except Exception as e:
            log.warning(f"Embedding error: {e}")
            return None


# ─────────────────────────────────────────────────────────────
# Fallback: numpy cosine search (when turbovec not installed)
# ─────────────────────────────────────────────────────────────
class NumpyFallbackIndex:
    """Simple cosine search — slower but works without the Rust extension."""

    def __init__(self, dim: int):
        self.dim   = dim
        self._vecs = np.zeros((0, dim), dtype=np.float32)
        self._ids  = []

    def add_with_ids(self, vectors: np.ndarray, ids: np.ndarray):
        self._vecs = np.vstack([self._vecs, vectors]) if len(self._vecs) else vectors.copy()
        self._ids.extend(ids.tolist())

    def search(self, query: np.ndarray, k: int, allowlist=None):
        if len(self._vecs) == 0:
            return np.array([]), np.array([])
        scores = self._vecs @ query.flatten()
        if allowlist is not None:
            allow_set = set(allowlist.tolist())
            mask = np.array([i in allow_set for i in self._ids])
            scores = np.where(mask, scores, -1.0)
        top_k = min(k, len(scores))
        idx = np.argpartition(scores, -top_k)[-top_k:]
        idx = idx[np.argsort(scores[idx])[::-1]]
        return scores[idx], np.array([self._ids[i] for i in idx], dtype=np.uint64)

    def remove(self, uid: int):
        if uid in self._ids:
            pos = self._ids.index(uid)
            self._ids.pop(pos)
            self._vecs = np.delete(self._vecs, pos, axis=0)

    def __len__(self):
        return len(self._ids)


def _make_index(dim: int = EMBED_DIM, bit_width: int = BIT_WIDTH):
    """Return a turbovec IdMapIndex if available, else the numpy fallback."""
    if TURBOVEC_AVAILABLE:
        return IdMapIndex(dim=dim, bit_width=bit_width)
    return NumpyFallbackIndex(dim=dim)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(message)s")
    print("turbovec available:", TURBOVEC_AVAILABLE)
    emb = OllamaEmbedder()
    v = emb.embed("hello world")
    print("embedding dim:", None if v is None else v.shape)
