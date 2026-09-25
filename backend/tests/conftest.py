"""Build a small end-to-end pipeline once and point the API at it."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.app.services.store import DataStore, set_store
from backend.main import create_app
from ml.data.official.load import OfficialStatement
from ml.data.synthetic import SyntheticGenerator, write_outputs
from ml.inference.predict import generate_predictions, write_predictions
from ml.pipeline import load_inputs
from ml.preprocessing.grid import Grid
from ml.preprocessing.pipeline import preprocess
from ml.tests.conftest import make_small_config
from ml.training.train import train_models


@pytest.fixture(scope="session")
def api_cfg(tmp_path_factory):
    cfg = make_small_config(tmp_path_factory.mktemp("crimex-api"))
    grid = Grid.build(cfg.region, cfg.grid)
    stmt = OfficialStatement.load(cfg.paths.official_statement)
    write_outputs(SyntheticGenerator(cfg, grid, stmt).generate(), cfg.paths.raw_dir)
    preprocess(cfg)
    inputs = load_inputs(cfg)
    bundle = train_models(inputs, log=lambda _: None)
    bundle.save(cfg.paths.artifacts_dir / "models")
    write_predictions(generate_predictions(inputs, bundle), cfg.paths.artifacts_dir / "predictions")
    return cfg


@pytest.fixture(scope="session")
def client(api_cfg):
    set_store(DataStore(api_cfg))
    with TestClient(create_app()) as c:
        yield c
    set_store(None)


@pytest.fixture(scope="session")
def meta(client):
    return client.get("/api/v1/meta").json()
