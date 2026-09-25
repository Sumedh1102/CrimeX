from __future__ import annotations

import numpy as np

from ml.config import load_config
from ml.preprocessing.geometry import points_in_polygon
from ml.preprocessing.grid import Grid


def test_points_in_polygon_square():
    square = [[0, 0], [1, 0], [1, 1], [0, 1]]
    inside = points_in_polygon(np.array([0.5, 1.5, 0.1]), np.array([0.5, 0.5, 0.9]), square)
    assert inside.tolist() == [True, False, True]


def test_default_grid_covers_mumbai_study_region():
    cfg = load_config()
    g = Grid.build(cfg.region, cfg.grid)
    assert 150 < g.n_zones < 300
    assert g.zone_ids[0] == "Z001"
    # zone numbering follows reading order from the north-west
    order = g.rows * g.n_cols + g.cols
    assert np.all(np.diff(order) > 0)
    # a point in the Arabian Sea is outside, a point in the city is inside
    idx = g.point_to_zone_index(np.array([19.0, 19.05]), np.array([72.70, 72.86]))
    assert idx[0] == -1 and idx[1] >= 0


def test_centroids_map_to_their_own_zone(small_grid):
    idx = small_grid.point_to_zone_index(small_grid.centroid_lat, small_grid.centroid_lon)
    assert np.array_equal(idx, np.arange(small_grid.n_zones))


def test_neighbors_symmetric_and_exclude_self(small_grid):
    i, j, d = small_grid.neighbors(1)
    pairs = set(zip(i.tolist(), j.tolist(), strict=True))
    assert all((b, a) in pairs for a, b in pairs)
    assert all(a != b for a, b in pairs)
    assert np.all(d > 0)


def test_weight_matrices(small_grid):
    w = small_grid.binary_weights(1, include_self=True)
    assert np.allclose(np.diag(w), 1)
    assert np.allclose(w, w.T)
    idw = small_grid.inverse_distance_weights(2, eps_km=0.1)
    assert np.allclose(np.diag(idw), 0)
    assert idw.max() > 0
