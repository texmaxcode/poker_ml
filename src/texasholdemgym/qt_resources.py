from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path

from PySide6 import QtCore


class QrcRegistrationError(RuntimeError):
     pass
 
 
def _which(cmd: str) -> str | None:
     for p in os.environ.get("PATH", "").split(os.pathsep):
         c = Path(p) / cmd
         if c.is_file() and os.access(c, os.X_OK):
             return str(c)
     return None


def _rcc_from_pyside6() -> str | None:
    """Qt ships `rcc` under PySide6 (often not on PATH); dev installs and CI use this."""
    try:
        import PySide6  # local import — only when PATH lookup failed
    except Exception:
        return None
    libexec = Path(PySide6.__file__).resolve().parent / "Qt" / "libexec" / "rcc"
    if libexec.is_file() and os.access(libexec, os.X_OK):
        return str(libexec)
    return None
 
 
def ensure_qrc_resources_registered(qrc_path: Path, qml_root: Path) -> None:
     """
     Existing QML uses `qrc:/...` for *everything* (Main.qml, assets, training JSON).
 
     In a fully static build, resources are often compiled into the binary. In this Python package,
     we compile a temporary `.rcc` at runtime (dev + CI) and register it.
 
     Requirements:
       - Qt's `rcc` must be available (typically via the Qt install).
         You can point at it via `QT_RCC=/path/to/rcc`.
     """
     if QtCore.QResource(":/Main.qml").isValid():
         return
 
     qrc_path = qrc_path.resolve()
     if not qrc_path.is_file():
         raise QrcRegistrationError(f"qrc not found: {qrc_path}")
 
     rcc = os.environ.get("QT_RCC") or _which("rcc") or _rcc_from_pyside6()
     if not rcc:
         raise QrcRegistrationError(
             "Qt 'rcc' not found on PATH. Install Qt (or set QT_RCC=/path/to/rcc)."
         )
 
     with tempfile.TemporaryDirectory(prefix="texas-holdem-gym-qrc-") as td:
         out = Path(td) / "application.rcc"
         # `rcc` resolves files relative to the qrc file directory.
         subprocess.run(
             [rcc, str(qrc_path), "-binary", "-o", str(out)],
             cwd=str(qml_root),
             check=True,
             stdout=subprocess.PIPE,
             stderr=subprocess.PIPE,
             text=True,
         )
         ok = QtCore.QResource.registerResource(str(out))
         if not ok:
             raise QrcRegistrationError("Failed to register compiled .rcc resource bundle.")
 
