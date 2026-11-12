def mask_to_rings(mask, gt, min_area_px=16, epsilon=0.8):
    """Convert a boolean mask to world-coordinate polygon rings.

    mask: 2D boolean/uint8 array. gt: GDAL-style affine from
    crop_raster_to_image: [x_min, px_w, rot1, y_max, rot2, -px_h], so
    X = gt[0] + col * gt[1], Y = gt[3] + row * gt[5].
    Returns a list of rings, each a list of (x, y) tuples in layer CRS,
    closed (first point repeated at the end).
    """
    import cv2
    import numpy as np

    m = (np.asarray(mask) > 0).astype(np.uint8) * 255
    contours, _hierarchy = cv2.findContours(
        m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )
    rings = []
    for contour in contours:
        if len(contour) < 3 or cv2.contourArea(contour) < min_area_px:
            continue
        approx = cv2.approxPolyDP(contour, epsilon, True)
        if len(approx) < 3:
            approx = contour
        ring = [
            (gt[0] + float(p[0][0]) * gt[1], gt[3] + float(p[0][1]) * gt[5])
            for p in approx
        ]
        ring.append(ring[0])
        rings.append(ring)
    return rings


def rings_to_geometry(rings):
    from qgis.core import QgsGeometry, QgsPointXY

    if not rings:
        return None
    polygon = [[QgsPointXY(x, y) for x, y in ring] for ring in rings]
    return QgsGeometry.fromPolygonXY(polygon)
