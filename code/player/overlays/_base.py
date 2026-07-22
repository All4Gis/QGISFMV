# -*- coding: utf-8 -*-
"""Shared base for QGIS map-canvas vector overlays (sensor cone, distance rings, etc.)."""

from qgis.core import (
    QgsVectorLayer,
    QgsProject,
    QgsCategorizedSymbolRenderer,
    QgsRendererCategory,
)

from QGISFMV.utils.logging import log


class VectorOverlayBase:
    """Common lifecycle for single-feature vector layers on the map canvas.

    Subclasses must implement:
      - ``_create_layer()``: create and return a configured ``QgsVectorLayer``.
    """

    def __init__(self):
        self.layer = None
        self._visible = False

    def setVisible(self, visible):
        self._visible = visible
        if not visible:
            self._removeLayer()

    @property
    def isVisible(self):
        return self._visible

    def _ensureLayer(self, group_name=None):
        """Return the overlay layer, creating it if necessary."""
        if self.layer is not None and self.layer.isValid():
            return self.layer

        vl = self._create_layer()
        if vl is None or not vl.isValid():
            return None

        self._addLayerToTree(vl, group_name)
        self.layer = vl
        return vl

    def _removeLayer(self):
        if self.layer is not None:
            try:
                QgsProject.instance().removeMapLayer(self.layer.id())
            except Exception as exc:
                log.debug("Overlay layer removal failed: %s", exc)
            self.layer = None

    def _clear_features(self):
        """Remove all features from the overlay layer."""
        layer = self.layer
        if layer is None:
            return
        provider = layer.dataProvider()
        ids = [feat.id() for feat in layer.getFeatures()]
        if ids:
            provider.deleteFeatures(ids)

    @staticmethod
    def _addLayerToTree(vl, group_name):
        """Register the layer in the QGIS project and layer tree."""
        QgsProject.instance().addMapLayer(vl, False)
        root = QgsProject.instance().layerTreeRoot()
        if group_name:
            grp = root.findGroup(group_name)
            if grp is not None:
                grp.addLayer(vl)
                return
        root.addLayer(vl)
