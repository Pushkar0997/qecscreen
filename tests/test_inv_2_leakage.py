"""INV-2-T: no construction program is on both sides of any split (M0-SPLIT-02).

``test_no_program_leakage`` (CONTRACT INV-2's name) runs every splitter
``qecscreen.splits`` exports over frames keyed on the M0 programs, uneven
program sizes, every admissible fold count and shuffled row orders. The
leakage check is itself tested: it fires on a row-level split of the same
frame, so an empty intersection is a property of the splitter, not of a check
that cannot fail.
"""

import numpy as np
import pandas as pd
import pytest
from sklearn.model_selection import KFold

from qecscreen import splits
from qecscreen.codes.sample import TEMPLATES

PROGRAMS = [f"bb_v1_{name}" for name, _, _ in TEMPLATES]


def _frame(seed: int) -> pd.DataFrame:
    """Rows keyed on the M0 programs, 1..40 rows each, in a shuffled order."""
    rng = np.random.default_rng(seed)
    programs = [p for p in PROGRAMS for _ in range(int(rng.integers(1, 41)))]
    rng.shuffle(programs)
    return pd.DataFrame({
        "code_id": [f"{p}-{i:012x}" for i, p in enumerate(programs)],
        "construction_program_id": programs,
    })


def _leaked_programs(df: pd.DataFrame, train: np.ndarray, test: np.ndarray) -> set[str]:
    return set(df.iloc[train]["construction_program_id"]) & set(df.iloc[test]["construction_program_id"])


def _every_split(df: pd.DataFrame):
    for name in splits.__all__:
        splitter = getattr(splits, name)
        for n_splits in range(2, df["construction_program_id"].nunique() + 1):
            for train, test in splitter(df, n_splits):
                yield name, n_splits, train, test


@pytest.mark.parametrize("seed", range(5))
def test_no_program_leakage(seed):
    df = _frame(seed)
    count = 0
    for name, n_splits, train, test in _every_split(df):
        assert _leaked_programs(df, train, test) == set(), f"{name}(n_splits={n_splits}) leaks"
        assert len(train) and len(test)
        count += 1
    assert count == sum(range(2, len(PROGRAMS) + 1))


def test_the_leakage_check_fires_on_a_row_split():
    df = _frame(0)
    leaked = set()
    for train, test in KFold(n_splits=5, shuffle=True, random_state=0).split(df):
        leaked |= _leaked_programs(df, train, test)
    assert leaked, "a row-level split of this frame must put some program on both sides"
