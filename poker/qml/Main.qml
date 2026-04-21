import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Window
import Theme 1.0
import PokerUi 1.0

/// Root window — pages live under `screens/`; shared UI in `components/` (`PokerUi` module).
ApplicationWindow {
    id: win
    /// Open maximized immediately. `showMaximized()` in `Component.onCompleted` ran *after* the first
    /// paint at `width`/`height`, which caused a visible resize jump on startup.
    visibility: Window.Maximized
    /// Show immediately — avoids a frame at implicit size before `visibility` applies on some platforms.
    visible: true

    function syncTrainerClocksOnResume() {
        if (preflopTrainerPage.visible)
            preflopTrainerPage.syncTrainerClocks()
        if (flopTrainerPage.visible)
            flopTrainerPage.syncTrainerClocks()
        if (turnTrainerPage.visible)
            turnTrainerPage.syncTrainerClocks()
        if (riverTrainerPage.visible)
            riverTrainerPage.syncTrainerClocks()
    }

    onActiveChanged: function () {
        if (win.active)
            syncTrainerClocksOnResume()
    }

    onVisibilityChanged: function () {
        if (win.visibility !== Window.Hidden && win.visibility !== Window.Minimized)
            syncTrainerClocksOnResume()
    }

    width: Metrics.windowWidthDefault
    height: Metrics.windowHeightDefault
    minimumWidth: Metrics.windowMinWidth
    minimumHeight: Metrics.windowMinHeight

    /// Shrink header chrome proportionally — 700px short-side → scale 1.0; smaller windows get compact chrome.
    readonly property real chromeScale: Math.min(1.0, Math.min(width, height) / 700.0)

    title: qsTr("Texas Hold'em Gym")
    color: Theme.bgWindow

    // GroupBox titles, ComboBox, SpinBox, and other Controls read palette roles; defaults are light-theme (black text).
    palette: Palette {
        window: Theme.bgWindow
        windowText: Theme.textPrimary
        base: Theme.inputBg
        alternateBase: Theme.panelElevated
        text: Theme.textPrimary
        button: Theme.panel
        buttonText: Theme.textPrimary
        highlight: Theme.panelBorder
        highlightedText: Theme.textPrimary
        toolTipBase: Theme.panelElevated
        toolTipText: Theme.textPrimary
        // Fusion/GroupBox frames use mid/shadow/light; without these, borders vanish on dark window.
        mid: Theme.panelBorder
        dark: Theme.panelBorderMuted
        light: Theme.chromeLine
        shadow: Theme.insetDark
    }

    BrandedBackground {
        z: -1
        anchors.fill: parent
    }

    /// App version from context property `appVersion` (e.g. git describe via env at build time).
    Label {
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        anchors.margins: 10
        z: 1000
        text: typeof appVersion !== "undefined" && appVersion.length > 0 ? appVersion : ""
        font.family: Theme.fontFamilyMono
        font.pointSize: 9
        opacity: 0.4
        color: Theme.textMuted
    }

    font.family: Theme.fontFamilyUi
    font.pointSize: Theme.uiBasePt

    header: ToolBar {
        visible: stack.currentIndex > 0
        implicitHeight: Math.max(40, Math.round(Metrics.toolbarHeight * win.chromeScale))

        background: Rectangle {
            color: Theme.headerBg
            Rectangle {
                anchors.bottom: parent.bottom
                width: parent.width
                height: 1
                color: Theme.headerRule
            }
        }

        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: Math.max(6, Math.round((Metrics.toolbarMarginH + 4) * win.chromeScale))
            anchors.rightMargin: Math.max(6, Math.round((Metrics.toolbarMarginH + 4) * win.chromeScale))
            anchors.topMargin: Math.max(4, Math.round(Metrics.toolbarMarginV * win.chromeScale))
            anchors.bottomMargin: Math.max(4, Math.round(Metrics.toolbarMarginV * win.chromeScale))
            spacing: Math.max(6, Math.round(8 * win.chromeScale))

            /// Lobby — left third
            Item {
                Layout.fillWidth: true
                Layout.minimumWidth: backBtn.implicitWidth

                GameButton {
                    id: backBtn
                    anchors.left: parent.left
                    anchors.verticalCenter: parent.verticalCenter
                    style: "chrome"
                    chromeScale: win.chromeScale
                    overrideHeight: Math.round(Metrics.toolbarChromeHeight * win.chromeScale)
                    text: qsTr("Lobby")
                    iconSource: "qrc:/assets/icons/home.svg"
                    chromeFontFamily: Theme.fontFamilyButton
                    clickEnabled: true
                    onClicked: stack.currentIndex = 0
                }
            }

            /// Page title — center column
            Label {
                Layout.fillWidth: true
                Layout.minimumWidth: 80
                Layout.fillHeight: true
                Layout.alignment: Qt.AlignVCenter
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
                font.family: Theme.fontFamilyDisplay
                font.bold: true
                font.capitalization: Font.AllUppercase
                font.pointSize: Math.max(11, Math.round(Theme.uiToolBarTitlePt * win.chromeScale))
                font.letterSpacing: 1
                color: Theme.gold
                text: headerTitleForIndex(stack.currentIndex)
            }

            /// Transient status (e.g. “Settings saved.”) — right third, opposite Lobby
            Item {
                Layout.fillWidth: true
                Layout.minimumWidth: backBtn.implicitWidth

                Rectangle {
                    id: toastChip
                    visible: win.appToastText.length > 0
                    anchors.right: parent.right
                    anchors.verticalCenter: parent.verticalCenter
                    height: toastBarLabel.implicitHeight + Math.max(10, Math.round(12 * win.chromeScale))
                    width: Math.min(420, Math.max(toastBarLabel.implicitWidth + Math.max(20, Math.round(28 * win.chromeScale)),
                            Math.max(26, Math.round(Metrics.toolbarChromeHeight * win.chromeScale)) * 2))
                    radius: Math.max(8, Math.round(10 * win.chromeScale))
                    color: Qt.tint(Theme.panelElevated, Qt.alpha(Theme.gold, 0.07))
                    border.width: 1
                    border.color: Qt.alpha(Theme.chromeLineGold, 0.45)

                    Label {
                        id: toastBarLabel
                        anchors.centerIn: parent
                        width: Math.min(400, parent.width - Math.max(16, Math.round(22 * win.chromeScale)))
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                        wrapMode: Text.WordWrap
                        maximumLineCount: 2
                        text: win.appToastText
                        color: Theme.goldMuted
                        font.family: Theme.fontFamilyButton
                        font.weight: Font.Medium
                        font.pixelSize: Math.max(13, Math.round((Theme.trainerCaptionPx + 1) * win.chromeScale))
                        font.letterSpacing: 0.35
                    }
                }
            }
        }
    }

    /// Ephemeral message shown in the header opposite the Lobby button (`toastChip`).
    property string appToastText: ""
    function showAppToast(msg) {
        win.appToastText = msg
        appToastTimer.restart()
    }

    Timer {
        id: appToastTimer
        interval: 2600
        repeat: false
        onTriggered: win.appToastText = ""
    }

    function headerTitleForIndex(idx) {
        switch (idx) {
        case 1:
            return qsTr("Texas Hold'em")
        case 2:
            return qsTr("Bots & ranges")
        case 3:
            return qsTr("Solver & equity")
        case 4:
            return qsTr("Stats")
        case 5:
            return qsTr("Training")
        case 6:
            return qsTr("Preflop trainer")
        case 7:
            return qsTr("Flop trainer")
        case 8:
            return qsTr("Turn trainer")
        case 9:
            return qsTr("River trainer")
        case 10:
            return qsTr("Opening ranges")
        case 11:
            return qsTr("Hand history")
        default:
            return ""
        }
    }

    StackLayout {
        id: stack
        anchors.fill: parent
        currentIndex: 0

        /// Previous stack index — used to scroll content to top when returning from the lobby.
        property int _prevIndex: 0

        onCurrentIndexChanged: {
            const cur = stack.currentIndex
            const prev = stack._prevIndex
            if (cur > 0 && prev === 0) {
                Qt.callLater(function () {
                    switch (cur) {
                    case 2:
                        setupPage.scrollMainToTop()
                        break
                    case 3:
                        solverPage.scrollMainToTop()
                        break
                    case 4:
                        statsPage.scrollMainToTop()
                        break
                    case 5:
                        trainerHomePage.scrollMainToTop()
                        break
                    case 6:
                        preflopTrainerPage.scrollMainToTop()
                        break
                    case 7:
                        flopTrainerPage.scrollMainToTop()
                        break
                    case 8:
                        turnTrainerPage.scrollMainToTop()
                        break
                    case 9:
                        riverTrainerPage.scrollMainToTop()
                        break
                    case 10:
                        rangeViewerPage.scrollMainToTop()
                        break
                    case 11:
                        break
                    }
                })
            }
            stack._prevIndex = cur
        }

        Component.onCompleted: stack._prevIndex = stack.currentIndex

        LobbyScreen {
            stackLayout: stack
        }

        GameScreen {
            pokerGameAccess: pokerGame
        }

        SetupScreen {
            id: setupPage
            pokerGameAccess: pokerGame
        }

        SolverScreen {
            id: solverPage
        }

        StatsScreen {
            id: statsPage
            pokerGameAccess: pokerGame
        }

        TrainerHome {
            id: trainerHomePage
            stackLayout: stack
        }

        PreflopTrainer {
            id: preflopTrainerPage
            stackLayout: stack
        }

        FlopTrainer {
            id: flopTrainerPage
            stackLayout: stack
        }

        TurnTrainer {
            id: turnTrainerPage
            stackLayout: stack
        }

        RiverTrainer {
            id: riverTrainerPage
            stackLayout: stack
        }

        RangeViewer {
            id: rangeViewerPage
            stackLayout: stack
        }

        HandHistoryScreen {
            id: handHistoryPage
            stackLayout: stack
        }
    }
}
