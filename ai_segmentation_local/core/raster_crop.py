from qgis.PyQt.QtCore import QSize, Qt
from qgis.PyQt.QtGui import QImage, QPainter
from qgis.core import QgsMapRendererCustomPainterJob, QgsMapSettings


def crop_raster_to_image(layer, extent, max_side=1536):
    """Render `extent` (in the layer CRS) of a raster layer to an RGB array.

    Returns (image_rgb, gt) where gt = [x_min, px_w, 0, y_max, 0, -px_h]
    (GDAL order) maps pixel (col, row) to layer CRS coordinates:
    X = gt[0] + col * gt[1], Y = gt[3] + row * gt[5].
    """
    import numpy as np

    w_extent = extent.width()
    h_extent = extent.height()
    if w_extent <= 0 or h_extent <= 0:
        raise RuntimeError("The zone is empty.")

    scale = max(w_extent, h_extent) / float(max_side)
    w = max(1, int(round(w_extent / scale)))
    h = max(1, int(round(h_extent / scale)))

    settings = QgsMapSettings()
    settings.setLayers([layer])
    settings.setDestinationCrs(layer.crs())
    settings.setExtent(extent)
    settings.setOutputSize(QSize(w, h))
    settings.setOutputDpi(96)
    settings.setFlag(QgsMapSettings.Flag.Antialiasing, False)
    settings.setBackgroundColor(Qt.white)

    image = QImage(w, h, QImage.Format_ARGB32_Premultiplied)
    image.fill(Qt.white)
    painter = QPainter(image)
    job = QgsMapRendererCustomPainterJob(settings, painter)
    job.start()
    job.waitForFinished()
    painter.end()

    try:
        buf = image.constBits()
    except AttributeError:
        buf = image.bits()
    try:
        buf.setsize(image.sizeInBytes())
    except (AttributeError, TypeError):
        pass
    arr = np.frombuffer(bytes(buf), dtype=np.uint8).reshape(h, w, 4)
    rgb = np.ascontiguousarray(arr[:, :, 2::-1])

    gt = [
        extent.xMinimum(),
        w_extent / w,
        0.0,
        extent.yMaximum(),
        0.0,
        -h_extent / h,
    ]
    return rgb, gt
