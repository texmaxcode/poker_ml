import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Theme 1.0
import PokerUi 1.0

Page {
    id: game_screen
    objectName: "game_screen"
    padding: 0
    font.family: Theme.fontFamilyUi

    /// `StackLayout` keeps non-current pages hidden — engine updates can be skipped or bindings stale until shown.
    /// Re-bind + full sync whenever the user opens the table (Python `setRootObject` is a no-op for same ref but runs `_sync_root`).
    onVisibleChanged: {
        if (visible && pokerGameAccess) {
            // Next frame: lets StackLayout finish sizing the page before we pump engine state into Quick.
            Qt.callLater(function () {
                if (game_screen.visible && pokerGameAccess)
                    pokerGameAccess.setRootObject(game_screen)
            })
        }
    }

    BotNames {
        id: botNames
    }

    property int pot: 0
    /// Physical pots (main + sides) from `hand_contrib_`; empty when pot is 0.
    property var potSlices: []
    property var seatStacks: [100, 100, 100, 100, 100, 100]
    property var seatC1: ["", "", "", "", "", ""]
    property var seatC2: ["", "", "", "", "", ""]
    property var seatInHand: [true, true, true, true, true, true]
    property var seatStreetChips: [0, 0, 0, 0, 0, 0]
    /// Engine: last action label this street per seat (Call / Raise / Check / Fold / …).
    property var seatStreetActions: ["", "", "", "", "", ""]
    property int maxStreetContrib: 0
    property int buttonSeat: 0
    property int sbSeat: -1
    property int bbSeat: -1
    /// Per-seat BTN/SB/BB/UTG/HJ/CO — computed in engine (`PokerGame.seatPositionLabel`), pushed each sync.
    property var seatPositionLabels: ["—", "—", "—", "—", "—", "—"]
    /// Stakes from `configure` / persisted settings (`game::sync_ui` pushes these to the page root).
    property int smallBlind: 1
    property int bigBlind: 3

    property string board0: ""
    property string board1: ""
    property string board2: ""
    property string board3: ""
    property string board4: ""
    property string statusText: qsTr("Starting…")
    property string humanHandText: ""
    property bool showdown: false
    /// Bumps each new hand (`game::clear_for_new_hand`) so seats reset hole-card flip state.
    property int handSeq: 0
    property int actingSeat: -1
    property int decisionSecondsLeft: 0
    property bool humanMoreTimeAvailable: false
    property bool humanCanCheck: false
    property bool humanBbPreflopOption: false
    property bool humanCanRaiseFacing: false
    property int facingNeedChips: 0
    property int facingMinRaiseChips: 0
    property int facingMaxChips: 0
    property int facingPotAmount: 0
    property int openRaiseMinChips: 0
    property int openRaiseMaxChips: 0
    property int bbPreflopMinChips: 0
    property int bbPreflopMaxChips: 0
    property int humanStackChips: 0
    property bool humanBbCanRaise: false
    property var pokerGameAccess: null
    /// Hero “Play as bot” — mirrored from engine (`interactiveHuman` on `PokerGame`).
    property bool interactiveHuman: true
    property bool humanSittingOut: false
    property var seatParticipating: [true, true, true, true, true, true]
    property bool humanCanBuyBackIn: false
    property int buyInChips: 100
    /// Matches `game::botDecisionDelaySec` / Setup — pushed from engine each sync.
    property int botDecisionDelaySec: 2

    signal buttonClicked(string button)

    background: BrandedBackground {
        anchors.fill: parent
    }

    /// Floating HUD beside seat 0 — bottom-aligned to the hero seat’s right edge when space allows.
    readonly property bool hudBottomDock: false

    Item {
        id: gameRoot
        z: 1
        anchors.fill: parent

        Item {
            id: tableArea
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.bottom: game_screen.hudBottomDock ? game_controls.top : parent.bottom

            readonly property point feltCenter: Qt.point(width / 2, height / 2)

            readonly property real shortSide: Math.min(width, height)
            /// Layout authored for ~1024px short side — scale down earlier so seats + orbit fit narrow windows.
            readonly property real tableScale: Math.min(1.0, shortSide / 1024.0)
            readonly property real edgeMargin: Math.max(4, Math.round(10 * tableScale))
            readonly property real seatHalfW: 109 * tableScale
            readonly property real seatHalfH: 156 * tableScale
            readonly property real seatGap: 10 * tableScale
            /// Pull corner seats slightly inward on small viewports (was fixed 1.09).
            readonly property real cornerBoost: 1.0 + 0.09 * Math.min(1.0, tableScale * 1.15)
            readonly property real maxLayoutOvalW: Math.max(240 * tableScale, width - 4 * seatHalfW - 2 * seatGap - 36 * tableScale - 2 * edgeMargin)
            readonly property real maxLayoutOvalH: Math.max(180 * tableScale, height - 4 * seatHalfH - 2 * seatGap - 48 * tableScale - 2 * edgeMargin)
            readonly property real layoutOvalW: Math.min(Math.min(width * 0.98, height * 1.32), maxLayoutOvalW)
            readonly property real layoutOvalH: Math.min(Math.min(height * 0.74, width * 0.46), maxLayoutOvalH)
            readonly property real feltBleedW: Math.max(320 * tableScale, width * 0.2)
            readonly property real feltBleedH: Math.max(260 * tableScale, height * 0.22)
            readonly property real feltOvalW: Math.min(layoutOvalW + feltBleedW, width - 8)
            readonly property real feltOvalH: Math.min(layoutOvalH + feltBleedH, height - 8)
            readonly property real orbitRxRaw: layoutOvalW * 0.5 + seatGap + seatHalfW
            readonly property real orbitRyRaw: layoutOvalH * 0.5 + seatGap + seatHalfH
            readonly property real orbitRx: Math.min(orbitRxRaw, (width * 0.5 - seatHalfW - 14 * tableScale - edgeMargin) / 0.866)
            readonly property real orbitRy: Math.min(orbitRyRaw, (height * 0.5 - seatHalfH - 14 * tableScale - edgeMargin) / 0.866)

            /// Gap between hero seat and HUD (must match `GameControls` floatHud gap).
            readonly property real hudSeatGap: 10
            /// Embedded HUD width — action row + status; kept narrower beside the hero seat so the felt stays visible.
            readonly property real hudPanelW: {
                var w = tableArea.width
                var em = tableArea.edgeMargin
                var ss = tableArea.shortSide
                var g = hudSeatGap
                var target = Math.min(320, Math.max(168, Math.round(w * 0.19 + ss * 0.048)))
                var cap = w - 2 * em
                var hs = humanSeat
                if (hs) {
                    var pr = hs.x + hs.width + g
                    cap = Math.min(cap, w - em - pr)
                    var s1 = seatRepeater.count > 1 ? seatRepeater.itemAt(1) : null
                    if (s1 && s1.x > pr + 8) {
                        var toSeat1 = s1.x - g - pr
                        if (toSeat1 >= 0)
                            cap = Math.min(cap, toSeat1)
                    }
                    var s5 = seatRepeater.count > 5 ? seatRepeater.itemAt(5) : null
                    if (s5) {
                        var toSeat5 = hs.x - 2 * g - s5.x - s5.width
                        if (toSeat5 >= 0)
                            cap = Math.min(cap, toSeat5)
                    }
                }
                return Math.max(112, Math.min(target, cap))
            }

            TableFelt {
                z: 0
                anchors.fill: parent
                feltOvalW: tableArea.feltOvalW
                feltOvalH: tableArea.feltOvalH
            }

            Table {
                id: table
                z: 3
                anchors.fill: parent
                centerScale: tableArea.tableScale
                pot_amount: game_screen.pot
                pot_slices: game_screen.potSlices
                smallBlind: game_screen.smallBlind
                bigBlind: game_screen.bigBlind
                actingSeat: game_screen.actingSeat
                decisionSecondsLeft: game_screen.decisionSecondsLeft
                facingNeedChips: game_screen.facingNeedChips
                humanSittingOut: game_screen.humanSittingOut
                board0: game_screen.board0
                board1: game_screen.board1
                board2: game_screen.board2
                board3: game_screen.board3
                board4: game_screen.board4
            }

            Repeater {
                id: seatRepeater
                z: 2
                model: 6
                delegate: Item {
                id: seatWrap
                required property int index
                width: Math.round(208 * tableArea.tableScale)
                height: Math.round(302 * tableArea.tableScale)
                /// Orbit matches engine seat order `(s + 1) % 6` clockwise around the felt (BTN/SB/BB advance clockwise).
                readonly property real angle: Math.PI / 2 + index * 2 * Math.PI / 6
                readonly property real cornerMul: (index === 1 || index === 2 || index === 4 || index === 5) ? tableArea.cornerBoost : 1.0
                readonly property real scx: tableArea.feltCenter.x + tableArea.orbitRx * Math.cos(angle) * cornerMul
                readonly property real scy: tableArea.feltCenter.y + tableArea.orbitRy * Math.sin(angle) * cornerMul
                x: Math.min(tableArea.width - width - tableArea.edgeMargin, Math.max(tableArea.edgeMargin, scx - width / 2))
                y: Math.min(tableArea.height - height - tableArea.edgeMargin, Math.max(tableArea.edgeMargin, scy - height / 2))

                Player {
                    anchors.fill: parent
                    uiScale: tableArea.tableScale
                    seatIndex: index
                    name: botNames.displayName(index)
                    position: game_screen.seatPositionLabels[index] !== undefined
                              ? game_screen.seatPositionLabels[index] : "—"
                    isDealer: index === game_screen.buttonSeat
                    seatAtTable: {
                        var p = game_screen.seatParticipating
                        if (!p || p.length <= index)
                            return true
                        return p[index] !== false
                    }
                    inHand: game_screen.seatInHand[index] !== false
                    first_card: (seatAtTable && game_screen.seatInHand[index] !== false
                                 && game_screen.seatC1[index] !== undefined)
                                ? game_screen.seatC1[index] : ""
                    second_card: (seatAtTable && game_screen.seatInHand[index] !== false
                                  && game_screen.seatC2[index] !== undefined)
                                 ? game_screen.seatC2[index] : ""
                    stackChips: game_screen.seatStacks[index] !== undefined ? game_screen.seatStacks[index] : 100
                    streetBetChips: game_screen.seatStreetChips[index] !== undefined ? game_screen.seatStreetChips[index] : 0
                    streetActionText: game_screen.seatStreetActions[index] !== undefined
                                      ? game_screen.seatStreetActions[index] : ""
                    /// Hero: faces in hand. Bots: backs until showdown, then faces (same `show_cards` + card assets).
                    show_cards: seatAtTable && (game_screen.seatInHand[index] !== false)
                                  && (index === 0 || game_screen.showdown)
                    isActing: game_screen.actingSeat === index
                    isHumanSeat: index === 0
                    interactiveHuman: index === 0 && game_screen.interactiveHuman
                    decisionSecondsLeft: game_screen.decisionSecondsLeft
                    botDecisionDelaySec: game_screen.botDecisionDelaySec
                    foldedDim: (game_screen.seatInHand[index] === false)
                    /// "WATCHING" only when sitting out to observe; not when autoplaying your strategy (Play as bot).
                    humanWatching: index === 0 && game_screen.humanSittingOut
                            && game_screen.interactiveHuman
                    handEpoch: game_screen.handSeq
                }
                }
            }

            readonly property Item humanSeat: seatRepeater.count > 0 ? seatRepeater.itemAt(0) : null
            /// True when the HUD cannot sit beside the hero seat without overlapping — center above/between seats.
            readonly property bool hudStacked: {
                if (game_screen.hudBottomDock)
                    return false
                var hs = humanSeat
                if (!hs)
                    return false
                var w = hudPanelW
                var g = tableArea.hudSeatGap
                var rightOk = hs.x + hs.width + g + w <= width - edgeMargin
                var leftOk = hs.x - g - w >= edgeMargin
                return !rightOk && !leftOk
            }
        }

        GameControls {
            id: game_controls
            parent: gameRoot
            z: 20
            embeddedMode: !game_screen.hudBottomDock
            visible: true
            panelWidth: tableArea.hudPanelW

            readonly property real floatHudX: {
                var m = tableArea.edgeMargin
                if (tableArea.hudStacked)
                    return Math.max(m, (tableArea.width - game_controls.width) * 0.5)
                var hs = tableArea.humanSeat
                if (!hs)
                    return m
                var gap = tableArea.hudSeatGap
                var w = game_controls.width
                var placeRight = hs.x + hs.width + gap
                if (placeRight + w <= tableArea.width - m)
                    return placeRight
                return Math.max(m, hs.x - w - gap)
            }
            readonly property real floatHudY: {
                var m = tableArea.edgeMargin
                var hs = tableArea.humanSeat
                if (!hs)
                    return 0
                var maxY = tableArea.height - game_controls.height - m
                if (tableArea.hudStacked) {
                    var above = hs.y - game_controls.height - 10
                    return Math.max(m, Math.min(above, maxY))
                }
                var ideal = hs.y + hs.height - game_controls.height
                return Math.min(Math.max(m, ideal), maxY)
            }

            anchors.left: game_screen.hudBottomDock ? parent.left : undefined
            anchors.right: game_screen.hudBottomDock ? parent.right : undefined
            anchors.bottom: game_screen.hudBottomDock ? parent.bottom : undefined

            x: game_screen.hudBottomDock ? 0 : floatHudX
            y: game_screen.hudBottomDock ? 0 : floatHudY

            pageRoot: game_screen
            statusText: game_screen.statusText
            humanHandText: game_screen.humanHandText
            decisionSecondsLeft: game_screen.decisionSecondsLeft
            humanMoreTimeAvailable: game_screen.humanMoreTimeAvailable
            humanCanCheck: game_screen.humanCanCheck
            humanBbPreflopOption: game_screen.humanBbPreflopOption
            humanCanRaiseFacing: game_screen.humanCanRaiseFacing
            facingNeedChips: game_screen.facingNeedChips
            facingMinRaiseChips: game_screen.facingMinRaiseChips
            facingMaxChips: game_screen.facingMaxChips
            facingPotAmount: game_screen.facingPotAmount
            openRaiseMinChips: game_screen.openRaiseMinChips
            openRaiseMaxChips: game_screen.openRaiseMaxChips
            bbPreflopMinChips: game_screen.bbPreflopMinChips
            bbPreflopMaxChips: game_screen.bbPreflopMaxChips
            humanStackChips: game_screen.humanStackChips
            humanBbCanRaise: game_screen.humanBbCanRaise
            humanSitOut: game_screen.humanSittingOut
            pokerGame: game_screen.pokerGameAccess
            humanCanBuyBackIn: game_screen.humanCanBuyBackIn
            buyInChips: game_screen.buyInChips
            hudScale: tableArea.tableScale
        }

        MouseArea {
            z: 19
            anchors.fill: gameRoot
            visible: game_controls.sizingDialogOpen
            onClicked: {
                game_controls.raiseSizingExpanded = false
                game_controls.openRaiseSizingExpanded = false
                game_controls.bbPreflopSizingExpanded = false
            }
        }
    }
}
