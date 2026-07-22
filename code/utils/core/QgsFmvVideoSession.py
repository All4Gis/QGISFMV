# -*- coding: utf-8 -*-
"""Per-video telemetry / georeferencing session state.

Replaces the former module-global ``gv`` singleton.  Callers should prefer
``get_active_session()`` or an injected ``VideoSession`` instance.  The
legacy ``QgsFmvUtils.gv`` name remains as a thin alias to the active
session for backward compatibility.
"""

from QGISFMV.utils.core.QgsFmvUtilsState import globalVariablesState

# Active session for the currently focused player (single-video default).
_active_session = None


class VideoSession(globalVariablesState):
    """Mutable telemetry state for one open video player."""

    def __init__(self, iface=None):
        super().__init__()
        if iface is not None:
            self.iface = iface

    def reset_telemetry(self):
        """Clear footprint / sensor / geotransform fields (keep iface + centerMode)."""
        iface = self.iface
        center = self.centerMode
        self.__init__(iface=iface)
        self.centerMode = center

    def activate(self):
        """Make this the process-wide active session (legacy ``gv`` alias)."""
        global _active_session
        _active_session = self
        _sync_legacy_gv()
        return self

    def deactivate(self):
        """Clear active session if it is this instance."""
        global _active_session
        if _active_session is self:
            _active_session = None
            _sync_legacy_gv()


def get_active_session():
    """Return the active :class:`VideoSession`, or ``None``."""
    return _active_session


def ensure_session(iface=None):
    """Return the active session, creating one if needed."""
    global _active_session
    if _active_session is None:
        _active_session = VideoSession(iface=iface)
        _sync_legacy_gv()
    elif iface is not None:
        _active_session.setIface(iface)
    return _active_session


def set_active_session(session):
    """Replace the active session (``None`` clears it)."""
    global _active_session
    _active_session = session
    _sync_legacy_gv()
    return _active_session


def _sync_legacy_gv():
    """Keep ``QgsFmvUtils.gv`` pointing at the active session."""
    try:
        import QGISFMV.utils.core.QgsFmvUtils as utils

        utils.gv = _active_session
    except Exception:
        pass


# Alias kept for readability at call sites / docs.
VideoState = VideoSession
