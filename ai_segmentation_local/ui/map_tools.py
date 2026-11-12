from qgis.PyQt.QtCore import Qt, pyqtSignal
from qgis.PyQt.QtGui import QColor
from qgis.core import QgsGeometry, QgsWkbTypes
from qgis.gui import QgsMapToolEmitPoint, QgsRubberBand


class ZoneMapTool(QgsMapToolEmitPoint):
    """Draw a polygon zone: left click adds a vertex, double click or right
    click finishes."""

    zone_ready = pyqtSignal(QgsGeometry)

    def __init__(self, canvas):
        super().__init__(canvas)
        self.canvas = canvas
        self.rubber = QgsRubberBand(canvas, QgsWkbTypes.PolygonGeometry)
        self.rubber.setColor(QColor(70, 150, 255, 220))
        self.rubber.setFillColor(QColor(70, 150, 255, 50))
        self.rubber.setWidth(2)
        self.points = []

    def canvasPressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.points.append(self.toMapCoordinates(event.pos()))
            self._refresh()
        elif event.button() == Qt.RightButton:
            self._finish()

    def canvasDoubleClickEvent(self, event):
        self._finish()

    def _refresh(self):
        if len(self.points) >= 3:
            ring = self.points + [self.points[0]]
            self.rubber.setToGeometry(QgsGeometry.fromPolygonXY([ring]), None)
        elif len(self.points) == 2:
            self.rubber.setToGeometry(
                QgsGeometry.fromPolylineXY(self.points), None
            )

    def _finish(self):
        if len(self.points) >= 3:
            ring = self.points + [self.points[0]]
            geom = QgsGeometry.fromPolygonXY([ring])
            self.rubber.setToGeometry(geom, None)
            self.zone_ready.emit(geom)
        self.reset()

    def reset(self):
        self.points = []
        self.rubber.reset(QgsWkbTypes.PolygonGeometry)

    def deactivate(self):
        self.reset()
        super().deactivate()


class ClickMapTool(QgsMapToolEmitPoint):
    """Left click adds a positive point, right click adds a negative point."""

    points_changed = pyqtSignal(list, list)

    def __init__(self, canvas):
        super().__init__(canvas)
        self.canvas = canvas
        self.pos_rubber = QgsRubberBand(canvas, QgsWkbTypes.PointGeometry)
        self.pos_rubber.setColor(QColor(0, 190, 0, 255))
        self.pos_rubber.setIconSize(10)
        self.neg_rubber = QgsRubberBand(canvas, QgsWkbTypes.PointGeometry)
        self.neg_rubber.setColor(QColor(230, 40, 40, 255))
        self.neg_rubber.setIconSize(10)
        self.pos = []
        self.neg = []

    def canvasPressEvent(self, event):
        point = self.toMapCoordinates(event.pos())
        if event.button() == Qt.LeftButton:
            self.pos.append(point)
        elif event.button() == Qt.RightButton:
            self.neg.append(point)
        self._refresh()
        self.points_changed.emit(list(self.pos), list(self.neg))

    def _refresh(self):
        self.pos_rubber.reset(QgsWkbTypes.PointGeometry)
        for p in self.pos:
            self.pos_rubber.addPoint(p)
        self.neg_rubber.reset(QgsWkbTypes.PointGeometry)
        for p in self.neg:
            self.neg_rubber.addPoint(p)

    def reset(self):
        self.pos = []
        self.neg = []
        self.pos_rubber.reset(QgsWkbTypes.PointGeometry)
        self.neg_rubber.reset(QgsWkbTypes.PointGeometry)

    def deactivate(self):
        self.reset()
        super().deactivate()
