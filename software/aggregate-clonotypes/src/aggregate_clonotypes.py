"""Per-clonotype aggregation for the VDJ Multiomic Integration block.

Joins per-cell tables to the cell<->clonotype linker on [sampleId, cellId], groups by scClonotypeKey
across samples (spec A-0005, no sample axis), and computes the per-clonotype binding profile and
properties.

The math functions are ported verbatim from the clonotype-distribution block's compartment_analysis.py
(spec A-0013) and the dominant-category rule (spec A-0012); they are pure and unit-tested. Every output
is sorted before writing for determinism + workflow canonicality.

Per-antigen presence cutoff: a feature is "present"/bound for a clonotype when its within-clonotype
fraction exceeds that feature's presence threshold (a per-antigen map, falling back to a global
default). Breadth counts present features, and the dominant-antigen call is made over the present
features only. Restriction index is left over every nonzero feature (it measures raw concentration,
not thresholded presence).
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


def present_features(
    per_feature: dict[str, float],
    thresholds: dict[str, float],
    default_threshold: float,
) -> dict[str, float]:
    """The subset of per-feature counts whose within-clonotype fraction is strictly greater than that
    feature's presence threshold (per-antigen map, falling back to default_threshold). Returns the
    surviving {feature: count}; empty when there is no signal. This is the set breadth counts and the
    set the dominant-antigen call is made over."""
    total = sum(c for c in per_feature.values() if c > 0)
    if total <= 0:
        return {}
    return {f: c for f, c in per_feature.items() if c > 0 and (c / total) > thresholds.get(f, default_threshold)}


def dominant_category(counts: dict[str, float], threshold: float) -> str | None:
    """Dominant-category rule (spec A-0012): unique max with share >= threshold, else 'ambiguous'
    when signal exists, else None. threshold clamped up to the 0.5 floor."""
    threshold = max(threshold, DOMINANCE_FLOOR)
    positive = {k: v for k, v in counts.items() if v > 0}
    total = sum(positive.values())
    if total <= 0:
        return None
    max_val = max(positive.values())
    winners = [k for k, v in positive.items() if v == max_val]
    if len(winners) == 1 and (max_val / total) >= threshold:
        return winners[0]
    return "ambiguous"


def _load_presence_thresholds(spec: str | None) -> dict[str, float]:
    """Parse the optional per-antigen presence-threshold map (inline JSON object feature -> threshold).
    Absent or empty -> {}, so every feature falls back to the global --presence-threshold default."""
    if spec is None or spec == "":
        return {}
    raw = json.loads(spec)
    return {str(k): float(v) for k, v in raw.items()}


def _clonotype_feature_counts(feats: pl.DataFrame, linker: pl.DataFrame) -> pl.DataFrame:
    """(sampleId, cellId, feature, umiCount) join linker (sampleId, cellId, scClonotypeKey) ->
    (scClonotypeKey, feature, count) summed across samples (spec A-0005). Inner join drops cells with
    no clonotype (DP-4); features whose summed count is 0 in a clonotype are dropped too, keeping the
    matrix sparse per DP-4 and avoiding a 0/0 within-clonotype fraction downstream."""
    return (
        feats.join(linker, on=["sampleId", "cellId"], how="inner")
        .group_by(["scClonotypeKey", "feature"])
        .agg(pl.col("umiCount").sum().alias("count"))
        .filter(pl.col("count") > 0)
    )


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
    p.add_argument("--gex-csv", default=None)
    p.add_argument("--annotation-csv", default=None)
    p.add_argument("--dominance-threshold", type=float, default=0.6)
    p.add_argument("--dominance-threshold-feature", type=float, default=None)
    p.add_argument("--dominance-threshold-annotation", type=float, default=None)
    p.add_argument("--presence-threshold", type=float, default=0.0)
    p.add_argument(
        "--presence-thresholds",
        default=None,
        help="Optional inline JSON: per-antigen presence-threshold map {feature: threshold}. Features "
        "not listed fall back to --presence-threshold.",
    )
    p.add_argument("--expression-method", choices=["mean", "max"], default="mean")
    p.add_argument("--output-prefix", default="result")
    args = p.parse_args()

    presence_thresholds = _load_presence_thresholds(args.presence_thresholds)

    # Dominance threshold per dominant-category call: features and annotations each carry their own,
    # falling back to the shared --dominance-threshold when their specific value is absent.
    feature_dominance = (
        args.dominance_threshold_feature
        if args.dominance_threshold_feature is not None
        else args.dominance_threshold
    )
    annotation_dominance = (
        args.dominance_threshold_annotation
        if args.dominance_threshold_annotation is not None
        else args.dominance_threshold
    )

    # Read each input CSV once. The linker feeds the feature aggregation and (optionally) the GEX and
    # annotation joins below; reading it a single time avoids re-parsing a per-cell table (one row per
    # cell) up to three times in a 16 GiB run.
    linker = pl.read_csv(args.linker_csv)  # sampleId, cellId, scClonotypeKey

    # Feature (antigen) aggregation is optional: the block also runs on VDJ + annotations with no feature
    # integration. When a feature CSV is present, emit the count / fraction matrices and the per-clonotype
    # properties (RI, breadth, dominant feature); otherwise skip them.
    feature_names: list[str] = []
    if args.feature_csv is not None:
        cf = _clonotype_feature_counts(pl.read_csv(args.feature_csv), linker)
        feature_names = sorted(cf["feature"].unique().to_list()) if not cf.is_empty() else []

        # advanced count matrix (clonotype x feature)
        (
            cf.select(["scClonotypeKey", "feature", "count"])
            .sort(["scClonotypeKey", "feature"])
            .write_csv(f"{args.output_prefix}_counts.csv")
        )

        # per-feature fractions, long (clonotype x feature) — drives the in-block property heatmap
        frac_long = cf.with_columns(
            (pl.col("count") / pl.col("count").sum().over("scClonotypeKey")).alias("fraction")
        )
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
            present = present_features(per_feature, presence_thresholds, args.presence_threshold)
            prop_rows.append(
                {
                    "scClonotypeKey": clono,
                    "restrictionIndex": restriction_index(counts),
                    "breadth": len(present),
                    "dominantFeature": dominant_category(present, feature_dominance),
                }
            )
        _write_sorted(
            prop_rows,
            {
                "scClonotypeKey": pl.String,
                "restrictionIndex": pl.Float64,
                "breadth": pl.Int64,
                "dominantFeature": pl.String,
            },
            f"{args.output_prefix}_properties.csv",
        )

    # distinct feature names (empty when no feature integration) — for the dominant-antigen discreteValues
    # and the per-antigen fraction columns downstream.
    with open(f"{args.output_prefix}_feature_names.json", "w") as f:
        json.dump(feature_names, f)

    # optional GEX: mean/max per (clonotype, gene)
    if args.gex_csv is not None:
        gex = pl.read_csv(args.gex_csv).join(linker, on=["sampleId", "cellId"], how="inner")
        agg = pl.col("count").mean() if args.expression_method == "mean" else pl.col("count").max()
        (
            gex.group_by(["scClonotypeKey", "geneId"])
            .agg(agg.alias("expression"))
            .sort(["scClonotypeKey", "geneId"])
            .write_csv(f"{args.output_prefix}_expression.csv")
        )

    # optional annotation: dominant cell type per clonotype (dominant-category rule)
    annotation_values: list[str] = []
    if args.annotation_csv is not None:
        ann = pl.read_csv(args.annotation_csv).join(linker, on=["sampleId", "cellId"], how="inner")
        annotation_values = sorted(v for v in ann["cellType"].unique().to_list() if v is not None)
        ann_rows = []
        for (clono,), grp in ann.group_by(["scClonotypeKey"]):
            vc = grp["cellType"].value_counts()
            d = dict(zip(vc["cellType"].to_list(), vc["count"].to_list()))
            ann_rows.append(
                {"scClonotypeKey": clono, "dominantCellType": dominant_category(d, annotation_dominance)}
            )
        _write_sorted(
            ann_rows,
            {"scClonotypeKey": pl.String, "dominantCellType": pl.String},
            f"{args.output_prefix}_annotation.csv",
        )

    # distinct annotation values, for the dominant-cell-type column's discreteValues (downstream
    # multi-select filter). Empty list when no annotation is integrated.
    with open(f"{args.output_prefix}_annotation_values.json", "w") as f:
        json.dump(annotation_values, f)


if __name__ == "__main__":
    main()
