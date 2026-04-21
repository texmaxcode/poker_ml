from __future__ import annotations

from PySide6 import QtCore


class ToyNashSolver(QtCore.QObject):
     solveFinished = QtCore.Signal("QVariantMap")
 
     def __init__(self) -> None:
         super().__init__()
         self._running = False
 
     @QtCore.Slot(result=bool)
     def solveRunning(self) -> bool:
         return self._running
 
     @QtCore.Slot(int)
     def solveKuhnAsync(self, iterations: int) -> None:
         self._start("Kuhn", int(iterations))
 
     @QtCore.Slot(int)
     def solveLeducAsync(self, iterations: int) -> None:
         self._start("Leduc", int(iterations))
 
     def _start(self, name: str, iterations: int) -> None:
         if self._running:
             return
         self._running = True
 
         def done():
             self._running = False
             self.solveFinished.emit(
                 {
                     "summaryText": f"{name} solver finished (stub).",
                     "detailText": f"Ran {max(1, iterations)} iterations (no real CFR+ yet).",
                 }
             )
 
         QtCore.QTimer.singleShot(50, done)
 
