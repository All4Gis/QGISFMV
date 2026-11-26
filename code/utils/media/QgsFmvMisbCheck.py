"""Run the external ``misb-check`` ST 0601 KLV validator and parse its report.

``misb-check`` (from the ``misb`` crate, https://github.com/Mattbusel/misb)
validates the MISB ST 0601 KLV metadata carried in drone video (STANAG 4609)
and reports problems that silently misplace the video footprint on the map:
bad checksums, wrong-size tags, impossible sensor/frame-center geometry and
slant-range inconsistencies. It is an optional dependency: users install the
binary themselves (``cargo install misb`` or a release binary) and this
module shells out to it, exactly like the plugin shells out to FFmpeg.

Binary resolution order:

1. ``QGISFMV_MISB_CHECK`` environment variable (explicit path override)
2. ``misb-check`` on the ``PATH``

Exit status contract of the CLI: 0 = pass, 1 = validation findings,
2 = unreadable input or bad arguments. Both 0 and 1 carry a JSON report on
stdout when ``--format json`` is given.
"""

import json
import os
import platform
import shutil
import subprocess
from dataclasses import dataclass, field

try:
    from QGIS_FMV.utils.logging import log
except ImportError:
    import logging

    log = logging.getLogger("qgis_fmv")

_windows = platform.system() == "Windows"

ENV_VAR = "QGISFMV_MISB_CHECK"
DEFAULT_TIMEOUT = 600

_misb_check_path = "misb-check.exe" if _windows else "misb-check"


class MisbCheckUnavailable(RuntimeError):
    """The misb-check binary could not be found."""


class MisbCheckError(RuntimeError):
    """misb-check ran but failed to produce a report (exit status 2)."""


@dataclass
class MisbFinding:
    """One validation finding from the misb-check JSON report."""

    severity: str
    code: str
    message: str
    pid: int | None = None
    packet: int | None = None
    offset: int | None = None
    tag: int | None = None


@dataclass
class MisbReport:
    """Validation report for a single file."""

    file: str
    container: str
    passed: bool
    packets: int
    errors: int
    warnings: int
    findings: list = field(default_factory=list)


def find_misb_check():
    """Return the resolved misb-check binary path, or "" when not found."""
    global _misb_check_path

    if _misb_check_path and os.path.isfile(_misb_check_path):
        return _misb_check_path

    override = os.environ.get(ENV_VAR, "").strip()
    if override and os.path.isfile(override):
        _misb_check_path = override
        return _misb_check_path

    found = shutil.which("misb-check.exe" if _windows else "misb-check")
    if found:
        _misb_check_path = found

    return _misb_check_path if os.path.isfile(_misb_check_path or "") else ""


def invalidate_cache():
    """Force re-resolution on next call (after installing the binary)."""
    global _misb_check_path
    _misb_check_path = "misb-check.exe" if _windows else "misb-check"


def parse_report(data):
    """Build a :class:`MisbReport` from one entry of the JSON report."""
    findings = [
        MisbFinding(
            severity=f.get("severity", ""),
            code=f.get("code", ""),
            message=f.get("message", ""),
            pid=f.get("pid"),
            packet=f.get("packet"),
            offset=f.get("offset"),
            tag=f.get("tag"),
        )
        for f in data.get("findings", [])
    ]
    return MisbReport(
        file=data.get("file", ""),
        container=data.get("container", ""),
        passed=bool(data.get("passed")),
        packets=int(data.get("packets", 0)),
        errors=int(data.get("errors", 0)),
        warnings=int(data.get("warnings", 0)),
        findings=findings,
    )


def run_misb_check(path, binary=None, timeout=DEFAULT_TIMEOUT):
    """Run ``misb-check --format json`` on *path* and return the report.

    Raises :class:`MisbCheckUnavailable` when the binary is missing and
    :class:`MisbCheckError` when the run itself fails (unreadable input,
    timeout, or malformed output).
    """
    exe = binary or find_misb_check()
    if not exe:
        raise MisbCheckUnavailable(
            "misb-check binary not found. Install it with "
            "'cargo install misb' or set the " + ENV_VAR + " environment "
            "variable to the binary path."
        )

    kwargs = {
        "capture_output": True,
        "text": True,
        "timeout": timeout,
    }
    if _windows:
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)

    try:
        proc = subprocess.run([exe, "--format", "json", path], **kwargs)
    except FileNotFoundError as exc:
        raise MisbCheckUnavailable(f"misb-check not runnable: {exc}") from exc
    except subprocess.TimeoutExpired as exc:
        raise MisbCheckError(
            f"misb-check timed out after {timeout} s on {path}"
        ) from exc
    except OSError as exc:
        raise MisbCheckError(f"could not run misb-check: {exc}") from exc

    if proc.returncode not in (0, 1):
        detail = (proc.stderr or "").strip()
        raise MisbCheckError(
            f"misb-check failed on {path} (exit {proc.returncode})"
            + (f": {detail}" if detail else "")
        )

    try:
        entries = json.loads(proc.stdout)
        report = parse_report(entries[0])
    except (ValueError, IndexError, KeyError, TypeError) as exc:
        raise MisbCheckError(
            f"could not parse misb-check output for {path}: {exc}"
        ) from exc

    log.debug(
        "misb-check %s: passed=%s errors=%s warnings=%s packets=%s",
        path,
        report.passed,
        report.errors,
        report.warnings,
        report.packets,
    )
    return report


def format_report(report, max_findings=20):
    """Render a :class:`MisbReport` as human-readable text."""
    verdict = "PASS" if report.passed else "FAIL"
    lines = [
        f"{report.file}: {verdict} "
        f"({report.errors} errors, {report.warnings} warnings, "
        f"{report.packets} ST 0601 packets, {report.container})"
    ]
    shown = 0
    for f in report.findings:
        if max_findings and shown >= max_findings:
            break
        where = []
        if f.packet is not None:
            where.append(f"packet {f.packet}")
        if f.tag is not None:
            where.append(f"tag {f.tag}")
        prefix = f" ({', '.join(where)})" if where else ""
        lines.append(f"{f.severity}[{f.code}]{prefix}: {f.message}")
        shown += 1
    remaining = len(report.findings) - shown
    if remaining > 0:
        lines.append(f"... {remaining} more findings")
    return "\n".join(lines)
