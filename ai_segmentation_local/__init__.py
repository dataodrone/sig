import os

PLUGIN_DIR = os.path.dirname(os.path.abspath(__file__))


def classFactory(iface):
    from .plugin import AISegmentationLocalPlugin

    return AISegmentationLocalPlugin(iface)
