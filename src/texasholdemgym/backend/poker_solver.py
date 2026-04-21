from __future__ import annotations

import random

from PySide6 import QtCore


class PokerSolver(QtCore.QObject):
     equityComputationFinished = QtCore.Signal("QVariantMap")
 
     @QtCore.Slot(str, str, str, str, str, str, int, int, int)
     def computeEquityAsync(
         self,
         hero1: str,
         hero2: str,
         board: str,
         villain_range: str,
         villain_e1: str,
         villain_e2: str,
         iterations: int,
         pot_before_call: int,
         to_call: int,
     ) -> None:
         # Placeholder: emits plausible-ish numbers so UI wiring works.
         it = int(iterations) if int(iterations) > 0 else 1000
         eq = 50.0 + random.uniform(-8.0, 8.0)
         se = max(0.2, 100.0 / (it ** 0.5))
         m = {
             "equityPct": float(eq),
             "stdErrPct": float(se),
             "iterations": int(it),
             "detailText": "Python port stub (no real simulation yet).",
         }
         # EV helper fields are optional; leave out for now.
         QtCore.QTimer.singleShot(10, lambda: self.equityComputationFinished.emit(m))
 
