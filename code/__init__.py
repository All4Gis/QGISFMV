import logging
import sys

logger = logging.getLogger("qgis_fmv")


def _bootstrap_plugin():
    from QGIS_FMV.utils.settings.python_deps_bootstrap import bootstrapPythonDepsPath

    bootstrapPythonDepsPath()


def _ensure_pymisb(iface):
    """Install pymisb before QgsFmv imports. Remaining deps run in a QgsTask."""
    from QGIS_FMV.utils.settings.python_deps_bootstrap import ensurePymisb

    ok, err = ensurePymisb()
    if ok:
        return
    detail = err or "network, proxy, or SSL error"
    logger.error("[QGIS_FMV] Could not auto-install pymisb: %s", detail)
    try:
        from qgis.core import Qgis as QGis

        iface.messageBar().pushMessage(
            "QGIS FMV",
            "Could not install pymisb (%s). Open FMV Settings to retry." % detail,
            QGis.MessageLevel.Critical,
            15,
        )
    except Exception:
        pass


# Skip heavy imports when pytest loads ``code`` as a parent package (code/tests).
if "pytest" not in sys.modules:
    _bootstrap_plugin()


def classFactory(iface):
    import os

    # QGIS Plugin Manager has no pip hook — first enable must install pymisb.
    _ensure_pymisb(iface)

    from .QgsFmv import Fmv

    plugin = Fmv(iface)

    if os.environ.get("QGISFMV_DEBUG") == "1":
        try:
            import debugpy

            debugpy.connect(("localhost", 5678))
            logger.debug("[QGIS_FMV] debugpy connected on localhost:5678")
        except ImportError:
            logger.warning(
                "[QGIS_FMV] debugpy not found — run debug_qgis.sh or: "
                'pip3 install --target="$HOME/Library/Application Support/QGIS/QGIS4/profiles/default/python" debugpy'
            )
        except Exception as exc:
            logger.error("[QGIS_FMV] debugpy error: %s", exc)

    return plugin
