"""Tests for the misb-check external validator wrapper."""

import json
import os
import shutil
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

from code.tests.support import load_plugin_module

import pytest


@pytest.fixture
def checker():
    module = load_plugin_module(
        "utils/media/QgsFmvMisbCheck.py",
        "QGIS_FMV.utils.media.QgsFmvMisbCheck",
    )
    module.invalidate_cache()
    yield module
    module.invalidate_cache()


PASS_ENTRY = {
    "file": "flight.ts",
    "container": "mpeg-ts",
    "passed": True,
    "packets": 24,
    "errors": 0,
    "warnings": 1,
    "findings": [
        {
            "severity": "warning",
            "code": "TIME-REPEATED",
            "pid": 256,
            "packet": 3,
            "offset": 752,
            "tag": 2,
            "message": "time stamp repeated",
        }
    ],
}

FAIL_ENTRY = {
    "file": "DynamicConstantMISMMSPacketData.bin",
    "container": "klv",
    "passed": False,
    "packets": 1,
    "errors": 3,
    "warnings": 0,
    "findings": [
        {
            "severity": "error",
            "code": "CHECKSUM",
            "pid": None,
            "packet": 0,
            "offset": 0,
            "tag": 1,
            "message": "checksum says 0xaa43, the packet sums to 0x3e1e",
        },
        {
            "severity": "error",
            "code": "BEYOND-HORIZON",
            "pid": None,
            "packet": 0,
            "offset": 0,
            "tag": 23,
            "message": "frame center is 11535.2 km from the sensor",
        },
    ],
}


def _completed(payload, returncode):
    proc = MagicMock()
    proc.returncode = returncode
    proc.stdout = json.dumps([payload])
    proc.stderr = ""
    return proc


class TestParseReport:
    def test_pass_entry(self, checker):
        report = checker.parse_report(PASS_ENTRY)
        assert report.passed
        assert report.packets == 24
        assert report.errors == 0
        assert report.warnings == 1
        assert len(report.findings) == 1
        finding = report.findings[0]
        assert finding.code == "TIME-REPEATED"
        assert finding.pid == 256
        assert finding.tag == 2

    def test_fail_entry(self, checker):
        report = checker.parse_report(FAIL_ENTRY)
        assert not report.passed
        assert report.errors == 3
        assert [f.code for f in report.findings] == ["CHECKSUM", "BEYOND-HORIZON"]


class TestFormatReport:
    def test_verdict_and_counts(self, checker):
        text = checker.format_report(checker.parse_report(FAIL_ENTRY))
        assert "FAIL" in text
        assert "3 errors" in text
        assert "error[CHECKSUM]" in text
        assert "packet 0" in text
        assert "tag 1" in text

    def test_max_findings_truncates(self, checker):
        entry = dict(FAIL_ENTRY)
        entry["findings"] = FAIL_ENTRY["findings"] * 5
        report = checker.parse_report(entry)
        text = checker.format_report(report, max_findings=2)
        assert text.count("error[") == 2
        assert "8 more findings" in text


class TestRunMisbCheck:
    def test_binary_missing_raises_unavailable(self, checker):
        with patch.object(checker, "find_misb_check", return_value=""):
            with pytest.raises(checker.MisbCheckUnavailable):
                checker.run_misb_check("x.ts")

    def test_exit_zero_passes(self, checker):
        with patch("subprocess.run", return_value=_completed(PASS_ENTRY, 0)):
            report = checker.run_misb_check("flight.ts", binary="misb-check")
        assert report.passed

    def test_exit_one_returns_findings(self, checker):
        with patch("subprocess.run", return_value=_completed(FAIL_ENTRY, 1)):
            report = checker.run_misb_check("bad.klv", binary="misb-check")
        assert not report.passed
        assert report.findings[0].code == "CHECKSUM"

    def test_exit_two_raises_error(self, checker):
        proc = _completed({}, 2)
        proc.stdout = ""
        proc.stderr = "usage: misb-check ..."
        with patch("subprocess.run", return_value=proc):
            with pytest.raises(checker.MisbCheckError, match="exit 2"):
                checker.run_misb_check("bad.klv", binary="misb-check")

    def test_binary_not_runnable(self, checker):
        with patch("subprocess.run", side_effect=FileNotFoundError("nope")):
            with pytest.raises(checker.MisbCheckUnavailable):
                checker.run_misb_check("x.ts", binary="misb-check")

    def test_timeout_raises_error(self, checker):
        with patch(
            "subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="misb-check", timeout=1),
        ):
            with pytest.raises(checker.MisbCheckError, match="timed out"):
                checker.run_misb_check("x.ts", binary="misb-check", timeout=1)

    def test_malformed_output_raises_error(self, checker):
        proc = _completed({}, 0)
        proc.stdout = "not json"
        with patch("subprocess.run", return_value=proc):
            with pytest.raises(checker.MisbCheckError, match="parse"):
                checker.run_misb_check("x.ts", binary="misb-check")

    def test_args_use_json_format(self, checker):
        with patch(
            "subprocess.run", return_value=_completed(PASS_ENTRY, 0)
        ) as run_mock:
            checker.run_misb_check("flight.ts", binary="/opt/misb-check")
        args = run_mock.call_args[0][0]
        assert args == ["/opt/misb-check", "--format", "json", "flight.ts"]


class TestFindMisbCheck:
    def test_env_var_override(self, checker, tmp_path):
        fake = tmp_path / "misb-check"
        fake.write_text("#!/bin/sh\n")
        with patch.dict(os.environ, {checker.ENV_VAR: str(fake)}):
            checker.invalidate_cache()
            assert checker.find_misb_check() == str(fake)

    def test_missing_everywhere_returns_empty(self, checker):
        with patch.dict(os.environ, {checker.ENV_VAR: ""}):
            with patch("shutil.which", return_value=None):
                checker.invalidate_cache()
                assert checker.find_misb_check() == ""


def _real_binary():
    return os.environ.get("QGISFMV_MISB_CHECK") or shutil.which("misb-check")


@pytest.mark.skipif(_real_binary() is None, reason="misb-check binary not installed")
class TestRealBinary:
    """End-to-end against the plugin's own KLV test sample."""

    DATA = Path(__file__).resolve().parent / "data"

    def test_flags_bad_checksum_sample(self, checker):
        binary = _real_binary()
        sample = self.DATA / "DynamicConstantMISMMSPacketData.bin"
        report = checker.run_misb_check(str(sample), binary=binary)
        assert not report.passed
        codes = {f.code for f in report.findings}
        assert "CHECKSUM" in codes
