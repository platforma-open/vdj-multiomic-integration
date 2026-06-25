"""Behavioral tests for aggregate_clonotypes.py (VDJ Multiomic Integration software).

Run from software/:
    uv sync --all-groups
    uv run pytest -m "not slow"   # fast: pure functions + properties + parity
    uv run pytest                 # + the slow CLI/golden lane
"""

import csv
import math
import pathlib
import statistics
import subprocess
import sys

import numpy as np
import pytest
from aggregate_clonotypes import aggregate_expression, breadth, dominant_category, restriction_index
from compartment_ref import restriction_index as ref_restriction_index
from hypothesis import given
from hypothesis import strategies as st

SRC = pathlib.Path(__file__).parents[1] / "src" / "aggregate_clonotypes.py"

# UMI counts are non-negative INTEGERS — generate them as such. (Generating arbitrary floats would
# feed denormals like 5e-324 into the log2 entropy, where x/total underflows to 0.0; that input
# can't occur on real data, so we model the real domain instead of hardening against impossibilities.)
_counts = st.lists(
    st.integers(min_value=0, max_value=10_000).map(float),
    min_size=1,
    max_size=12,
)


# --- restriction index (spec A-0013; compartment_analysis.py:214) ---


def test_ri_single_feature_is_one():
    assert restriction_index([10.0]) == 1.0


def test_ri_even_split_is_zero():
    assert restriction_index([5.0, 5.0]) == pytest.approx(0.0)


def test_ri_skewed_split():
    # fractions 0.8/0.2; H = 0.72193; N=2 -> RI = 0.27807
    assert restriction_index([8.0, 2.0]) == pytest.approx(0.27807, abs=1e-4)


def test_ri_ignores_zero_categories():
    assert restriction_index([10.0, 0.0, 0.0]) == 1.0  # N counts nonzero only


def test_ri_no_signal_is_nan():
    assert math.isnan(restriction_index([0.0, 0.0]))


# --- breadth (spec A-0013; compartment_analysis.py:387) ---


def test_breadth_default_threshold_counts_nonzero():
    assert breadth([8.0, 2.0, 0.0], presence_threshold=0.0) == 2


def test_breadth_with_threshold():
    # fractions 0.8/0.2; presence 0.3 -> only 0.8 passes -> 1
    assert breadth([8.0, 2.0], presence_threshold=0.3) == 1


# --- dominant category (spec A-0012, reused) ---


def test_dominant_winner():
    assert dominant_category({"A": 7, "B": 3}, 0.6) == "A"


def test_dominant_ambiguous():
    assert dominant_category({"A": 4, "B": 3, "C": 3}, 0.6) == "ambiguous"


def test_dominant_exact_split_floor():
    assert dominant_category({"A": 5, "B": 5}, 0.5) == "ambiguous"


def test_dominant_none():
    assert dominant_category({"A": 0}, 0.6) is None


# --- expression aggregation (spec A-0019) ---


def test_expression_mean_default():
    assert aggregate_expression([2.0, 4.0, 6.0]) == pytest.approx(4.0)


def test_expression_max():
    assert aggregate_expression([2.0, 4.0, 6.0], method="max") == 6.0


# --- properties (invariants that hold for ALL valid inputs) ---


@given(_counts)
def test_ri_bounded_0_1(counts):
    ri = restriction_index(counts)
    if not math.isnan(ri):
        assert 0.0 <= ri <= 1.0


@given(_counts, st.floats(min_value=0.0, max_value=0.5), st.floats(min_value=0.0, max_value=0.5))
def test_breadth_monotonic_in_threshold(counts, t1, t2):
    lo, hi = sorted((t1, t2))
    assert breadth(counts, hi) <= breadth(counts, lo)


@given(
    st.dictionaries(st.text(min_size=1), st.integers(min_value=0, max_value=1000), max_size=8),
    st.floats(min_value=0.5, max_value=1.0),
)
def test_dominant_result_in_domain(counts, threshold):
    r = dominant_category(counts, threshold)
    assert r is None or r == "ambiguous" or r in counts


# expression values are non-negative (counts / normalized expression); compare mean against the
# accurate statistics.fmean oracle (robust to the float rounding that a raw min<=mean<=max check trips on).
@given(
    st.lists(
        st.floats(min_value=0, max_value=1e6, allow_nan=False, allow_infinity=False, allow_subnormal=False),
        min_size=1,
        max_size=20,
    )
)
def test_expression_mean_and_max(values):
    assert aggregate_expression(values, "mean") == pytest.approx(statistics.fmean(values))
    assert aggregate_expression(values, "max") == max(values)


# --- parity vs the verbatim compartment_analysis.py reference (spec A-0013) ---


@given(_counts)
def test_parity_vs_compartment_analysis(counts):
    ours = restriction_index(counts)
    theirs = ref_restriction_index(np.array(counts, dtype=float))
    if math.isnan(ours) or math.isnan(theirs):
        assert math.isnan(ours) and math.isnan(theirs)
    else:
        assert ours == pytest.approx(theirs)


# --- end-to-end CLI over the committed bed (slow lane) ---


@pytest.mark.slow
def test_cli_writes_outputs(features_csv, linker_csv, tmp_path):
    subprocess.run(
        [
            sys.executable,
            str(SRC),
            "--feature-csv",
            str(features_csv),
            "--linker-csv",
            str(linker_csv),
            "--output-prefix",
            str(tmp_path / "result"),
        ],
        check=True,
        cwd=tmp_path,
    )
    for name in ["result_counts.csv", "result_fractions.csv", "result_properties.csv"]:
        assert (tmp_path / name).exists(), f"missing {name}"


@pytest.mark.slow
def test_cli_golden_properties(features_csv, linker_csv, tmp_path):
    # C1 spans samples s1+s2 (pooled: AGX 8, BGX 2); C2 single feature; cellZ (no clonotype) dropped.
    subprocess.run(
        [
            sys.executable,
            str(SRC),
            "--feature-csv",
            str(features_csv),
            "--linker-csv",
            str(linker_csv),
            "--output-prefix",
            str(tmp_path / "result"),
        ],
        check=True,
        cwd=tmp_path,
    )
    with open(tmp_path / "result_properties.csv", newline="") as f:
        rows = {r["scClonotypeKey"]: r for r in csv.DictReader(f)}
    assert set(rows) == {"C1", "C2"}  # cellZ dropped (inner join); C1 pooled across samples
    assert float(rows["C1"]["restrictionIndex"]) == pytest.approx(0.27807, abs=1e-4)
    assert int(rows["C1"]["breadth"]) == 2
    assert rows["C1"]["dominantFeature"] == "AGX"
    assert float(rows["C2"]["restrictionIndex"]) == 1.0
    assert int(rows["C2"]["breadth"]) == 1
