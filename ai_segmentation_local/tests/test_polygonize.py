"""Unit test for mask_to_rings that runs without QGIS.

Run with: python3 tests/test_polygonize.py
Requires numpy and opencv-python-headless (pip install numpy opencv-python-headless).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main():
    import numpy as np

    from core.polygonize import mask_to_rings

    mask = np.zeros((100, 120), dtype=bool)
    mask[20:60, 30:90] = True
    gt = [1000.0, 2.0, 0.0, 5000.0, 0.0, -2.0]

    rings = mask_to_rings(mask, gt, min_area_px=10)
    assert len(rings) == 1, "expected 1 ring, got %d" % len(rings)
    ring = rings[0]
    assert ring[0] == ring[-1], "ring must be closed"
    xs = [p[0] for p in ring]
    ys = [p[1] for p in ring]
    assert min(xs) >= 1000.0 + 29 * 2.0 - 1e-6
    assert max(xs) <= 1000.0 + 90 * 2.0 + 1e-6
    assert max(ys) <= 5000.0 - 19 * 2.0 + 1e-6
    assert min(ys) >= 5000.0 - 60 * 2.0 - 1e-6

    empty = mask_to_rings(np.zeros((10, 10), dtype=bool), gt)
    assert empty == [], "empty mask must give no rings"

    print("test_polygonize: OK")


if __name__ == "__main__":
    main()
