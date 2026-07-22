# -*- coding: utf-8 -*-
import logging
import sys

logger = logging.getLogger("qgis_fmv")


def _bootstrap_plugin():
    from QGISFMV.utils.settings.python_deps_bootstrap import bootstrapPythonDepsPath

    bootstrapPythonDepsPath()
    from QGISFMV.gui import resources_rc  # noqa: F401  (registers Qt resources/icons)


# Skip heavy imports when pytest loads ``code`` as a parent package (code/tests).
if "pytest" not in sys.modules:
    _bootstrap_plugin()


def classFactory(iface):
    import os
    from .QgsFmv import Fmv

    plugin = Fmv(iface)

    if os.environ.get("FRAN_DEBUG") == "1":
        try:
            import debugpy

            debugpy.connect(("localhost", 5678))
            logger.debug("[QGISFMV] debugpy connected on localhost:5678")
        except ImportError:
            logger.warning(
                "[QGISFMV] debugpy not found — run debug_qgis.sh or: "
                'pip3 install --target="$HOME/Library/Application Support/QGIS/QGIS4/profiles/default/python" debugpy'
            )
        except Exception as exc:
            logger.error("[QGISFMV] debugpy error: %s", exc)

    return plugin
