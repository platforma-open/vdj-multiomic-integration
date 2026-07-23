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
from aggregate_clonotypes import (
    CROSS_REACTIVE,
    breadth,
    dominant_category,
    feature_breakdown,
    present_features,
    resolve_offtargets_from_csv,
    restriction_index,
)
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


# --- restriction index (parity with compartment_analysis.py:214) ---


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


# --- breadth (parity with compartment_analysis.py:387) ---


def test_breadth_default_threshold_counts_nonzero():
    assert breadth([8.0, 2.0, 0.0], presence_threshold=0.0) == 2


def test_breadth_with_threshold():
    # fractions 0.8/0.2; presence 0.3 -> only 0.8 passes -> 1
    assert breadth([8.0, 2.0], presence_threshold=0.3) == 1


# --- presence cutoff (global within-clonotype fraction threshold, applied to every feature) ---


def test_present_features_default_keeps_all_nonzero():
    # threshold 0.0 -> every nonzero feature survives
    assert present_features({"A": 8, "B": 2}, 0.0) == {"A": 8, "B": 2}


def test_present_features_threshold_drops_below_cutoff():
    # fractions 0.8/0.2; threshold 0.25 -> only A survives
    assert present_features({"A": 8, "B": 2}, 0.25) == {"A": 8}


def test_present_features_no_signal_is_empty():
    assert present_features({"A": 0, "B": 0}, 0.0) == {}


# --- dominant category (reused) ---


def test_dominant_winner():
    assert dominant_category({"A": 7, "B": 3}, 0.6) == "A"


def test_dominant_ambiguous():
    assert dominant_category({"A": 4, "B": 3, "C": 3}, 0.6) == "ambiguous"


def test_dominant_exact_split_floor():
    assert dominant_category({"A": 5, "B": 5}, 0.5) == "ambiguous"


def test_dominant_none():
    assert dominant_category({"A": 0}, 0.6) is None


# --- off-target-aware dominant call + cross-reactive label (F2, mirrors FI consensus_category) ---


def test_dominant_excludes_offtargets():
    # Off-target excluded from winners, kept in denominator: AGX 3 / OT 5 -> 3/8 < 0.6 -> ambiguous.
    assert dominant_category({"AGX": 3, "OT": 5}, 0.6, offtargets=frozenset({"OT"})) == "ambiguous"


def test_dominant_offtarget_single_ontarget_wins():
    assert dominant_category({"AGX": 7, "OT": 2}, 0.6, offtargets=frozenset({"OT"})) == "AGX"


def test_dominant_crossreactive_two_targets():
    # human+cyno split 45/45, OT 10 -> on-target set 90% across 2 targets -> cross-reactive.
    assert (
        dominant_category(
            {"TgtA_human": 45, "TgtA_cyno": 45, "OT": 10},
            0.6,
            offtargets=frozenset({"OT"}),
            label_crossreactive=True,
        )
        == CROSS_REACTIVE
    )


def test_dominant_crossreactive_needs_label():
    assert (
        dominant_category({"TgtA_human": 45, "TgtA_cyno": 45, "OT": 10}, 0.6, offtargets=frozenset({"OT"}))
        == "ambiguous"
    )


def test_dominant_offtarget_swamped_is_ambiguous():
    # On-target set 40% (< 0.6), OT swamps -> ambiguous, never cross-reactive.
    assert (
        dominant_category(
            {"TgtA": 20, "TgtB": 20, "OT": 60},
            0.6,
            offtargets=frozenset({"OT"}),
            label_crossreactive=True,
        )
        == "ambiguous"
    )


# --- off-target set resolution from the property CSV (case-sensitive value matching) ---


def test_resolve_offtargets_from_csv_exact_match_unchanged(tmp_path):
    # Exact-case designations resolve as before; returned feature names are verbatim from the CSV.
    csv = tmp_path / "prop.csv"
    csv.write_text(
        "feature,value\nTgtA,Target\nDecoyX,Decoy\nOTx, Off-Target \n"  # whitespace tolerated (stripped)
    )
    got = resolve_offtargets_from_csv(str(csv), {"Off-Target", "Decoy"})
    assert got == {"DecoyX", "OTx"}


def test_resolve_offtargets_from_csv_case_sensitive(tmp_path):
    # Whitespace-trimmed but CASE-SENSITIVE: selecting "Off-Target" catches only that exact value, NOT
    # "off-target"/"OFF-TARGET". Real B043 panels carry mixed casing in one column; the user selects every
    # casing they mean (each is offered separately in the dropdown) — the block never broadens silently.
    csv = tmp_path / "prop.csv"
    csv.write_text(
        "feature,value\n"
        "AgExact, Off-Target \n"  # surrounding whitespace -> trimmed, matches
        "AgLower,off-target\n"  # lowercase — a DIFFERENT value, not selected
        "AgUpper,OFF-TARGET\n"  # uppercase — a DIFFERENT value, not selected
        "AgOn,Target\n"
    )
    # Only "Off-Target" selected: the exact (whitespace-padded) row matches; the other casings do not.
    assert resolve_offtargets_from_csv(str(csv), {"Off-Target"}) == {"AgExact"}
    # Selecting all three casings explicitly resolves all three.
    assert resolve_offtargets_from_csv(str(csv), {"Off-Target", "off-target", "OFF-TARGET"}) == {
        "AgExact",
        "AgLower",
        "AgUpper",
    }


def test_dominant_offtarget_membership_case_sensitive():
    # Feature-name membership in the offtargets set is whitespace-trimmed but CASE-SENSITIVE (names come
    # from one panel, so they match exactly in practice).
    # Exact name -> excluded: "Off-Target" drops, only "AGX" (3/8 < 0.6) remains -> ambiguous.
    assert dominant_category({"Off-Target": 5, "AGX": 3}, 0.6, offtargets=frozenset({"Off-Target"})) == "ambiguous"
    # Case-differing name -> NOT excluded: "Off-Target" (5/8 >= 0.6) stays a candidate and wins outright.
    assert dominant_category({"Off-Target": 5, "AGX": 3}, 0.6, offtargets=frozenset({"off-target"})) == "Off-Target"


# --- per-clonotype feature breakdown string (F2) ---


def test_feature_breakdown_sorted_desc_with_percents():
    # 61% / 34% / 5% -> dominant first, whole percents.
    s = feature_breakdown({"TgtA_human": 61, "TgtA_cyno": 34, "OT": 5})
    assert s == "TgtA_human (61%), TgtA_cyno (34%), OT (5%)"


def test_feature_breakdown_tiny_fraction_is_lt1():
    # a nonzero feature rounding below 1% shows "<1%", not "0%".
    s = feature_breakdown({"A": 999, "B": 1})
    assert "B (<1%)" in s and s.startswith("A (")


def test_feature_breakdown_empty_when_no_signal():
    assert feature_breakdown({"A": 0}) == ""
    assert feature_breakdown({}) == ""


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


# --- parity vs the verbatim compartment_analysis.py reference ---


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
    annotation_rows=None,
    annotations=None,
    presence_threshold=None,
    offtarget_features=None,
    control_features=None,
    control_rows=None,
):
    linker = tmp_path / "linker.csv"
    _write_csv(linker, ["sampleId", "cellId", "scClonotypeKey"], linker_rows)
    cmd = [
        sys.executable,
        str(SRC),
        "--linker-csv",
        str(linker),
        "--output-prefix",
        str(tmp_path / "result"),
    ]
    # feature is optional: pass feature_rows=None for a VDJ + annotations-only run
    if feature_rows is not None:
        feats = tmp_path / "features.csv"
        _write_csv(feats, ["sampleId", "cellId", "feature", "umiCount"], feature_rows)
        cmd += ["--feature-csv", str(feats)]
    if presence_threshold is not None:
        cmd += ["--presence-threshold", str(presence_threshold)]
    if offtarget_features is not None:
        cmd += ["--offtarget-features", offtarget_features]
    if control_features is not None:
        cmd += ["--control-features", control_features]
    # negative-control marker CSV (feature,value): the dedicated per-feature marker FI emits on the
    # feature axis; features whose value is "true" are the negative control.
    if control_rows is not None:
        control_csv = tmp_path / "control.csv"
        _write_csv(control_csv, ["feature", "value"], control_rows)
        cmd += ["--control-csv", str(control_csv)]
    # annotation manifest: `annotations` (list of (rows, dominance)) takes precedence; else the single
    # `annotation_rows` maps to one entry at dominance 0.6.
    ann_entries = (
        annotations if annotations is not None else ([(annotation_rows, 0.6)] if annotation_rows is not None else [])
    )
    if ann_entries:
        manifest = []
        for i, (rows, dom) in enumerate(ann_entries):
            ann = tmp_path / f"annotation_{i}.csv"
            _write_csv(ann, ["sampleId", "cellId", "value"], rows)
            manifest.append({"csv": str(ann), "key": f"ann{i}", "label": f"ann{i}", "dominance": dom})
        cmd += ["--annotations", json.dumps(manifest)]
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
    assert set(fieldnames) == {
        "scClonotypeKey",
        "restrictionIndex",
        "breadth",
        "dominantFeature",
        "featureBreakdown",
    }


@pytest.mark.slow
def test_cli_all_zero_counts_are_dropped_no_nan(tmp_path):
    # A clonotype whose only feature rows are all-zero UMI has no antigen signal: it must be dropped
    # (sparse), never emit a 0/0=NaN fraction or a null-dtype dominant column.
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


# --- optional annotation branch: dominant cell type per clonotype (dominant-category rule) ---


@pytest.mark.slow
def test_cli_annotation_dominant_cell_type(tmp_path):
    # C1: 2x Tcell + 1x Bcell -> 2/3 = 0.67 >= 0.6 threshold -> Tcell.
    # C2: 1x Tcell -> 1.0 -> Tcell.
    # C3: 1x Tcell + 1x Bcell -> tied at the 0.5 floor, two winners -> "ambiguous".
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
    with open(tmp_path / "result_annotations_wide.csv", newline="") as f:
        rows = {r["scClonotypeKey"]: r["ann0"] for r in csv.DictReader(f)}
    assert rows == {"C1": "Tcell", "C2": "Tcell", "C3": "ambiguous"}


@pytest.mark.slow
def test_cli_annotation_null_values_excluded_from_dominance(tmp_path):
    # Cells with a null annotation value must not count as a competing category. Without dropping them,
    # C1 = {Tcell: 2, null: 2} ties and reads "ambiguous"; dropping nulls leaves {Tcell: 2} -> "Tcell".
    _run_cli(
        tmp_path,
        feature_rows=[("s1", c, "AGX", 5) for c in ("cA", "cB", "cC", "cD")],
        linker_rows=[
            ("s1", "cA", "C1"),
            ("s1", "cB", "C1"),
            ("s1", "cC", "C1"),
            ("s1", "cD", "C1"),
        ],
        annotation_rows=[
            ("s1", "cA", "Tcell"),
            ("s1", "cB", "Tcell"),
            ("s1", "cC", None),
            ("s1", "cD", None),
        ],
    )
    with open(tmp_path / "result_annotations_wide.csv", newline="") as f:
        rows = {r["scClonotypeKey"]: r["ann0"] for r in csv.DictReader(f)}
    assert rows == {"C1": "Tcell"}
    with open(tmp_path / "result_annotation_values.json") as f:
        assert json.load(f)["ann0"] == ["Tcell"]  # null is not a category


@pytest.mark.slow
def test_cli_numeric_annotation_labels_stay_strings(tmp_path):
    # Leiden cluster ids ("0","1") look numeric; they must be treated as string categories, not coerced
    # to Int, which would emit numeric discreteValues that no longer match the String dominant column
    # (breaking the downstream Lead Selection filter).
    _run_cli(
        tmp_path,
        feature_rows=[("s1", c, "AGX", 5) for c in ("cA", "cB", "cC")],
        linker_rows=[("s1", "cA", "C1"), ("s1", "cB", "C1"), ("s1", "cC", "C2")],
        annotation_rows=[("s1", "cA", "0"), ("s1", "cB", "0"), ("s1", "cC", "1")],
    )
    with open(tmp_path / "result_annotations_wide.csv", newline="") as f:
        rows = {r["scClonotypeKey"]: r["ann0"] for r in csv.DictReader(f)}
    assert rows == {"C1": "0", "C2": "1"}
    with open(tmp_path / "result_annotation_values.json") as f:
        vals = json.load(f)["ann0"]
    assert vals == ["0", "1"] and all(isinstance(v, str) for v in vals)  # strings, not ints


@pytest.mark.slow
def test_cli_multiple_annotations(tmp_path):
    # Two annotations folded independently -> one dominant column each (ann0, ann1) in the wide CSV, each
    # with its own distinct-values list. ann0 = cell type, ann1 = cluster.
    _run_cli(
        tmp_path,
        feature_rows=[("s1", c, "AGX", 5) for c in ("cA", "cB", "cC")],
        linker_rows=[("s1", "cA", "C1"), ("s1", "cB", "C1"), ("s1", "cC", "C2")],
        annotations=[
            # ann0 cell type: C1 = 2x Tcell -> Tcell; C2 = 1x Bcell -> Bcell.
            ([("s1", "cA", "Tcell"), ("s1", "cB", "Tcell"), ("s1", "cC", "Bcell")], 0.6),
            # ann1 cluster: C1 = CL0 + CL1 tied at 0.5 floor -> ambiguous; C2 = CL2 -> CL2.
            ([("s1", "cA", "CL0"), ("s1", "cB", "CL1"), ("s1", "cC", "CL2")], 0.6),
        ],
    )
    with open(tmp_path / "result_annotations_wide.csv", newline="") as f:
        rows = {r["scClonotypeKey"]: (r["ann0"], r["ann1"]) for r in csv.DictReader(f)}
    assert rows["C1"] == ("Tcell", "ambiguous")
    assert rows["C2"] == ("Bcell", "CL2")
    with open(tmp_path / "result_annotation_values.json") as f:
        vals = json.load(f)
    assert set(vals["ann0"]) == {"Tcell", "Bcell"}
    assert set(vals["ann1"]) == {"CL0", "CL1", "CL2"}
    # pre-aggregated composition: clonotype count per (annotation, dominant category)
    with open(tmp_path / "result_composition.csv", newline="") as f:
        comp = {(r["annotation"], r["category"]): int(r["count"]) for r in csv.DictReader(f)}
    assert comp == {
        ("ann0", "Tcell"): 1,
        ("ann0", "Bcell"): 1,
        ("ann1", "ambiguous"): 1,
        ("ann1", "CL2"): 1,
    }


@pytest.mark.slow
def test_cli_no_feature_annotation_only(tmp_path):
    # VDJ + annotations only (no feature integration): the run succeeds, emits the annotation output, and
    # does NOT write the feature matrices / properties CSVs.
    _run_cli(
        tmp_path,
        feature_rows=None,
        linker_rows=[("s1", "cA", "C1"), ("s1", "cB", "C1")],
        annotation_rows=[("s1", "cA", "Tcell"), ("s1", "cB", "Tcell")],
    )
    with open(tmp_path / "result_annotations_wide.csv", newline="") as f:
        rows = {r["scClonotypeKey"]: r["ann0"] for r in csv.DictReader(f)}
    assert rows == {"C1": "Tcell"}
    assert not (tmp_path / "result_properties.csv").exists()
    assert not (tmp_path / "result_fractions.csv").exists()


# --- per-antigen fraction columns + feature-names output (one fraction pcolumn per antigen) ---


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
def test_cli_offtarget_dominant_and_breakdown(tmp_path):
    # F2 end-to-end: with --offtarget-features the dominant call excludes off-targets and labels an
    # on-target split as cross-reactive; the featureBreakdown string lists every feature dominant-first.
    # C1: TgtA_human 45 + TgtA_cyno 45 + OT 10 (one cell each, same clonotype) -> cross-reactive.
    # C2: TgtA_human 80 + OT 20 -> single on-target wins.
    _run_cli(
        tmp_path,
        feature_rows=[
            ("s1", "cA", "TgtA_human", 45),
            ("s1", "cA", "TgtA_cyno", 45),
            ("s1", "cA", "OT", 10),
            ("s1", "cB", "TgtA_human", 80),
            ("s1", "cB", "OT", 20),
        ],
        linker_rows=[("s1", "cA", "C1"), ("s1", "cB", "C2")],
        offtarget_features="OT,Decoy1",
    )
    with open(tmp_path / "result_properties.csv", newline="") as f:
        rows = {r["scClonotypeKey"]: r for r in csv.DictReader(f)}
    assert rows["C1"]["dominantFeature"] == CROSS_REACTIVE
    assert rows["C2"]["dominantFeature"] == "TgtA_human"
    # breakdown lists every feature (incl. off-target), dominant first, whole percents.
    # 45/45 tie broken by name ascending (cyno before human); OT last.
    assert rows["C1"]["featureBreakdown"] == "TgtA_cyno (45%), TgtA_human (45%), OT (10%)"
    assert rows["C2"]["featureBreakdown"] == "TgtA_human (80%), OT (20%)"


@pytest.mark.slow
def test_cli_global_presence_threshold(tmp_path):
    # C1: AGX 8 (0.8), BGX 2 (0.2). A global cutoff of 0.3 drops BGX from "present":
    # breadth 2 -> 1, and the dominant call is made over surviving {AGX} -> AGX at 100%.
    _run_cli(
        tmp_path,
        feature_rows=[("s1", "cA", "AGX", 8), ("s1", "cA", "BGX", 2)],
        linker_rows=[("s1", "cA", "C1")],
        presence_threshold=0.3,
    )
    with open(tmp_path / "result_properties.csv", newline="") as f:
        row = next(csv.DictReader(f))
    assert int(row["breadth"]) == 1  # only AGX clears the cutoff
    assert row["dominantFeature"] == "AGX"
    # The raw per-antigen fractions are unaffected by the presence cutoff (they report real signal).
    with open(tmp_path / "result_fractions_wide.csv", newline="") as f:
        wide = next(csv.DictReader(f))
    assert float(wide["BGX"]) == pytest.approx(0.2)


# --- negative-control exclusion (control-aware metrics): the control is FULLY removed from RI, antigen
# breadth, the per-antigen fraction columns, and the dominant call. Off-targets, by contrast, stay in
# the metrics and are only excluded from the dominant winner. ---


@pytest.mark.slow
def test_cli_control_excluded_from_all_metrics(tmp_path):
    # C1: TgtA 8, Ctrl 2 (control designated). The control is not a real antigen: it must not appear as a
    # fraction column, must not count toward RI/breadth, and must not win the dominant call. With Ctrl
    # removed, C1 binds a single antigen -> RI 1.0, breadth 1, dominant TgtA, TgtA fraction 1.0.
    _run_cli(
        tmp_path,
        feature_rows=[("s1", "cA", "TgtA", 8), ("s1", "cA", "Ctrl", 2)],
        linker_rows=[("s1", "cA", "C1")],
        control_features="Ctrl",
    )
    with open(tmp_path / "result_feature_names.json") as f:
        assert json.load(f) == ["TgtA"]  # Ctrl dropped from the feature set entirely
    with open(tmp_path / "result_fractions_wide.csv", newline="") as f:
        wide = {r["scClonotypeKey"]: r for r in csv.DictReader(f)}
    assert set(wide["C1"]) == {"scClonotypeKey", "TgtA"}  # no Ctrl column
    assert float(wide["C1"]["TgtA"]) == pytest.approx(1.0)
    with open(tmp_path / "result_properties.csv", newline="") as f:
        row = next(csv.DictReader(f))
    assert float(row["restrictionIndex"]) == 1.0  # single antigen once control excluded
    assert int(row["breadth"]) == 1
    assert row["dominantFeature"] == "TgtA"
    assert row["featureBreakdown"] == "TgtA (100%)"  # control absent from the breakdown too


@pytest.mark.slow
def test_cli_control_via_marker_csv(tmp_path):
    # The workflow feeds the control as the dedicated per-feature marker CSV (feature,value); only rows
    # whose value is "true" are the control. A non-"true" row must NOT be treated as control.
    _run_cli(
        tmp_path,
        feature_rows=[("s1", "cA", "TgtA", 8), ("s1", "cA", "Ctrl", 2)],
        linker_rows=[("s1", "cA", "C1")],
        control_rows=[("Ctrl", "true"), ("TgtA", "false")],
    )
    with open(tmp_path / "result_feature_names.json") as f:
        assert json.load(f) == ["TgtA"]  # only the value=="true" feature is excluded
    with open(tmp_path / "result_properties.csv", newline="") as f:
        row = next(csv.DictReader(f))
    assert row["dominantFeature"] == "TgtA"
    assert int(row["breadth"]) == 1


@pytest.mark.slow
def test_cli_control_and_offtarget_are_distinct(tmp_path):
    # Control is fully removed; off-target stays IN the metrics but out of the dominant winner.
    # C1: Tgt 50 + OT 30 + Ctrl 20. Control removed -> denominator = Tgt 50 + OT 30 = 80. OT excluded from
    # winners -> Tgt 50/80 = 0.625 >= 0.6 -> dominant Tgt. Breadth counts Tgt + OT (control gone) = 2.
    _run_cli(
        tmp_path,
        feature_rows=[
            ("s1", "cA", "Tgt", 50),
            ("s1", "cB", "OT", 30),
            ("s1", "cC", "Ctrl", 20),
        ],
        linker_rows=[("s1", "cA", "C1"), ("s1", "cB", "C1"), ("s1", "cC", "C1")],
        control_features="Ctrl",
        offtarget_features="OT",
    )
    with open(tmp_path / "result_feature_names.json") as f:
        assert json.load(f) == ["OT", "Tgt"]  # off-target retained, control removed
    with open(tmp_path / "result_fractions_wide.csv", newline="") as f:
        wide = {r["scClonotypeKey"]: r for r in csv.DictReader(f)}
    assert set(wide["C1"]) == {"scClonotypeKey", "OT", "Tgt"}  # OT kept, no Ctrl column
    assert float(wide["C1"]["Tgt"]) == pytest.approx(50 / 80)
    assert float(wide["C1"]["OT"]) == pytest.approx(30 / 80)
    with open(tmp_path / "result_properties.csv", newline="") as f:
        row = next(csv.DictReader(f))
    assert row["dominantFeature"] == "Tgt"
    assert int(row["breadth"]) == 2  # Tgt + OT; control excluded


@pytest.mark.slow
def test_cli_control_only_clonotype_dropped(tmp_path):
    # A clonotype whose only feature signal is the control has no antigen signal once the control is
    # removed -> dropped from the properties (like an all-zero clonotype), never emitted with a null call.
    _run_cli(
        tmp_path,
        feature_rows=[("s1", "cA", "Ctrl", 5), ("s1", "cB", "TgtA", 5)],
        linker_rows=[("s1", "cA", "C1"), ("s1", "cB", "C2")],
        control_features="Ctrl",
    )
    with open(tmp_path / "result_properties.csv", newline="") as f:
        keys = {r["scClonotypeKey"] for r in csv.DictReader(f)}
    assert keys == {"C2"}  # C1 (control-only) dropped
