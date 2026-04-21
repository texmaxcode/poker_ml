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

    property string statusLine: qsTr("Starting…")
    property string board0: ""
    property string board1: ""
    property string board2: ""
    property string board3: ""
    property string board4: ""
    property string hero1: ""
    property string hero2: ""
    property string spotId: ""
    property bool inputLocked: false
    property int secLeft: 0
    property int decisionSecLeft: 0
    property real decisionDeadlineMs: 0
    property real advanceDeadlineMs: 0
    property int seatVisualEpoch: 0
    property bool _returningFromHidden: false
    property bool _drillSurfaceShown: false
    property bool assetLoadFailed: false
    property bool _drillStarted: false
    readonly property real spotPotBb: 5.5
    readonly property int trainerPotChips: Math.round(page.spotPotBb * 2)
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
            submit("check")
        }
    }

    function tickAdvanceTimer() {
        const left = Math.max(0, Math.ceil((advanceDeadlineMs - Date.now()) / 1000))
        secLeft = left
        if (left <= 0) {
            secTimer.stop()
            advanceDeadlineMs = 0
            inputLocked = false
            next()
        }
    }

    function syncTrainerClocks() {
        if (inputLocked && advanceDeadlineMs <= 0 && decisionDeadlineMs <= 0) {
            secTimer.stop()
            inputLocked = false
            next()
            return
        }
        if (!inputLocked && decisionDeadlineMs > 0) {
            const left = Math.max(0, Math.ceil((decisionDeadlineMs - Date.now()) / 1000))
            decisionSecLeft = left
            if (left <= 0) {
                decisionTimer.stop()
                decisionSecLeft = 0
                decisionDeadlineMs = 0
                submit("check")
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
                next()
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

    function stopDrillWhileAway() {
        cancelPendingAdvance()
    }

    function restartDrillAfterReturn() {
        if (page.assetLoadFailed)
            return
        trainer.startRiverDrill("srp_btn_bb")
        next()
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
            next()
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
        const ok = trainer.loadRiverSpots("qrc:/assets/training/spots_river_v1.json")
        page.assetLoadFailed = !ok
        if (!ok) {
            statusLine = qsTr("Could not load river spots.")
            return
        }
        trainer.startRiverDrill("srp_btn_bb")
    }

    function next() {
        cancelPendingAdvance()
        const q = trainer.nextRiverQuestion()
        if (q.error !== undefined) {
            statusLine = String(q.error)
            return
        }
        spotId = String(q.spotId)
        hero1 = String(q.hero1)
        hero2 = String(q.hero2)
        board0 = String(q.board0)
        board1 = String(q.board1)
        board2 = String(q.board2)
        board3 = String(q.board3)
        board4 = String(q.board4)
        seatVisualEpoch++
        resetTrainerPotDisplay()
        statusLine = qsTr("Pick the best play.")
        startDecisionClock()
    }

    function submit(a) {
        decisionTimer.stop()
        decisionSecLeft = 0
        decisionDeadlineMs = 0
        const r = trainer.submitRiverAnswer(a)
        if (r.error !== undefined) {
            statusLine = String(r.error)
            startAutoAdvance()
            return
        }
        const spotLabel = Theme.trainerSpotDisplayTitle(spotId)
        statusLine = qsTr("%1 — %2 (freq %3%) · EV loss %4 bb")
                .arg(spotLabel.length ? spotLabel : spotId)
                .arg(String(r.grade))
                .arg(Math.round(Number(r.chosenFreq) * 100))
                .arg(Number(r.evLossBb).toFixed(3))
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

                readonly property int _hudReserveQuantized: Math.max(172, Math.ceil(riverExerciseHud.height / 4) * 4)
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
                    text: qsTr("River spots failed to load. The bundled JSON asset may be missing or invalid.")
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

                        readonly property int riverStripIntrinsic: 5 * Theme.trainerFlopBoardCardWidth
                                + 4 * Theme.trainerDrillHudSpacing
                        readonly property real drillScale: {
                            var fixedH = 60
                            var scalableH = Theme.trainerFlopBoardCardHeight + 288.0 + 30.0
                            var hScale = (Math.max(1, drillArea.height) - fixedH) / scalableH
                            var wScale = (Math.max(1, drillArea.width) - 24) / Math.max(1, riverStripIntrinsic)
                            return Math.min(1.0, Math.max(0.28, Math.min(hScale, wScale)))
                        }
                        readonly property int drillCardW: Math.round(Theme.trainerFlopBoardCardWidth * drillScale)
                        readonly property int drillCardH: Math.round(Theme.trainerFlopBoardCardHeight * drillScale)
                        readonly property int drillCardGap: Math.max(2, Math.round(Theme.trainerDrillHudSpacing * drillScale))
                        readonly property int riverBoardStripWidth: 5 * drillCardW + 4 * drillCardGap
                        readonly property int tableSeatW: Math.round(218 * drillScale)
                        readonly property int tableSeatH: Math.round(312 * drillScale)
                        readonly property int panelPad: Math.max(4, Math.round(10 * drillScale))
                        readonly property int seatShadowBleed: Math.max(4, Math.round(8 * drillScale))

                        ColumnLayout {
                            id: riverDrillStack
                            anchors.fill: parent
                            anchors.leftMargin: drillArea.panelPad
                            anchors.rightMargin: drillArea.panelPad
                            anchors.topMargin: drillArea.panelPad
                            anchors.bottomMargin: drillArea.panelPad + drillArea.seatShadowBleed
                            spacing: Math.max(2, Math.round(6 * drillArea.drillScale))

                            Column {
                                Layout.alignment: Qt.AlignHCenter
                                spacing: Math.max(3, Math.round(6 * drillArea.drillScale))
                                width: drillArea.riverBoardStripWidth

                                Rectangle {
                                    anchors.horizontalCenter: parent.horizontalCenter
                                    width: riverPotBanner.implicitWidth + 22
                                    height: riverPotBanner.implicitHeight + 12
                                    radius: 8
                                    color: Theme.hudBg1
                                    border.color: Theme.hudBorder
                                    border.width: 2

                                    Text {
                                        id: riverPotBanner
                                        anchors.centerIn: parent
                                        text: qsTr("Pot $%1").arg(Math.round(page.trainerPotShown))
                                        color: Theme.gold
                                        font.family: Theme.fontFamilyMono
                                        font.pixelSize: Math.max(10, Math.round(Theme.trainerCaptionPx
                                                * Math.max(0.8, drillArea.drillScale)))
                                        font.bold: true

                                        transform: Scale {
                                            id: riverTrainerPotValueScale
                                            origin.x: riverPotBanner.width * 0.5
                                            origin.y: riverPotBanner.height * 0.5
                                            xScale: 1
                                            yScale: 1
                                        }
                                    }
                                }

                                Row {
                                    id: riverBoardRow
                                    spacing: drillArea.drillCardGap
                                    width: drillArea.riverBoardStripWidth
                                    Card {
                                        width: drillArea.drillCardW
                                        height: drillArea.drillCardH
                                        displayScaleFactor: drillArea.drillScale
                                        card: board0
                                        flipped: true
                                        tableCard: true
                                        instantFace: true
                                    }
                                    Card {
                                        width: drillArea.drillCardW
                                        height: drillArea.drillCardH
                                        displayScaleFactor: drillArea.drillScale
                                        card: board1
                                        flipped: true
                                        tableCard: true
                                        instantFace: true
                                    }
                                    Card {
                                        width: drillArea.drillCardW
                                        height: drillArea.drillCardH
                                        displayScaleFactor: drillArea.drillScale
                                        card: board2
                                        flipped: true
                                        tableCard: true
                                        instantFace: true
                                    }
                                    Card {
                                        width: drillArea.drillCardW
                                        height: drillArea.drillCardH
                                        displayScaleFactor: drillArea.drillScale
                                        card: board3
                                        flipped: true
                                        tableCard: true
                                        instantFace: true
                                    }
                                    Card {
                                        width: drillArea.drillCardW
                                        height: drillArea.drillCardH
                                        displayScaleFactor: drillArea.drillScale
                                        card: board4
                                        flipped: true
                                        tableCard: true
                                        instantFace: true
                                    }
                                }
                            }

                            Text {
                                Layout.fillWidth: true
                                visible: page.spotId.length > 0
                                text: Theme.trainerSpotDisplayTitle(page.spotId)
                                wrapMode: Text.WordWrap
                                horizontalAlignment: Text.AlignHCenter
                                color: Theme.textSecondary
                                font.family: Theme.fontFamilyUi
                                font.pixelSize: Theme.trainerBodyPx
                                lineHeight: Theme.bodyLineHeight
                            }

                            Item {
                                id: riverSeatRow
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
                                        position: "BTN"
                                        first_card: page.hero1
                                        second_card: page.hero2
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
                    id: riverExerciseHud
                    Layout.fillWidth: true
                    trainerMode: true
                    trainerFlopStreet: true
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
                    facingNeedChips: 0
                    facingMinRaiseChips: 6
                    facingMaxChips: 200
                    facingPotAmount: page.trainerPotChips
                    humanStackChips: 200
                    humanBbCanRaise: false
                    humanCanBuyBackIn: false
                }

                Connections {
                    target: riverExerciseHud
                    function onTrainerAction(action, amount) {
                        const u = String(action).toUpperCase()
                        if (u === "CHECK")
                            page.submit("check")
                        else if (u === "BET33") {
                            page.bumpTrainerPot(Number(amount))
                            page.submit("bet33")
                        } else if (u === "BET75") {
                            page.bumpTrainerPot(Number(amount))
                            page.submit("bet75")
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
                    target: riverTrainerPotValueScale
                    property: "xScale"
                    to: 1.08
                    duration: 95
                    easing.type: Easing.OutCubic
                }
                NumberAnimation {
                    target: riverTrainerPotValueScale
                    property: "yScale"
                    to: 1.08
                    duration: 95
                    easing.type: Easing.OutCubic
                }
            }
            ParallelAnimation {
                NumberAnimation {
                    target: riverTrainerPotValueScale
                    property: "xScale"
                    to: 1.0
                    duration: 160
                    easing.type: Easing.OutCubic
                }
                NumberAnimation {
                    target: riverTrainerPotValueScale
                    property: "yScale"
                    to: 1.0
                    duration: 160
                    easing.type: Easing.OutCubic
                }
            }
        }
    }
}
