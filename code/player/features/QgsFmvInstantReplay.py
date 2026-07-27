# -*- coding: utf-8 -*-
"""Instant Replay — on alert/sentinel, pause and rewind a few seconds."""

from __future__ import annotations

import time

from QGISFMV.utils.constants import INSTANT_REPLAY_COOLDOWN_MS, INSTANT_REPLAY_SEC
from QGISFMV.utils.logging import log
from QGISFMV.utils.ui.QgsUtils import QgsUtils as qgsu


class InstantReplayController:
    """Rewind+pause when an alert fires (great for Sentinel demos)."""

    def __init__(self, player, seconds=None):
        self.player = player
        self._enabled = False
        self._seconds = float(seconds if seconds is not None else INSTANT_REPLAY_SEC)
        self._cooldown_ms = int(INSTANT_REPLAY_COOLDOWN_MS)
        self._last_ms = 0

    def setEnabled(self, value):
        self._enabled = bool(value)
        return self._enabled

    def isEnabled(self):
        return self._enabled

    def onAlert(self, _message=""):
        """Slot for ``alertManager.alertTriggered``."""
        if not self._enabled:
            return False
        now = int(time.time() * 1000)
        if now - self._last_ms < self._cooldown_ms:
            return False
        player = self.player
        qmp = getattr(player, "player", None)
        if qmp is None:
            return False
        try:
            pos = int(qmp.position())
            target = max(0, pos - int(self._seconds * 1000))
            pipe = getattr(player, "metadataPipeline", None)
            if pipe is not None and hasattr(pipe, "resetAppliedLayerSeq"):
                pipe.resetAppliedLayerSeq()
            pb = getattr(player, "playbackController", None)
            if pb is not None and hasattr(pb, "pauseAt"):
                pb.pauseAt(target)
            else:
                qmp.setPosition(target)
                qmp.pause()
            self._last_ms = now
            qgsu.showUserAndLogMessage(
                "",
                f"Instant Replay −{self._seconds:.0f}s → pause",
                onlyLog=True,
            )
            return True
        except Exception as exc:
            log.debug("instant replay failed: %s", exc)
            return False
