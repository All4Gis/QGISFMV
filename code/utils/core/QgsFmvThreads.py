# -*- coding: utf-8 -*-
"""Safe QThread teardown helpers.

Qt aborts (qFatal) if a still-running QThread is destroyed as a QObject child
of a widget. On QGIS quit, docks are destroyed even when closeEvent/unload
ordering is messy — always detach + quit/wait before parents go away.
"""


def stop_qthread(thread, timeout_ms=2000):
    """Detach, quit, and wait for a QThread. Safe to call with None / twice."""
    if thread is None:
        return
    try:
        # Detach first so a parent QWidget destructor cannot qFatal on us.
        thread.setParent(None)
    except Exception as exc:
        from QGISFMV.utils.logging import log
        log.debug("thread setParent(None) failed: %s", exc)
    try:
        if thread.isRunning():
            thread.quit()
            if not thread.wait(int(timeout_ms)):
                thread.terminate()
                thread.wait(500)
    except Exception as exc:
        from QGISFMV.utils.logging import log
        log.debug("thread quit/wait failed: %s", exc)
