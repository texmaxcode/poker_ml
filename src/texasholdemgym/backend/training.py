from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from PySide6 import QtCore

if TYPE_CHECKING:
    from texasholdemgym.backend.sqlite_store import AppDatabase

_TRAINING_KV_KEY = "training_store_v1"

_DRILL_KEYS = ("preflop", "flop", "turn", "river")


def _grade_counts_as_correct(grade: str, chosen_freq: float) -> bool:
    """Align with Trainer home copy: Correct if label says so or chosen frequency ≥ 70%."""
    g = str(grade).strip().lower()
    if "wrong" in g:
        return False
    if "mix" in g:
        return False
    if "correct" in g:
        return True
    try:
        f = float(chosen_freq)
    except (TypeError, ValueError):
        f = 0.0
    return f >= 0.7


@dataclass
class _TrainerProgress:
    totalD: int = 0
    correctD: int = 0
    totalEvLossBb: float = 0.0

    def to_map(self) -> dict[str, Any]:
        acc = (100.0 * self.correctD / self.totalD) if self.totalD > 0 else 0.0
        return {
            "totalD": int(self.totalD),
            "correctD": int(self.correctD),
            "accPct": float(acc),
            "totalEvLossBb": float(self.totalEvLossBb),
            # Aliases for QML that used these names.
            "totalDecisions": int(self.totalD),
            "totalCorrect": int(self.correctD),
        }


@dataclass
class _DrillBuckets:
    """Per-street drill counters (preflop / flop / turn / river)."""

    preflop: _TrainerProgress = field(default_factory=_TrainerProgress)
    flop: _TrainerProgress = field(default_factory=_TrainerProgress)
    turn: _TrainerProgress = field(default_factory=_TrainerProgress)
    river: _TrainerProgress = field(default_factory=_TrainerProgress)

    def bucket(self, drill: str) -> _TrainerProgress:
        d = str(drill).strip().lower()
        if d == "preflop":
            return self.preflop
        if d == "flop":
            return self.flop
        if d == "turn":
            return self.turn
        if d == "river":
            return self.river
        return self.preflop

    def to_map(self) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for name in _DRILL_KEYS:
            b = self.bucket(name)
            acc = (100.0 * b.correctD / b.totalD) if b.totalD > 0 else 0.0
            out[name] = {
                "totalD": int(b.totalD),
                "correctD": int(b.correctD),
                "accPct": float(acc),
                "totalEvLossBb": float(b.totalEvLossBb),
            }
        return out

    @staticmethod
    def from_dict(raw: Any) -> "_DrillBuckets":
        b = _DrillBuckets()
        if not isinstance(raw, dict):
            return b
        for name in _DRILL_KEYS:
            sub = raw.get(name)
            if not isinstance(sub, dict):
                continue
            tgt = b.bucket(name)
            tgt.totalD = int(sub.get("totalD", 0))
            tgt.correctD = int(sub.get("correctD", 0))
            tgt.totalEvLossBb = float(sub.get("totalEvLossBb", 0.0))
        return b


class TrainingStore(QtCore.QObject):
    progressChanged = QtCore.Signal()
    trainerAutoAdvanceMsChanged = QtCore.Signal()
    trainerDecisionSecondsChanged = QtCore.Signal()

    def __init__(self, db: AppDatabase | None = None) -> None:
        super().__init__()
        self._db = db
        self._trainer_auto_advance_ms = 2500
        self._trainer_decision_seconds = 10
        self._progress = _TrainerProgress()
        self._drills = _DrillBuckets()
        self._load_from_db()
        self.progressChanged.connect(self._persist_training_kv)

    def _load_from_db(self) -> None:
        if self._db is None:
            return
        m = self._db.kv_get_json(_TRAINING_KV_KEY)
        if not isinstance(m, dict):
            return
        if "trainerAutoAdvanceMs" in m:
            self._trainer_auto_advance_ms = int(m["trainerAutoAdvanceMs"])
        if "trainerDecisionSeconds" in m:
            self._trainer_decision_seconds = int(m["trainerDecisionSeconds"])
        p = m.get("progress")
        if isinstance(p, dict):
            self._progress.totalD = int(p.get("totalD", 0))
            self._progress.correctD = int(p.get("correctD", 0))
            self._progress.totalEvLossBb = float(p.get("totalEvLossBb", 0.0))
        self._drills = _DrillBuckets.from_dict(m.get("drillStats"))

    def _persist_training_kv(self) -> None:
        if self._db is None:
            return
        self._db.kv_set_json(
            _TRAINING_KV_KEY,
            {
                "trainerAutoAdvanceMs": int(self._trainer_auto_advance_ms),
                "trainerDecisionSeconds": int(self._trainer_decision_seconds),
                "progress": {
                    "totalD": int(self._progress.totalD),
                    "correctD": int(self._progress.correctD),
                    "totalEvLossBb": float(self._progress.totalEvLossBb),
                },
                "drillStats": self._drills.to_map(),
            },
        )

    def record_drill_answer(
        self,
        drill: str,
        grade: str,
        chosen_freq: float,
        ev_loss_bb: float,
    ) -> None:
        """Update aggregate + per-drill stats; emit `progressChanged` (persists via signal)."""
        ok = _grade_counts_as_correct(grade, chosen_freq)
        ev = float(ev_loss_bb)
        self._progress.totalD += 1
        if ok:
            self._progress.correctD += 1
        self._progress.totalEvLossBb += ev
        bucket = self._drills.bucket(drill)
        bucket.totalD += 1
        if ok:
            bucket.correctD += 1
        bucket.totalEvLossBb += ev
        self.progressChanged.emit()

    @QtCore.Property(int, notify=trainerAutoAdvanceMsChanged)
    def trainerAutoAdvanceMs(self) -> int:
        return int(self._trainer_auto_advance_ms)

    @trainerAutoAdvanceMs.setter
    def trainerAutoAdvanceMs(self, v: int) -> None:
        v = int(v)
        if v != self._trainer_auto_advance_ms:
            self._trainer_auto_advance_ms = v
            self.trainerAutoAdvanceMsChanged.emit()
            self._persist_training_kv()

    @QtCore.Property(int, notify=trainerDecisionSecondsChanged)
    def trainerDecisionSeconds(self) -> int:
        return int(self._trainer_decision_seconds)

    @trainerDecisionSeconds.setter
    def trainerDecisionSeconds(self, v: int) -> None:
        v = int(v)
        if v != self._trainer_decision_seconds:
            self._trainer_decision_seconds = v
            self.trainerDecisionSecondsChanged.emit()
            self._persist_training_kv()

    @QtCore.Slot(result="QVariantMap")
    def loadProgress(self):
        m = self._progress.to_map()
        m["drillStats"] = self._drills.to_map()
        return m

    @QtCore.Slot()
    def resetProgress(self) -> None:
        self._progress = _TrainerProgress()
        self._drills = _DrillBuckets()
        self.progressChanged.emit()


class Trainer(QtCore.QObject):
    def __init__(self, store: TrainingStore) -> None:
        super().__init__()
        self._store = store
        self._mode = ""
        self._pos = ""
        self._stub_seq = 0

    def _stub_grade_and_freq(self) -> tuple[str, float]:
        """Until real solver grading exists, alternate Correct/Wrong so aggregate accuracy updates."""
        self._stub_seq += 1
        if self._stub_seq % 2 == 1:
            return ("Correct", 0.88)
        return ("Wrong", 0.22)

    def _finish_answer(
        self, drill: str, grade: str, chosen_freq: float, ev_loss_bb: float, extra: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        self._store.record_drill_answer(drill, grade, chosen_freq, ev_loss_bb)
        out: dict[str, Any] = {
            "grade": grade,
            "chosenFreq": float(chosen_freq),
            "evLossBb": float(ev_loss_bb),
        }
        if extra:
            out.update(extra)
        return out

    @QtCore.Slot(str, result="QVariantList")
    def preflopModesForPosition(self, position: str):
        return ["open", "vs_3bet", "sb_vs_btn"] if position else ["open"]

    @QtCore.Slot(str, result=bool)
    def loadPreflopRanges(self, _url: str) -> bool:
        return True

    @QtCore.Slot(str, str)
    def startPreflopDrill(self, position: str, mode: str) -> None:
        self._pos = str(position)
        self._mode = str(mode)

    @QtCore.Slot(result="QVariantMap")
    def nextPreflopQuestion(self):
        # Keys must match PreflopTrainer.qml (`card1` / `card2` are SVG basenames under qrc:/assets/cards/).
        return {
            "spotId": "stub",
            "position": "BTN",
            "mode": "open",
            "card1": "spades_ace.svg",
            "card2": "hearts_king.svg",
            "actions": ["fold", "call", "raise"],
        }

    @QtCore.Slot(str, float, result="QVariantMap")
    def submitPreflopAnswer(self, action: str, amount: float):
        # Stub: replace with real strategy grading; keep keys QML expects.
        g, f = self._stub_grade_and_freq()
        return self._finish_answer(
            "preflop",
            g,
            f,
            0.0,
            {"bestAction": "raise"},
        )

    @QtCore.Slot(str, result=bool)
    def loadFlopSpots(self, _url: str) -> bool:
        return True

    @QtCore.Slot(str)
    def startFlopDrill(self, spot_id: str) -> None:
        self._mode = str(spot_id)

    @QtCore.Slot(result="QVariantMap")
    def nextFlopQuestion(self):
        return {
            "spotId": "stub",
            "hero1": "spades_ace.svg",
            "hero2": "diamonds_queen.svg",
            "board0": "hearts_ace.svg",
            "board1": "diamonds_king.svg",
            "board2": "clubs_2.svg",
            "potBb": 6,
            "actions": ["check", "bet33", "bet75"],
        }

    @QtCore.Slot(str, result="QVariantMap")
    def submitFlopAnswer(self, action: str):
        g, f = self._stub_grade_and_freq()
        return self._finish_answer("flop", g, f, 0.12)

    @QtCore.Slot(str, result=bool)
    def loadTurnSpots(self, _url: str) -> bool:
        return True

    @QtCore.Slot(str)
    def startTurnDrill(self, spot_id: str) -> None:
        self._mode = str(spot_id)

    @QtCore.Slot(result="QVariantMap")
    def nextTurnQuestion(self):
        return {
            "spotId": "stub",
            "hero1": "spades_ace.svg",
            "hero2": "diamonds_queen.svg",
            "board0": "hearts_ace.svg",
            "board1": "diamonds_king.svg",
            "board2": "clubs_2.svg",
            "board3": "clubs_7.svg",
            "potBb": 10,
            "actions": ["check", "bet33", "bet75"],
        }

    @QtCore.Slot(str, result="QVariantMap")
    def submitTurnAnswer(self, action: str):
        g, f = self._stub_grade_and_freq()
        return self._finish_answer("turn", g, f, 0.08)

    @QtCore.Slot(str, result=bool)
    def loadRiverSpots(self, _url: str) -> bool:
        return True

    @QtCore.Slot(str)
    def startRiverDrill(self, spot_id: str) -> None:
        self._mode = str(spot_id)

    @QtCore.Slot(result="QVariantMap")
    def nextRiverQuestion(self):
        return {
            "spotId": "stub",
            "hero1": "spades_ace.svg",
            "hero2": "diamonds_queen.svg",
            "board0": "hearts_ace.svg",
            "board1": "diamonds_king.svg",
            "board2": "clubs_2.svg",
            "board3": "clubs_7.svg",
            "board4": "diamonds_3.svg",
            "potBb": 18,
            "actions": ["check", "bet33", "bet75"],
        }

    @QtCore.Slot(str, result="QVariantMap")
    def submitRiverAnswer(self, action: str):
        g, f = self._stub_grade_and_freq()
        return self._finish_answer("river", g, f, 0.25)
