"""Embedding interface: input in, 512-d vector out.

Test mode uses deterministic hash vectors so tests run with no
download. Real mode uses a CLIP style model when installed.
Both share one method shape so wiring the real model later is
a drop in change. Fully offline unless ClipEmbedder is used.
"""

from __future__ import annotations

import hashlib

import numpy as np

from edge.config import DIM


class BaseEmbedder:
    """One method contract for all embedders."""

    dim: int = DIM

    def encode_text(self, key: str) -> list[float]:
        raise NotImplementedError

    def encode_image(self, data: bytes) -> list[float]:
        raise NotImplementedError


class HashEmbedder(BaseEmbedder):
    """Deterministic hash vectors for tests and sim.

    Same input always gives the same unit length vector.
    Different inputs give near orthogonal vectors.
    No model, no network, no files.
    """

    def __init__(self, dim: int = DIM) -> None:
        if dim < 8:
            raise ValueError("dim must be at least 8")
        self.dim = dim

    @staticmethod
    def _seed(key: bytes) -> int:
        digest = hashlib.sha256(key).digest()
        return int.from_bytes(digest[:8], "big")

    def _vector_from_seed(self, seed: int) -> list[float]:
        rng = np.random.default_rng(seed)
        vec = rng.normal(size=self.dim)
        norm = float(np.linalg.norm(vec))
        if norm == 0.0:
            vec[0] = 1.0
            norm = 1.0
        return (vec / norm).tolist()

    def encode_text(self, key: str) -> list[float]:
        if not isinstance(key, str) or not key:
            raise ValueError("key must be a non-empty string")
        return self._vector_from_seed(self._seed(key.encode("utf-8")))

    def encode_image(self, data: bytes) -> list[float]:
        if not isinstance(data, bytes) or not data:
            raise ValueError("data must be non-empty bytes")
        return self._vector_from_seed(self._seed(data))


class ClipEmbedder(BaseEmbedder):
    """Real image model wrapper. Optional dependency.

    Needs torch plus transformers plus a CLIP checkpoint.
    Loads lazily so imports stay light when only hash mode is used.
    Output is L2 normalized to length dim. If dim is not 512 the
    vector is projected with a fixed random matrix so the store
    shape stays constant.
    """

    def __init__(
        self, model_name: str = "openai/clip-vit-base-patch32", dim: int = DIM
    ) -> None:
        if not model_name or not isinstance(model_name, str):
            raise ValueError("model_name must be a non-empty string")
        self.model_name = model_name
        self.dim = dim
        self._model = None
        self._processor = None

    def _load(self) -> None:
        try:
            import torch  # noqa: F401
            from transformers import CLIPModel, CLIPProcessor
        except ImportError as exc:
            raise RuntimeError(
                "clip mode needs torch plus transformers, "
                "use HashEmbedder for offline tests"
            ) from exc
        self._model = CLIPModel.from_pretrained(self.model_name)
        self._processor = CLIPProcessor.from_pretrained(self.model_name)
        self._model.eval()

    def encode_text(self, key: str) -> list[float]:
        if not isinstance(key, str) or not key:
            raise ValueError("key must be a non-empty string")
        if self._model is None:
            self._load()
        import torch

        inputs = self._processor(text=[key], return_tensors="pt", padding=True)
        with torch.no_grad():
            feat = self._model.get_text_features(**inputs)[0]
            feat = feat / feat.norm()
        return self._fit_dim(feat.tolist())

    def encode_image(self, data: bytes) -> list[float]:
        if not isinstance(data, bytes) or not data:
            raise ValueError("data must be non-empty bytes")
        if self._model is None:
            self._load()
        import io

        import torch
        from PIL import Image

        img = Image.open(io.BytesIO(data)).convert("RGB")
        inputs = self._processor(images=[img], return_tensors="pt")
        with torch.no_grad():
            feat = self._model.get_image_features(**inputs)[0]
            feat = feat / feat.norm()
        return self._fit_dim(feat.tolist())

    def _fit_dim(self, vec: list[float]) -> list[float]:
        if len(vec) == self.dim:
            return [float(x) for x in vec]
        rng = np.random.default_rng(42)
        proj = rng.normal(size=(len(vec), self.dim))
        out = np.array(vec, dtype=float) @ proj
        norm = float(np.linalg.norm(out)) or 1.0
        return (out / norm).tolist()


def get_embedder(mode: str = "hash", **kwargs) -> BaseEmbedder:
    """Factory used by sim and future sensor code."""
    if mode == "hash":
        return HashEmbedder(**kwargs)
    if mode == "clip":
        return ClipEmbedder(**kwargs)
    raise ValueError("mode must be hash or clip")
