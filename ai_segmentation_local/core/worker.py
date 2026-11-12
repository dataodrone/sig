import traceback

from qgis.PyQt.QtCore import QThread, pyqtSignal
from qgis.core import QgsCoordinateTransform

from .backend import LocalBackend
from .deps import ensure_deps
from .polygonize import mask_to_rings, rings_to_geometry
from .raster_crop import crop_raster_to_image

MODE_AUTO = "auto"
MODE_CLICK = "click"


class SegmentationWorker(QThread):
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(list)
    failed = pyqtSignal(str)

    def __init__(self, plugin_dir, layer, canvas_crs, mode, label,
                 zone=None, pos_points=None, neg_points=None, canvas_extent=None,
                 parent=None):
        super().__init__(parent)
        self.plugin_dir = plugin_dir
        self.layer = layer
        self.canvas_crs = canvas_crs
        self.mode = mode
        self.label = label
        self.zone = zone
        self.pos_points = pos_points or []
        self.neg_points = neg_points or []
        self.canvas_extent = canvas_extent

    def _to_layer_crs(self):
        xform = QgsCoordinateTransform(
            self.canvas_crs, self.layer.crs(), self.layer
        )
        return xform

    def run(self):
        try:
            self.progress.emit(5, "Preparing the local AI stack (first run downloads the free models)...")
            ensure_deps(self.plugin_dir, lambda m: self.progress.emit(8, m))
            backend = LocalBackend(self.plugin_dir, lambda m: self.progress.emit(15, m))
            xform = self._to_layer_crs()

            if self.mode == MODE_AUTO:
                results = self._run_auto(backend, xform)
            else:
                results = self._run_click(backend, xform)

            self.progress.emit(95, "Adding polygons to the results layer...")
            self.finished.emit(results)
        except Exception:
            self.failed.emit(traceback.format_exc())

    def _run_auto(self, backend, xform):
        if self.zone is None:
            raise RuntimeError("Draw a zone on the map first.")
        zone = self.zone.transformed(xform)
        extent = zone.boundingBox()
        extent.scale(1.05)
        self.progress.emit(25, "Rendering the zone from the raster layer...")
        image, gt = crop_raster_to_image(self.layer, extent, max_side=1536)
        self.progress.emit(40, "Detecting '%s' locally (SAM + CLIP, no network)..." % self.label)
        detections = backend.detect_label(image, self.label)
        results = []
        for det in detections:
            for ring in mask_to_rings(det["mask"], gt):
                geom = rings_to_geometry([ring])
                if geom is not None and not geom.isEmpty():
                    results.append({
                        "geometry": geom,
                        "label": self.label,
                        "confidence": det["score"],
                        "mode": MODE_AUTO,
                    })
        self.progress.emit(90, "%d object(s) found" % len(results))
        return results

    def _run_click(self, backend, xform):
        if not self.pos_points:
            raise RuntimeError("Click at least one object on the map first.")
        pos = [p.transformed(xform) for p in self.pos_points]
        neg = [p.transformed(xform) for p in self.neg_points]
        all_pts = pos + neg
        xs = [p.x() for p in all_pts]
        ys = [p.y() for p in all_pts]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        ref = self.canvas_extent
        pad_x = max((max_x - min_x) * 0.6, (ref.width() if ref else 100.0) * 0.05)
        pad_y = max((max_y - min_y) * 0.6, (ref.height() if ref else 100.0) * 0.05)
        from qgis.core import QgsRectangle

        crop = QgsRectangle(
            min_x - pad_x, min_y - pad_y, max_x + pad_x, max_y + pad_y
        )
        self.progress.emit(25, "Rendering the area around your click(s)...")
        image, gt = crop_raster_to_image(self.layer, crop, max_side=1024)
        coords = [
            ((p.x() - gt[0]) / gt[1], (p.y() - gt[3]) / gt[5])
            for p in all_pts
        ]
        labels = [1] * len(pos) + [0] * len(neg)
        self.progress.emit(40, "Segmenting the clicked object locally (SAM)...")
        mask = backend.segment_points(image, coords, labels)
        results = []
        for ring in mask_to_rings(mask, gt):
            geom = rings_to_geometry([ring])
            if geom is not None and not geom.isEmpty():
                results.append({
                    "geometry": geom,
                    "label": self.label or "object",
                    "confidence": 1.0,
                    "mode": MODE_CLICK,
                })
        self.progress.emit(90, "%d outline(s) created" % len(results))
        return results
