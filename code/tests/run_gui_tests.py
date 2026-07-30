# -*- coding: utf-8 -*-
"""
Run all GUI / visual tests inside QGIS.

Paste this into the QGIS Python console or execute via::

    QGISFMV/tests/run_gui_tests.sh

It boots the plugin, runs every test in test_gui_*.py, and prints a summary.
"""

import os
import sys
import traceback

# Ensure the plugin root is on the path
_plugin_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _plugin_root not in sys.path:
    sys.path.insert(0, _plugin_root)

from QGISFMV.tests.gui_test_harness import GUITestHarness

# Test modules to run
_TEST_MODULES = [
    "QGISFMV.tests.test_gui_manager",
    "QGISFMV.tests.test_gui_player",
]


def run_all():
    """Run all GUI tests and print results."""
    harness = GUITestHarness()
    harness.start()

    passed = 0
    failed = 0
    skipped = 0
    errors = []

    for mod_name in _TEST_MODULES:
        print(f"\n{'='*60}")
        print(f"  Module: {mod_name}")
        print(f"{'='*60}")

        try:
            mod = __import__(mod_name, fromlist=[""])
        except Exception as exc:
            print(f"  IMPORT FAILED: {exc}")
            errors.append((mod_name, str(exc)))
            failed += 1
            continue

        # Find all test classes
        for attr_name in dir(mod):
            attr = getattr(mod, attr_name)
            if not isinstance(attr, type) or not attr_name.startswith("Test"):
                continue

            print(f"\n  Class: {attr_name}")

            # Find all test methods
            for method_name in sorted(dir(attr)):
                if not method_name.startswith("test_"):
                    continue

                method = getattr(attr, method_name)
                if not callable(method):
                    continue

                test_id = f"{attr_name}.{method_name}"
                try:
                    # Create instance and run
                    instance = attr()
                    instance.harness = harness
                    method(instance)
                    print(f"    PASS  {test_id}")
                    passed += 1
                except pytest.skip.Exception:
                    print(f"    SKIP  {test_id}")
                    skipped += 1
                except AssertionError as exc:
                    print(f"    FAIL  {test_id}: {exc}")
                    errors.append((test_id, str(exc)))
                    failed += 1
                except Exception as exc:
                    print(f"    ERROR {test_id}: {exc}")
                    traceback.print_exc()
                    errors.append((test_id, str(exc)))
                    failed += 1

    # Summary
    print(f"\n{'='*60}")
    print(f"  RESULTS: {passed} passed, {failed} failed, {skipped} skipped")
    print(f"{'='*60}")

    if errors:
        print("\n  Failures:")
        for test_id, msg in errors:
            print(f"    - {test_id}: {msg}")

    harness.stop()
    return failed == 0


# Allow import as a module or direct execution
if __name__ == "__main__":
    import pytest

    success = run_all()
    sys.exit(0 if success else 1)
