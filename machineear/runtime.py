"""Make project-local Windows native dependencies discoverable on demand."""

import os
from pathlib import Path
import sys

_DLL_HANDLES = []


def prepare_native_runtime():
    """Register the active environment's runtime DLLs, without system changes."""
    if os.name != "nt" or _DLL_HANDLES:
        return
    # msvc-runtime installs into sys.prefix and Scripts. Keep the handles alive
    # for this process; registration ends when the process exits.
    for directory in (Path(sys.prefix), Path(sys.prefix) / "Scripts"):
        if directory.is_dir():
            _DLL_HANDLES.append(os.add_dll_directory(str(directory)))
