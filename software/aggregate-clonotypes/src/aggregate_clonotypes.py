"""Per-clonotype aggregation for the VDJ Multiomic Integration block.

Joins per-cell tables to the cell<->clonotype linker on [sampleId, cellId], groups by scClonotypeKey
across samples (no sample axis), and computes the per-clonotype binding profile and properties.

The math functions are ported verbatim from the clonotype-distribution block's compartment_analysis.py,
alongside the dominant-category rule; they are pure and unit-tested. Every output is sorted before
writing for determinism + workflow canonicality.

Presence cutoff: a feature is "present"/bound for a clonotype when its within-clonotype fraction
exceeds the global presence threshold (applied to every feature). Breadth counts present features,
and the dominant-antigen call is made over the present features only. Restriction index is left over
every nonzero feature (it measures raw concentration, not thresholded presence).
"""

import argparse
import json
import math

import polars as pl

DOMINANCE_FLOOR = 0.5


def shannon_entropy(p: list[float]) -> float:
    """Base-2 Shannon entropy. Mirrors compartment_analysis.py:206-211."""
    nz = [x for x in p if x > 0]
    if not nz:
        return 0.0
    total = sum(nz)
    probs = [x / total for x in nz]
    return -sum(x * math.log2(x) for x in probs)


def restriction_index(counts: list[float]) -> float:
    """RI = 1 - H(p)/log2(N), N = number of nonzero categories.
    Mirrors compartment_analysis.py:214-223 (N==0 -> nan, N==1 -> 1.0)."""
    nz = [x for x in counts if x > 0]
    n = len(nz)
    if n == 0:
        return float("nan")
    if n == 1:
        return 1.0
    return 1.0 - shannon_entropy(nz) / math.log2(n)


def breadth(counts: list[float], presence_threshold: float = 0.0) -> int:
    """Number of features whose within-clonotype fraction is strictly > presence_threshold.
    Mirrors compartment_analysis.py:387-389 (strict '>', default 0.0)."""
    total = sum(c for c in counts if c > 0)
    if total <= 0:
        return 0
    return sum(1 for c in counts if (c / total) > presence_threshold)


def present_features(per_feature: dict[str, float], threshold: float) -> dict[str, float]:
    """The subset of per-feature counts whose within-clonotype fraction is strictly greater than the
    presence threshold (applied to every feature). Returns the surviving {feature: count}; empty when
    there is no signal. This is the set breadth counts and the set the dominant-antigen call is made over."""
    total = sum(c for c in per_feature.values() if c > 0)
    if total <= 0:
        return {}
    return {f: c for f, c in per_feature.items() if c > 0 and (c / total) > threshold}


CROSS_REACTIVE = "cross-reactive"


def dominant_category(
    counts: dict[str, float],
    threshold: float,
    offtargets: frozenset[str] = frozenset(),
    label_crossreactive: bool = False,
) -> str | None:
    """Dominant-category rule: unique max with share >= threshold, else 'ambiguous'
    when signal exists, else None. threshold clamped up to the 0.5 floor.

    ``offtargets`` (features designated off-target via the chosen per-feature property — e.g. a Type
    property valued Off-Target / Decoy) are excluded from the
    winner candidates but kept in the denominator, so an off-target-dominated clonotype is "ambiguous",
    never an off-target. Membership is tested whitespace-insensitively but CASE-SENSITIVELY (strip on both
    sides, no case folding); the returned winner stays verbatim.
    When they are supplied and ``label_crossreactive`` is set, a clonotype whose
    on-target signal collectively passes the threshold but is split across >= 2 on-target features is
    "cross-reactive" (a genuine multi-/cross-reactive binder — e.g. a target's human + cyno variants)
    rather than lumped into "ambiguous". With no off-targets designated the rule is unchanged. Mirrors
    the off-target / cross-reactive rule of Feature Integration's consensus_category; unlike FI it takes
    no negative-control parameter, so a control-dominated clonotype is called with the control's own name
    unless the control is also designated off-target."""
    threshold = max(threshold, DOMINANCE_FLOOR)
    positive = {k: v for k, v in counts.items() if v > 0}
    total = sum(positive.values())
    if total <= 0:
        return None
    offtargets_norm = {o.strip() for o in offtargets}
    candidates = {k: v for k, v in positive.items() if k.strip() not in offtargets_norm}
    if not candidates:
        return "ambiguous"  # only off-target signal — no on-target to call
    max_val = max(candidates.values())
    winners = [k for k, v in candidates.items() if v == max_val]
    if len(winners) == 1 and (max_val / total) >= threshold:
        return winners[0]
    if label_crossreactive and len(candidates) >= 2 and (sum(candidates.values()) / total) >= threshold:
        return CROSS_REACTIVE
    return "ambiguous"


def feature_breakdown(per_feature: dict[str, float]) -> str:
    """A readable per-clonotype binding profile: every feature with signal as ``feature (fraction%)``,
    comma-separated and sorted by descending fraction (dominant feature first, name as tie-break).
    Fractions display as whole percents, with "<1%" for a nonzero feature that rounds below 1%. Empty
    string when the clonotype has no signal. Mirrors Feature Integration's per-cell featureSummary so
    the breakdown reads the same at cell and clonotype level (the customer lead-selection ask)."""
    positive = {k: v for k, v in per_feature.items() if v > 0}
    total = sum(positive.values())
    if total <= 0:
        return ""
    entries = []
    for feat, cnt in sorted(positive.items(), key=lambda kv: (-kv[1], kv[0])):
        pct = round(cnt / total * 100)
        pct_str = "<1%" if pct == 0 else f"{pct}%"
        entries.append(f"{feat} ({pct_str})")
    return ", ".join(entries)


def _clonotype_feature_counts(feats: pl.DataFrame, linker: pl.DataFrame) -> pl.DataFrame:
    """(sampleId, cellId, feature, umiCount) join linker (sampleId, cellId, scClonotypeKey) ->
    (scClonotypeKey, feature, count) summed across samples. Inner join drops cells with
    no clonotype; features whose summed count is 0 in a clonotype are dropped too, keeping the
    matrix sparse and avoiding a 0/0 within-clonotype fraction downstream."""
    return (
        feats.join(linker, on=["sampleId", "cellId"], how="inner")
        .group_by(["scClonotypeKey", "feature"])
        .agg(pl.col("umiCount").sum().alias("count"))
        .filter(pl.col("count") > 0)
    )


def resolve_offtargets_from_csv(csv_path: str, wanted: set[str]) -> set[str]:
    """Off-target FEATURE names resolved from a (feature,value) property CSV: the features whose ``value``
    column entry is one of ``wanted``. The workflow exports the chosen per-feature property column here so
    the off-target designation is property-driven (like Feature Integration).

    Values are matched exactly, whitespace-trimmed but CASE-SENSITIVE (strip on BOTH sides, no case
    folding): a feature is off-target only if its ``value`` is byte-identical (after trimming) to one the
    user selected. Real panels (e.g. B043) may carry mixed casing of one designation — ``Off-Target`` and
    ``Off-target`` in a single Type column — so the user selects every casing they mean; each distinct value
    is offered separately in the block's dropdown, and the block never silently broadens a selection to
    unselected values. Whitespace is trimmed (invisible in the picker); casing is left intact (visible, the
    user's to choose). The returned FEATURE names are verbatim (whitespace-trimmed) from the CSV."""
    prop = pl.read_csv(csv_path, schema_overrides={"feature": pl.String, "value": pl.String})
    wanted_norm = [w.strip() for w in wanted]
    return set(prop.filter(pl.col("value").str.strip_chars().is_in(wanted_norm))["feature"].str.strip_chars().to_list())


def _write_sorted(rows: list[dict], schema: dict, out_path: str) -> None:
    """Write per-clonotype rows to CSV sorted by scClonotypeKey. When rows is empty — e.g. the feature
    or annotation cells share no (sampleId, cellId) with the linker, so the inner join is empty —
    pl.DataFrame([]) has no columns and .sort() raises ColumnNotFoundError; fall back to a header-only
    frame built from `schema` so the block emits an empty-but-valid result instead of crashing mid-run."""
    df = pl.DataFrame(rows) if rows else pl.DataFrame(schema=schema)
    df.sort(["scClonotypeKey"]).write_csv(out_path)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--feature-csv", default=None)
    p.add_argument("--linker-csv", required=True)
    p.add_argument(
        "--annotations",
        default=None,
        help="JSON manifest of annotation inputs: [{'csv': ..., 'key': ..., 'dominance': ...}].",
    )
    p.add_argument("--dominance-threshold", type=float, default=0.6)
    p.add_argument("--dominance-threshold-feature", type=float, default=None)
    p.add_argument("--presence-threshold", type=float, default=0.0)
    p.add_argument(
        "--offtarget-features",
        default=None,
        help="comma-separated feature names designated off-target. Excluded from the dominant-feature "
        "call (like a control) and, when present, enable the cross-reactive label.",
    )
    p.add_argument(
        "--offtarget-property-csv",
        default=None,
        help="a (feature,value) CSV of the designated per-feature property; features whose value is in "
        "--offtarget-values are resolved to the off-target set. The workflow exports the chosen feature-"
        "property column here so the off-target designation is property-driven (like Feature Integration).",
    )
    p.add_argument(
        "--offtarget-values",
        default=None,
        help="comma-separated values of the --offtarget-property-csv value column that mark a feature "
        "as off-target (e.g. 'Off-Target,Decoy').",
    )
    p.add_argument("--output-prefix", default="result")
    args = p.parse_args()

    # Off-target feature set (F2). Two sources, unioned: an explicit --offtarget-features name list, and a
    # property-driven resolution — a (feature,value) CSV of the chosen per-feature property, keeping only
    # features whose value is in --offtarget-values. Off-targets are excluded from the dominant-feature
    # call (kept in the denominator) and, when any exist, enable the cross-reactive label. Empty -> unchanged.
    offtargets = (
        set(f.strip() for f in args.offtarget_features.split(",") if f.strip()) if args.offtarget_features else set()
    )
    if (args.offtarget_property_csv is None) != (args.offtarget_values is None):
        raise SystemExit("--offtarget-property-csv and --offtarget-values must be given together")
    if args.offtarget_property_csv is not None:
        wanted = {v.strip() for v in args.offtarget_values.split(",") if v.strip()}
        offtargets |= resolve_offtargets_from_csv(args.offtarget_property_csv, wanted)
    offtargets = frozenset(offtargets)
    label_crossreactive = len(offtargets) > 0

    # Feature dominance threshold, falling back to the shared --dominance-threshold. Each annotation
    # carries its own dominance in the --annotations manifest.
    feature_dominance = (
        args.dominance_threshold_feature if args.dominance_threshold_feature is not None else args.dominance_threshold
    )

    # Read each input CSV once. The linker feeds the feature aggregation and (optionally) the annotation
    # join below; reading it a single time avoids re-parsing a per-cell table (one row per cell) more
    # than once in a 16 GiB run.
    # Force identifier / label columns to String: barcodes, sample ids and categorical labels (e.g.
    # Leiden cluster ids "0","1") look numeric to CSV type inference, which would coerce them to Int and
    # both break the String-typed dominant column and mismatch join keys across the per-cell tables.
    linker = pl.read_csv(
        args.linker_csv,
        schema_overrides={"sampleId": pl.String, "cellId": pl.String, "scClonotypeKey": pl.String},
    )  # sampleId, cellId, scClonotypeKey

    # Feature (antigen) aggregation is optional: the block also runs on VDJ + annotations with no feature
    # integration. When a feature CSV is present, emit the count / fraction matrices and the per-clonotype
    # properties (RI, breadth, dominant feature); otherwise skip them.
    feature_names: list[str] = []
    if args.feature_csv is not None:
        cf = _clonotype_feature_counts(
            pl.read_csv(
                args.feature_csv,
                schema_overrides={"sampleId": pl.String, "cellId": pl.String, "feature": pl.String},
            ),
            linker,
        )
        feature_names = sorted(cf["feature"].unique().to_list()) if not cf.is_empty() else []

        # advanced count matrix (clonotype x feature)
        (
            cf.select(["scClonotypeKey", "feature", "count"])
            .sort(["scClonotypeKey", "feature"])
            .write_csv(f"{args.output_prefix}_counts.csv")
        )

        # per-feature fractions, long (clonotype x feature) — drives the in-block property heatmap
        frac_long = cf.with_columns((pl.col("count") / pl.col("count").sum().over("scClonotypeKey")).alias("fraction"))
        (
            frac_long.select(["scClonotypeKey", "feature", "fraction"])
            .sort(["scClonotypeKey", "feature"])
            .write_csv(f"{args.output_prefix}_fractions.csv")
        )

        # per-feature fractions, wide (one column per antigen, keyed [scClonotypeKey]) — each becomes a
        # per-clonotype scalar column for Lead Selection. Clonotypes with no signal for an antigen get 0.
        if feature_names:
            wide = (
                frac_long.pivot(on="feature", index="scClonotypeKey", values="fraction")
                .fill_null(0.0)
                .select(["scClonotypeKey", *feature_names])
                .sort("scClonotypeKey")
            )
        else:
            wide = pl.DataFrame(schema={"scClonotypeKey": pl.String})
        wide.write_csv(f"{args.output_prefix}_fractions_wide.csv")

        # per-clonotype scalar properties: RI, breadth, dominant feature. Breadth and the dominant call
        # use the present features (presence cutoff); RI is over every nonzero feature.
        prop_rows = []
        for (clono,), grp in cf.group_by(["scClonotypeKey"]):
            counts = grp["count"].to_list()
            per_feature = dict(zip(grp["feature"].to_list(), counts))
            present = present_features(per_feature, args.presence_threshold)
            prop_rows.append(
                {
                    "scClonotypeKey": clono,
                    "restrictionIndex": restriction_index(counts),
                    "breadth": len(present),
                    # off-target-aware dominant call (F2): off-targets excluded from winners; a clonotype
                    # whose on-target signal is split across >= 2 targets is "cross-reactive".
                    "dominantFeature": dominant_category(
                        present, feature_dominance, offtargets=offtargets, label_crossreactive=label_crossreactive
                    ),
                    # readable per-clonotype binding profile (all features, dominant first) — mirrors FI's
                    # per-cell featureSummary; the customer lead-selection breakdown ask.
                    "featureBreakdown": feature_breakdown(per_feature),
                }
            )
        _write_sorted(
            prop_rows,
            {
                "scClonotypeKey": pl.String,
                "restrictionIndex": pl.Float64,
                "breadth": pl.Int64,
                "dominantFeature": pl.String,
                "featureBreakdown": pl.String,
            },
            f"{args.output_prefix}_properties.csv",
        )

    # distinct feature names (empty when no feature integration) — for the dominant-antigen discreteValues
    # and the per-antigen fraction columns downstream.
    with open(f"{args.output_prefix}_feature_names.json", "w") as f:
        json.dump(feature_names, f)

    # annotations (0..N): each folds onto clonotypes by the dominant-category rule with its own dominance
    # threshold. Emitted as one wide CSV (a dominant column per annotation key, keyed [scClonotypeKey]) plus
    # a {key: distinct values} map for the downstream discreteValues multi-select. Column value header in
    # each input CSV is "value" (generic across cell type, cluster id, or any categorical annotation).
    annotation_manifest = json.loads(args.annotations) if args.annotations else []
    annotation_values: dict[str, list[str]] = {}
    # Composition rows (annotation label, dominant category, clonotype count) — the aggregated table the
    # Composition stacked bar plots. Pre-aggregated here (not per clonotype) so it stays tiny regardless of
    # dataset size: at most #annotations x #categories rows.
    composition_rows: list[dict] = []
    if annotation_manifest:
        # base of every clonotype so an annotation missing for a clonotype yields null
        wide_ann = linker.select("scClonotypeKey").unique()
        for entry in annotation_manifest:
            key = entry["key"]
            dom = entry["dominance"]
            label = entry["label"]
            # drop cells with a null annotation value so None never competes as a category in the
            # dominance calc (a clonotype whose cells are all null then gets a null dominant call)
            ann = (
                pl.read_csv(
                    entry["csv"],
                    schema_overrides={"sampleId": pl.String, "cellId": pl.String, "value": pl.String},
                )
                .join(linker, on=["sampleId", "cellId"], how="inner")
                .filter(pl.col("value").is_not_null())
            )
            annotation_values[key] = sorted(v for v in ann["value"].unique().to_list() if v is not None)
            rows = []
            for (clono,), grp in ann.group_by(["scClonotypeKey"]):
                vc = grp["value"].value_counts()
                d = dict(zip(vc["value"].to_list(), vc["count"].to_list()))
                rows.append({"scClonotypeKey": clono, key: dominant_category(d, dom)})
            df = pl.DataFrame(rows, schema={"scClonotypeKey": pl.String, key: pl.String})
            wide_ann = wide_ann.join(df, on="scClonotypeKey", how="left")
            # clonotype count per dominant category (drop null = clonotypes with no cells for this annotation)
            comp = df.filter(pl.col(key).is_not_null()).group_by(key).agg(pl.len().alias("count"))
            for cat, n in zip(comp[key].to_list(), comp["count"].to_list()):
                composition_rows.append({"annotation": label, "category": cat, "count": n})
        wide_ann.sort("scClonotypeKey").write_csv(f"{args.output_prefix}_annotations_wide.csv")

    # {key: distinct annotation values} for the per-annotation dominant column discreteValues (downstream
    # multi-select). Empty map when no annotation is integrated.
    with open(f"{args.output_prefix}_annotation_values.json", "w") as f:
        json.dump(annotation_values, f)

    # composition-count table for the Composition stacked bar (one row per annotation x category). Empty
    # (header-only) when no annotation is integrated.
    comp_schema = {"annotation": pl.String, "category": pl.String, "count": pl.Int64}
    comp_df = (
        pl.DataFrame(composition_rows, schema=comp_schema) if composition_rows else pl.DataFrame(schema=comp_schema)
    )
    comp_df.sort(["annotation", "category"]).write_csv(f"{args.output_prefix}_composition.csv")


if __name__ == "__main__":
    main()
