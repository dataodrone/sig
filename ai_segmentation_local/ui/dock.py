import os

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import (
    QComboBox,
    QDockWidget,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from qgis.core import QgsProject, QgsRasterLayer

from ..core.results import (
    add_result,
    clear_results,
    export_gpkg,
    results_layer,
    set_layer_crs,
)
from ..core.worker import MODE_AUTO, MODE_CLICK, SegmentationWorker
from .map_tools import ClickMapTool, ZoneMapTool

PLUGIN_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

MODES = [
    (MODE_AUTO, "Automatic: draw a zone, name an object"),
    (MODE_CLICK, "Semi-auto: click an object on the map"),
]


class SegmentationDock(QDockWidget):
    def __init__(self, iface):
        super().__init__("AI Segmentation Local (free)", iface.mainWindow())
        self.iface = iface
        self.canvas = iface.mapCanvas()
        self.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        self.setObjectName("AISegmentationLocalDock")

        self.zone_tool = ZoneMapTool(self.canvas)
        self.click_tool = ClickMapTool(self.canvas)
        self.zone_tool.zone_ready.connect(self._on_zone_ready)
        self.click_tool.points_changed.connect(self._on_points_changed)

        self.zone = None
        self.pos_points = []
        self.neg_points = []
        self.worker = None

        self._build_ui()
        self._refresh_raster_layers()
        QgsProject.instance().layersAdded.connect(self._refresh_raster_layers)
        QgsProject.instance().layersRemoved.connect(self._refresh_raster_layers)

    def _build_ui(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)

        intro = QLabel(
            "100% local and free: open models run on your computer. "
            "No account, no API key, no subscription, nothing is sent online."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        self.raster_combo = QComboBox()
        layout.addWidget(QLabel("Raster layer:"))
        layout.addWidget(self.raster_combo)

        self.mode_combo = QComboBox()
        for key, text in MODES:
            self.mode_combo.addItem(text, key)
        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        layout.addWidget(QLabel("Mode:"))
        layout.addWidget(self.mode_combo)

        self.label_edit = QLineEdit()
        self.label_edit.setPlaceholderText('e.g. "buildings", "trees", "solar panels"...')
        layout.addWidget(QLabel("What to find (automatic mode):"))
        layout.addWidget(self.label_edit)

        pick_box = QGroupBox("1. Select on the map")
        pick_layout = QVBoxLayout(pick_box)
        self.zone_button = QPushButton("Draw a detection zone on the map")
        self.zone_button.clicked.connect(self._activate_zone_tool)
        pick_layout.addWidget(self.zone_button)
        self.click_button = QPushButton("Click the object on the map (right click = negative point)")
        self.click_button.clicked.connect(self._activate_click_tool)
        pick_layout.addWidget(self.click_button)
        self.pick_hint = QLabel("")
        self.pick_hint.setWordWrap(True)
        pick_layout.addWidget(self.pick_hint)
        layout.addWidget(pick_box)

        self.run_button = QPushButton("Run detection (local, free)")
        self.run_button.clicked.connect(self._run)
        layout.addWidget(self.run_button)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        layout.addWidget(self.progress)
        self.status = QLabel("Ready.")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

        results_box = QGroupBox("Results")
        results_layout = QVBoxLayout(results_box)
        self.count_label = QLabel("0 polygon in the results layer")
        results_layout.addWidget(self.count_label)
        buttons = QHBoxLayout()
        self.clear_button = QPushButton("Clear results")
        self.clear_button.clicked.connect(self._clear_results)
        buttons.addWidget(self.clear_button)
        self.export_button = QPushButton("Export to GeoPackage...")
        self.export_button.clicked.connect(self._export)
        buttons.addWidget(self.export_button)
        results_layout.addLayout(buttons)
        layout.addWidget(results_box)

        layout.addStretch(1)
        self.setWidget(widget)
        self._on_mode_changed()

    def _refresh_raster_layers(self, *_args):
        current = self.raster_combo.currentData()
        self.raster_combo.clear()
        for layer in QgsProject.instance().mapLayers().values():
            if isinstance(layer, QgsRasterLayer) and layer.isValid():
                self.raster_combo.addItem(layer.name(), layer)
        if current is not None:
            idx = self.raster_combo.findData(current)
            if idx >= 0:
                self.raster_combo.setCurrentIndex(idx)

    def _current_raster(self):
        return self.raster_combo.currentData()

    def _on_mode_changed(self, *_args):
        mode = self.mode_combo.currentData()
        auto = mode == MODE_AUTO
        self.zone_button.setVisible(auto)
        self.click_button.setVisible(not auto)
        self.label_edit.setEnabled(auto)
        self.zone = None
        self.pos_points = []
        self.neg_points = []
        self._set_hint("")

    def _activate_zone_tool(self):
        self.canvas.setMapTool(self.zone_tool)
        self._set_hint("Left click: add a vertex. Double click or right click: finish the zone.")

    def _activate_click_tool(self):
        self.canvas.setMapTool(self.click_tool)
        self._set_hint("Left click on the object (you can click several). Right click: negative point.")

    def _on_zone_ready(self, geom):
        self.zone = geom
        self._set_hint("Zone defined. Now press 'Run detection'.")

    def _on_points_changed(self, pos, neg):
        self.pos_points = pos
        self.neg_points = neg
        self._set_hint(
            "%d positive point(s), %d negative point(s). Press 'Run detection'."
            % (len(pos), len(neg))
        )

    def _set_hint(self, text):
        self.pick_hint.setText(text)

    def _set_status(self, text):
        self.status.setText(text)

    def _run(self):
        layer = self._current_raster()
        if layer is None:
            QMessageBox.warning(self, "AI Segmentation Local", "Add a raster layer to the project first.")
            return
        mode = self.mode_combo.currentData()
        label = self.label_edit.text().strip()
        if mode == MODE_AUTO:
            if self.zone is None:
                QMessageBox.warning(self, "AI Segmentation Local", "Draw a zone on the map first.")
                return
            if not label:
                QMessageBox.warning(self, "AI Segmentation Local", "Type what to find, e.g. \"buildings\".")
                return
        else:
            if not self.pos_points:
                QMessageBox.warning(self, "AI Segmentation Local", "Click at least one object on the map first.")
                return
        if self.worker is not None and self.worker.isRunning():
            return

        self.run_button.setEnabled(False)
        self.progress.setValue(0)
        self._set_status("Running locally...")
        self.worker = SegmentationWorker(
            PLUGIN_DIR,
            layer,
            self.canvas.mapSettings().destinationCrs(),
            mode,
            label,
            zone=self.zone,
            pos_points=self.pos_points,
            neg_points=self.neg_points,
            canvas_extent=self.canvas.extent(),
            parent=self,
        )
        self.worker.progress.connect(self._on_progress)
        self.worker.finished.connect(self._on_finished)
        self.worker.failed.connect(self._on_failed)
        self.worker.start()

    def _on_progress(self, value, message):
        self.progress.setValue(value)
        self._set_status(message)

    def _on_finished(self, results):
        layer = self._current_raster()
        out = results_layer()
        if layer is not None:
            set_layer_crs(out, layer.crs())
        for item in results:
            add_result(out, item["geometry"], item["label"], item["confidence"], item["mode"])
        self._update_count(out)
        if results and not out.extent().isEmpty():
            self.canvas.setExtent(out.extent())
            self.canvas.refresh()
        self._set_status("Done: %d polygon(s) added to '%s'." % (len(results), out.name()))
        self.progress.setValue(100)
        self.run_button.setEnabled(True)
        self.zone = None
        self.pos_points = []
        self.neg_points = []

    def _on_failed(self, tb):
        self._set_status("Error. See the message.")
        QMessageBox.critical(self, "AI Segmentation Local", tb[-4000:])
        self.progress.setValue(0)
        self.run_button.setEnabled(True)

    def _update_count(self, layer=None):
        layer = layer or results_layer()
        self.count_label.setText("%d polygon(s) in the results layer" % layer.featureCount())

    def _clear_results(self):
        layer = results_layer()
        clear_results(layer)
        self._update_count(layer)
        self._set_status("Results cleared.")

    def _export(self):
        layer = results_layer()
        if layer.featureCount() == 0:
            QMessageBox.information(self, "AI Segmentation Local", "No polygon to export yet.")
            return
        path, _filter = QFileDialog.getSaveFileName(
            self, "Export results to GeoPackage", "", "GeoPackage (*.gpkg)"
        )
        if not path:
            return
        if not path.lower().endswith(".gpkg"):
            path += ".gpkg"
        try:
            export_gpkg(layer, path)
        except RuntimeError as exc:
            QMessageBox.critical(self, "AI Segmentation Local", str(exc))
            return
        self._set_status("Exported to %s" % path)

    def closeEvent(self, event):
        if self.canvas.mapTool() in (self.zone_tool, self.click_tool):
            self.canvas.unsetMapTool(self.canvas.mapTool())
        super().closeEvent(event)
