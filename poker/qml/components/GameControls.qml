import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Window
import Theme 1.0
import PokerUi 1.0

/// Bottom HUD (full width) or floating panel beside the human seat (`embeddedMode`).
Item {
    id: game_controls
    width: game_controls.embeddedMode ? (game_controls.panelWidth > 0 ? game_controls.panelWidth : implicitWidth) : (parent ? parent.width : implicitWidth)
    /// Panel chrome: top inset (`mainColTopMargin`) + column + bottom inset (`barBottomPad`).
    height: mainCol.height + mainColTopMargin + barBottomPad

    /// When true, use compact timer row instead of full-width status row.
    property bool embeddedMode: false
    /// When true, FOLD/CALL/RAISE + raise sizing emit `trainerAction` instead of `pokerGame` (must be above `trainerDockScale`).
    property bool trainerMode: false
    /// Set from `GameScreen` (`tableArea.tableScale`) so the embedded HUD shrinks with the table.
    property real hudScale: 1.0
    /// Embedded HUD scale: follows table + a small boost from window short side so chrome stays readable on 720p-class windows.
    readonly property real _winShort: {
        var w = Window.window
        return (w && w.width > 0) ? Math.min(w.width, w.height) : 720
    }
    readonly property real ez: embeddedMode ? Math.max(0.58, Math.min(1.0, hudScale * (1.0 + 0.06 * Math.min(1.0, _winShort / 900.0)))) : 1.0
    /// Full-width trainer dock: shrink buttons / spacing on narrow columns (min window / small drill panel).
    readonly property real trainerDockScale: {
        if (!trainerMode || embeddedMode)
            return 1.0
        var w = game_controls.width
        if (w <= 0)
            return 0.82
        return Math.min(1.0, Math.max(0.58, w / 380.0))
    }
    /// Trainer full-width dock: scaled pill targets so FOLD/CALL/RAISE fit narrow panels.
    readonly property int actPill76: (trainerMode && !embeddedMode) ? Math.max(52, Math.round(76 * trainerDockScale)) : 76
    readonly property int actPill88: (trainerMode && !embeddedMode) ? Math.max(56, Math.round(88 * trainerDockScale)) : 88
    readonly property int actPill108: (trainerMode && !embeddedMode) ? Math.max(64, Math.round(108 * trainerDockScale)) : 108

    readonly property int hudBtnPt: {
        var base = Math.max(9, Math.round(Theme.uiHudButtonPt * ez))
        if (trainerMode && !embeddedMode)
            return Math.max(8, Math.round(base * trainerDockScale))
        return base
    }
    readonly property int hudActBtnH: {
        var base = Math.max(26, Math.round(34 * ez))
        if (trainerMode && !embeddedMode)
            return Math.max(22, Math.round(base * trainerDockScale))
        return base
    }
    readonly property int hudBodyPx: {
        var base = Math.max(10, Math.round(Theme.uiBodyPx * ez))
        if (trainerMode && !embeddedMode)
            return Math.max(9, Math.round(base * trainerDockScale))
        return base
    }
    /// Narrow windows / embedded HUD: slightly smaller status line to save vertical space.
    readonly property bool statusLayoutTight: embeddedMode
            || (Window.window !== null && Window.window.width > 0 && Window.window.width < 520)
    readonly property int statusHudBodyPx: statusLayoutTight
            ? Math.max(9, Math.round((Theme.uiBodyPx - 1) * ez))
            : hudBodyPx
    readonly property int hudMicroPx: Math.max(8, Math.round(Theme.uiMicroPx * ez))
    readonly property int hudSmallPx: Math.max(9, Math.round(Theme.uiSmallPx * ez))
    /// Timer row (“Act”, seconds) — slightly larger than micro copy for legibility.
    readonly property int hudTimerLabelPx: Math.max(10, Math.round((Theme.uiSmallPx + 1) * ez))

    readonly property int barBottomPad: embeddedMode ? Math.max(3, Math.round(6 * ez)) : (trainerMode ? 6 : 12)
    /// Inset below the panel top border — timer / “Act” row (embedded HUD was flush to the edge at 1px).
    readonly property int mainColTopMargin: embeddedMode ? Math.max(5, Math.round(11 * ez)) : (trainerMode ? 6 : 10)
    readonly property int mainColSpacing: embeddedMode ? Math.max(3, Math.round(5 * ez)) : (trainerMode ? 6 : 12)
    /// Horizontal gap between FOLD / CALL / RAISE (and similar action rows).
    readonly property int actionRowSpacing: {
        if (embeddedMode)
            return Math.max(6, Math.round(14 * ez))
        if (trainerMode)
            return Math.max(3, Math.round(12 * trainerDockScale))
        return 16
    }
    readonly property int embeddedTimerRowMinH: Math.max(18, Math.round(22 * ez))
    /// Uniform inset inside the HUD panel so rows/columns line up (avoid mixing `x: 8` with ad‑hoc widths).
    readonly property int hudSideMargin: embeddedMode ? Math.max(4, Math.round(8 * ez)) : 11
    /// Used when `embeddedMode` is true; set from `GameScreen` so the panel does not span the table width.
    property real panelWidth: 0

    property var pageRoot: null
    property var pokerGame: null
    property bool humanSitOut: false
    property string statusText: ""
    /// Trainer / HUD: secondary line (e.g. “Next hand in N s”) shown beside the timer strip, not merged into `statusText`.
    property string statusSubText: ""
    property string humanHandText: ""
    property int decisionSecondsLeft: 0
    /// For progress bar scaling (table = 20s; trainers may use `trainingStore.trainerDecisionSeconds`).
    property int decisionTimeTotal: 20
    property bool humanMoreTimeAvailable: false
    property bool humanCanCheck: false
    property bool humanBbPreflopOption: false
    property bool humanCanRaiseFacing: false
    property bool humanBbCanRaise: false
    property int facingNeedChips: 0
    property int facingMinRaiseChips: 0
    property int facingMaxChips: 0
    property int facingPotAmount: 0
    property int openRaiseMinChips: 0
    property int openRaiseMaxChips: 0
    property int bbPreflopMinChips: 0
    property int bbPreflopMaxChips: 0
    property int humanStackChips: 0
    property bool humanCanBuyBackIn: false
    property int buyInChips: 100

    /// With `trainerMode`, use flop drill actions (CHECK / Bet 33% / Bet 75%) instead of FOLD/CALL/RAISE.
    property bool trainerFlopStreet: false
    /// Disables actions (e.g. trainer auto-advance) while keeping the HUD visible.
    property bool trainerInputLocked: false

    signal trainerAction(string action, int amountChips)

    /// Mirrors `pokerGame.interactiveHuman` — NOTIFY on nested `var` refs is unreliable for RowLayout bindings.
    property bool engineHumanInteractive: true

    function refreshEngineHumanInteractive() {
        if (!pokerGame) {
            engineHumanInteractive = true
            return
        }
        engineHumanInteractive = pokerGame.interactiveHuman !== false
    }

    Component.onCompleted: refreshEngineHumanInteractive()
    onPokerGameChanged: refreshEngineHumanInteractive()

    Connections {
        enabled: game_controls.pokerGame !== null
        target: game_controls.pokerGame
        function onInteractiveHumanChanged() {
            game_controls.refreshEngineHumanInteractive()
        }
    }

    /// Seat 0 is played by engine bots (vs interactive human actions).
    readonly property bool playingAsBot: pokerGame !== null && !engineHumanInteractive
    /// Act / countdown / bar live on `Player` street row when embedded or in trainers — avoid duplicate chrome.
    readonly property bool showHudActTimerRow: game_controls.humanDecisionActive && !game_controls.trainerMode && !game_controls.embeddedMode
    /// “More” time stays in the panel beside the seat when embedded (`showHudActTimerRow` is off there).
    readonly property bool showMoreTimeButton: game_controls.humanMoreTimeAvailable && game_controls.humanDecisionActive && !game_controls.trainerMode
    readonly property bool humanDecisionActive: trainerMode ? (!trainerInputLocked && decisionSecondsLeft > 0) : (decisionSecondsLeft > 0 && humanStackChips > 0)
    readonly property bool humanHasChips: humanStackChips > 0
    /// Busted (0 stack) players watch but do not get the action UI.
    readonly property bool showWagerUi: !humanSitOut && humanStackChips > 0
    readonly property bool facingRaise: !humanCanCheck && !humanBbPreflopOption
            && (trainerMode ? (!trainerInputLocked && decisionSecondsLeft > 0) : humanDecisionActive)
    readonly property bool checkOrRaiseSized: humanDecisionActive && humanCanCheck && !humanBbPreflopOption
    readonly property bool canFacingCall: facingRaise && (facingNeedChips <= 0 || humanHasChips)
    readonly property bool canRaiseFacing: facingRaise && humanCanRaiseFacing && humanHasChips
    readonly property bool canOpenRaise: checkOrRaiseSized && humanHasChips && openRaiseMinChips > 0 && openRaiseMaxChips >= openRaiseMinChips
    /// False while sitting out — disables action buttons; do not use alone to collapse the whole HUD.
    readonly property bool showHumanActions: !humanSitOut
    /// Timer / progress strip: table uses sit-out/watch; trainers show while the drill waits for input.
    readonly property bool showTableDecisionChrome: trainerMode ? (showHumanActions && showWagerUi) : (showWagerUi || humanSitOut)

    /// Table: hand strength is shown in the dedicated row above; banner is status / showdown (+ watching when sitting out).
    readonly property string statusFullDisplay: {
        if (trainerMode) {
            var hand = humanHandText.length > 0 ? humanHandText : ""
            var base = statusText.length > 0 ? statusText : qsTr("Ready.")
            if (hand.length > 0 && base.length > 0)
                return hand + "\n" + base
            return hand.length > 0 ? hand : base
        }
        if (humanSitOut)
            return (statusText.length > 0) ? statusText : qsTr("Watching — next hand you skip.")
        var base = statusText.length > 0 ? statusText : qsTr("Ready.")
        return base
    }

    /// Show raise slider + presets only after the user taps RAISE (facing a raise).
    property bool raiseSizingExpanded: false
    /// Show open-raise slider + presets only after Raise (first in on the street).
    property bool openRaiseSizingExpanded: false
    /// BB preflop: choose amount to add over the big blind.
    property bool bbPreflopSizingExpanded: false
    /// Caps raise / open / BB sizing strips so Min–All presets are not stretched edge-to-edge on minimum windows.
    readonly property int sizingStripMaxWidth: Math.max(200, Math.round(300 * ez))

    readonly property bool sizingDialogOpen: raiseSizingExpanded || openRaiseSizingExpanded
            || bbPreflopSizingExpanded

    function collapseRaiseSizingPanels() {
        raiseSizingExpanded = false
        openRaiseSizingExpanded = false
        bbPreflopSizingExpanded = false
    }

    function raiseSpinSafeMin() {
        return Math.min(facingMinRaiseChips, facingMaxChips)
    }

    function raiseSpinSafeMax() {
        return Math.max(facingMinRaiseChips, facingMaxChips)
    }

    function openRaiseSafeMin() {
        return Math.min(openRaiseMinChips, openRaiseMaxChips)
    }

    function openRaiseSafeMax() {
        return Math.max(openRaiseMinChips, openRaiseMaxChips)
    }

    function bbPreflopSpinSafeMin() {
        return Math.min(bbPreflopMinChips, bbPreflopMaxChips)
    }

    function bbPreflopSpinSafeMax() {
        return Math.max(bbPreflopMinChips, bbPreflopMaxChips)
    }

    function submitBbPreflopRaise() {
        if (trainerMode)
            return
        if (!pokerGame || !game_controls.bbPreflopSizingExpanded || !game_controls.humanBbPreflopOption
                || !game_controls.humanBbCanRaise)
            return
        pokerGame.submitBbPreflopRaise(Math.round(bbPreflopSlider.value))
        bbPreflopSizingExpanded = false
    }

    function submitFacingRaise() {
        if (trainerMode) {
            if (!game_controls.raiseSizingExpanded || !game_controls.canRaiseFacing || !game_controls.facingRaise)
                return
            game_controls.trainerAction("raise", Math.round(raiseSlider.value))
            game_controls.raiseSizingExpanded = false
            return
        }
        if (!pokerGame || !game_controls.raiseSizingExpanded || !game_controls.canRaiseFacing
                || !game_controls.facingRaise)
            return
        pokerGame.submitFacingAction(2, Math.round(raiseSlider.value))
        raiseSizingExpanded = false
    }

    function submitOpenRaise() {
        if (trainerMode)
            return
        if (!pokerGame || !game_controls.openRaiseSizingExpanded || !game_controls.canOpenRaise
                || !game_controls.checkOrRaiseSized)
            return
        pokerGame.submitCheckOrBet(false, Math.round(openRaiseSlider.value))
        openRaiseSizingExpanded = false
    }

    Connections {
        target: raiseSlider
        function onPressedChanged() {
            if (!raiseSlider.pressed)
                game_controls.submitFacingRaise()
        }
    }

    Connections {
        target: openRaiseSlider
        function onPressedChanged() {
            if (!openRaiseSlider.pressed)
                game_controls.submitOpenRaise()
        }
    }

    Connections {
        target: game_controls
        function onFacingRaiseChanged() {
            if (!game_controls.facingRaise)
                game_controls.raiseSizingExpanded = false
        }
        function onHumanDecisionActiveChanged() {
            if (!game_controls.humanDecisionActive) {
                game_controls.raiseSizingExpanded = false
                game_controls.openRaiseSizingExpanded = false
                game_controls.bbPreflopSizingExpanded = false
            }
        }
        function onCheckOrRaiseSizedChanged() {
            if (!game_controls.checkOrRaiseSized)
                game_controls.openRaiseSizingExpanded = false
        }
        function onCanRaiseFacingChanged() {
            if (!game_controls.canRaiseFacing)
                game_controls.raiseSizingExpanded = false
        }
        function onCanOpenRaiseChanged() {
            if (!game_controls.canOpenRaise)
                game_controls.openRaiseSizingExpanded = false
        }
        function onHumanBbPreflopOptionChanged() {
            if (!game_controls.humanBbPreflopOption)
                game_controls.bbPreflopSizingExpanded = false
        }
    }

    Rectangle {
        id: bar
        anchors.left: parent.left
        anchors.right: parent.right
        height: mainCol.height + mainColTopMargin + barBottomPad
        radius: game_controls.embeddedMode ? Math.round(10 * game_controls.ez) : 10
        color: Theme.headerBg
        border.width: 1
        border.color: Qt.alpha(Theme.gold, 0.25)

        Rectangle {
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            height: 1
            radius: 10
            color: Qt.alpha(Theme.gold, 0.12)
        }

        Column {
            id: mainCol
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.leftMargin: game_controls.hudSideMargin
            anchors.rightMargin: game_controls.hudSideMargin
            anchors.topMargin: game_controls.mainColTopMargin
            spacing: game_controls.mainColSpacing

            Text {
                id: trainerMessageLine
                visible: game_controls.trainerMode && game_controls.showHumanActions && game_controls.showWagerUi
                width: parent.width
                text: game_controls.statusText.length > 0 ? game_controls.statusText : qsTr("Ready.")
                color: Theme.textPrimary
                font.family: Theme.fontFamilyUi
                font.pixelSize: game_controls.hudBodyPx
                wrapMode: game_controls.embeddedMode ? Text.NoWrap : Text.WordWrap
                elide: Text.ElideRight
            }

            Column {
                id: decisionChrome
                width: parent.width
                spacing: game_controls.embeddedMode ? Math.round(4 * game_controls.ez) : 10
                /// Table + interactive human: keep timer strip so the panel height stays stable. Table + play-as-bot:
                /// omit the empty strip (Sit out is not shown while bot plays — same as before).
                visible: game_controls.showTableDecisionChrome && (!game_controls.embeddedMode || game_controls.engineHumanInteractive || game_controls.trainerMode)

                Item {
                    width: parent.width
                    height: game_controls.embeddedMode ? Math.max(game_controls.embeddedTimerRowMinH, timerRow.implicitHeight) : timerRow.implicitHeight
                    RowLayout {
                        id: timerRow
                        anchors.verticalCenter: parent.verticalCenter
                        width: parent.width
                        spacing: game_controls.embeddedMode ? Math.max(8, Math.round(14 * game_controls.ez)) : 10

                        Text {
                        visible: game_controls.showHudActTimerRow
                        text: qsTr("Act")
                        color: Theme.hudActionLabel
                        font.family: Theme.fontFamilyUi
                        font.pixelSize: game_controls.hudTimerLabelPx
                        font.bold: true
                        Layout.minimumWidth: visible ? Math.round(26 * game_controls.ez) : 0
                        Layout.preferredWidth: visible ? implicitWidth : 0
                    }

                    Text {
                        visible: game_controls.showHudActTimerRow
                        text: qsTr("%1s").arg(game_controls.decisionSecondsLeft)
                        color: Theme.seatBorderAct
                        font.family: Theme.fontFamilyMono
                        font.pixelSize: game_controls.hudTimerLabelPx + 1
                        font.bold: true
                        horizontalAlignment: Text.AlignHCenter
                        Layout.minimumWidth: visible ? Math.round(34 * game_controls.ez) : 0
                        Layout.preferredWidth: visible ? implicitWidth : 0
                    }

                    GameButton {
                        visible: game_controls.showMoreTimeButton
                        /// Wide enough for button font “More” — do not cap with `Layout.preferredWidth` (caused “M…” elide).
                        pillWidth: Math.round(80 * game_controls.ez)
                        horizontalPadding: Math.round(18 * game_controls.ez)
                        fontSize: game_controls.hudBtnPt
                        text: qsTr("Add Time")
                        buttonColor: Theme.hudActionPanel
                        textColor: Theme.hudActionBright
                        overrideHeight: game_controls.hudActBtnH
                        Layout.minimumWidth: visible ? Math.round(122 * game_controls.ez) : 0
                        onClicked: {
                            game_controls.collapseRaiseSizingPanels()
                            if (pageRoot)
                                pageRoot.buttonClicked("MORE_TIME")
                        }
                    }

                    Item {
                        Layout.fillWidth: true
                        height: 1
                    }

                    Label {
                        id: statusSubLine
                        visible: game_controls.statusSubText.length > 0
                        text: game_controls.statusSubText
                        color: Theme.textSecondary
                        font.family: Theme.fontFamilyUi
                        font.pixelSize: game_controls.hudSmallPx
                        horizontalAlignment: Text.AlignRight
                        elide: Text.ElideLeft
                        wrapMode: Text.NoWrap
                        /// Cap width so Act / timer / Sit out keep space — was ~42% of row and stretched the HUD.
                        readonly property real _maxSubW: Math.min(Math.round(150 * game_controls.ez),
                                Math.max(72, timerRow.width * 0.30))
                        Layout.minimumWidth: Math.round(56 * game_controls.ez)
                        Layout.maximumWidth: _maxSubW
                        Layout.preferredWidth: _maxSubW
                    }

                    ThemedCheckBox {
                        id: sitOutCheck
                        visible: !game_controls.trainerMode && !game_controls.playingAsBot
                        Layout.alignment: Qt.AlignVCenter
                        text: qsTr("Sit out")
                        font.family: Theme.fontFamilyUi
                        font.pixelSize: game_controls.hudMicroPx
                        topPadding: game_controls.embeddedMode ? Math.round(4 * game_controls.ez) : 14
                        bottomPadding: game_controls.embeddedMode ? Math.round(4 * game_controls.ez) : 14
                        leftPadding: game_controls.embeddedMode ? Math.round(6 * game_controls.ez) : 12
                        rightPadding: game_controls.embeddedMode ? Math.round(6 * game_controls.ez) : 12
                        checked: game_controls.humanSitOut
                        onToggled: {
                            game_controls.collapseRaiseSizingPanels()
                            if (pokerGame) {
                                pokerGame.setHumanSitOut(sitOutCheck.checked)
                                Qt.callLater(function () {
                                    if (pokerGame)
                                        pokerGame.savePersistedSettings()
                                })
                            }
                        }
                    }
                    }
                }

                ProgressBar {
                    id: embeddedDecisionBar
                    /// Only with legacy full-width HUD timer row; embedded + trainers use `Player` street bar.
                    visible: game_controls.showTableDecisionChrome && game_controls.showHudActTimerRow
                    width: parent.width
                    height: Math.round(4 * game_controls.ez)
                    padding: Math.round(1 * game_controls.ez)
                    opacity: (game_controls.humanDecisionActive || (game_controls.trainerMode && game_controls.statusSubText.length > 0)) ? 1.0 : 0.35
                    from: 0
                    to: 1
                    value: Math.max(0, Math.min(1, game_controls.decisionSecondsLeft / Math.max(1, game_controls.decisionTimeTotal)))
                    background: Rectangle {
                        implicitHeight: 6
                        implicitWidth: 200
                        radius: 3
                        color: Theme.progressTrack
                    }
                    contentItem: Item {
                        implicitHeight: 6
                        Rectangle {
                            width: embeddedDecisionBar.visualPosition * parent.width
                            height: parent.height
                            radius: 3
                            color: Theme.seatBorderAct
                        }
                    }
                }
            }

            // Raise sizing (facing a raise): above FOLD / CALL / RAISE
            Rectangle {
                visible: game_controls.showHumanActions && game_controls.showWagerUi
                        && game_controls.facingRaise
                        && game_controls.canRaiseFacing
                        && game_controls.raiseSizingExpanded
                        && !(game_controls.trainerMode && game_controls.trainerFlopStreet)
                width: Math.min(parent.width, game_controls.sizingStripMaxWidth)
                anchors.horizontalCenter: parent.horizontalCenter
                height: visible ? raiseSizerCol.implicitHeight + 2 * Theme.sizingRaisePanelPadV : 0
                color: Theme.panelElevated
                border.color: Theme.inputBorder
                border.width: 1
                clip: true

                Column {
                    id: raiseSizerCol
                    width: parent.width - 2 * Theme.sizingRaisePanelPadH
                    anchors.horizontalCenter: parent.horizontalCenter
                    anchors.top: parent.top
                    anchors.topMargin: Theme.sizingRaisePanelPadV
                    spacing: Theme.sizingRaiseSliderToPresetGap

                    RowLayout {
                        width: parent.width
                        spacing: 10
                        Slider {
                            id: raiseSlider
                            Layout.fillWidth: true
                            from: game_controls.raiseSpinSafeMin()
                            to: game_controls.raiseSpinSafeMax()
                            stepSize: 1
                            snapMode: Slider.SnapAlways
                            value: from

                        function syncRaiseSlider() {
                            raiseSlider.from = game_controls.raiseSpinSafeMin()
                            raiseSlider.to = game_controls.raiseSpinSafeMax()
                            if (raiseSlider.to < raiseSlider.from) {
                                raiseSlider.value = raiseSlider.from
                                return
                            }
                            raiseSlider.value = Math.min(
                                Math.max(game_controls.facingMinRaiseChips, raiseSlider.from),
                                raiseSlider.to)
                        }

                        Component.onCompleted: syncRaiseSlider()
                        }
                        Text {
                            Layout.preferredWidth: 52
                            text: Math.round(raiseSlider.value)
                            color: Theme.focusGold
                            font.family: Theme.fontFamilyMono
                            font.pixelSize: game_controls.hudBodyPx
                            font.bold: true
                            horizontalAlignment: Text.AlignRight
                        }
                    }

                    Connections {
                        target: game_controls
                        function onFacingMinRaiseChipsChanged() {
                            raiseSlider.syncRaiseSlider()
                        }
                        function onFacingMaxChipsChanged() {
                            raiseSlider.syncRaiseSlider()
                        }
                        function onFacingRaiseChanged() {
                            if (game_controls.facingRaise)
                                raiseSlider.syncRaiseSlider()
                        }
                    }

                    SizingPresetBar {
                        id: raisePresetRow
                        width: parent.width
                        hud: game_controls
                        slider: raiseSlider
                        flavor: "raise"
                        afterPreset: game_controls.submitFacingRaise
                    }
                }
            }

            // Facing a raise: fold / call / raise (table + preflop drill), or flop drill check / bets — Flow wraps on min width.
            Flow {
                visible: game_controls.showHumanActions && game_controls.showWagerUi && game_controls.facingRaise
                width: parent.width
                spacing: game_controls.actionRowSpacing

                GameButton {
                    visible: !game_controls.trainerMode || !game_controls.trainerFlopStreet
                    text: qsTr("FOLD")
                    pillWidth: game_controls.actPill76
                    buttonColor: Theme.dangerBg
                    textColor: Theme.dangerText
                    fontSize: game_controls.hudBtnPt
                    overrideHeight: game_controls.hudActBtnH
                    clickEnabled: game_controls.trainerMode
                            ? (!game_controls.trainerInputLocked && game_controls.facingRaise
                                    && game_controls.decisionSecondsLeft > 0)
                            : game_controls.facingRaise
                    opacity: game_controls.facingRaise ? 1.0 : 0.42
                    onClicked: {
                        game_controls.collapseRaiseSizingPanels()
                        if (game_controls.trainerMode) {
                            game_controls.trainerAction("FOLD", 0)
                            return
                        }
                        if (pageRoot && game_controls.facingRaise)
                            pageRoot.buttonClicked("FOLD")
                    }
                }

                GameButton {
                    visible: game_controls.canFacingCall
                            && (!game_controls.trainerMode || !game_controls.trainerFlopStreet)
                    text: game_controls.facingNeedChips > 0
                          ? qsTr("Call %1").arg(game_controls.facingNeedChips)
                          : qsTr("CALL")
                    pillWidth: game_controls.actPill108
                    buttonColor: Theme.focusGold
                    textColor: Theme.insetDark
                    fontSize: game_controls.hudBtnPt
                    overrideHeight: game_controls.hudActBtnH
                    clickEnabled: game_controls.trainerMode
                            ? (!game_controls.trainerInputLocked && game_controls.facingRaise
                                    && game_controls.decisionSecondsLeft > 0)
                            : true
                    onClicked: {
                        game_controls.collapseRaiseSizingPanels()
                        if (game_controls.trainerMode) {
                            game_controls.trainerAction("CALL", game_controls.facingNeedChips)
                            return
                        }
                        if (pageRoot && game_controls.facingRaise)
                            pageRoot.buttonClicked("CALL")
                    }
                }

                GameButton {
                    visible: game_controls.canRaiseFacing && !game_controls.raiseSizingExpanded
                            && (!game_controls.trainerMode || !game_controls.trainerFlopStreet)
                    text: qsTr("RAISE")
                    pillWidth: game_controls.actPill88
                    buttonColor: Theme.successGreen
                    textColor: Theme.onAccentText
                    fontSize: game_controls.hudBtnPt
                    overrideHeight: game_controls.hudActBtnH
                    clickEnabled: game_controls.trainerMode
                            ? (!game_controls.trainerInputLocked && game_controls.facingRaise
                                    && game_controls.decisionSecondsLeft > 0)
                            : true
                    onClicked: {
                        if (game_controls.trainerMode && game_controls.trainerInputLocked)
                            return
                        if (game_controls.trainerMode && game_controls.decisionSecondsLeft <= 0)
                            return
                        game_controls.raiseSizingExpanded = true
                    }
                }

                GameButton {
                    visible: game_controls.trainerMode && game_controls.trainerFlopStreet
                    text: qsTr("CHECK")
                    pillWidth: game_controls.actPill76
                    buttonColor: Theme.panelBorder
                    textColor: Theme.textPrimary
                    fontSize: game_controls.hudBtnPt
                    hudLabelFontFamily: Theme.fontFamilyUi
                    overrideHeight: game_controls.hudActBtnH
                    clickEnabled: !game_controls.trainerInputLocked && game_controls.facingRaise
                            && game_controls.decisionSecondsLeft > 0
                    opacity: game_controls.facingRaise ? 1.0 : 0.42
                    onClicked: {
                        game_controls.collapseRaiseSizingPanels()
                        if (game_controls.trainerMode)
                            game_controls.trainerAction("CHECK", 0)
                    }
                }

                GameButton {
                    visible: game_controls.trainerMode && game_controls.trainerFlopStreet
                    text: qsTr("Bet ⅓ pot")
                    pillWidth: game_controls.actPill108
                    buttonColor: Theme.focusGold
                    textColor: Theme.insetDark
                    fontSize: game_controls.hudBtnPt
                    hudLabelFontFamily: Theme.fontFamilyUi
                    overrideHeight: game_controls.hudActBtnH
                    clickEnabled: !game_controls.trainerInputLocked && game_controls.facingRaise
                            && game_controls.decisionSecondsLeft > 0
                    opacity: game_controls.facingRaise ? 1.0 : 0.42
                    onClicked: {
                        game_controls.collapseRaiseSizingPanels()
                        if (game_controls.trainerMode)
                            game_controls.trainerAction("BET33", Math.max(0, Math.round(0.33 * game_controls.facingPotAmount)))
                    }
                }

                GameButton {
                    visible: game_controls.trainerMode && game_controls.trainerFlopStreet
                    text: qsTr("Bet ¾ pot")
                    pillWidth: game_controls.actPill88
                    buttonColor: Theme.successGreen
                    textColor: Theme.onAccentText
                    fontSize: game_controls.hudBtnPt
                    hudLabelFontFamily: Theme.fontFamilyUi
                    overrideHeight: game_controls.hudActBtnH
                    clickEnabled: !game_controls.trainerInputLocked && game_controls.facingRaise
                            && game_controls.decisionSecondsLeft > 0
                    opacity: game_controls.facingRaise ? 1.0 : 0.42
                    onClicked: {
                        game_controls.collapseRaiseSizingPanels()
                        if (game_controls.trainerMode)
                            game_controls.trainerAction("BET75", Math.max(0, Math.round(0.75 * game_controls.facingPotAmount)))
                    }
                }
            }

            // BB preflop raise sizing (chips to add on top of posting BB)
            Rectangle {
                visible: game_controls.showHumanActions && game_controls.showWagerUi
                        && game_controls.humanDecisionActive
                        && game_controls.humanBbPreflopOption
                        && game_controls.humanBbCanRaise
                        && game_controls.bbPreflopSizingExpanded
                        && game_controls.bbPreflopMaxChips >= game_controls.bbPreflopMinChips
                width: Math.min(parent.width, game_controls.sizingStripMaxWidth)
                anchors.horizontalCenter: parent.horizontalCenter
                height: visible
                        ? bbPreflopSizerCol.implicitHeight + 2 * Theme.sizingRaisePanelPadV : 0
                color: Theme.panelElevated
                border.color: Theme.inputBorder
                border.width: 1
                clip: true

                Column {
                    id: bbPreflopSizerCol
                    width: parent.width - 2 * Theme.sizingRaisePanelPadH
                    anchors.horizontalCenter: parent.horizontalCenter
                    anchors.top: parent.top
                    anchors.topMargin: Theme.sizingRaisePanelPadV
                    spacing: Theme.sizingRaiseSliderToPresetGap

                    RowLayout {
                        width: parent.width
                        spacing: 10
                        Slider {
                            id: bbPreflopSlider
                            Layout.fillWidth: true
                            from: game_controls.bbPreflopSpinSafeMin()
                            to: game_controls.bbPreflopSpinSafeMax()
                            stepSize: 1
                            snapMode: Slider.SnapAlways
                            value: from

                        function syncBbPreflopSlider() {
                            bbPreflopSlider.from = game_controls.bbPreflopSpinSafeMin()
                            bbPreflopSlider.to = game_controls.bbPreflopSpinSafeMax()
                            if (bbPreflopSlider.to < bbPreflopSlider.from) {
                                bbPreflopSlider.value = bbPreflopSlider.from
                                return
                            }
                            bbPreflopSlider.value = Math.min(
                                Math.max(game_controls.bbPreflopMinChips, bbPreflopSlider.from),
                                bbPreflopSlider.to)
                        }

                        Component.onCompleted: syncBbPreflopSlider()
                        }
                        Text {
                            Layout.preferredWidth: 52
                            text: Math.round(bbPreflopSlider.value)
                            color: Theme.focusGold
                            font.family: Theme.fontFamilyMono
                            font.pixelSize: game_controls.hudBodyPx
                            font.bold: true
                            horizontalAlignment: Text.AlignRight
                        }
                    }

                    Connections {
                        target: bbPreflopSlider
                        function onPressedChanged() {
                            if (!bbPreflopSlider.pressed)
                                game_controls.submitBbPreflopRaise()
                        }
                    }

                    Connections {
                        target: game_controls
                        function onBbPreflopMinChipsChanged() {
                            bbPreflopSlider.syncBbPreflopSlider()
                        }
                        function onBbPreflopMaxChipsChanged() {
                            bbPreflopSlider.syncBbPreflopSlider()
                        }
                    }

                    SizingPresetBar {
                        width: parent.width
                        hud: game_controls
                        slider: bbPreflopSlider
                        flavor: "bb"
                        afterPreset: game_controls.submitBbPreflopRaise
                    }
                }
            }

            // BB preflop option
            Row {
                visible: game_controls.showHumanActions && game_controls.showWagerUi
                        && game_controls.humanDecisionActive
                        && game_controls.humanBbPreflopOption
                width: parent.width
                spacing: game_controls.actionRowSpacing

                GameButton {
                    text: qsTr("CHECK")
                    pillWidth: 96
                    fontSize: game_controls.hudBtnPt
                    overrideHeight: game_controls.hudActBtnH
                    buttonColor: Theme.panelBorder
                    textColor: Theme.textPrimary
                    onClicked: {
                        game_controls.collapseRaiseSizingPanels()
                        if (game_controls.trainerMode)
                            return
                        if (pageRoot)
                            pageRoot.buttonClicked("CHECK")
                    }
                }

                GameButton {
                    visible: game_controls.humanBbCanRaise && game_controls.humanHasChips
                            && !game_controls.bbPreflopSizingExpanded
                    text: qsTr("Raise")
                    pillWidth: 96
                    fontSize: game_controls.hudBtnPt
                    overrideHeight: game_controls.hudActBtnH
                    buttonColor: Theme.successGreen
                    textColor: Theme.onAccentText
                    onClicked: {
                        if (game_controls.trainerMode)
                            return
                        game_controls.bbPreflopSizingExpanded = true
                    }
                }
            }

            // Open raise sizing (checked to you): above CHECK / FOLD / RAISE
            Rectangle {
                visible: game_controls.showHumanActions && game_controls.showWagerUi
                        && game_controls.checkOrRaiseSized
                        && game_controls.canOpenRaise
                        && game_controls.openRaiseSizingExpanded
                width: Math.min(parent.width, game_controls.sizingStripMaxWidth)
                anchors.horizontalCenter: parent.horizontalCenter
                height: visible ? openRaiseSizerCol.implicitHeight + 2 * Theme.sizingRaisePanelPadV : 0
                color: Theme.panelElevated
                border.color: Theme.inputBorder
                border.width: 1
                clip: true

                Column {
                    id: openRaiseSizerCol
                    width: parent.width - 2 * Theme.sizingRaisePanelPadH
                    anchors.horizontalCenter: parent.horizontalCenter
                    anchors.top: parent.top
                    anchors.topMargin: Theme.sizingRaisePanelPadV
                    spacing: Theme.sizingRaiseSliderToPresetGap

                    RowLayout {
                        width: parent.width
                        spacing: 10
                        Slider {
                            id: openRaiseSlider
                            Layout.fillWidth: true
                            from: game_controls.openRaiseSafeMin()
                            to: game_controls.openRaiseSafeMax()
                            stepSize: 1
                            snapMode: Slider.SnapAlways
                            value: from

                        function syncOpenRaiseSlider() {
                            openRaiseSlider.from = game_controls.openRaiseSafeMin()
                            openRaiseSlider.to = game_controls.openRaiseSafeMax()
                            if (openRaiseSlider.to < openRaiseSlider.from) {
                                openRaiseSlider.value = openRaiseSlider.from
                                return
                            }
                            openRaiseSlider.value = Math.min(
                                Math.max(game_controls.openRaiseMinChips, openRaiseSlider.from),
                                openRaiseSlider.to)
                        }

                        Component.onCompleted: syncOpenRaiseSlider()
                        }
                        Text {
                            Layout.preferredWidth: 52
                            text: Math.round(openRaiseSlider.value)
                            color: Theme.focusGold
                            font.family: Theme.fontFamilyMono
                            font.pixelSize: game_controls.hudBodyPx
                            font.bold: true
                            horizontalAlignment: Text.AlignRight
                        }
                    }

                    Connections {
                        target: game_controls
                        function onOpenRaiseMinChipsChanged() {
                            openRaiseSlider.syncOpenRaiseSlider()
                        }
                        function onOpenRaiseMaxChipsChanged() {
                            openRaiseSlider.syncOpenRaiseSlider()
                        }
                        function onCheckOrRaiseSizedChanged() {
                            if (game_controls.checkOrRaiseSized)
                                openRaiseSlider.syncOpenRaiseSlider()
                        }
                    }

                    SizingPresetBar {
                        id: openRaisePresetRow
                        width: parent.width
                        hud: game_controls
                        slider: openRaiseSlider
                        flavor: "open"
                        afterPreset: game_controls.submitOpenRaise
                    }
                }
            }

            // Check or fold (post-flop) + open raise trigger
            Row {
                visible: game_controls.showHumanActions && game_controls.showWagerUi
                        && game_controls.checkOrRaiseSized
                width: parent.width
                spacing: game_controls.actionRowSpacing

                GameButton {
                    text: qsTr("CHECK")
                    pillWidth: 88
                    fontSize: game_controls.hudBtnPt
                    overrideHeight: game_controls.hudActBtnH
                    buttonColor: Theme.panelBorder
                    textColor: Theme.textPrimary
                    onClicked: {
                        game_controls.collapseRaiseSizingPanels()
                        if (game_controls.trainerMode)
                            return
                        if (pokerGame)
                            pokerGame.submitCheckOrBet(true, 0)
                    }
                }

                GameButton {
                    text: qsTr("FOLD")
                    pillWidth: 76
                    fontSize: game_controls.hudBtnPt
                    overrideHeight: game_controls.hudActBtnH
                    buttonColor: Theme.dangerBg
                    textColor: Theme.dangerText
                    onClicked: {
                        game_controls.collapseRaiseSizingPanels()
                        if (game_controls.trainerMode)
                            return
                        if (pokerGame)
                            pokerGame.submitFoldFromCheck()
                    }
                }

                GameButton {
                    visible: game_controls.canOpenRaise && !game_controls.openRaiseSizingExpanded
                    text: qsTr("Raise")
                    pillWidth: 88
                    fontSize: game_controls.hudBtnPt
                    overrideHeight: game_controls.hudActBtnH
                    buttonColor: Theme.successGreen
                    textColor: Theme.onAccentText
                    onClicked: {
                        if (game_controls.trainerMode)
                            return
                        game_controls.openRaiseSizingExpanded = true
                    }
                }
            }

            RowLayout {
                id: buyBackRow
                visible: !game_controls.trainerMode && game_controls.embeddedMode
                        && game_controls.humanCanBuyBackIn
                        && (game_controls.showHumanActions || game_controls.humanSitOut)
                width: parent.width
                spacing: 12

                GameButton {
                    text: qsTr("Buy back in ($%1)").arg(game_controls.buyInChips)
                    fontSize: game_controls.hudBtnPt
                    pillWidth: 0
                    horizontalPadding: 16
                    overrideHeight: Math.max(24, Math.round(30 * game_controls.ez))
                    buttonColor: Theme.focusGold
                    textColor: Theme.insetDark
                    clickEnabled: game_controls.pokerGame !== null
                    onClicked: {
                        game_controls.collapseRaiseSizingPanels()
                        if (game_controls.pokerGame)
                            game_controls.pokerGame.tryBuyBackIn(0)
                    }
                }

                Item {
                    Layout.fillWidth: true
                    height: 1
                }
            }

            /// Status / showdown **above** the hole-card line so the system message sits higher in the panel.
            Rectangle {
                id: statusBanner
                /// Showdown: engine `statusText` (winner name(s) + hand type). Hide while your decision timer runs.
                visible: !game_controls.trainerMode
                        && !(game_controls.embeddedMode && game_controls.humanDecisionActive)
                width: parent.width
                readonly property int statusBannerInnerTopPad: game_controls.statusLayoutTight
                        ? Math.max(2, Math.round(3 * game_controls.ez))
                        : Math.max(4, Math.round(6 * game_controls.ez))
                implicitHeight: statusTableColumn.implicitHeight
                        + (game_controls.statusLayoutTight
                           ? Math.max(4, Math.round(5 * game_controls.ez))
                           : Math.max(6, Math.round(8 * game_controls.ez)))
                        + statusBannerInnerTopPad
                radius: Math.round(6 * game_controls.ez)
                color: Theme.inputBg
                border.color: Theme.inputBorder
                border.width: 1
                clip: true

                Column {
                    id: statusTableColumn
                    visible: !game_controls.trainerMode
                    width: parent.width - (game_controls.statusLayoutTight ? 8 : 12)
                    anchors.horizontalCenter: parent.horizontalCenter
                    anchors.top: parent.top
                    anchors.topMargin: parent.statusBannerInnerTopPad
                    spacing: game_controls.statusLayoutTight
                            ? Math.max(2, Math.round(4 * game_controls.ez))
                            : Math.max(4, Math.round(6 * game_controls.ez))

                    Text {
                        id: statusBannerTableText
                        width: parent.width
                        text: game_controls.statusFullDisplay
                        color: Theme.textPrimary
                        font.family: Theme.fontFamilyUi
                        font.pixelSize: game_controls.statusHudBodyPx
                        wrapMode: Text.NoWrap
                        elide: Text.ElideRight
                    }
                }
            }

            Rectangle {
                /// Same chrome as the hole-card row: show while sitting out (status + icon), as bot, or when dealt hole cards.
                visible: !game_controls.trainerMode
                        && (game_controls.humanSitOut || game_controls.playingAsBot
                            || game_controls.humanHandText.length > 0)
                width: parent.width
                implicitHeight: Math.max(Math.round(44 * game_controls.ez),
                        handRowLayout.implicitHeight + Math.max(10, Math.round(16 * game_controls.ez)))
                radius: Math.round(6 * game_controls.ez)
                color: Theme.panelElevated
                border.width: 1
                border.color: Qt.alpha(Theme.gold, 0.42)
                clip: true

                RowLayout {
                    id: handRowLayout
                    anchors.fill: parent
                    anchors.margins: Math.max(6, Math.round(10 * game_controls.ez))
                    spacing: Math.max(6, Math.round(10 * game_controls.ez))

                    Image {
                        visible: game_controls.humanSitOut
                        Layout.alignment: Qt.AlignVCenter
                        Layout.preferredWidth: Math.max(18, Math.round(22 * game_controls.ez))
                        Layout.preferredHeight: Math.max(18, Math.round(22 * game_controls.ez))
                        fillMode: Image.PreserveAspectFit
                        source: "qrc:/assets/icons/table.svg"
                    }

                    Text {
                        visible: game_controls.humanSitOut
                        Layout.alignment: Qt.AlignVCenter
                        text: qsTr("Sitting out")
                        color: Theme.textSecondary
                        font.family: Theme.fontFamilyUi
                        font.pixelSize: game_controls.hudMicroPx
                    }

                    Image {
                        visible: game_controls.playingAsBot && !game_controls.humanSitOut
                        Layout.alignment: Qt.AlignVCenter
                        Layout.preferredWidth: Math.max(18, Math.round(22 * game_controls.ez))
                        Layout.preferredHeight: Math.max(18, Math.round(22 * game_controls.ez))
                        fillMode: Image.PreserveAspectFit
                        source: "qrc:/assets/icons/bots.svg"
                    }

                    Text {
                        visible: game_controls.playingAsBot && !game_controls.humanSitOut
                        Layout.alignment: Qt.AlignVCenter
                        text: qsTr("Bot playing")
                        color: Theme.textSecondary
                        font.family: Theme.fontFamilyUi
                        font.pixelSize: game_controls.hudMicroPx
                    }

                    Text {
                        id: yourHandLabel
                        /// Only stretch when showing hole cards; otherwise a trailing spacer keeps sit/bot copy left-aligned.
                        Layout.fillWidth: visible
                        Layout.minimumWidth: 0
                        Layout.alignment: Qt.AlignVCenter
                        visible: !game_controls.humanSitOut && game_controls.humanHandText.length > 0
                        text: game_controls.humanHandText
                        color: Theme.focusGold
                        font.family: Theme.fontFamilyUi
                        font.pixelSize: game_controls.hudBodyPx
                        font.bold: true
                        wrapMode: Text.NoWrap
                        elide: Text.ElideRight
                    }

                    Item {
                        Layout.fillWidth: true
                        Layout.minimumWidth: 0
                        Layout.preferredHeight: 1
                        visible: !yourHandLabel.visible
                    }
                }
            }

            Item {
                width: 1
                height: 2
            }
        }
    }
}
