import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Theme 1.0
import PokerUi 1.0

/// Seat panel — hole cards hidden when folded; street chips shown in gold.
Item {
    id: root

    property string name: "Default"
    property string first_card: ""
    property string second_card: ""
    property color stackFill: Theme.seatStackTint
    property string position: ""
    property bool isDealer: false
    property bool isActing: false
    /// Seat 0: human uses the same countdown source as the table HUD (`decisionSecondsLeft`).
    property bool isHumanSeat: false
    /// Seat 0 only: from engine — false when “Play as bot” (same timer UX as other bots: `botDecisionDelaySec`).
    property bool interactiveHuman: true
    property int decisionSecondsLeft: 0
    readonly property int decisionTimeTotal: 20
    /// Bot pause duration (seconds) from Setup — must match `game::bot_action_pause` / `botDecisionDelaySec`.
    property int botDecisionDelaySec: 2
    /// When true, hole cards may show faces (hero in hand; any seat at showdown — see `GameScreen`).
    property bool show_cards: false
    property bool inHand: true
    property bool foldedDim: false
    /// Seat 0: show "WATCHING" when sitting out to observe (not folded); false when autoplaying as bot.
    property bool humanWatching: false
    /// False when this seat is turned off in setup (bots only).
    property bool seatAtTable: true
    property int stackChips: 100
    property int streetBetChips: 0
    /// Engine label: Call / Raise / Check / Fold / SB / BB.
    property string streetActionText: ""
    /// From `Game.handSeq`: new value each hand so hole cards snap face-down and stagger resets.
    property int handEpoch: 0
    /// Training: show hole cards face-up without flip delay.
    property bool instantHoleCards: false
    /// Seat index 0–5 for chart-matched name color; `-1` uses default text color.
    property int seatIndex: -1
    /// 1.0 = design size; below 1 on small windows (GameScreen tableScale) so seats match orbit spacing.
    property real uiScale: 1.0
    readonly property real _s: uiScale > 0 ? uiScale : 1.0

    readonly property color gold: Theme.gold
    readonly property color borderAct: Theme.seatBorderAct
    readonly property color borderDealer: Theme.gold
    readonly property color borderIdle: Theme.seatBorderIdle

    /// Name strip: lift background slightly and brighten seat-colored text while this seat is acting.
    readonly property color namePlateBg: root.isActing
            ? Qt.lighter(Qt.tint(Theme.panelElevated, Qt.alpha(Theme.focusGold, 0.14)), 1.09)
            : Theme.panelElevated
    readonly property color nameTextColor: {
        var c = root.seatIndex >= 0 ? Theme.colorForSeat(root.seatIndex) : Theme.textPrimary
        return root.isActing ? Qt.lighter(c, 1.28) : c
    }

    readonly property color streetActionColor: {
        var t = root.streetActionText.toLowerCase()
        // Match All-in / ALL IN / Allin (engine uses "All-in $N"); must come before "raise".
        var letters = t.replace(/[^a-z]/g, "")
        if (t.indexOf("all-in") >= 0 || t.indexOf("all in") >= 0 || letters.indexOf("allin") >= 0)
            return Theme.streetActionAllIn
        if (t.indexOf("raise") >= 0)
            return Theme.streetActionRaise
        if (t.indexOf("call") >= 0)
            return Theme.streetActionCall
        if (t.indexOf("check") >= 0)
            return Theme.streetActionCheck
        if (t.indexOf("fold") >= 0)
            return Theme.streetActionFold
        return Theme.gold
    }

    /// Fixed footprint so seats do not jump when fold / watch / acting / street text changes.
    /// Width = pair of hole cards + horizontal inner padding (see `seatInnerPad`).
    readonly property int seatInnerPad: Math.round(6 * _s)
    /// cardRowH matches hole card height (no extra band); see `cardRowH` / `cardRow` anchors.
    implicitHeight: Math.round(300 * _s)
    implicitWidth: Math.round(Theme.holePairTotalWidth * _s)

    /// Cards / street / name / stack share one column width (see `Theme.holePairTotalWidth`).
    /// When the seat is squeezed (trainers, tight HUD), never exceed real width — avoids clipping BTN/Rye badge.
    readonly property int contentWidth: {
        var design = Math.round(Theme.holePairTotalWidth * _s)
        var inner = Math.floor(root.width * seatInnerPad)
        if (root.width <= 0 || inner >= design)
            return design
        return Math.max(96, inner)
    }
    readonly property int cardW: Math.round(Theme.holeCardWidth * _s)
    readonly property int cardH: Math.round(Theme.holeCardHeight * _s)
    readonly property int cardGap: Math.round(Theme.holeCardGap * _s)
    readonly property int cardRowH: Math.round(Theme.holeCardHeight * _s)
    readonly property int namePosSpacing: Math.round(2 * _s)
    /// Horizontal gap between name and position badges (slightly wider than `namePosSpacing` for clear separation).
    readonly property int namePosGap: Math.round(4 * _s)
    /// Street / timer band: one text line + optional thin progress (timer when thinking, action after).
    readonly property int streetRowH: Math.round(28 * _s)
    readonly property bool seatUsesHumanDecisionUi: root.isHumanSeat && root.interactiveHuman
    readonly property bool showHumanDecisionTimer: root.seatUsesHumanDecisionUi && root.isActing && root.decisionSecondsLeft > 0 && root.inHand && root.seatAtTable
    /// Bots and seat 0 autoplay — UI-thread pacing aligned with `botDecisionDelaySec` / `bot_action_pause`.
    readonly property bool showBotDecisionTimer: !root.seatUsesHumanDecisionUi && root.isActing && root.inHand
            && root.seatAtTable
    readonly property int botTimerSecondsShown: Math.max(0, Math.min(root.botDecisionDelaySec, Math.ceil(root.botTurnFrac * root.botDecisionDelaySec)))
    /// Position badge — shrink when `contentWidth` is tight so name + BTN stay inside clip bounds.
    readonly property int posBox: Math.round(46 * _s)
    /// Name strip uses the same height as the position badge (`posBox`).
    readonly property int nameRowH: root.posBox
    readonly property int stackRowH: Math.round(28 * _s)
    /// Hero: face-up whenever in the hand with a card asset (do not rely on `show_cards` alone — avoids binding glitches).
    /// Bots: only at showdown (`show_cards`).
    readonly property bool holeCard1Flipped: root.first_card.length > 0
            && (root.isHumanSeat ? (root.inHand && root.seatAtTable) : root.show_cards)
    readonly property bool holeCard2Flipped: root.second_card.length > 0
            && (root.isHumanSeat ? (root.inHand && root.seatAtTable) : root.show_cards)

    opacity: (foldedDim && seatAtTable) ? 0.52 : 1.0
    Behavior on opacity {
        NumberAnimation { duration: 280; easing.type: Easing.InOutQuad }
    }

    property int stackDisplay: root.stackChips
    onStackChipsChanged: stackDisplay = root.stackChips

    Behavior on stackDisplay {
        NumberAnimation {
            duration: 320
            easing.type: Easing.OutCubic
        }
    }

    /// Depletes over `botDecisionDelaySec` wall seconds (keeps bar + “Ns” aligned with `bot_action_pause`).
    property real botTurnFrac: 1.0
    readonly property real _botTickMs: 50
    Timer {
        id: botActTimer
        interval: root._botTickMs
        repeat: true
        running: root.isActing && !root.seatUsesHumanDecisionUi
        onTriggered: {
            var sec = Math.max(1, root.botDecisionDelaySec)
            var durMs = sec * 1000
            var step = root._botTickMs / durMs
            root.botTurnFrac = Math.max(0, root.botTurnFrac - step)
        }
    }

    onIsActingChanged: {
        if (root.isActing && !root.seatUsesHumanDecisionUi)
            root.botTurnFrac = 1.0
    }
    onBotDecisionDelaySecChanged: {
        if (root.isActing && !root.seatUsesHumanDecisionUi)
            root.botTurnFrac = 1.0
    }

    Rectangle {
        id: seatShadow
        anchors.fill: parent
        anchors.margins: Math.round(-2 * _s)
        anchors.topMargin: 0
        anchors.bottomMargin: Math.round(-4 * _s)
        radius: Math.round(8 * _s)
        color: "#40000000"
        z: -1
    }

    Rectangle {
        id: actGlow
        visible: root.isActing
        anchors.fill: parent
        anchors.margins: Math.round(-4 * _s)
        radius: Math.round(10 * _s)
        color: "transparent"
        border.width: 2
        border.color: Qt.alpha(root.borderAct, actGlow._pulse)
        property real _pulse: 0.35
        SequentialAnimation on _pulse {
            loops: Animation.Infinite
            running: root.isActing
            NumberAnimation { from: 0.35; to: 0.7; duration: 800; easing.type: Easing.InOutSine }
            NumberAnimation { from: 0.7; to: 0.35; duration: 800; easing.type: Easing.InOutSine }
        }
    }

    Rectangle {
        anchors.fill: parent
        radius: Math.round(8 * _s)
        color: Theme.seatPanel
        border.color: root.isActing ? root.borderAct : (root.isDealer ? root.borderDealer : root.borderIdle)
        border.width: root.isActing ? Math.round(2 * _s) : (root.isDealer ? Math.round(1 * _s) : 1)
        clip: true
        Behavior on border.color {
            ColorAnimation { duration: 200 }
        }

        ColumnLayout {
            anchors.fill: parent
            anchors.leftMargin: root.seatInnerPad
            anchors.rightMargin: root.seatInnerPad
            anchors.bottomMargin: root.seatInnerPad
            anchors.topMargin: 0
            spacing: Math.round(3 * _s)

            /// Same height for cards / folded / inactive so the seat does not shift between states.
            StackLayout {
                Layout.preferredHeight: root.cardRowH
                Layout.maximumHeight: root.cardRowH
                Layout.minimumHeight: root.cardRowH
                Layout.preferredWidth: root.contentWidth
                Layout.maximumWidth: root.contentWidth
                Layout.minimumWidth: root.contentWidth
                Layout.alignment: Qt.AlignHCenter
                currentIndex: !root.seatAtTable ? 2 : (root.inHand ? 0 : 1)

                Item {
                    width: root.contentWidth
                    height: root.cardRowH

                    Row {
                        anchors.horizontalCenter: parent.horizontalCenter
                        anchors.top: parent.top
                        spacing: root.cardGap

                        Card {
                            width: root.cardW
                            height: root.cardH
                            /// Match `TableBoardCard` / board row: supersample SVGs when `uiScale` &lt; 1 so holes stay as crisp as board.
                            displayScaleFactor: root._s
                            card: root.first_card
                            flipped: root.holeCard1Flipped
                            dealEpoch: root.handEpoch
                            instantFace: root.instantHoleCards
                        }

                        Card {
                            width: root.cardW
                            height: root.cardH
                            displayScaleFactor: root._s
                            card: root.second_card
                            flipped: root.holeCard2Flipped
                            dealEpoch: root.handEpoch
                            instantFace: root.instantHoleCards
                        }
                    }
                }

                Item {
                    width: root.contentWidth
                    height: root.cardRowH
                    Text {
                        anchors.fill: parent
                        anchors.margins: Math.round(2 * _s)
                        text: root.humanWatching ? qsTr("WATCHING") : qsTr("FOLDED")
                        color: root.humanWatching ? Theme.accentBlue : Theme.textMuted
                        font.family: Theme.fontFamilyUi
                        font.pointSize: Theme.uiSeatFoldPt * _s
                        font.bold: true
                        font.letterSpacing: 1
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                        wrapMode: Text.WordWrap
                        maximumLineCount: 2
                        elide: Text.ElideRight
                    }
                }

                Item {
                    width: root.contentWidth
                    height: root.cardRowH
                    Text {
                        anchors.fill: parent
                        anchors.margins: Math.round(2 * _s)
                        text: qsTr("INACTIVE")
                        color: Theme.textMuted
                        font.family: Theme.fontFamilyUi
                        font.pointSize: Math.max(8, Theme.uiSeatFoldPt * _s)
                        font.bold: true
                        font.letterSpacing: 1
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }
                }
            }

            /// Street action **or** human decision timer (same slot — timer while thinking, label after act).
            Item {
                Layout.preferredHeight: root.streetRowH
                Layout.maximumHeight: root.streetRowH
                Layout.minimumHeight: root.streetRowH
                Layout.preferredWidth: root.contentWidth
                Layout.maximumWidth: root.contentWidth
                Layout.minimumWidth: root.contentWidth
                Layout.alignment: Qt.AlignHCenter

                Rectangle {
                    anchors.fill: parent
                    visible: root.inHand && root.seatAtTable && (root.showHumanDecisionTimer || root.showBotDecisionTimer || root.streetActionText.length > 0 || root.isActing)
                    radius: Math.round(5 * _s)
                    /// Blend into seat panel — avoid a heavy HUD slab (`hudBg1`).
                    color: Qt.alpha(Theme.textPrimary, 0.035)
                    border.width: (root.showHumanDecisionTimer || root.showBotDecisionTimer) ? 0 : 1
                    border.color: root.isActing ? Qt.alpha(Theme.panelBorderMuted, 0.28) : Qt.alpha(root.streetActionColor, 0.55)

                    Column {
                        anchors.fill: parent
                        anchors.leftMargin: Math.round(4 * _s)
                        anchors.rightMargin: Math.round(4 * _s)
                        anchors.topMargin: Math.round(2 * _s)
                        anchors.bottomMargin: Math.round(2 * _s)
                        spacing: Math.round(2 * _s)

                        Text {
                            width: parent.width
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                            text: {
                                if (root.showHumanDecisionTimer)
                                    return qsTr("%1s").arg(root.decisionSecondsLeft)
                                if (root.showBotDecisionTimer)
                                    return qsTr("%1s").arg(root.botTimerSecondsShown)
                                return root.streetActionText
                            }
                            visible: root.showHumanDecisionTimer || root.showBotDecisionTimer || root.streetActionText.length > 0
                            color: (root.showHumanDecisionTimer || root.showBotDecisionTimer) ? Theme.textSecondary : root.streetActionColor
                            font.family: (root.showHumanDecisionTimer || root.showBotDecisionTimer) ? Theme.fontFamilyMono : Theme.fontFamilyUi
                            font.pointSize: Theme.uiSeatStreetPt * _s
                            font.bold: true
                            wrapMode: Text.NoWrap
                            elide: Text.ElideRight
                            maximumLineCount: 1
                        }

                        ProgressBar {
                            id: seatStreetBar
                            width: parent.width
                            height: Math.round(5 * _s)
                            visible: root.isActing
                            padding: Math.max(0, Math.round(1 * _s))
                            from: 0
                            to: 1
                            value: {
                                if (!root.isActing)
                                    return 0
                                if (root.seatUsesHumanDecisionUi)
                                    return Math.max(0, Math.min(1, root.decisionSecondsLeft / root.decisionTimeTotal))
                                return root.botTurnFrac
                            }

                            background: Rectangle {
                                implicitHeight: Math.round(4 * _s)
                                color: Qt.alpha(Theme.textPrimary, 0.08)
                                radius: Math.round(2 * _s)
                            }

                            contentItem: Item {
                                implicitHeight: Math.round(4 * _s)
                                Rectangle {
                                    width: seatStreetBar.visualPosition * parent.width
                                    height: parent.height
                                    radius: Math.round(2 * _s)
                                    color: root.borderAct
                                }
                            }
                        }
                    }
                }
            }

            RowLayout {
                Layout.alignment: Qt.AlignHCenter
                Layout.preferredHeight: root.nameRowH
                Layout.maximumHeight: root.nameRowH
                Layout.preferredWidth: root.contentWidth
                Layout.maximumWidth: root.contentWidth
                Layout.minimumWidth: root.contentWidth
                spacing: root.namePosGap

                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: root.posBox
                    Layout.maximumHeight: root.posBox
                    Layout.minimumWidth: 36
                    Layout.alignment: Qt.AlignVCenter
                    radius: Math.round(4 * _s)
                    color: root.namePlateBg
                    clip: true
                    Behavior on color {
                        ColorAnimation {
                            duration: 200
                            easing.type: Easing.OutQuad
                        }
                    }

                    Text {
                        anchors.fill: parent
                        anchors.margins: Math.round(3 * _s)
                        text: root.name
                        color: root.nameTextColor
                        font.family: Theme.fontFamilyButton
                        font.pointSize: Theme.uiSeatNamePt * _s
                        font.weight: Font.Normal
                        elide: Text.ElideRight
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                        wrapMode: Text.WrapAnywhere
                        maximumLineCount: 2
                        Behavior on color {
                            ColorAnimation {
                                duration: 200
                                easing.type: Easing.OutQuad
                            }
                        }
                    }
                }

                Rectangle {
                    Layout.preferredWidth: root.posBox
                    Layout.preferredHeight: root.posBox
                    Layout.alignment: Qt.AlignVCenter
                    radius: Math.round(4 * _s)
                    color: root.isDealer ? Qt.lighter(Theme.hudBg0, 1.14)
                                         : Qt.lighter(Theme.panelElevated, 1.12)
                    border.width: root.isDealer ? 2 : 1
                    border.color: root.isDealer ? root.gold : Qt.lighter(Theme.panelBorderMuted, 1.08)
                    clip: true

                    Text {
                        anchors.centerIn: parent
                        width: parent.width -  Math.round(2 * _s)
                        text: root.position
                        color: root.isDealer ? Theme.textPrimary : Theme.textSecondary
                        font.family: Theme.fontFamilyDisplay
                        font.pointSize: Math.max(7, Math.min(Theme.uiSeatPosPt * _s, root.posBox * 0.38))
                        font.bold: true
                        horizontalAlignment: Text.AlignHCenter
                        elide: Text.ElideRight
                    }
                }
            }

            ColumnLayout {
                Layout.alignment: Qt.AlignHCenter
                Layout.preferredWidth: root.contentWidth
                Layout.maximumWidth: root.contentWidth
                Layout.minimumWidth: root.contentWidth
                spacing: 2

                Rectangle {
                    Layout.alignment: Qt.AlignHCenter
                    Layout.fillWidth: true
                    Layout.preferredHeight: root.stackRowH
                    Layout.maximumHeight: root.stackRowH
                    radius: Math.round(4 * _s)
                    color: root.stackFill
                    border.width: 1
                    border.color: Qt.alpha(Theme.gold, 0.33)

                    Text {
                        anchors.centerIn: parent
                        text: "$" + root.stackDisplay
                        color: Theme.textPrimary
                        font.family: Theme.fontFamilyMono
                        font.pointSize: Theme.uiStackPt * _s
                        font.bold: true
                    }
                }

            }
        }
    }
}
