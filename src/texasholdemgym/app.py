from __future__ import annotations

import os
import sys
from pathlib import Path

from PySide6 import QtCore, QtGui, QtQml

from texasholdemgym.backend.hand_history import HandHistory
from texasholdemgym.backend.poker_game import PokerGame
from texasholdemgym.backend.poker_solver import PokerSolver
from texasholdemgym.backend.session_store import SessionStore
from texasholdemgym.backend.sqlite_store import AppDatabase
from texasholdemgym.backend.toy_nash_solver import ToyNashSolver
from texasholdemgym.backend.training import Trainer, TrainingStore
from texasholdemgym.qt_resources import ensure_qrc_resources_registered


def _repo_root_from_here() -> Path:
    # src/texasholdemgym/app.py -> repo root (dev mode). For installed wheels,
    # resources must be packaged; for now we support running from source.
    return Path(__file__).resolve().parents[2]


def _qml_root(repo_root: Path) -> Path:
    return repo_root / "poker" / "qml"


def _set_default_env() -> None:
    # Allow QML XMLHttpRequest to read bundled training JSON from qrc paths.
    os.environ.setdefault("QML_XHR_ALLOW_FILE_READ", "1")

    # Prefer Wayland when present (typical Linux desktop default).
    if "QT_QPA_PLATFORM" not in os.environ:
        if os.environ.get("WAYLAND_DISPLAY") or os.environ.get("XDG_SESSION_TYPE") == "wayland":
            os.environ["QT_QPA_PLATFORM"] = "wayland"


def _register_fonts() -> dict[str, str]:
    # Fonts are referenced by qrc paths in the existing QML.
    def family_from_qrc(path: str) -> str:
        fid = QtGui.QFontDatabase.addApplicationFont(path)
        if fid < 0:
            return ""
        fams = QtGui.QFontDatabase.applicationFontFamilies(fid)
        return fams[0] if fams else ""

    fam_ui = family_from_qrc(":/assets/fonts/Merriweather-opsz-wdth-wght.ttf") or "Merriweather"
    fam_display = family_from_qrc(":/assets/fonts/Rye-Regular.ttf") or "Rye"
    fam_button = family_from_qrc(":/assets/fonts/HoltwoodOneSC-Regular.ttf") or "Holtwood One SC"
    fam_mono = family_from_qrc(":/assets/fonts/RobotoMono-wght.ttf") or "Roboto Mono"

    f = QtGui.QFont()
    f.setFamily(fam_ui)
    f.setWeight(QtGui.QFont.Weight.Normal)
    f.setPointSizeF(13.0)
    QtGui.QGuiApplication.setFont(f)

    return {
        "appFontFamily": fam_ui,
        "appFontFamilyDisplay": fam_display,
        "appFontFamilyButton": fam_button,
        "appFontFamilyMono": fam_mono,
    }


def main(argv: list[str] | None = None) -> int:
    _set_default_env()
    argv = argv if argv is not None else sys.argv

    QtCore.QCoreApplication.setOrganizationName("TexasHoldemGym")
    QtCore.QCoreApplication.setApplicationName("Texas Hold'em Gym")
    QtCore.QCoreApplication.setApplicationVersion(os.environ.get("POKER_APP_VERSION", "0.1+py"))

    app = QtGui.QGuiApplication(argv)

    qml_root = _qml_root(_repo_root_from_here())
    ensure_qrc_resources_registered(qml_root / "application.qrc", qml_root)

    app_icon = QtGui.QIcon(":/assets/images/logo.png")
    app.setWindowIcon(app_icon)
    app.setDesktopFileName("texas-holdem-gym")

    fonts = _register_fonts()

    db = AppDatabase()
    hand_history = HandHistory(db)
    poker_game = PokerGame(db=db, hand_history=hand_history)
    poker_solver = PokerSolver()
    toy_nash_solver = ToyNashSolver()
    training_store = TrainingStore(db)
    trainer = Trainer(training_store)
    session_store = SessionStore(db)
    poker_game.loadPersistedSettings()

    engine = QtQml.QQmlApplicationEngine()

    # Allow resolving `import Theme 1.0` and `import PokerUi 1.0` via qmldir files.
    engine.addImportPath(str(qml_root))
    engine.addImportPath("qrc:/")

    ctx = engine.rootContext()
    for k, v in fonts.items():
        ctx.setContextProperty(k, v)
    ctx.setContextProperty("appVersion", QtCore.QCoreApplication.applicationVersion())
    ctx.setContextProperty("pokerGame", poker_game)
    ctx.setContextProperty("pokerSolver", poker_solver)
    ctx.setContextProperty("toyNashSolver", toy_nash_solver)
    ctx.setContextProperty("trainingStore", training_store)
    ctx.setContextProperty("trainer", trainer)
    ctx.setContextProperty("sessionStore", session_store)
    ctx.setContextProperty("handHistory", hand_history)

    engine.load(QtCore.QUrl("qrc:/Main.qml"))

    if not engine.rootObjects():
        return 1

    def _try_bind_game_screen() -> bool:
        win = engine.rootObjects()[0] if engine.rootObjects() else None
        gp = win.findChild(QtCore.QObject, "game_screen") if win else None
        if not gp:
            return False
        poker_game.setRootObject(gp)
        poker_game.beginNewHand()
        return True

    # Pump the event loop so `StackLayout` + delegates finish building; then bind immediately.
    # A fixed `singleShot(400)` alone can still miss on slow hosts or leave stacks unsynced until first visit.
    for _ in range(200):
        app.processEvents()
        if _try_bind_game_screen():
            break
    else:

        def _bind_game_screen_retry() -> None:
            if _try_bind_game_screen():
                return
            QtCore.QTimer.singleShot(200, _bind_game_screen_retry)

        QtCore.qWarning("game_screen not found after initial bind loop; retrying on a timer.")
        QtCore.QTimer.singleShot(0, _bind_game_screen_retry)

    return app.exec()
