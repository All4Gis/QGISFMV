# -*- coding: utf-8 -*-
"""Player feature controllers (mosaic, record, metadata pipeline, map-center, timeline,
alerts, snapshots, playback transport, close/teardown, task-result routing, export,
context menus, draw-tool toggles) extracted from the QgsFmvPlayer god-class.

Each controller takes the owning ``QgsFmvPlayer`` instance (``self.player`` /
``self._player``) and exposes the behaviour that used to live directly on the
player. The player keeps thin delegate methods only where Qt Designer needs a
slot to exist directly on the player class (e.g. actions/buttons wired from
``ui_FmvPlayer.ui``), or where other code (the manager, other controllers)
calls the player as a public entry point.
"""
