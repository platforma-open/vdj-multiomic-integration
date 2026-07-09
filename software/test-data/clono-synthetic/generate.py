"""Regenerate the synthetic per-clonotype test bed.

Run from this directory:  python generate.py

C1 spans two samples (cross-sample pooling); C2 is single-feature; cellZ is unlinked (dropped by the
inner join). See README.md for the hand-computed expected metrics.
"""

# (sampleId, cellId, feature, umiCount)
FEATURES = [
    ("s1", "cellA", "AGX", 4),
    ("s1", "cellA", "BGX", 1),
    ("s2", "cellB", "AGX", 4),
    ("s2", "cellB", "BGX", 1),
    ("s1", "cellC", "AGX", 5),
    ("s1", "cellZ", "AGX", 3),  # not in the linker -> dropped
]

# (sampleId, cellId, scClonotypeKey)
LINKER = [
    ("s1", "cellA", "C1"),
    ("s2", "cellB", "C1"),
    ("s1", "cellC", "C2"),
]


def main() -> None:
    with open("features.csv", "w") as f:
        f.write("sampleId,cellId,feature,umiCount\n")
        for s, c, feat, n in FEATURES:
            f.write(f"{s},{c},{feat},{n}\n")
    with open("linker.csv", "w") as f:
        f.write("sampleId,cellId,scClonotypeKey\n")
        for s, c, k in LINKER:
            f.write(f"{s},{c},{k}\n")


if __name__ == "__main__":
    main()
