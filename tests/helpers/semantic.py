"""A deterministic stand-in for the code model: hashed bag of words (no download, no torch)."""

import zlib

import numpy as np

from verireview.semantic import words

DIM = 64


def fake_encoder(texts: list[str]) -> np.ndarray:
    """texts → L2-normalised hashed word counts; texts sharing words are similar."""
    out = np.zeros((len(texts), DIM))
    for row, text in enumerate(texts):
        for word in words(text):
            out[row, zlib.crc32(word.encode()) % DIM] += 1.0
        norm = np.linalg.norm(out[row])
        if norm:
            out[row] /= norm
    return out
