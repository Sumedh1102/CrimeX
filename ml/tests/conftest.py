"""Shared fixtures: a small, fast configuration and a generated dataset."""

from __future__ import annotations

import pytest

from ml.config import PlatformConfig, load_config
from ml.data.official.load import OfficialStatement
from ml.data.synthetic import SyntheticGenerator, write_outputs
from ml.preprocessing.grid import Grid
from ml.preprocessing.pipeline import preprocess


def make_small_config(root) -> PlatformConfig:
    return load_config(
        None,
        grid__cell_size_m=3000,
        synthetic__start_date="2023-01-01",
        synthetic__n_stations=5,
        training__xgb__n_estimators=60,
        training__rf__n_estimators=30,
        training__rf__max_train_rows=50_000,
        paths__data_dir=str(root / "data"),
        paths__artifacts_dir=str(root / "artifacts"),
    )


@pytest.fixture(scope="session")
def small_cfg(tmp_path_factory) -> PlatformConfig:
    return make_small_config(tmp_path_factory.mktemp("crimex"))


@pytest.fixture(scope="session")
def small_grid(small_cfg) -> Grid:
    return Grid.build(small_cfg.region, small_cfg.grid)


@pytest.fixture(scope="session")
def generated(small_cfg, small_grid):
    stmt = OfficialStatement.load(small_cfg.paths.official_statement)
    result = SyntheticGenerator(small_cfg, small_grid, stmt).generate()
    write_outputs(result, small_cfg.paths.raw_dir)
    return result


@pytest.fixture(scope="session")
def processed(small_cfg, generated):
    return preprocess(small_cfg)
