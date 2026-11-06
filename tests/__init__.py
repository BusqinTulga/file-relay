"""Isolate every test runner before application modules capture data_root."""
import atexit
import os
import tempfile

_test_root = tempfile.TemporaryDirectory(prefix="filerelay-tests-")
os.environ["FILERELAY_DATA_ROOT"] = _test_root.name
atexit.register(_test_root.cleanup)
