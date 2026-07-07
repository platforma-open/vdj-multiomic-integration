"""Per-clonotype aggregation for the VDJ Multiomic Integration block.

Joins per-cell tables to the cell<->clonotype linker on [sampleId, cellId], groups by scClonotypeKey
across samples (spec A-0005, no sample axis), and computes the per-clonotype binding profile and
properties.

The math functions are ported verbatim from the clonotype-distribution block's compartment_analysis.py
(spec A-0013) and the dominant-category rule (spec A-0012); they are pure and unit-tested. Every output
is sorted before writing for determinism + workflow canonicality.
"""

import argparse
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
    p.add_argument("--feature-csv", required=True)
    p.add_argument("--linker-csv", required=True)
    p.add_argument("--gex-csv", default=None)
    p.add_argument("--annotation-csv", default=None)
    p.add_argument("--dominance-threshold", type=float, default=0.6)
    p.add_argument("--presence-threshold", type=float, default=0.0)
    p.add_argument("--expression-method", choices=["mean", "max"], default="mean")
    p.add_argument("--output-prefix", default="result")
    args = p.parse_args()

    # Read each input CSV once. The linker feeds the feature aggregation and (optionally) the GEX and
    # annotation joins below; reading it a single time avoids re-parsing a per-cell table (one row per
    # cell) up to three times in a 16 GiB run.
    linker = pl.read_csv(args.linker_csv)  # sampleId, cellId, scClonotypeKey
    cf = _clonotype_feature_counts(pl.read_csv(args.feature_csv), linker)

    # advanced count matrix (clonotype x feature)
    (
        cf.select(["scClonotypeKey", "feature", "count"])
        .sort(["scClonotypeKey", "feature"])
        .write_csv(f"{args.output_prefix}_counts.csv")
    )

    # per-feature fractions
    (
        cf.with_columns((pl.col("count") / pl.col("count").sum().over("scClonotypeKey")).alias("fraction"))
        .select(["scClonotypeKey", "feature", "fraction"])
        .sort(["scClonotypeKey", "feature"])
        .write_csv(f"{args.output_prefix}_fractions.csv")
    )

    # per-clonotype scalar properties: RI, breadth, dominant feature
    prop_rows = []
    for (clono,), grp in cf.group_by(["scClonotypeKey"]):
        counts = grp["count"].to_list()
        per_feature = dict(zip(grp["feature"].to_list(), counts))
        prop_rows.append(
            {
                "scClonotypeKey": clono,
                "restrictionIndex": restriction_index(counts),
                "breadth": breadth(counts, args.presence_threshold),
                "dominantFeature": dominant_category(per_feature, args.dominance_threshold),
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
    if args.annotation_csv is not None:
        ann = pl.read_csv(args.annotation_csv).join(linker, on=["sampleId", "cellId"], how="inner")
        ann_rows = []
        for (clono,), grp in ann.group_by(["scClonotypeKey"]):
            vc = grp["cellType"].value_counts()
            d = dict(zip(vc["cellType"].to_list(), vc["count"].to_list()))
            ann_rows.append(
                {"scClonotypeKey": clono, "dominantCellType": dominant_category(d, args.dominance_threshold)}
            )
        _write_sorted(
            ann_rows,
            {"scClonotypeKey": pl.String, "dominantCellType": pl.String},
            f"{args.output_prefix}_annotation.csv",
        )


if __name__ == "__main__":
    main()
