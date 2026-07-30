# -*- coding: utf-8 -*-
"""Rule-based alerts — notify when telemetry conditions are met."""

from qgis.core import Qgis as QGis
from qgis.PyQt.QtCore import QObject, pyqtSignal
from qgis.PyQt.QtWidgets import QDialog

from QGISFMV.player.dialogs.QgsFmvAlertRule import FmvAlertRuleDialog
from QGISFMV.utils.ui.QgsUtils import QgsUtils as qgsu


class AlertRule:
    """One alert rule: (field_name, operator, value)."""

    OPS = {
        ">": lambda a, b: a > b,
        "<": lambda a, b: a < b,
        ">=": lambda a, b: a >= b,
        "<=": lambda a, b: a <= b,
        "==": lambda a, b: a == b,
        "!=": lambda a, b: a != b,
    }

    def __init__(self, field, op, value, label=""):
        self.field = field
        self.op = op
        self.value = value
        self.label = label or f"{field} {op} {value}"
        self._last_triggered = 0

    def check(self, metadata_dict):
        """Check if any metadata entry triggers this rule."""
        for key, val in metadata_dict.items():
            field_name = str(val[0]).lower()
            if self.field.lower() in field_name:
                try:
                    actual = float(val[1])
                    threshold = float(self.value)
                    if self.OPS[self.op](actual, threshold):
                        return True, actual
                except (TypeError, ValueError, IndexError, KeyError):
                    pass
        return False, None


class AlertManager(QObject):
    """Manages alert rules and fires notifications."""

    alertTriggered = pyqtSignal(str)

    def __init__(self, player, parent=None):
        super().__init__(parent)
        self.player = player
        self._rules = []
        self._enabled = False
        self._cooldown_ms = 2000
        self._last_alert_ms = 0

    def addRule(self, rule):
        """Append an alert rule to the list."""
        self._rules.append(rule)

    def clearRules(self):
        """Remove all alert rules."""
        self._rules.clear()

    def rules(self):
        """Return a copy of the current alert rules list."""
        return list(self._rules)

    def toggle(self):
        """Toggle alerting on/off; warns if no rules are defined."""
        self._enabled = not self._enabled
        if self._enabled and not self._rules:
            qgsu.showUserAndLogMessage(
                "",
                "No alert rules defined. Add rules first.",
                level=QGis.MessageLevel.Warning,
            )
            self._enabled = False
        return self._enabled

    def checkMetadata(self, metadata_dict):
        """Check all rules against current metadata."""
        if not self._enabled or not self._rules:
            return

        import time

        now = int(time.time() * 1000)
        if now - self._last_alert_ms < self._cooldown_ms:
            return

        for rule in self._rules:
            triggered, actual = rule.check(metadata_dict)
            if triggered:
                self._last_alert_ms = now
                msg = f"ALERT: {rule.label} (actual: {actual})"
                self.alertTriggered.emit(msg)
                qgsu.showUserAndLogMessage(
                    "Alert",
                    msg,
                    level=QGis.MessageLevel.Warning,
                    duration=5,
                )
                break

    def addRuleDialog(self):
        """Show the Designer-backed dialog to add a rule."""
        dlg = FmvAlertRuleDialog(
            self.player,
            operators=list(AlertRule.OPS.keys()),
        )
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        field, op, value = dlg.selectedRule()
        if not value:
            qgsu.showUserAndLogMessage(
                "",
                "Threshold value is required.",
                level=QGis.MessageLevel.Warning,
            )
            return

        try:
            float(value)
        except ValueError:
            qgsu.showUserAndLogMessage(
                "",
                "Invalid numeric threshold.",
                level=QGis.MessageLevel.Warning,
            )
            return

        rule = AlertRule(field, op, value)
        self.addRule(rule)
        qgsu.showUserAndLogMessage(
            "",
            f"Alert rule added: {rule.label}",
            onlyLog=True,
        )
