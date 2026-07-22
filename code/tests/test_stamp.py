# -*- coding: utf-8 -*-
"""Stamp overlay asset checks."""

from code.tests.support import CODE


class TestStampOverlay:
    def test_stamp_disk_file_exists(self):
        stamp_path = CODE / "images" / "stamp" / "confidential.png"
        assert stamp_path.is_file()
        assert stamp_path.stat().st_size > 0
