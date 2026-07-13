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


def dominant_category(counts: dict[str, float], threshold: float) -> str | None:
    """Dominant-category rule: unique max with share >= threshold, else 'ambiguous'
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
    (scClonotypeKey, feature, count) summed across samples. Inner join drops cells with
    no clonotype; features whose summed count is 0 in a clonotype are dropped too, keeping the
    matrix sparse and avoiding a 0/0 within-clonotype fraction downstream."""
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
    p.add_argument(
        "--annotations",
        default=None,
        help="JSON manifest of annotation inputs: [{'csv': ..., 'key': ..., 'dominance': ...}].",
    )
    p.add_argument("--dominance-threshold", type=float, default=0.6)
    p.add_argument("--dominance-threshold-feature", type=float, default=None)
    p.add_argument("--presence-threshold", type=float, default=0.0)
    p.add_argument("--output-prefix", default="result")
    args = p.parse_args()

    # Feature dominance threshold, falling back to the shared --dominance-threshold. Each annotation
    # carries its own dominance in the --annotations manifest.
    feature_dominance = (
        args.dominance_threshold_feature if args.dominance_threshold_feature is not None else args.dominance_threshold
    )

    # Read each input CSV once. The linker feeds the feature aggregation and (optionally) the GEX and
    # annotation joins below; reading it a single time avoids re-parsing a per-cell table (one row per
    # cell) up to three times in a 16 GiB run.
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
