import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Theme 1.0
import PokerUi 1.0

Page {
    id: solverPage
    padding: 0
    font.family: Theme.fontFamilyUi

    property bool simRunning: false
    /// Full text from last run (equity block + detailText); shown in the log dialog.
    property string lastFullLog: ""
    /// Short lines for the main panel (spot + key numbers).
    property string summaryText: qsTr("Run a simulation for a brief summary. Open Full log for the complete output.")
    property string nashSummaryText: qsTr("Pick a toy game and run CFR+ to compute an approximate Nash equilibrium.")
    property string nashDetailText: ""
    /// True when equity run reported an error or returned unusable numbers (crash-safe fallback).
    property bool equitySummaryIsError: false
    property bool nashResultIsError: false

    readonly property real solverUiScale: Theme.compactUiScale(Math.min(solverPage.width, solverPage.height))
    readonly property int solverFormGridCols: scroll.availableWidth < 500 ? 1 : 2
    readonly property int solverFieldFontPx: Math.max(12, Math.round((Theme.trainerCaptionPx - 2) * solverUiScale))
    readonly property int solverFieldPadH: Math.max(10, Math.round(13 * solverUiScale))
    readonly property int solverFieldPadV: Math.max(7, Math.round(9 * solverUiScale))
    readonly property int solverLabelPx: Math.max(12, Math.round(Theme.formLabelPx * solverUiScale))
    readonly property bool solverNashStacked: scroll.availableWidth < 560

    function applySavedSolver(m) {
        if (m.hero1 !== undefined && m.hero1.length > 0)
            h1.text = m.hero1
        if (m.hero2 !== undefined && m.hero2.length > 0)
            h2.text = m.hero2
        if (m.board !== undefined)
            brd.text = m.board
        if (m.villainRange !== undefined && m.villainRange.length > 0)
            vrange.text = m.villainRange
        if (m.villainE1 !== undefined)
            ve1.text = m.villainE1
        if (m.villainE2 !== undefined)
            ve2.text = m.villainE2
        if (m.iterations !== undefined)
            iters.value = m.iterations
        if (m.potBeforeCall !== undefined)
            potSpin.value = m.potBeforeCall
        if (m.toCall !== undefined)
            callSpin.value = m.toCall
    }

    Component.onCompleted: Qt.callLater(function () {
        applySavedSolver(sessionStore.loadSolverFields())
    })

    TextEdit {
        id: clipBuffer
        visible: false
        height: 1
        width: 1
        text: ""
    }

    Popup {
        id: fullLogPopup
        parent: Overlay.overlay
        modal: true
        focus: true
        closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
        width: Math.min(720, Overlay.overlay ? Overlay.overlay.width - 32 : 640)
        height: Math.min(520, Overlay.overlay ? Overlay.overlay.height - 48 : 480)
        x: Math.round((parent.width - width) / 2)
        y: Math.round((parent.height - height) / 2)
        padding: 0

        background: Rectangle {
            color: Theme.panel
            border.color: Theme.headerRule
            border.width: 1
            radius: 10
        }

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: Theme.uiGroupedPanelPadding
            spacing: Theme.uiGroupInnerSpacing

            Label {
                text: qsTr("Simulation log")
                font.family: Theme.fontFamilyDisplay
                font.bold: true
                font.capitalization: Font.AllUppercase
                font.pixelSize: Theme.trainerSectionPx
                font.letterSpacing: 0.5
                color: Theme.gold
            }

            ScrollView {
                id: logScroll
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.minimumHeight: 200
                clip: true
                ScrollBar.horizontal.policy: ScrollBar.AlwaysOff

                TextArea {
                    id: logTextArea
                    width: logScroll.availableWidth
                    readOnly: true
                    wrapMode: TextArea.Wrap
                    font.family: Theme.fontFamilyMono
                    font.pixelSize: Theme.uiMonoPx
                    color: Theme.textPrimary
                    text: solverPage.lastFullLog
                    padding: 10
                    background: Rectangle {
                        color: Theme.bgGradientMid
                        border.color: Theme.headerRule
                        border.width: 1
                        radius: 8
                    }
                }
            }

            Button {
                text: qsTr("Close")
                font.family: Theme.fontFamilyButton
                Layout.alignment: Qt.AlignRight
                onClicked: fullLogPopup.close()
            }
        }
    }

    background: BrandedBackground {
        anchors.fill: parent
    }

    Connections {
        target: ApplicationWindow.window
        function onClosing(close) {
            sessionStore.saveSolverFields({
                "hero1": h1.text,
                "hero2": h2.text,
                "board": brd.text,
                "villainRange": vrange.text,
                "villainE1": ve1.text,
                "villainE2": ve2.text,
                "iterations": iters.value,
                "potBeforeCall": potSpin.value,
                "toCall": callSpin.value
            })
        }
    }

    Connections {
        target: pokerSolver
        function onEquityComputationFinished(m) {
            solverPage.simRunning = false
            solverPage.equitySummaryIsError = false
            if (m["error"] !== undefined && String(m["error"]).length > 0) {
                const err = String(m["error"])
                solverPage.lastFullLog = err
                solverPage.summaryText = err
                solverPage.equitySummaryIsError = true
                return
            }
            const eq = Number(m.equityPct)
            const se = Number(m.stdErrPct)
            const it = Number(m.iterations)
            if (!isFinite(eq) || !isFinite(se) || !isFinite(it)) {
                const msg = qsTr("Equity computation finished without valid results. Try different cards, range, or iterations.")
                solverPage.lastFullLog = msg
                solverPage.summaryText = msg
                solverPage.equitySummaryIsError = true
                return
            }
            let t = ""
            t += qsTr("Equity: ") + eq.toFixed(2) + " %"
            t += "  (± ~" + se.toFixed(2) + " % 1σ)\n"
            t += qsTr("Iterations: ") + it + "\n"
            if (m.breakEvenPct !== undefined && isFinite(Number(m.breakEvenPct))
                    && m.evCall !== undefined && isFinite(Number(m.evCall))
                    && m.recommendation !== undefined) {
                t += qsTr("Break-even equity to call: ") + Number(m.breakEvenPct).toFixed(2) + " %\n"
                t += qsTr("EV of call: ") + Number(m.evCall).toFixed(3) + "\n"
                t += qsTr("Suggestion: ") + m.recommendation + "\n"
            }
            if (m.mdfPct !== undefined && isFinite(Number(m.mdfPct)))
                t += qsTr("MDF heuristic (~defense freq vs this raise): ") + Number(m.mdfPct).toFixed(1) + " %\n"
            t += "\n" + (m.detailText !== undefined ? m.detailText : "")
            solverPage.lastFullLog = t

            let s = ""
            s += h1.text + " " + h2.text
            if (brd.text.trim().length > 0)
                s += " · " + brd.text.trim()
            s += "\n"
            s += qsTr("Equity ") + eq.toFixed(2) + "% (±" + se.toFixed(2) + "%) · "
                    + it + " " + qsTr("iters")
            if (m.breakEvenPct !== undefined && isFinite(Number(m.breakEvenPct))
                    && m.evCall !== undefined && isFinite(Number(m.evCall))
                    && m.recommendation !== undefined) {
                s += "\n" + qsTr("BE ") + Number(m.breakEvenPct).toFixed(1) + "% · EV " + Number(m.evCall).toFixed(3)
                        + " · " + m.recommendation
            }
            if (m.mdfPct !== undefined && isFinite(Number(m.mdfPct)))
                s += "\n" + qsTr("MDF ~") + Number(m.mdfPct).toFixed(1) + "%"
            solverPage.summaryText = s
        }
    }

    Connections {
        target: toyNashSolver
        function onSolveFinished(m) {
            solverPage.simRunning = false
            solverPage.nashResultIsError = false
            if (m["error"] !== undefined && String(m["error"]).length > 0) {
                const err = String(m["error"])
                solverPage.nashSummaryText = err
                solverPage.nashDetailText = ""
                solverPage.nashResultIsError = true
                return
            }
            solverPage.nashSummaryText = String(m.summaryText !== undefined ? m.summaryText : "")
            solverPage.nashDetailText = String(m.detailText !== undefined ? m.detailText : "")
        }
    }

    function scrollMainToTop() {
        var flick = scroll.contentItem
        if (flick) {
            flick.contentY = 0
            flick.contentX = 0
        }
    }

    ScrollView {
        id: scroll
        anchors.fill: parent
        clip: true
        ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
        topPadding: Theme.uiScrollViewTopPadding

        RowLayout {
            width: scroll.availableWidth
            spacing: 0

            Item {
                Layout.fillWidth: true
                Layout.minimumWidth: 0
            }

            ColumnLayout {
                id: solverCol
                Layout.preferredWidth: Math.min(Theme.trainerContentMaxWidth, Math.max(280, scroll.availableWidth - 40))
                Layout.maximumWidth: Theme.trainerContentMaxWidth
                spacing: Theme.trainerColumnSpacing

                ThemedPanel {
                    Layout.fillWidth: true
                    panelTitle: qsTr("Hand & board")
                    panelTitlePixelSize: Math.max(16, Math.round(Theme.trainerSectionPx * solverPage.solverUiScale))
                    panelPadding: Math.max(12, Math.round(Theme.trainerPanelPadding * solverPage.solverUiScale))

                    ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 0

                        GridLayout {
                            Layout.fillWidth: true
                            columns: solverPage.solverFormGridCols
                            columnSpacing: Math.max(8, Math.round(Theme.formColGap * solverPage.solverUiScale))
                            rowSpacing: Math.max(8, Math.round(Theme.formRowSpacing * solverPage.solverUiScale))

                        Label {
                            text: qsTr("Hero card 1")
                            Layout.alignment: solverPage.solverFormGridCols === 1
                                    ? (Qt.AlignLeft | Qt.AlignVCenter)
                                    : (Qt.AlignRight | Qt.AlignVCenter)
                            Layout.maximumWidth: solverPage.solverFormGridCols === 1 ? 99999 : Math.round(140 * solverPage.solverUiScale)
                            font.pixelSize: solverPage.solverLabelPx
                        }
                        TextField {
                            id: h1
                            placeholderText: "Ah"
                            text: "Ah"
                            font.pixelSize: solverPage.solverFieldFontPx
                            leftPadding: solverPage.solverFieldPadH
                            rightPadding: solverPage.solverFieldPadH
                            topPadding: solverPage.solverFieldPadV
                            bottomPadding: solverPage.solverFieldPadV
                            Layout.fillWidth: solverPage.solverFormGridCols === 1
                            Layout.maximumWidth: solverPage.solverFormGridCols === 1
                                    ? 99999
                                    : Math.round(120 * solverPage.solverUiScale)
                            implicitWidth: solverPage.solverFormGridCols === 1
                                    ? 160
                                    : Math.round(112 * solverPage.solverUiScale)
                        }
                        Label {
                            text: qsTr("Hero card 2")
                            Layout.alignment: solverPage.solverFormGridCols === 1
                                    ? (Qt.AlignLeft | Qt.AlignVCenter)
                                    : (Qt.AlignRight | Qt.AlignVCenter)
                            font.pixelSize: solverPage.solverLabelPx
                        }
                        TextField {
                            id: h2
                            placeholderText: "Kd"
                            text: "Kd"
                            font.pixelSize: solverPage.solverFieldFontPx
                            leftPadding: solverPage.solverFieldPadH
                            rightPadding: solverPage.solverFieldPadH
                            topPadding: solverPage.solverFieldPadV
                            bottomPadding: solverPage.solverFieldPadV
                            Layout.fillWidth: solverPage.solverFormGridCols === 1
                            Layout.maximumWidth: solverPage.solverFormGridCols === 1
                                    ? 99999
                                    : Math.round(120 * solverPage.solverUiScale)
                            implicitWidth: solverPage.solverFormGridCols === 1
                                    ? 160
                                    : Math.round(112 * solverPage.solverUiScale)
                        }
                        Label {
                            text: qsTr("Board (optional)")
                            Layout.alignment: solverPage.solverFormGridCols === 1
                                    ? (Qt.AlignLeft | Qt.AlignVCenter)
                                    : (Qt.AlignRight | Qt.AlignVCenter)
                            font.pixelSize: solverPage.solverLabelPx
                        }
                        TextField {
                            id: brd
                            placeholderText: "Qs Jh 2c or empty"
                            placeholderTextColor: Qt.alpha(Theme.textSecondary, 0.88)
                            font.pixelSize: solverPage.solverFieldFontPx
                            leftPadding: solverPage.solverFieldPadH
                            rightPadding: solverPage.solverFieldPadH
                            topPadding: solverPage.solverFieldPadV
                            bottomPadding: solverPage.solverFieldPadV
                            Layout.fillWidth: true
                            Layout.maximumWidth: solverPage.solverFormGridCols === 1
                                    ? 99999
                                    : Math.round(560 * solverPage.solverUiScale)
                        }
                        Label {
                            text: qsTr("Villain range")
                            Layout.alignment: solverPage.solverFormGridCols === 1
                                    ? (Qt.AlignLeft | Qt.AlignTop)
                                    : (Qt.AlignRight | Qt.AlignTop)
                            font.pixelSize: solverPage.solverLabelPx
                        }
                        TextField {
                            id: vrange
                            placeholderText: "AA,AKs,QQ+"
                            text: "AA,TT+,AKs,AKo"
                            font.pixelSize: solverPage.solverFieldFontPx
                            leftPadding: solverPage.solverFieldPadH
                            rightPadding: solverPage.solverFieldPadH
                            topPadding: solverPage.solverFieldPadV
                            bottomPadding: solverPage.solverFieldPadV
                            Layout.fillWidth: true
                            Layout.maximumWidth: solverPage.solverFormGridCols === 1
                                    ? 99999
                                    : Math.round(560 * solverPage.solverUiScale)
                        }
                        Label {
                            text: qsTr("Villain exact")
                            Layout.alignment: solverPage.solverFormGridCols === 1
                                    ? (Qt.AlignLeft | Qt.AlignVCenter)
                                    : (Qt.AlignRight | Qt.AlignVCenter)
                            font.pixelSize: solverPage.solverLabelPx
                        }
                        RowLayout {
                            spacing: Math.max(6, Math.round(8 * solverPage.solverUiScale))
                            Layout.fillWidth: solverPage.solverFormGridCols === 1
                            TextField {
                                id: ve1
                                placeholderText: "Qs"
                                font.pixelSize: solverPage.solverFieldFontPx
                                leftPadding: solverPage.solverFieldPadH
                                rightPadding: solverPage.solverFieldPadH
                                topPadding: solverPage.solverFieldPadV
                                bottomPadding: solverPage.solverFieldPadV
                                Layout.fillWidth: solverPage.solverFormGridCols === 1
                                Layout.preferredWidth: Math.round(96 * solverPage.solverUiScale)
                                implicitWidth: Math.round(96 * solverPage.solverUiScale)
                            }
                            TextField {
                                id: ve2
                                placeholderText: "Jh"
                                font.pixelSize: solverPage.solverFieldFontPx
                                leftPadding: solverPage.solverFieldPadH
                                rightPadding: solverPage.solverFieldPadH
                                topPadding: solverPage.solverFieldPadV
                                bottomPadding: solverPage.solverFieldPadV
                                Layout.fillWidth: solverPage.solverFormGridCols === 1
                                Layout.preferredWidth: Math.round(96 * solverPage.solverUiScale)
                                implicitWidth: Math.round(96 * solverPage.solverUiScale)
                            }
                            Item {
                                Layout.fillWidth: true
                            }
                        }
                        }
                    }
                }

                ThemedPanel {
                    Layout.fillWidth: true
                    panelTitle: qsTr("Simulation & pot odds")
                    panelTitlePixelSize: Math.max(16, Math.round(Theme.trainerSectionPx * solverPage.solverUiScale))
                    panelPadding: Math.max(12, Math.round(Theme.trainerPanelPadding * solverPage.solverUiScale))

                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 0

                        GridLayout {
                            Layout.fillWidth: true
                            columns: solverPage.solverFormGridCols
                            columnSpacing: Math.max(8, Math.round(Theme.formColGap * solverPage.solverUiScale))
                            rowSpacing: Math.max(8, Math.round(Theme.formRowSpacing * solverPage.solverUiScale))

                        Label {
                            text: qsTr("Iterations")
                            Layout.alignment: solverPage.solverFormGridCols === 1
                                    ? (Qt.AlignLeft | Qt.AlignVCenter)
                                    : (Qt.AlignLeft | Qt.AlignVCenter)
                            font.pixelSize: solverPage.solverLabelPx
                        }
                        SpinBox {
                            id: iters
                            from: 1000
                            to: 2000000
                            value: 40000
                            stepSize: 1000
                            editable: true
                            font.pixelSize: solverPage.solverLabelPx
                            Layout.fillWidth: solverPage.solverFormGridCols === 1
                            Layout.maximumWidth: solverPage.solverFormGridCols === 1
                                    ? 99999
                                    : Math.round(220 * solverPage.solverUiScale)
                            implicitWidth: Math.round(200 * solverPage.solverUiScale)
                        }
                        Label {
                            text: qsTr("Pot before call")
                            Layout.alignment: Qt.AlignLeft | Qt.AlignVCenter
                            font.pixelSize: solverPage.solverLabelPx
                        }
                        SpinBox {
                            id: potSpin
                            from: 0
                            to: 100000
                            value: 100
                            editable: true
                            font.pixelSize: solverPage.solverLabelPx
                            Layout.fillWidth: solverPage.solverFormGridCols === 1
                            Layout.maximumWidth: solverPage.solverFormGridCols === 1
                                    ? 99999
                                    : Math.round(220 * solverPage.solverUiScale)
                            implicitWidth: Math.round(200 * solverPage.solverUiScale)
                        }
                        Label {
                            text: qsTr("To call")
                            Layout.alignment: Qt.AlignLeft | Qt.AlignVCenter
                            font.pixelSize: solverPage.solverLabelPx
                        }
                        SpinBox {
                            id: callSpin
                            from: 0
                            to: 100000
                            value: 50
                            editable: true
                            font.pixelSize: solverPage.solverLabelPx
                            Layout.fillWidth: solverPage.solverFormGridCols === 1
                            Layout.maximumWidth: solverPage.solverFormGridCols === 1
                                    ? 99999
                                    : Math.round(220 * solverPage.solverUiScale)
                            implicitWidth: Math.round(200 * solverPage.solverUiScale)
                        }
                        }
                    }
                }

                RowLayout {
                    Layout.fillWidth: true
                    spacing: Math.max(10, Math.round(Theme.trainerColumnSpacing * solverPage.solverUiScale))

                    Button {
                        id: runSimBtn
                        text: qsTr("Run simulation")
                        font.family: Theme.fontFamilyButton
                        font.pixelSize: Math.max(12, Math.round(Theme.trainerButtonLabelPx * solverPage.solverUiScale))
                        Layout.preferredWidth: Math.round(200 * solverPage.solverUiScale)
                        highlighted: true
                        enabled: !solverPage.simRunning
                        onClicked: {
                            solverPage.simRunning = true
                            solverPage.equitySummaryIsError = false
                            solverPage.summaryText = qsTr("Running simulation on a background thread…")
                            solverPage.lastFullLog = ""
                            pokerSolver.computeEquityAsync(
                                h1.text,
                                h2.text,
                                brd.text,
                                vrange.text,
                                ve1.text,
                                ve2.text,
                                iters.value,
                                potSpin.value,
                                callSpin.value
                            )
                        }
                    }

                    BusyIndicator {
                        visible: solverPage.simRunning
                        running: solverPage.simRunning
                        Layout.preferredWidth: Math.round(40 * solverPage.solverUiScale)
                        Layout.preferredHeight: Math.round(40 * solverPage.solverUiScale)
                    }

                    Label {
                        visible: solverPage.simRunning
                        text: qsTr("Working…")
                        color: Theme.focusGold
                        font.pixelSize: Math.max(12, Math.round(Theme.trainerCaptionPx * solverPage.solverUiScale))
                    }

                    Item {
                        Layout.fillWidth: true
                    }
                }

                ThemedPanel {
                    Layout.fillWidth: true
                    panelTitle: qsTr("Results")
                    panelTitlePixelSize: Math.max(16, Math.round(Theme.trainerSectionPx * solverPage.solverUiScale))
                    panelPadding: Math.max(12, Math.round(Theme.trainerPanelPadding * solverPage.solverUiScale))

                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: Theme.uiGroupInnerSpacing

                        Text {
                            id: summaryLabel
                            Layout.fillWidth: true
                            text: solverPage.summaryText
                            wrapMode: Text.Wrap
                            color: solverPage.equitySummaryIsError ? Theme.dangerText : Theme.textSecondary
                            font.family: Theme.fontFamilyUi
                            font.pixelSize: Math.max(13, Math.round(Theme.trainerBodyPx * solverPage.solverUiScale))
                            lineHeight: Theme.bodyLineHeight
                            HoverHandler {
                                id: summaryHover
                            }
                            ToolTip.visible: summaryHover.hovered && solverPage.lastFullLog.length > 0
                            ToolTip.delay: 400
                            ToolTip.text: qsTr("Summary only. Open Full log for equity details, combos, and notes.")
                        }

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 8

                            Button {
                                text: qsTr("Full log")
                                font.family: Theme.fontFamilyButton
                                enabled: solverPage.lastFullLog.length > 0
                                onClicked: fullLogPopup.open()
                            }

                            Button {
                                text: qsTr("Copy")
                                font.family: Theme.fontFamilyButton
                                enabled: solverPage.lastFullLog.length > 0
                                onClicked: {
                                    clipBuffer.text = solverPage.lastFullLog
                                    clipBuffer.forceActiveFocus()
                                    clipBuffer.selectAll()
                                    clipBuffer.copy()
                                }
                            }

                            Item {
                                Layout.fillWidth: true
                            }
                        }
                    }
                }

                ThemedPanel {
                    Layout.fillWidth: true
                    panelTitle: qsTr("Nash solver (CFR+) — toy games")
                    panelTitlePixelSize: Math.max(16, Math.round(Theme.trainerSectionPx * solverPage.solverUiScale))
                    panelPadding: Math.max(12, Math.round(Theme.trainerPanelPadding * solverPage.solverUiScale))

                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: Theme.uiGroupInnerSpacing

                        Text {
                            Layout.fillWidth: true
                            text: qsTr("Computes an approximate Nash equilibrium for small benchmark poker games. ")
                                  + qsTr("This is the same family of algorithms used by full Hold'em solvers, ")
                                  + qsTr("but on tiny games so it runs locally.")
                            wrapMode: Text.Wrap
                            color: Theme.textSecondary
                            font.pixelSize: Math.max(13, Math.round(Theme.trainerBodyPx * solverPage.solverUiScale))
                            lineHeight: Theme.bodyLineHeight
                        }

                        GridLayout {
                            Layout.fillWidth: true
                            columns: solverPage.solverNashStacked ? 1 : 4
                            columnSpacing: 10
                            rowSpacing: 10

                            ComboBox {
                                id: nashGame
                                Layout.fillWidth: solverPage.solverNashStacked
                                font.pixelSize: solverPage.solverLabelPx
                                Layout.preferredWidth: solverPage.solverNashStacked ? implicitWidth : Math.round(220 * solverPage.solverUiScale)
                                model: [qsTr("Kuhn (3-card)"), qsTr("Leduc (toy Hold'em)")]
                                currentIndex: 0
                            }

                            SpinBox {
                                id: nashIters
                                from: 100
                                to: 500000
                                value: 5000
                                stepSize: 100
                                editable: true
                                font.pixelSize: solverPage.solverLabelPx
                                Layout.fillWidth: solverPage.solverNashStacked
                                Layout.maximumWidth: solverPage.solverNashStacked
                                        ? 99999
                                        : Math.round(220 * solverPage.solverUiScale)
                                implicitWidth: Math.round(220 * solverPage.solverUiScale)
                            }

                            Button {
                                text: qsTr("Run CFR+")
                                font.family: Theme.fontFamilyButton
                                font.pixelSize: Math.max(12, Math.round(Theme.trainerButtonLabelPx * solverPage.solverUiScale))
                                highlighted: true
                                enabled: !solverPage.simRunning && !(toyNashSolver && toyNashSolver.solveRunning())
                                onClicked: {
                                    solverPage.simRunning = true
                                    solverPage.nashResultIsError = false
                                    solverPage.nashSummaryText = qsTr("Solving…")
                                    solverPage.nashDetailText = ""
                                    if (nashGame.currentIndex === 0)
                                        toyNashSolver.solveKuhnAsync(nashIters.value)
                                    else
                                        toyNashSolver.solveLeducAsync(nashIters.value)
                                }
                            }

                            BusyIndicator {
                                visible: (toyNashSolver && toyNashSolver.solveRunning()) || solverPage.simRunning
                                running: visible
                                Layout.preferredWidth: Math.round(32 * solverPage.solverUiScale)
                                Layout.preferredHeight: Math.round(32 * solverPage.solverUiScale)
                            }
                        }

                        TextArea {
                            Layout.fillWidth: true
                            Layout.minimumHeight: Math.max(120, Math.round(150 * solverPage.solverUiScale))
                            readOnly: true
                            wrapMode: TextArea.Wrap
                            font.family: Theme.fontFamilyMono
                            font.pixelSize: Math.max(11, Math.round(Theme.uiMonoPx * solverPage.solverUiScale))
                            color: solverPage.nashResultIsError ? Theme.dangerText : Theme.textPrimary
                            text: solverPage.nashSummaryText + "\n\n" + solverPage.nashDetailText
                            background: Rectangle {
                                color: Theme.bgGradientMid
                                border.color: Theme.headerRule
                                border.width: 1
                                radius: 8
                            }
                        }
                    }
                }
            }

            Item {
                Layout.fillWidth: true
                Layout.minimumWidth: 0
            }
        }
    }
}
