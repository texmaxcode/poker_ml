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
    property var trainingProgress: ({})

    background: BrandedBackground { anchors.fill: parent }

    function refreshTraining() {
        var p = trainingStore.loadProgress()
        trainingProgress = (p && typeof p === "object") ? p : {}
    }

    Connections {
        target: trainingStore
        function onProgressChanged() {
            page.refreshTraining()
        }
        function onTrainerAutoAdvanceMsChanged() {
            delaySecSpin.value = Math.round(trainingStore.trainerAutoAdvanceMs / 1000)
        }
    }

    function go(idx) {
        if (stackLayout)
            stackLayout.currentIndex = idx
    }

    function scrollMainToTop() {
        var flick = scrollView.contentItem
        if (flick) {
            flick.contentY = 0
            flick.contentX = 0
        }
    }

    ScrollView {
        id: scrollView
        anchors.fill: parent
        clip: true
        topPadding: Theme.trainerPageTopPadding

        RowLayout {
            width: scrollView.availableWidth
            spacing: 0

            Item {
                Layout.fillWidth: true
                Layout.minimumWidth: 0
            }

            ColumnLayout {
                id: mainCol
                Layout.preferredWidth: Math.min(Theme.trainerContentMaxWidth, Math.max(280, scrollView.availableWidth - 40))
                Layout.maximumWidth: Theme.trainerContentMaxWidth
                spacing: Theme.trainerColumnSpacing

                Rectangle {
                    Layout.fillWidth: true
                    implicitHeight: progressCol.implicitHeight + 2 * Theme.trainerPanelPadding
                    radius: Theme.trainerPanelRadius
                    color: Qt.alpha(Theme.panel, 0.5)
                    border.width: 1
                    border.color: Qt.alpha(Theme.chromeLine, 0.5)

                    ColumnLayout {
                        id: progressCol
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.top: parent.top
                        anchors.margins: Theme.trainerPanelPadding
                        spacing: Theme.uiGroupInnerSpacing

                        Label {
                            Layout.fillWidth: true
                            text: qsTr("Training progress")
                            font.family: Theme.fontFamilyDisplay
                            font.bold: true
                            font.capitalization: Font.AllUppercase
                            font.pixelSize: Theme.trainerSectionPx
                            font.letterSpacing: 0.5
                            color: Theme.sectionTitle
                        }

                        Label {
                            Layout.fillWidth: true
                            wrapMode: Text.WordWrap
                            text: qsTr(
                                "Counts every trainer answer. Accuracy is the share graded “Correct” (frequency ≥70% in the loaded strategy). "
                                + "EV lost adds postflop EV gaps in big blinds vs the best line; preflop rows add 0 EV here. Reset clears stats but keeps your auto-advance delay.")
                            color: Theme.textSecondary
                            font.pixelSize: Theme.trainerBodyPx
                            lineHeight: Theme.bodyLineHeight
                        }

                        /// Backend keys: `totalD` / `correctD` / `totalEvLossBb` (aliases: totalDecisions / totalCorrect).
                        readonly property int totalD: Number(page.trainingProgress.totalD
                                || page.trainingProgress.totalDecisions || 0)
                        readonly property int totalC: Number(page.trainingProgress.correctD
                                || page.trainingProgress.totalCorrect || 0)
                        readonly property real totalEv: Number(page.trainingProgress.totalEvLossBb || 0)
                        readonly property real accPct: totalD > 0 ? (100.0 * totalC / totalD) : 0
                        readonly property var drillStats: page.trainingProgress.drillStats || ({})

                        GridLayout {
                            Layout.fillWidth: true
                            columns: progressCol.width > 520 ? 3 : 1
                            rowSpacing: Theme.uiGroupInnerSpacing
                            columnSpacing: Theme.uiGroupInnerSpacing

                            Rectangle {
                                Layout.fillWidth: true
                                implicitHeight: trainingMetricsCol.implicitHeight + 28
                                radius: 10
                                color: Theme.panelElevated
                                border.width: 1
                                border.color: Qt.alpha(Theme.chromeLine, 0.55)
                                Column {
                                    id: trainingMetricsCol
                                    x: 14
                                    y: 14
                                    width: parent.width - 28
                                    spacing: 6
                                    Text {
                                        text: qsTr("DECISIONS")
                                        color: Theme.textMuted
                                        font.family: Theme.fontFamilyDisplay
                                        font.pixelSize: Theme.trainerMetricLabelPx
                                        font.letterSpacing: 1
                                    }
                                    Text { text: String(progressCol.totalD); color: Theme.gold; font.bold: true; font.pixelSize: Theme.trainerMetricValuePx }
                                }
                            }

                            Rectangle {
                                Layout.fillWidth: true
                                implicitHeight: trainingAccCol.implicitHeight + 28
                                radius: 10
                                color: Theme.panelElevated
                                border.width: 1
                                border.color: Qt.alpha(Theme.chromeLine, 0.55)
                                Column {
                                    id: trainingAccCol
                                    x: 14
                                    y: 14
                                    width: parent.width - 28
                                    spacing: 6
                                    Text {
                                        text: qsTr("ACCURACY")
                                        color: Theme.textMuted
                                        font.family: Theme.fontFamilyDisplay
                                        font.pixelSize: Theme.trainerMetricLabelPx
                                        font.letterSpacing: 1
                                    }
                                    Text { text: progressCol.accPct.toFixed(1) + "%"; color: Theme.gold; font.family: Theme.fontFamilyMono; font.bold: true; font.pixelSize: Theme.trainerMetricValuePx }
                                }
                            }

                            Rectangle {
                                Layout.fillWidth: true
                                implicitHeight: trainingEvCol.implicitHeight + 28
                                radius: 10
                                color: Theme.panelElevated
                                border.width: 1
                                border.color: Qt.alpha(Theme.chromeLine, 0.55)
                                Column {
                                    id: trainingEvCol
                                    x: 14
                                    y: 14
                                    width: parent.width - 28
                                    spacing: 6
                                    Text {
                                        text: qsTr("EV LOST")
                                        color: Theme.textMuted
                                        font.family: Theme.fontFamilyDisplay
                                        font.pixelSize: Theme.trainerMetricLabelPx
                                        font.letterSpacing: 1
                                    }
                                    Text { text: progressCol.totalEv.toFixed(3) + " bb"; color: Theme.gold; font.family: Theme.fontFamilyMono; font.bold: true; font.pixelSize: Theme.trainerMetricValuePx }
                                }
                            }
                        }

                        Label {
                            Layout.fillWidth: true
                            wrapMode: Text.WordWrap
                            text: qsTr("By drill")
                            font.family: Theme.fontFamilyDisplay
                            font.bold: true
                            font.capitalization: Font.AllUppercase
                            font.pixelSize: Theme.trainerSectionPx - 2
                            font.letterSpacing: 0.5
                            color: Theme.sectionTitle
                        }

                        GridLayout {
                            Layout.fillWidth: true
                            columns: progressCol.width > 520 ? 2 : 1
                            rowSpacing: 8
                            columnSpacing: Theme.uiGroupInnerSpacing

                            Repeater {
                                model: [
                                    { key: "preflop", label: qsTr("Preflop") },
                                    { key: "flop", label: qsTr("Flop") },
                                    { key: "turn", label: qsTr("Turn") },
                                    { key: "river", label: qsTr("River") }
                                ]

                                delegate: Rectangle {
                                    id: drillCard
                                    required property var modelData
                                    Layout.fillWidth: true
                                    implicitHeight: drillInner.implicitHeight + 24
                                    radius: 8
                                    color: Theme.panelElevated
                                    border.width: 1
                                    border.color: Qt.alpha(Theme.chromeLine, 0.5)

                                    readonly property var d: {
                                        var m = progressCol.drillStats[modelData.key]
                                        return (m && typeof m === "object") ? m : ({})
                                    }
                                    readonly property int dTotal: Number(d.totalD || 0)
                                    readonly property int dCorrect: Number(d.correctD || 0)
                                    readonly property real dAcc: dTotal > 0 ? (100.0 * dCorrect / dTotal) : 0
                                    readonly property real dEv: Number(d.totalEvLossBb || 0)

                                    Column {
                                        id: drillInner
                                        x: 12
                                        y: 10
                                        width: drillCard.width - 24
                                        spacing: 4
                                        Text {
                                            text: modelData.label
                                            color: Theme.textMuted
                                            font.family: Theme.fontFamilyDisplay
                                            font.pixelSize: Theme.trainerCaptionPx
                                            font.bold: true
                                        }
                                        Text {
                                            text: qsTr("%1 decisions · %2% acc · %3 bb EV lost")
                                                    .arg(drillCard.dTotal)
                                                    .arg(drillCard.dAcc.toFixed(1))
                                                    .arg(drillCard.dEv.toFixed(3))
                                            color: Theme.textPrimary
                                            font.pixelSize: Theme.trainerBodyPx
                                            wrapMode: Text.WordWrap
                                            width: parent.width
                                        }
                                    }
                                }
                            }
                        }

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 10

                            ResetButton {
                                text: qsTr("Reset training progress")
                                onClicked: trainingStore.resetProgress()
                            }
                            Item { Layout.fillWidth: true }
                        }
                    }
                }

                Rectangle {
                    Layout.fillWidth: true
                    implicitHeight: scoringCol.implicitHeight + 2 * Theme.trainerPanelPadding
                    radius: Theme.trainerPanelRadius
                    color: Qt.alpha(Theme.panel, 0.45)
                    border.width: 1
                    border.color: Qt.alpha(Theme.chromeLine, 0.45)

                    ColumnLayout {
                        id: scoringCol
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.top: parent.top
                        anchors.margins: Theme.trainerPanelPadding
                        spacing: 8

                        Label {
                            Layout.fillWidth: true
                            text: qsTr("How scoring works")
                            font.family: Theme.fontFamilyDisplay
                            font.bold: true
                            font.capitalization: Font.AllUppercase
                            font.pixelSize: Theme.trainerSectionPx
                            font.letterSpacing: 0.5
                            color: Theme.sectionTitle
                        }
                        Label {
                            Layout.fillWidth: true
                            wrapMode: Text.WordWrap
                            text: qsTr(
                                "Grades use the loaded strategy: Correct if your action’s frequency is ≥70%; Mix if 5–70%; Wrong if below 5%. "
                                + "Preflop uses the 13×13 chart for seat and mode. Postflop, EV loss (bb below the best line) is tracked in your progress.")
                            color: Theme.textSecondary
                            font.pixelSize: Theme.trainerBodyPx
                            lineHeight: Theme.bodyLineHeight
                        }
                    }
                }

                RowLayout {
                    Layout.fillWidth: true
                    Layout.alignment: Qt.AlignHCenter
                    spacing: 14

                    Label {
                        text: qsTr("Delay after answer")
                        color: Theme.textMuted
                        font.pixelSize: Theme.trainerCaptionPx
                        Layout.alignment: Qt.AlignVCenter
                    }
                    ThemedSpinBox {
                        id: delaySecSpin
                        Layout.preferredWidth: Theme.trainerSpinBoxWidth
                        labelPixelSize: Theme.trainerCaptionPx
                        Layout.alignment: Qt.AlignVCenter
                        from: 1
                        to: 120
                        editable: true
                        stepSize: 1
                        textFromValue: function (v) { return v + qsTr(" s") }
                        valueFromText: function (t) { return parseInt(t, 10) }
                        onValueModified: trainingStore.trainerAutoAdvanceMs = value * 1000
                    }
                }

                Flow {
                    Layout.fillWidth: true
                    spacing: Theme.trainerDrillHudSpacing
                    layoutDirection: Qt.LeftToRight

                    Item {
                        width: Math.max(0, (parent.width - drillNavContent.implicitWidth) / 2)
                        height: 1
                        visible: drillNavContent.implicitWidth < parent.width
                    }

                    Flow {
                        id: drillNavContent
                        spacing: Theme.trainerDrillHudSpacing
                        GameButton {
                            text: qsTr("Preflop")
                            pillWidth: 100
                            buttonColor: Theme.successGreen
                            textColor: Theme.onAccentText
                            fontSize: Theme.uiHudButtonPt
                            overrideHeight: 34
                            onClicked: page.go(6)
                        }
                        GameButton {
                            text: qsTr("Flop")
                            pillWidth: 88
                            buttonColor: Theme.successGreen
                            textColor: Theme.onAccentText
                            fontSize: Theme.uiHudButtonPt
                            overrideHeight: 34
                            onClicked: page.go(7)
                        }
                        GameButton {
                            text: qsTr("Turn")
                            pillWidth: 88
                            buttonColor: Theme.successGreen
                            textColor: Theme.onAccentText
                            fontSize: Theme.uiHudButtonPt
                            overrideHeight: 34
                            onClicked: page.go(8)
                        }
                        GameButton {
                            text: qsTr("River")
                            pillWidth: 88
                            buttonColor: Theme.successGreen
                            textColor: Theme.onAccentText
                            fontSize: Theme.uiHudButtonPt
                            overrideHeight: 34
                            onClicked: page.go(9)
                        }
                        GameButton {
                            text: qsTr("Ranges")
                            pillWidth: 96
                            buttonColor: Theme.successGreen
                            textColor: Theme.onAccentText
                            fontSize: Theme.uiHudButtonPt
                            overrideHeight: 34
                            onClicked: page.go(10)
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

    onVisibleChanged: {
        if (visible)
            page.refreshTraining()
    }

    Component.onCompleted: {
        delaySecSpin.value = Math.round(trainingStore.trainerAutoAdvanceMs / 1000)
        page.refreshTraining()
    }
}
