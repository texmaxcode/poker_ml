import QtQuick
import QtQuick.Layouts
import Theme 1.0
import PokerUi 1.0

/// Pot HUD + board below. Pot ticks up with animation; bumps when chips grow.
/// Center line is **total pot** only; `pot_slices` is kept for bindings but not shown as per-tier breakdown.
Item {
    id: table_container
    anchors.fill: parent

    property int pot_amount: 0
    /// Chip counts per physical pot (main, then side pots); from engine `nlhe_build_side_pot_slices`.
    property var pot_slices: []
    property int actingSeat: -1
    property int decisionSecondsLeft: 0
    property int facingNeedChips: 0
    property bool humanSittingOut: false
    readonly property bool humanDeciding: actingSeat === 0 && decisionSecondsLeft > 0 && !humanSittingOut
    readonly property bool showToCallHint: humanDeciding && facingNeedChips > 0

    property string board0: ""
    property string board1: ""
    property string board2: ""
    property string board3: ""
    property string board4: ""

    property int smallBlind: 1
    property int bigBlind: 3

    readonly property color gold: Theme.gold

    /// From `GameScreen.tableArea.tableScale` — matches seat/orbit scaling on small windows.
    property real centerScale: 1.0

    readonly property real _rowW: 5 * Theme.boardCardWidth + 4 * 6
    /// Shrink pot + board when narrow **or** vertically tight (wide+short windows were width-only before).
    readonly property real widthScale: Math.min(1.0, (width - 32) / table_container._rowW)
    readonly property real heightScale: Math.min(1.0, Math.max(0.32, height / 280))
    readonly property real boardRowScale: Math.min(widthScale, heightScale) * centerScale

    readonly property real _tableShort: Math.min(table_container.width, table_container.height)
    /// Pot bar + typography: same shrink as the board on tight layouts,
    /// but can grow past 1× on large table areas (bar was width-capped at 340px before).
    readonly property real potHudScale: Math.max(0.38, Math.min(1.42,
            boardRowScale * Math.min(1.4, Math.max(0.9, _tableShort / 780.0))))
    /// Slightly smaller than pre-trainer restyle so the pill matches the old compact strip footprint.
    readonly property real potBoxScale: potHudScale * 0.88

    /// Animated display value (counts toward current pot)
    property int potShown: 0
    property int _prevPotForBump: 0

    readonly property int _potAnimDuration: 320

    Component.onCompleted: {
        potShown = pot_amount
        _prevPotForBump = pot_amount
    }

    onPot_amountChanged: {
        if (pot_amount > _prevPotForBump && _prevPotForBump >= 0)
            potBumpAnim.restart()
        _prevPotForBump = pot_amount
        potShown = pot_amount
    }

    Behavior on potShown {
        NumberAnimation {
            duration: table_container._potAnimDuration
            easing.type: Easing.OutCubic
        }
    }

    Column {
        id: col
        spacing: Math.max(10, Math.round(18 * Math.max(table_container.boardRowScale, table_container.potHudScale * 0.92)))
        anchors.centerIn: parent

        /// Stakes as section label above the pill; pill holds **one line** (Pot $N) only.
        Column {
            id: potBlindsHud
            anchors.horizontalCenter: parent.horizontalCenter
            readonly property real _pw: table_container.width
            readonly property real _potPadW: Math.max(20, Math.round(26 * table_container.potBoxScale))
            readonly property real _potPadH: Math.max(9, Math.round(12 * table_container.potBoxScale))
            /// Insets for the stakes section label (top-left within the pot column).
            readonly property real _stakesMarginL: Math.max(4, Math.round(6 * table_container.potBoxScale))
            readonly property real _stakesMarginR: Math.max(4, Math.round(6 * table_container.potBoxScale))
            readonly property real _stakesMarginT: Math.max(2, Math.round(4 * table_container.potBoxScale))
            /// Fixed width so the pill does not grow/shrink when the pot amount or stakes text changes.
            readonly property real _potPillW: Math.round(Math.min(300, Math.max(200, _pw * 0.42)))
            width: Math.min(_potPillW + 8, Math.min(_pw * 0.72, _pw - 24))
            spacing: Math.max(6, Math.round(8 * table_container.potBoxScale))

            Text {
                id: stakesSectionLabel
                width: potBlindsHud.width - potBlindsHud._stakesMarginL - potBlindsHud._stakesMarginR
                x: potBlindsHud._stakesMarginL
                topPadding: potBlindsHud._stakesMarginT
                text: qsTr("$%1 / $%2 game").arg(table_container.smallBlind).arg(table_container.bigBlind)
                wrapMode: Text.NoWrap
                elide: Text.ElideRight
                color: Theme.sectionTitle
                font.family: Theme.fontFamilyDisplay
                font.capitalization: Font.AllUppercase
                font.letterSpacing: 0.5
                font.pixelSize: Math.max(6, Math.round((Theme.trainerCaptionPx - 4) * Math.max(0.72, table_container.potBoxScale)))
                horizontalAlignment: Text.AlignLeft
            }

            Rectangle {
                id: potTrainerBox
                anchors.horizontalCenter: parent.horizontalCenter
                width: potBlindsHud._potPillW
                height: potLineText.implicitHeight + potBlindsHud._potPadH
                radius: Math.max(5, Math.round(7 * Math.min(1.0, table_container.potBoxScale + 0.15)))
                color: Theme.hudBg1
                border.color: Theme.hudBorder
                border.width: Math.max(1, Math.round(1.5 * Math.min(1.0, table_container.potBoxScale + 0.12)))

                transform: Scale {
                    id: potBumpScale
                    origin.x: potTrainerBox.width * 0.5
                    origin.y: potTrainerBox.height * 0.5
                    xScale: 1
                    yScale: 1
                }

                Text {
                    id: potLineText
                    anchors.fill: parent
                    anchors.leftMargin: Math.round(potBlindsHud._potPadW * 0.5)
                    anchors.rightMargin: Math.round(potBlindsHud._potPadW * 0.5)
                    anchors.topMargin: Math.round(potBlindsHud._potPadH * 0.5)
                    anchors.bottomMargin: Math.round(potBlindsHud._potPadH * 0.5)
                    text: qsTr("Pot $%1 / $%2 to call").arg(Math.round(table_container.potShown)).arg(Math.round(table_container.facingNeedChips))
                    wrapMode: Text.NoWrap
                    maximumLineCount: 1
                    clip: true
                    color: Theme.gold
                    font.family: Theme.fontFamilyDisplay
                    font.bold: true
                    font.pixelSize: Math.max(11, Math.round(Theme.uiPotMainPt * table_container.potBoxScale))
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                    elide: Text.ElideRight
                }
            }

            SequentialAnimation {
                id: potBumpAnim
                ParallelAnimation {
                    NumberAnimation {
                        target: potBumpScale
                        property: "xScale"
                        to: 1.08
                        duration: 95
                        easing.type: Easing.OutCubic
                    }
                    NumberAnimation {
                        target: potBumpScale
                        property: "yScale"
                        to: 1.08
                        duration: 95
                        easing.type: Easing.OutCubic
                    }
                }
                ParallelAnimation {
                    NumberAnimation {
                        target: potBumpScale
                        property: "xScale"
                        to: 1.0
                        duration: 160
                        easing.type: Easing.OutCubic
                    }
                    NumberAnimation {
                        target: potBumpScale
                        property: "yScale"
                        to: 1.0
                        duration: 160
                        easing.type: Easing.OutCubic
                    }
                }
            }
        }

        /// `scale` does not shrink layout bounds — clip to scaled size so the column does not reserve 564px on narrow tables.
        Item {
            id: boardCluster
            readonly property real s: table_container.boardRowScale
            readonly property real rowW: 5 * Theme.boardCardWidth + 4 * 6
            width: Math.ceil(rowW * s + 8)
            height: Math.ceil(Theme.boardCardHeight * s + 8)
            anchors.horizontalCenter: parent.horizontalCenter

            Row {
                id: cardRow
                anchors.centerIn: parent
                spacing: 6
                scale: boardCluster.s
                transformOrigin: Item.Center

                TableBoardCard {
                    boardScale: table_container.boardRowScale
                    card: table_container.board0
                    staggerIndex: 0
                }
                TableBoardCard {
                    boardScale: table_container.boardRowScale
                    card: table_container.board1
                    staggerIndex: 1
                }
                TableBoardCard {
                    boardScale: table_container.boardRowScale
                    card: table_container.board2
                    staggerIndex: 2
                }
                TableBoardCard {
                    boardScale: table_container.boardRowScale
                    card: table_container.board3
                    staggerIndex: 3
                }
                TableBoardCard {
                    boardScale: table_container.boardRowScale
                    card: table_container.board4
                    staggerIndex: 4
                }
            }
        }
    }
}
