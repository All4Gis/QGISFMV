# -*- coding: utf-8 -*-
"""Alert-rule dialog — layout defined in ``ui_FmvAlertRule.ui``."""

from qgis.PyQt.QtWidgets import QDialog

from QGISFMV.gui.ui_FmvAlertRule import Ui_FmvAlertRule


# Default MISB-ish fields offered in the combo (editable list for callers).
DEFAULT_ALERT_FIELDS = (
    "Sensor Latitude",
    "Sensor Longitude",
    "Sensor True Altitude",
    "Slant Range",
    "Frame Center Latitude",
    "Frame Center Longitude",
    "Frame Center Elevation",
    "Sensor Relative Elevation Angle",
    "Sensor Relative Azimuth Angle",
)


class FmvAlertRuleDialog(QDialog, Ui_FmvAlertRule):
    """Collect field / operator / threshold for a telemetry alert rule."""

    def __init__(self, parent=None, fields=None, operators=None):
        super().__init__(parent)
        self.setupUi(self)
        self.cmbField.clear()
        self.cmbField.addItems(list(fields or DEFAULT_ALERT_FIELDS))
        self.cmbOperator.clear()
        self.cmbOperator.addItems(list(operators or (">", "<", ">=", "<=", "==", "!=")))

    def selectedRule(self):
        """Return ``(field, op, value)`` from the current form values."""
        return (
            self.cmbField.currentText(),
            self.cmbOperator.currentText(),
            self.lnThreshold.text().strip(),
        )
