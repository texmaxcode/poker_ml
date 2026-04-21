import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Theme 1.0
import PokerUi 1.0

Page {
    id: page
    padding: 0
    font.family: Theme.fontFamilyUi

    property StackLayout stackLayout: null

    property string position: "BTN"
    property string mode: "open"
    property string card1: ""
    property string card2: ""
    property string statusLine: qsTr("Load ranges and start a drill.")
    property bool inputLocked: false
    property int secLeft: 0
    /// Seconds left to answer (mirrors table decision clock).
    property int decisionSecLeft: 0
    /// Wall-clock ms deadlines so timers stay correct after app background or tab switch.
    property real decisionDeadlineMs: 0
    property real advanceDeadlineMs: 0
    /// Bumps when the hand changes so `Player` hole cards re-deal like at the table.
    property int seatVisualEpoch: 0
    /// True after user navigates away so we start a new drill question when they come back.
    property bool _returningFromHidden: false
    /// Avoid treating initial `visible: false` at startup as "left the page".
    property bool _drillSurfaceShown: false
    property bool assetLoadFailed: false
    /// Set when the user has opened this page once — avoids starting timers while the tab is not visible.
    property bool _drillStarted: false
    /// Matches HUD pot / sizing context ($2 BB training table).
    readonly property int trainerPotChips: 12
    /// Display chips (animates up on call / raise like the table HUD).
    property int trainerPotShown: trainerPotChips

    function resetTrainerPotDisplay() {
        trainerPotCountAnim.stop()
        trainerPotShown = trainerPotChips
    }

    function bumpTrainerPot(delta) {
        const d = Math.round(Number(delta))
        if (!isFinite(d) || d <= 0)
            return
        trainerPotCountAnim.stop()
        trainerPotCountAnim.from = trainerPotShown
        trainerPotCountAnim.to = trainerPotShown + d
        trainerPotCountAnim.restart()
        trainerPotBumpAnim.restart()
    }

    background: BrandedBackground { anchors.fill: parent }

    Timer {
        id: decisionTimer
        interval: 1000
        repeat: true
        running: false
        onTriggered: page.tickDecisionTimer()
    }

    Timer {
        id: secTimer
        interval: 1000
        repeat: true
        running: false
        onTriggered: page.tickAdvanceTimer()
    }

    function cancelPendingAdvance() {
        secTimer.stop()
        secLeft = 0
        inputLocked = false
        advanceDeadlineMs = 0
        decisionTimer.stop()
        decisionSecLeft = 0
        decisionDeadlineMs = 0
    }

    function tickDecisionTimer() {
        const left = Math.max(0, Math.ceil((decisionDeadlineMs - Date.now()) / 1000))
        decisionSecLeft = left
        if (left <= 0) {
            decisionTimer.stop()
            decisionSecLeft = 0
            decisionDeadlineMs = 0
            submit("fold")
        }
    }

    function tickAdvanceTimer() {
        const left = Math.max(0, Math.ceil((advanceDeadlineMs - Date.now()) / 1000))
        secLeft = left
        if (left <= 0) {
            secTimer.stop()
            advanceDeadlineMs = 0
            inputLocked = false
            nextQuestion()
        }
    }

    /// Resync after app resume or tab change. Wall-clock deadlines stay valid; QML `Timer` can stall
    /// after suspend while still reporting `running`, so always `restart()` when time remains.
    function syncTrainerClocks() {
        // Recover stuck "feedback / next hand" lock if deadlines were cleared without advancing (e.g. suspend).
        if (inputLocked && advanceDeadlineMs <= 0 && decisionDeadlineMs <= 0) {
            secTimer.stop()
            inputLocked = false
            nextQuestion()
            return
        }
        if (!inputLocked && decisionDeadlineMs > 0) {
            const left = Math.max(0, Math.ceil((decisionDeadlineMs - Date.now()) / 1000))
            decisionSecLeft = left
            if (left <= 0) {
                decisionTimer.stop()
                decisionSecLeft = 0
                decisionDeadlineMs = 0
                submit("fold")
            } else {
                decisionTimer.restart()
            }
        }
        if (inputLocked && advanceDeadlineMs > 0) {
            const left = Math.max(0, Math.ceil((advanceDeadlineMs - Date.now()) / 1000))
            secLeft = left
            if (left <= 0) {
                secTimer.stop()
                advanceDeadlineMs = 0
                inputLocked = false
                nextQuestion()
            } else {
                secTimer.restart()
            }
        }
    }

    function startDecisionClock() {
        decisionTimer.stop()
        const sec = Math.max(1, trainingStore.trainerDecisionSeconds)
        decisionDeadlineMs = Date.now() + sec * 1000
        decisionSecLeft = sec
        decisionTimer.start()
    }

    function startAutoAdvance() {
        secTimer.stop()
        inputLocked = true
        const ms = Math.max(1, trainingStore.trainerAutoAdvanceMs)
        advanceDeadlineMs = Date.now() + ms
        secLeft = Math.max(1, Math.ceil(ms / 1000))
        secTimer.start()
    }

    function goTrainingHome() {
        cancelPendingAdvance()
        if (stackLayout)
            stackLayout.currentIndex = 5
    }

    /// Stop timers when leaving this screen; stack may keep the page alive.
    function stopDrillWhileAway() {
        cancelPendingAdvance()
    }

    /// New question + clock after returning from another screen.
    function refreshModeModelForPosition() {
        const modes = trainer.preflopModesForPosition(page.position)
        modePick.modeKeys = modes
        modePick.model = modes.map(function (k) { return Theme.trainerModeDisplayLabel(k) })
        let idx = modes.indexOf(page.mode)
        if (idx < 0 && modes.length > 0) {
            page.mode = String(modes[0])
            idx = 0
        }
        modePick.currentIndex = idx >= 0 ? idx : 0
    }

    function restartDrillAfterReturn() {
        if (page.assetLoadFailed)
            return
        statusLine = qsTr("Ready.")
        refreshModeModelForPosition()
        trainer.startPreflopDrill(position, mode)
        nextQuestion()
    }

    onVisibleChanged: {
        if (!visible) {
            if (_drillSurfaceShown) {
                stopDrillWhileAway()
                _returningFromHidden = true
            }
            return
        }
        _drillSurfaceShown = true
        if (!page.assetLoadFailed && !page._drillStarted) {
            page._drillStarted = true
            nextQuestion()
            return
        }
        if (_returningFromHidden) {
            _returningFromHidden = false
            restartDrillAfterReturn()
        } else {
            syncTrainerClocks()
        }
    }

    Connections {
        target: Qt.application
        function onStateChanged() {
            if (Qt.application.state === Qt.ApplicationActive)
                page.syncTrainerClocks()
        }
    }

    Component.onCompleted: {
        delaySecSpin.value = Math.round(trainingStore.trainerAutoAdvanceMs / 1000)
        timeLimitSpin.value = trainingStore.trainerDecisionSeconds
        const ok = trainer.loadPreflopRanges("qrc:/assets/training/preflop_ranges_v1.json")
        page.assetLoadFailed = !ok
        statusLine = ok ? qsTr("Ready.") : qsTr("Could not load ranges.")
        if (!ok)
            return
        refreshModeModelForPosition()
        trainer.startPreflopDrill(position, mode)
    }

    function nextQuestion() {
        cancelPendingAdvance()
        const q = trainer.nextPreflopQuestion()
        if (q.error !== undefined) {
            statusLine = String(q.error)
            return
        }
        position = String(q.position)
        mode = String(q.mode)
        refreshModeModelForPosition()
        card1 = String(q.card1)
        card2 = String(q.card2)
        seatVisualEpoch++
        resetTrainerPotDisplay()
        statusLine = qsTr("Pick the best play.")
        startDecisionClock()
    }

    function submit(a) {
        decisionTimer.stop()
        decisionSecLeft = 0
        decisionDeadlineMs = 0
        const r = trainer.submitPreflopAnswer(a, 0)
        if (r.error !== undefined) {
            statusLine = String(r.error)
            startAutoAdvance()
            return
        }
        const grade = String(r.grade)
        const freq = Number(r.chosenFreq)
        const best = String(r.bestAction)
        const modeLabel = Theme.trainerModeDisplayLabel(mode)
        statusLine = qsTr("%1 %2 — %3 (%4%) · best: %5").arg(position).arg(modeLabel).arg(grade).arg(Math.round(freq * 100)).arg(best)
        startAutoAdvance()
    }

    function scrollMainToTop() { }

    Item {
        id: trainerRoot
        anchors.fill: parent
        anchors.topMargin: Theme.trainerPageTopPadding

        ScrollView {
            id: trainerScroll
            anchors.fill: parent
            clip: true
            ScrollBar.horizontal.policy: ScrollBar.AlwaysOff

        RowLayout {
            id: trainerRow
            width: trainerScroll.availableWidth
            spacing: 0

            Item {
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                Layout.alignment: Qt.AlignTop
            }

            ColumnLayout {
                id: trainerMainCol
                Layout.preferredWidth: Math.min(Theme.trainerContentMaxWidth, Math.max(260, trainerRoot.width - (trainerRoot.width < 600 ? 16 : 40)))
                Layout.maximumWidth: Theme.trainerContentMaxWidth
                Layout.alignment: Qt.AlignTop
                spacing: Theme.trainerColumnSpacing

                /// Quantized so resize / HUD text reflow does not nudge the drill panel every frame (reduces jumpiness).
                readonly property int _hudReserveQuantized: Math.max(172, Math.ceil(exerciseHud.height / 4) * 4)
                readonly property int drillViewportCap: Math.max(
                    Theme.trainerDrillPanelMinH,
                    Math.min(
                        Theme.trainerDrillPanelMaxH,
                        Math.round(Theme.trainerDrillPanelMaxHeightForViewport(
                            trainerRoot.height,
                            trainerChromeAboveDrill.implicitHeight + _hudReserveQuantized
                                + 2 * Theme.trainerColumnSpacing + 24) / 12) * 12))

                ColumnLayout {
                    id: trainerChromeAboveDrill
                    Layout.fillWidth: true
                    spacing: Theme.trainerColumnSpacing

                Text {
                    Layout.fillWidth: true
                    visible: page.assetLoadFailed
                    wrapMode: Text.WordWrap
                    text: qsTr("Training data failed to load. The bundled JSON asset may be missing or invalid.")
                    color: Theme.dangerText
                    font.pixelSize: Theme.trainerBodyPx
                    lineHeight: Theme.bodyLineHeight
                }

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 12

                    GameButton {
                        style: "form"
                        formFlat: true
                        text: qsTr("Training picks")
                        formFontPixelSize: Theme.trainerToolButtonPx
                        textColor: Theme.textPrimary
                        horizontalPadding: 14
                        onClicked: page.goTrainingHome()
                    }

                    Item { Layout.fillWidth: true }

                    Label {
                        text: qsTr("Delay")
                        color: Theme.textMuted
                        font.pixelSize: Theme.trainerCaptionPx
                        Layout.alignment: Qt.AlignVCenter
                    }
                    ThemedSpinBox {
                        id: delaySecSpin
                        labelPixelSize: Theme.trainerCaptionPx
                        Layout.preferredWidth: Theme.trainerSpinBoxWidth
                        Layout.alignment: Qt.AlignVCenter
                        from: 1
                        to: 120
                        editable: true
                        enabled: !page.assetLoadFailed
                        stepSize: 1
                        textFromValue: function (v) { return v + qsTr(" s") }
                        valueFromText: function (t) { return parseInt(t, 10) }
                        onValueModified: trainingStore.trainerAutoAdvanceMs = value * 1000
                    }

                    Label {
                        text: qsTr("Time limit")
                        color: Theme.textMuted
                        font.pixelSize: Theme.trainerCaptionPx
                        Layout.alignment: Qt.AlignVCenter
                    }
                    ThemedSpinBox {
                        id: timeLimitSpin
                        labelPixelSize: Theme.trainerCaptionPx
                        Layout.preferredWidth: Theme.trainerSpinBoxWidth
                        Layout.alignment: Qt.AlignVCenter
                        from: 5
                        to: 120
                        editable: true
                        enabled: !page.assetLoadFailed
                        stepSize: 1
                        textFromValue: function (v) { return v + qsTr(" s") }
                        valueFromText: function (t) { return parseInt(t, 10) }
                        onValueModified: trainingStore.trainerDecisionSeconds = value
                    }
                }

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 12

                    Label {
                        text: qsTr("Pos")
                        color: Theme.textMuted
                        font.pixelSize: Theme.trainerCaptionPx
                        Layout.alignment: Qt.AlignVCenter
                    }
                    ComboBox {
                        id: posPick
                        font.pixelSize: Theme.trainerCaptionPx
                        font.family: Theme.fontFamilyUi
                        Layout.preferredWidth: 112
                        enabled: !page.inputLocked && !page.assetLoadFailed
                        Layout.alignment: Qt.AlignVCenter
                        palette.button: Theme.panelElevated
                        palette.buttonText: Theme.textPrimary
                        palette.window: Theme.inputBg
                        palette.windowText: Theme.textPrimary
                        model: ["UTG", "HJ", "CO", "BTN", "SB", "BB"]
                        currentIndex: model.indexOf(page.position)
                        onActivated: function (index) {
                            cancelPendingAdvance()
                            page.position = String(model[index])
                            page.refreshModeModelForPosition()
                            trainer.startPreflopDrill(page.position, page.mode)
                            page.nextQuestion()
                        }
                    }

                    Label {
                        text: qsTr("Mode")
                        color: Theme.textMuted
                        font.pixelSize: Theme.trainerCaptionPx
                        Layout.alignment: Qt.AlignVCenter
                    }
                    ComboBox {
                        id: modePick
                        font.pixelSize: Theme.trainerCaptionPx
                        font.family: Theme.fontFamilyUi
                        Layout.fillWidth: true
                        Layout.alignment: Qt.AlignVCenter
                        enabled: !page.inputLocked && !page.assetLoadFailed
                        palette.button: Theme.panelElevated
                        palette.buttonText: Theme.textPrimary
                        palette.window: Theme.inputBg
                        palette.windowText: Theme.textPrimary
                        property var modeKeys: ["open"]
                        model: modeKeys.map(function (k) { return Theme.trainerModeDisplayLabel(k) })
                        currentIndex: 0
                        onActivated: function (index) {
                            cancelPendingAdvance()
                            page.mode = String(modeKeys[index])
                            trainer.startPreflopDrill(page.position, page.mode)
                            page.nextQuestion()
                        }
                    }
                }

                Connections {
                    target: trainingStore
                    function onTrainerAutoAdvanceMsChanged() {
                        delaySecSpin.value = Math.round(trainingStore.trainerAutoAdvanceMs / 1000)
                    }
                    function onTrainerDecisionSecondsChanged() {
                        timeLimitSpin.value = trainingStore.trainerDecisionSeconds
                    }
                }

                }

                Rectangle {
                    id: drillPanel
                    Layout.fillWidth: true
                    Layout.minimumHeight: Theme.trainerDrillPanelMinH
                    Layout.preferredHeight: trainerMainCol.drillViewportCap
                    Layout.maximumHeight: trainerMainCol.drillViewportCap
                    radius: Theme.trainerPanelRadius
                    color: Qt.alpha(Theme.panel, 0.35)
                    border.width: 1
                    border.color: Qt.alpha(Theme.chromeLine, 0.55)
                    clip: true

                    Item {
                        id: drillArea
                        anchors.fill: parent
                        anchors.margins: 2

                        readonly property real drillScale: {
                            var fixedH = 50
                            var scalableH = 288.0 + 20.0
                            var hScale = (Math.max(1, drillArea.height) - fixedH) / scalableH
                            var wScale = (Math.max(1, drillArea.width) - 24) / 218.0
                            return Math.min(1.0, Math.max(0.28, Math.min(hScale, wScale)))
                        }
                        readonly property int tableSeatW: Math.round(218 * drillScale)
                        readonly property int tableSeatH: Math.round(312 * drillScale)
                        readonly property int panelPad: Math.max(4, Math.round(10 * drillScale))
                        readonly property int seatShadowBleed: Math.max(4, Math.round(8 * drillScale))

                        ColumnLayout {
                            id: preflopDrillStack
                            anchors.fill: parent
                            anchors.leftMargin: drillArea.panelPad
                            anchors.rightMargin: drillArea.panelPad
                            anchors.topMargin: drillArea.panelPad
                            anchors.bottomMargin: drillArea.panelPad + drillArea.seatShadowBleed
                            spacing: Math.max(2, Math.round(6 * drillArea.drillScale))

                            Rectangle {
                                Layout.alignment: Qt.AlignHCenter
                                width: trainerPotBanner.implicitWidth + 22
                                height: trainerPotBanner.implicitHeight + 12
                                radius: 8
                                color: Theme.hudBg1
                                border.color: Theme.hudBorder
                                border.width: 2

                                Text {
                                    id: trainerPotBanner
                                    anchors.centerIn: parent
                                    text: qsTr("Pot $%1").arg(Math.round(page.trainerPotShown))
                                    color: Theme.gold
                                    font.family: Theme.fontFamilyMono
                                    font.pixelSize: Theme.trainerCaptionPx
                                    font.bold: true

                                    transform: Scale {
                                        id: trainerPotValueScale
                                        origin.x: trainerPotBanner.width * 0.5
                                        origin.y: trainerPotBanner.height * 0.5
                                        xScale: 1
                                        yScale: 1
                                    }
                                }
                            }

                            Text {
                                Layout.fillWidth: true
                                text: qsTr("Preflop · %1 · %2").arg(page.position).arg(Theme.trainerModeDisplayLabel(page.mode))
                                wrapMode: Text.WordWrap
                                horizontalAlignment: Text.AlignHCenter
                                color: Theme.textSecondary
                                font.family: Theme.fontFamilyUi
                                font.pixelSize: Theme.trainerBodyPx
                                lineHeight: Theme.bodyLineHeight
                            }

                            Item {
                                id: preflopSeatRow
                                Layout.fillWidth: true
                                Layout.fillHeight: true
                                Layout.preferredHeight: drillArea.tableSeatH
                                Layout.minimumHeight: 60
                                Layout.maximumHeight: drillArea.tableSeatH

                                Item {
                                    id: trainerSeatWrap
                                    width: Math.min(drillArea.tableSeatW,
                                            parent.width > 0 ? parent.width : drillArea.tableSeatW)
                                    height: Math.min(drillArea.tableSeatH,
                                            parent.height > 0 ? parent.height : drillArea.tableSeatH)
                                    anchors.horizontalCenter: parent.horizontalCenter
                                    anchors.bottom: parent.bottom

                                    Player {
                                        anchors.fill: parent
                                        uiScale: Theme.trainerSeatUiScaleClamped(drillArea.drillScale, trainerSeatWrap.height)
                                        seatIndex: 0
                                        name: qsTr("You")
                                        position: page.position
                                        first_card: page.card1
                                        second_card: page.card2
                                        show_cards: true
                                        inHand: true
                                        seatAtTable: true
                                        stackChips: 200
                                        streetActionText: page.decisionSecLeft > 0 && !page.inputLocked
                                                ? qsTr("Your action")
                                                : qsTr("—")
                                        handEpoch: page.seatVisualEpoch
                                        instantHoleCards: true
                                        isHumanSeat: true
                                        isActing: page.decisionSecLeft > 0 && !page.inputLocked
                                        decisionSecondsLeft: page.decisionSecLeft
                                    }
                                }
                            }
                        }
                    }
                }

                GameControls {
                    id: exerciseHud
                    Layout.fillWidth: true
                    trainerMode: true
                    trainerFlopStreet: false
                    pokerGame: null
                    embeddedMode: false
                    hudScale: Math.max(drillArea.drillScale, Theme.trainerHudMinScale)
                    trainerInputLocked: page.inputLocked || page.assetLoadFailed
                    humanSitOut: false
                    statusText: page.statusLine
                    statusSubText: page.secLeft > 0
                            ? qsTr("Next in %1 s").arg(page.secLeft)
                            : ""
                    humanHandText: ""
                    decisionSecondsLeft: page.inputLocked ? page.secLeft : page.decisionSecLeft
                    decisionTimeTotal: trainingStore ? trainingStore.trainerDecisionSeconds : 10
                    humanMoreTimeAvailable: false
                    humanCanCheck: false
                    humanBbPreflopOption: false
                    humanCanRaiseFacing: true
                    facingNeedChips: 3
                    facingMinRaiseChips: 6
                    facingMaxChips: 200
                    facingPotAmount: page.trainerPotChips
                    humanStackChips: 200
                    humanBbCanRaise: false
                    humanCanBuyBackIn: false
                }

                Connections {
                    target: exerciseHud
                    function onTrainerAction(action, amount) {
                        const u = String(action).toUpperCase()
                        if (u === "FOLD")
                            page.submit("fold")
                        else if (u === "CALL") {
                            page.bumpTrainerPot(amount > 0 ? Number(amount) : exerciseHud.facingNeedChips)
                            page.submit("call")
                        } else if (u === "RAISE") {
                            page.bumpTrainerPot(Number(amount))
                            page.submit("raise")
                        }
                    }
                }
            }

            Item {
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                Layout.alignment: Qt.AlignTop
            }
        }
        }
    }

    /// Holder for animations (`Page` expects `Item` children; avoid `visible: false` here — it can suppress animations).
    Item {
        id: trainerPotAnimHost
        width: 0
        height: 0
        opacity: 0

        NumberAnimation {
            id: trainerPotCountAnim
            target: page
            property: "trainerPotShown"
            duration: 320
            easing.type: Easing.OutCubic
        }

        SequentialAnimation {
            id: trainerPotBumpAnim
            ParallelAnimation {
                NumberAnimation {
                    target: trainerPotValueScale
                    property: "xScale"
                    to: 1.08
                    duration: 95
                    easing.type: Easing.OutCubic
                }
                NumberAnimation {
                    target: trainerPotValueScale
                    property: "yScale"
                    to: 1.08
                    duration: 95
                    easing.type: Easing.OutCubic
                }
            }
            ParallelAnimation {
                NumberAnimation {
                    target: trainerPotValueScale
                    property: "xScale"
                    to: 1.0
                    duration: 160
                    easing.type: Easing.OutCubic
                }
                NumberAnimation {
                    target: trainerPotValueScale
                    property: "yScale"
                    to: 1.0
                    duration: 160
                    easing.type: Easing.OutCubic
                }
            }
        }
    }
}
