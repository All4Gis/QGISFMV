# -*- coding: utf-8 -*-
"""Tests for VideoSession lifecycle (no QGIS runtime beyond stubs)."""

from unittest.mock import MagicMock, patch

import pytest

from code.tests.support import load_plugin_module


@pytest.fixture
def session_mod():
    return load_plugin_module(
        "utils/core/QgsFmvVideoSession.py",
        "QGISFMV.utils.core.QgsFmvVideoSession",
    )


class TestVideoSession:
    def test_activate_sets_active_session(self, session_mod):
        session_mod.set_active_session(None)
        session = session_mod.VideoSession(iface=MagicMock())
        session.setCenterMode(2)
        session.setFrameCenter(1.0, 2.0)
        with patch.object(session_mod, "_sync_legacy_gv"):
            session.activate()
        assert session_mod.get_active_session() is session
        assert session.getCenterMode() == 2
        assert session.getFrameCenterLat() == 1.0

    def test_reset_telemetry_keeps_iface_and_mode(self, session_mod):
        iface = MagicMock()
        session = session_mod.VideoSession(iface=iface)
        session.setCenterMode(3)
        session.setFrameCenter(10.0, 20.0)
        session.setCornerUL((1, 2))
        session.reset_telemetry()
        assert session.iface is iface
        assert session.getCenterMode() == 3
        assert session.getFrameCenterLat() is None
        assert session.getCornerUL() is None

    def test_deactivate_clears_active(self, session_mod):
        session_mod.set_active_session(None)
        session = session_mod.VideoSession(iface=MagicMock())
        with patch.object(session_mod, "_sync_legacy_gv"):
            session.activate()
            session.deactivate()
        assert session_mod.get_active_session() is None

    def test_ensure_session_reuses_active(self, session_mod):
        session_mod.set_active_session(None)
        iface = MagicMock()
        with patch.object(session_mod, "_sync_legacy_gv"):
            first = session_mod.ensure_session(iface)
            second = session_mod.ensure_session(iface)
        assert first is second
