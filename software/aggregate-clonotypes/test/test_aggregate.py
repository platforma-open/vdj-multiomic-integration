"""Behavioral tests for aggregate_clonotypes.py (VDJ Multiomic Integration software).

Run from software/:
    uv sync --all-groups
    uv run pytest -m "not slow"   # fast: pure functions + properties + parity
    uv run pytest                 # + the slow CLI/golden lane
"""

import csv
import json
import math
import pathlib
import subprocess
import sys

import numpy as np
import pytest
from aggregate_clonotypes import breadth, dominant_category, present_features, restriction_index
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


# --- per-antigen presence cutoff (feedback: per-antigen threshold = presence/binding cutoff) ---


def test_present_features_default_keeps_all_nonzero():
    # no per-antigen overrides, default 0.0 -> every nonzero feature survives
    assert present_features({"A": 8, "B": 2}, {}, 0.0) == {"A": 8, "B": 2}


def test_present_features_per_antigen_threshold_drops_below_cutoff():
    # fractions A=0.8, B=0.2; B needs 0.3 -> B dropped, A (needs default 0.0) kept
    assert present_features({"A": 8, "B": 2}, {"B": 0.3}, 0.0) == {"A": 8}


def test_present_features_global_default_applies_when_unlisted():
    # fractions 0.8/0.2; global default 0.25 -> only A survives
    assert present_features({"A": 8, "B": 2}, {}, 0.25) == {"A": 8}


def test_present_features_no_signal_is_empty():
    assert present_features({"A": 0, "B": 0}, {}, 0.0) == {}


# --- dominant category (spec A-0012, reused) ---


def test_dominant_winner():
    assert dominant_category({"A": 7, "B": 3}, 0.6) == "A"


def test_dominant_ambiguous():
    assert dominant_category({"A": 4, "B": 3, "C": 3}, 0.6) == "ambiguous"


def test_dominant_exact_split_floor():
    assert dominant_category({"A": 5, "B": 5}, 0.5) == "ambiguous"


def test_dominant_none():
    assert dominant_category({"A": 0}, 0.6) is None


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
    for name in [
        "result_counts.csv",
        "result_fractions.csv",
        "result_fractions_wide.csv",
        "result_feature_names.json",
        "result_properties.csv",
    ]:
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


def _write_csv(path, header, rows):
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def _run_cli(
    tmp_path,
    feature_rows,
    linker_rows,
    *,
    gex_rows=None,
    annotation_rows=None,
    expression_method=None,
    presence_threshold=None,
    presence_thresholds=None,
):
    feats = tmp_path / "features.csv"
    linker = tmp_path / "linker.csv"
    _write_csv(feats, ["sampleId", "cellId", "feature", "umiCount"], feature_rows)
    _write_csv(linker, ["sampleId", "cellId", "scClonotypeKey"], linker_rows)
    cmd = [
        sys.executable,
        str(SRC),
        "--feature-csv",
        str(feats),
        "--linker-csv",
        str(linker),
        "--output-prefix",
        str(tmp_path / "result"),
    ]
    if presence_threshold is not None:
        cmd += ["--presence-threshold", str(presence_threshold)]
    if presence_thresholds is not None:
        cmd += ["--presence-thresholds", json.dumps(presence_thresholds)]
    if gex_rows is not None:
        gex = tmp_path / "gex.csv"
        _write_csv(gex, ["sampleId", "cellId", "geneId", "count"], gex_rows)
        cmd += ["--gex-csv", str(gex)]
        if expression_method is not None:
            cmd += ["--expression-method", expression_method]
    if annotation_rows is not None:
        ann = tmp_path / "annotation.csv"
        _write_csv(ann, ["sampleId", "cellId", "cellType"], annotation_rows)
        cmd += ["--annotation-csv", str(ann)]
    subprocess.run(
        cmd,
        check=True,  # a mid-run crash surfaces as CalledProcessError -> test failure
        cwd=tmp_path,
    )


@pytest.mark.slow
def test_cli_disjoint_join_emits_empty_not_crash(tmp_path):
    # Feature cells and linker cells share no (sampleId, cellId): the inner join is empty. The run must
    # succeed and emit a header-only properties CSV (empty-but-valid) rather than crash on
    # pl.DataFrame([]).sort(...) — the barcode-mismatch failure mode the block hit in real data.
    _run_cli(
        tmp_path,
        feature_rows=[("s1", "cellA", "AGX", 8), ("s1", "cellA", "BGX", 2)],
        linker_rows=[("s1", "cellZ", "C1")],
    )
    props = tmp_path / "result_properties.csv"
    assert props.exists()
    with open(props, newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)
    assert rows == []  # header present, zero data rows
    assert set(fieldnames) == {"scClonotypeKey", "restrictionIndex", "breadth", "dominantFeature"}


@pytest.mark.slow
def test_cli_all_zero_counts_are_dropped_no_nan(tmp_path):
    # A clonotype whose only feature rows are all-zero UMI has no antigen signal: it must be dropped
    # (sparse, DP-4), never emit a 0/0=NaN fraction or a null-dtype dominant column.
    _run_cli(
        tmp_path,
        feature_rows=[
            ("s1", "cellA", "AGX", 0),
            ("s1", "cellA", "BGX", 0),
            ("s1", "cellC", "AGX", 5),
        ],
        linker_rows=[("s1", "cellA", "C1"), ("s1", "cellC", "C2")],
    )
    with open(tmp_path / "result_fractions.csv", newline="") as f:
        frac_rows = list(csv.DictReader(f))
    assert all(r["fraction"] not in ("NaN", "nan", "") for r in frac_rows)
    with open(tmp_path / "result_properties.csv", newline="") as f:
        keys = {r["scClonotypeKey"] for r in csv.DictReader(f)}
    assert keys == {"C2"}  # C1 (all-zero) dropped; C2 retained


# --- optional annotation branch: dominant cell type per clonotype (spec A-0020, dominant-category rule) ---


@pytest.mark.slow
def test_cli_annotation_dominant_cell_type(tmp_path):
    # C1: 2x Tcell + 1x Bcell -> 2/3 = 0.67 >= 0.6 threshold -> Tcell.
    # C2: 1x Tcell -> 1.0 -> Tcell.
    # C3: 1x Tcell + 1x Bcell -> tied at the 0.5 floor, two winners -> "ambiguous" (spec A-0012).
    _run_cli(
        tmp_path,
        feature_rows=[("s1", c, "AGX", 5) for c in ("cA", "cB", "cC", "cD", "cE", "cF")],
        linker_rows=[
            ("s1", "cA", "C1"),
            ("s1", "cB", "C1"),
            ("s1", "cC", "C1"),
            ("s1", "cD", "C2"),
            ("s1", "cE", "C3"),
            ("s1", "cF", "C3"),
        ],
        annotation_rows=[
            ("s1", "cA", "Tcell"),
            ("s1", "cB", "Tcell"),
            ("s1", "cC", "Bcell"),
            ("s1", "cD", "Tcell"),
            ("s1", "cE", "Tcell"),
            ("s1", "cF", "Bcell"),
        ],
    )
    with open(tmp_path / "result_annotation.csv", newline="") as f:
        rows = {r["scClonotypeKey"]: r["dominantCellType"] for r in csv.DictReader(f)}
    assert rows == {"C1": "Tcell", "C2": "Tcell", "C3": "ambiguous"}


# --- optional GEX branch: per-(clonotype, gene) mean/max expression (spec A-0019) ---
# NB these pin an intentional semantic: the mean is over the cells that CARRY a count for the gene
# (a sparse count matrix), not over every cell in the clonotype. C1/geneY below = mean(2) = 2.0, NOT
# mean(2, 0) = 1.0 — geneY has no row for cB, and no zero is imputed.


@pytest.mark.slow
def test_cli_gex_mean_expression(tmp_path):
    _run_cli(
        tmp_path,
        feature_rows=[("s1", "cA", "AGX", 5), ("s1", "cB", "AGX", 5), ("s1", "cD", "AGX", 5)],
        linker_rows=[("s1", "cA", "C1"), ("s1", "cB", "C1"), ("s1", "cD", "C2")],
        gex_rows=[
            ("s1", "cA", "geneX", 4),
            ("s1", "cB", "geneX", 8),
            ("s1", "cA", "geneY", 2),
            ("s1", "cD", "geneX", 10),
        ],
        expression_method="mean",
    )
    with open(tmp_path / "result_expression.csv", newline="") as f:
        rows = {(r["scClonotypeKey"], r["geneId"]): float(r["expression"]) for r in csv.DictReader(f)}
    assert rows == {("C1", "geneX"): 6.0, ("C1", "geneY"): 2.0, ("C2", "geneX"): 10.0}


@pytest.mark.slow
def test_cli_gex_max_expression(tmp_path):
    _run_cli(
        tmp_path,
        feature_rows=[("s1", "cA", "AGX", 5), ("s1", "cB", "AGX", 5), ("s1", "cD", "AGX", 5)],
        linker_rows=[("s1", "cA", "C1"), ("s1", "cB", "C1"), ("s1", "cD", "C2")],
        gex_rows=[
            ("s1", "cA", "geneX", 4),
            ("s1", "cB", "geneX", 8),
            ("s1", "cA", "geneY", 2),
            ("s1", "cD", "geneX", 10),
        ],
        expression_method="max",
    )
    with open(tmp_path / "result_expression.csv", newline="") as f:
        rows = {(r["scClonotypeKey"], r["geneId"]): float(r["expression"]) for r in csv.DictReader(f)}
    assert rows == {("C1", "geneX"): 8.0, ("C1", "geneY"): 2.0, ("C2", "geneX"): 10.0}


# --- per-antigen fraction columns + feature-names output (feedback: one fraction pcolumn per antigen) ---


@pytest.mark.slow
def test_cli_wide_fractions_and_feature_names(tmp_path):
    # C1 pooled: AGX 8, BGX 2 -> fractions 0.8/0.2. C2: only AGX -> 1.0 (0.0 for BGX, which it lacks).
    _run_cli(
        tmp_path,
        feature_rows=[
            ("s1", "cA", "AGX", 8),
            ("s1", "cA", "BGX", 2),
            ("s1", "cB", "AGX", 5),
        ],
        linker_rows=[("s1", "cA", "C1"), ("s1", "cB", "C2")],
    )
    with open(tmp_path / "result_feature_names.json") as f:
        assert json.load(f) == ["AGX", "BGX"]  # sorted distinct present features
    with open(tmp_path / "result_fractions_wide.csv", newline="") as f:
        rows = {r["scClonotypeKey"]: r for r in csv.DictReader(f)}
    assert set(rows["C1"]) == {"scClonotypeKey", "AGX", "BGX"}  # one column per antigen
    assert float(rows["C1"]["AGX"]) == pytest.approx(0.8)
    assert float(rows["C1"]["BGX"]) == pytest.approx(0.2)
    assert float(rows["C2"]["AGX"]) == pytest.approx(1.0)
    assert float(rows["C2"]["BGX"]) == pytest.approx(0.0)  # no BGX signal -> 0, not missing


@pytest.mark.slow
def test_cli_per_antigen_presence_threshold(tmp_path):
    # C1: AGX 8 (0.8), BGX 2 (0.2). A per-antigen cutoff of 0.3 on BGX drops it from "present":
    # breadth 2 -> 1, and the dominant call is made over surviving {AGX} -> AGX at 100%.
    _run_cli(
        tmp_path,
        feature_rows=[("s1", "cA", "AGX", 8), ("s1", "cA", "BGX", 2)],
        linker_rows=[("s1", "cA", "C1")],
        presence_thresholds={"BGX": 0.3},
    )
    with open(tmp_path / "result_properties.csv", newline="") as f:
        row = next(csv.DictReader(f))
    assert int(row["breadth"]) == 1  # only AGX survives its cutoff
    assert row["dominantFeature"] == "AGX"
    # The raw per-antigen fractions are unaffected by the presence cutoff (they report real signal).
    with open(tmp_path / "result_fractions_wide.csv", newline="") as f:
        wide = next(csv.DictReader(f))
    assert float(wide["BGX"]) == pytest.approx(0.2)
