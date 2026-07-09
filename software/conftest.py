"""Shared fixtures for the VDJ Multiomic Integration software tests.

A conftest.py at the software root is auto-applied to every test below it (fixtures consumed by name,
never via ``import conftest``). The committed test bed lives at software/test-data/clono-synthetic/:
a per-cell feature CSV (sampleId, cellId, feature, umiCount) and a cell<->clonotype linker CSV
(sampleId, cellId, scClonotypeKey).
"""

import pathlib

import pytest

BED = pathlib.Path(__file__).resolve().parent / "test-data" / "clono-synthetic"


@pytest.fixture(scope="session")
def features_csv():
    p = BED / "features.csv"
    if not p.exists():
        pytest.fail(
            f"committed test bed missing at {p}; restore software/test-data/clono-synthetic/",
            pytrace=False,
        )
    return p


@pytest.fixture(scope="session")
def linker_csv():
    p = BED / "linker.csv"
    if not p.exists():
        pytest.fail(
            f"committed test bed missing at {p}; restore software/test-data/clono-synthetic/",
            pytrace=False,
        )
    return p
