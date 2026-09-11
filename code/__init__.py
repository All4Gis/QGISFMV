import logging
import sys

logger = logging.getLogger("qgis_fmv")


def _bootstrap_plugin():
    from QGIS_FMV.utils.settings.python_deps_bootstrap import bootstrapPythonDepsPath

    bootstrapPythonDepsPath()


# Skip heavy imports when pytest loads ``code`` as a parent package (code/tests).
if "pytest" not in sys.modules:
    _bootstrap_plugin()


def classFactory(iface):
    import os

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
