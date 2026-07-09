"""Verbatim copy of shannon_entropy + restriction_index from
blocks/clonotype-distribution/software/src/compartment_analysis.py (lines 206-223) — the canonical
reference for spec A-0013. Used by the parity test to guard that our port stays identical to upstream.
Kept byte-for-byte (test-data is ruff-excluded; not ours to lint/format)."""

import math

import numpy as np


def shannon_entropy(p: np.ndarray) -> float:
    p = p[p > 0]
    if len(p) == 0:
        return 0.0
    p = p / p.sum()
    return -float(np.sum(p * np.log2(p)))


def restriction_index(freq_by_group: np.ndarray) -> float:
    """RI = 1 - H(p) / log2(N)"""
    nonzero = freq_by_group[freq_by_group > 0]
    n = len(nonzero)
    if n == 0:
        return float("nan")
    if n == 1:
        return 1.0
    h = shannon_entropy(nonzero)
    return 1.0 - h / math.log2(n)
