import os

from qgis.PyQt.QtCore import QVariant
from qgis.core import (
    QgsDistanceArea,
    QgsFeature,
    QgsFillSymbol,
    QgsProject,
    QgsSingleSymbolRenderer,
    QgsVectorFileWriter,
    QgsVectorLayer,
)

LAYER_NAME = "AI Segmentation (local)"


def results_layer():
    for layer in QgsProject.instance().mapLayersByName(LAYER_NAME):
        if layer.isValid():
            return layer
    layer = QgsVectorLayer("Polygon?crs=EPSG:4326", LAYER_NAME, "memory")
    provider = layer.dataProvider()
    from qgis.core import QgsField

    provider.addAttributes([
        QgsField("label", QVariant.String),
        QgsField("confidence", QVariant.Double),
        QgsField("area_m2", QVariant.Double),
        QgsField("mode", QVariant.String),
    ])
    layer.updateFields()
    symbol = QgsFillSymbol.createSimple({
        "color": "80,180,90,70",
        "outline_color": "20,100,40,255",
        "outline_width": "0.6",
    })
    layer.setRenderer(QgsSingleSymbolRenderer(symbol))
    QgsProject.instance().addMapLayer(layer)
    return layer


def set_layer_crs(layer, crs):
    if layer.crs() != crs:
        layer.setCrs(crs)


def add_result(layer, geometry, label, confidence, mode):
    feature = QgsFeature(layer.fields())
    feature.setGeometry(geometry)
    area = QgsDistanceArea()
    area.setSourceCrs(layer.crs(), QgsProject.instance().transformContext())
    area.setEllipsoid("WGS84")
    area_m2 = area.measureArea(geometry)
    feature.setAttributes([label, round(float(confidence), 3), round(area_m2, 1), mode])
    layer.dataProvider().addFeature(feature)
    layer.updateExtents()
    layer.triggerRepaint()


def clear_results(layer):
    provider = layer.dataProvider()
    provider.deleteFeatures([f.id() for f in layer.getFeatures()])
    layer.updateExtents()
    layer.triggerRepaint()


def export_gpkg(layer, path):
    options = QgsVectorFileWriter.SaveVectorOptions()
    options.driverName = "GPKG"
    options.layerName = "segmentation"
    if os.path.exists(path):
        options.actionOnExistingFile = (
            QgsVectorFileWriter.ActionOnExistingFile.AppendToLayerAddFields
        )
    else:
        options.actionOnExistingFile = (
            QgsVectorFileWriter.ActionOnExistingFile.CreateOrOverwriteFile
        )
    error, message = QgsVectorFileWriter.writeAsVectorFormatV3(
        layer, path, QgsProject.instance().transformContext(), options
    )
    if error != QgsVectorFileWriter.WriterError.NoError:
        raise RuntimeError(message or "Export failed")
    return path
