import os

from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction
from qgis.PyQt.QtCore import Qt

from .ui.dock import SegmentationDock


class AISegmentationLocalPlugin:
    def __init__(self, iface):
        self.iface = iface
        self.dock = None
        self.action = None

    def initGui(self):
        icon_path = os.path.join(os.path.dirname(__file__), "resources", "icon.png")
        icon = QIcon(icon_path)
        self.action = QAction(icon, "AI Segmentation Local (free)", self.iface.mainWindow())
        self.action.setCheckable(True)
        self.action.setToolTip(
            "Local AI segmentation: no account, no API key, no subscription"
        )
        self.action.triggered.connect(self._toggle_dock)
        self.iface.addPluginToMenu("&AI Segmentation Local", self.action)
        self.iface.addToolBarIcon(self.action)

    def unload(self):
        if self.action is not None:
            self.iface.removePluginMenu("&AI Segmentation Local", self.action)
            self.iface.removeToolBarIcon(self.action)
        if self.dock is not None:
            self.iface.removeDockWidget(self.dock)
            self.dock.deleteLater()
            self.dock = None

    def _toggle_dock(self, checked):
        if checked:
            if self.dock is None:
                self.dock = SegmentationDock(self.iface)
            self.iface.addDockWidget(Qt.RightDockWidgetArea, self.dock)
            self.dock.show()
        elif self.dock is not None:
            self.iface.removeDockWidget(self.dock)
