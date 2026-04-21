import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Theme 1.0
import PokerUi 1.0

/// Entry screen: logo + navigation to table, setup, solver.
Page {
    id: lobbyPage
    padding: 0
    font.family: Theme.fontFamilyUi

    property StackLayout stackLayout: null

    readonly property color gold: Theme.gold

    readonly property real lobbyShortSide: Math.min(lobbyPage.width, lobbyPage.height)
    readonly property real lobbyUiScale: Theme.compactUiScale(lobbyShortSide)
    readonly property int lobbyNavRowSpacing: Math.max(8, Math.round(Theme.uiLobbyNavRowSpacing * lobbyPage.lobbyUiScale))
    /// Banner height scales with the actual tile width (6 tiles in a single row).
    readonly property int lobbyNavTileCount: 6
    readonly property int lobbyBannerMaxH: {
        var panPad = Math.max(14, Math.round((Theme.trainerPanelPadding + 6) * lobbyPage.lobbyUiScale))
        var avail = mainCol.width > 8 ? mainCol.width - 2 * panPad : 280
        var tileW = Math.max(60, (avail - (lobbyNavTileCount - 1) * lobbyNavRowSpacing) / lobbyNavTileCount)
        return Math.max(52, Math.min(160, Math.round(tileW * 0.55)))
    }

    background: BrandedBackground {
        anchors.fill: parent
    }

    function go(idx) {
        if (stackLayout)
            stackLayout.currentIndex = idx
    }

    ScrollView {
        id: lobbyScroll
        anchors.fill: parent
        clip: true
        topPadding: Theme.uiScrollViewTopPadding

        Item {
            id: lobbyScrollContent
            width: lobbyScroll.availableWidth
            /// `ScrollView.availableHeight` is often 0 before the first layout pass; using it alone makes
            /// `height` jump when it becomes real. Prefer the page height, then scroll viewport.
            readonly property real lobbyViewportH: {
                const av = lobbyScroll.availableHeight
                const ph = lobbyPage.height
                if (ph > 1)
                    return ph
                if (av > 1)
                    return av
                return Math.max(av, ph, 400)
            }
            height: Math.max(lobbyViewportH, mainCol.implicitHeight)

            RowLayout {
                anchors.fill: parent
                spacing: 0

                Item {
                    Layout.fillWidth: true
                    Layout.minimumWidth: 0
                }

                ColumnLayout {
                    id: mainCol
                    Layout.preferredWidth: Math.min(Theme.trainerContentMaxWidth, Math.max(280, lobbyScroll.availableWidth - 40))
                    Layout.maximumWidth: Theme.trainerContentMaxWidth
                    Layout.fillHeight: true
                    spacing: Math.max(12, Math.round(16 * lobbyPage.lobbyUiScale))

                    Item {
                        Layout.fillHeight: true
                        Layout.minimumHeight: 0
                    }

                    Item {
                        Layout.fillWidth: true
                        Layout.preferredHeight: Math.min(420, Math.round(lobbyPage.lobbyShortSide * 0.42))
                        Layout.maximumHeight: Math.round(Math.min(520, lobbyPage.lobbyShortSide * 0.58))

                        Image {
                            id: lobbyLogo
                            anchors.centerIn: parent
                            width: Math.min(Math.round(lobbyPage.lobbyShortSide * 0.84), parent.width - 16)
                            height: Math.min(parent.height - 8, width * 0.72)
                            fillMode: Image.PreserveAspectFit
                            smooth: true
                            mipmap: true
                            source: "qrc:/assets/images/logo.png"
                        }
                        Text {
                            anchors.horizontalCenter: parent.horizontalCenter
                            anchors.top: lobbyLogo.bottom
                            anchors.topMargin: 8
                            width: parent.width - 24
                            horizontalAlignment: Text.AlignHCenter
                            wrapMode: Text.WordWrap
                            visible: lobbyLogo.status === Image.Error
                            text: qsTr("Logo image failed to load.")
                            color: Theme.dangerText
                            font.pixelSize: Theme.trainerCaptionPx
                        }
                    }

                    ThemedPanel {
                        Layout.fillWidth: true
                        panelTitle: qsTr("What would you like to do?")
                        panelTitlePixelSize: Math.max(16, Math.round(Theme.uiLobbyPanelTitlePx * lobbyPage.lobbyUiScale))
                        panelSectionSpacing: Math.max(10, Math.round(14 * lobbyPage.lobbyUiScale))
                        panelPadding: Math.max(14, Math.round((Theme.trainerPanelPadding + 6) * lobbyPage.lobbyUiScale))
                        panelOpacity: 0.45
                        borderOpacity: 0.45

                        RowLayout {
                            id: navTilesRow
                            Layout.fillWidth: true
                            spacing: lobbyPage.lobbyNavRowSpacing
                            LobbyNavTile {
                                bannerSource: "qrc:/assets/images/texas_holdem_icn.png"
                                sub: qsTr("Table")
                                detailTip: qsTr(
                                    "6-max Texas Hold’em table: you and five named bots. "
                                    + "Use the HUD to act; you can sit out and watch bots. Blinds and pot are centered on the felt.")
                                onClicked: lobbyPage.go(1)
                            }
                            LobbyNavTile {
                                bannerSource: "qrc:/assets/images/bots_and_ranges.png"
                                sub: qsTr("Setup")
                                detailTip: qsTr(
                                    "Set stakes ($ SB/BB, min open) and table cap (BB). Wallet and stacks are $; strategy buy-in is in BB. "
                                    + "Pick archetypes, edit 13×13 grids or paste text ranges; presets include strategy notes.")
                                onClicked: lobbyPage.go(2)
                            }
                            LobbyNavTile {
                                bannerSource: "qrc:/assets/images/solver_and_equity.png"
                                sub: qsTr("Tools")
                                detailTip: qsTr(
                                    "Monte Carlo equity vs a range or exact villain cards, with optional pot-odds and chip-EV. "
                                    + "Helpful for study — not a full multi-street GTO solver.")
                                onClicked: lobbyPage.go(3)
                            }
                            LobbyNavTile {
                                bannerSource: "qrc:/assets/images/training.png"
                                sub: qsTr("Drills")
                                detailTip: qsTr(
                                    "Preflop and postflop trainers with immediate feedback, mistake tracking, and progress stats.")
                                onClicked: lobbyPage.go(5)
                            }
                            LobbyNavTile {
                                bannerSource: "qrc:/assets/images/stats.png"
                                sub: qsTr("Ranks")
                                detailTip: qsTr(
                                    "Stack rankings and profit vs baseline ($ chip dollars), plus a line chart after each hand. "
                                    + "In Setup, wallet and on-table stacks are $; max-on-table and bot buy-in use BB (big-blind multiples).")
                                onClicked: lobbyPage.go(4)
                            }
                            LobbyNavTile {
                                bannerSource: "qrc:/assets/images/hands.png"
                                sub: qsTr("Hands")
                                detailTip: qsTr(
                                    "Replay log of previously played hands — board, seats, blinds, and every action with chip size. "
                                    + "Stored locally in the SQLite app database.")
                                onClicked: lobbyPage.go(11)
                            }
                        }
                    }

                    Item {
                        Layout.fillHeight: true
                        Layout.minimumHeight: 0
                    }
                }

                Item {
                    Layout.fillWidth: true
                    Layout.minimumWidth: 0
                }
            }
        }
    }

    component LobbyNavTile: Item {
        id: tileRoot
        property string sub: ""
        property string detailTip: ""
        property string bannerSource: ""
        signal clicked()

        readonly property real _navSubPx: Math.max(12, Math.round(Theme.uiLobbyNavSubPx * lobbyPage.lobbyUiScale))
        readonly property int _subBlockH: Math.max(32, Math.round(Theme.uiLobbyNavSubBlockH * lobbyPage.lobbyUiScale))
        readonly property real _tilePad: Math.max(8, Math.round(Theme.uiLobbyNavTilePadding * lobbyPage.lobbyUiScale))
        readonly property int _tileRadius: Math.max(10, Math.round(14 * lobbyPage.lobbyUiScale))

        Layout.fillWidth: true
        Layout.minimumWidth: Math.max(72, Math.round(82 * lobbyPage.lobbyUiScale))
        implicitHeight: tileColumn.implicitHeight + 2 * _tilePad
        Layout.preferredHeight: implicitHeight
        Layout.minimumHeight: Math.max(128, Math.round(Theme.uiLobbyNavTileMinHeight * lobbyPage.lobbyUiScale))

        Rectangle {
            id: tileFace
            width: parent.width
            height: tileColumn.implicitHeight + 2 * tileRoot._tilePad
            radius: tileRoot._tileRadius
            clip: true
            gradient: Gradient {
                GradientStop {
                    position: 0
                    color: Qt.lighter(Theme.hudBg0, 1.06)
                }
                GradientStop {
                    position: 0.5
                    color: Theme.hudBg0
                }
                GradientStop {
                    position: 1
                    color: Qt.tint(Theme.hudBg1, "#55301a22")
                }
            }
            border.width: navMa.containsMouse || navMa.pressed
                    ? Math.max(2, Math.round(2 * lobbyPage.lobbyUiScale))
                    : Math.max(1, Math.round(1 * lobbyPage.lobbyUiScale))
            border.color: navMa.containsMouse
                    ? Qt.lighter(Theme.chromeLineGold, 1.15)
                    : Qt.alpha(Theme.chromeLine, 0.85)

            ColumnLayout {
                id: tileColumn
                x: tileRoot._tilePad
                y: tileRoot._tilePad
                width: parent.width - 2 * tileRoot._tilePad
                spacing: Math.max(4, Math.round(Theme.uiLobbyNavTileStackSpacing * lobbyPage.lobbyUiScale))

                Item {
                    Layout.fillWidth: true
                    Layout.preferredHeight: lobbyPage.lobbyBannerMaxH
                    Layout.maximumHeight: lobbyPage.lobbyBannerMaxH
                    Image {
                        id: bannerImg
                        anchors.fill: parent
                        fillMode: Image.PreserveAspectFit
                        source: tileRoot.bannerSource
                        smooth: true
                        mipmap: true
                        asynchronous: true
                        opacity: navMa.containsMouse ? 1 : 0.94
                    }
                }

                Item {
                    Layout.fillWidth: true
                    Layout.minimumHeight: tileRoot._subBlockH
                    Layout.maximumHeight: tileRoot._subBlockH
                    Text {
                        anchors.fill: parent
                        text: tileRoot.sub
                        color: Theme.textSecondary
                        font.family: Theme.fontFamilyButton
                        font.pixelSize: tileRoot._navSubPx
                        font.weight: Font.Normal
                        wrapMode: Text.WordWrap
                        maximumLineCount: 2
                        elide: Text.ElideNone
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignTop
                        lineHeight: Theme.uiLobbyNavTileSubLineHeight
                    }
                }
            }

            Behavior on border.color {
                ColorAnimation {
                    duration: 120
                }
            }
            transform: Scale {
                origin.x: tileRoot.width / 2
                origin.y: tileRoot.height / 2
                xScale: navMa.containsMouse ? 1.02 : 1
                yScale: navMa.containsMouse ? 1.02 : 1
                Behavior on xScale {
                    NumberAnimation {
                        duration: 120
                        easing.type: Easing.OutCubic
                    }
                }
                Behavior on yScale {
                    NumberAnimation {
                        duration: 120
                        easing.type: Easing.OutCubic
                    }
                }
            }
        }

        MouseArea {
            id: navMa
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: tileRoot.clicked()
        }

        /// Squarer panel + larger offset than the default rounded tooltip (avoids ScrollView clip).
        ToolTip {
            id: lobbyDetailTip
            parent: Overlay.overlay
            modal: false
            focus: false
            delay: 800
            text: tileRoot.detailTip
            visible: navMa.containsMouse && tileRoot.detailTip.length > 0

            readonly property real _gap: Math.max(22, Math.round(30 * lobbyPage.lobbyUiScale))
            readonly property real _maxW: 420

            width: Math.min(_maxW, Math.max(168, tileRoot.width * 2.6))
            padding: Math.max(10, Math.round(14 * lobbyPage.lobbyUiScale))

            x: {
                const gx = tileRoot.mapToItem(Overlay.overlay, 0, 0).x
                const cx = gx + (tileRoot.width - width) * 0.5
                const ov = Overlay.overlay
                if (!ov || ov.width < 16)
                    return cx
                return Math.max(8, Math.min(cx, ov.width - width - 8))
            }
            y: tileRoot.mapToItem(Overlay.overlay, 0, 0).y - height - _gap

            background: Rectangle {
                color: Theme.panelElevated
                border.color: Qt.alpha(Theme.chromeLineGold, 0.55)
                border.width: 1
                radius: Math.max(3, Math.round(5 * lobbyPage.lobbyUiScale))
            }

            contentItem: Text {
                text: lobbyDetailTip.text
                wrapMode: Text.WordWrap
                color: Theme.textPrimary
                font.family: Theme.fontFamilyUi
                font.pixelSize: Math.max(12, Math.round(Theme.trainerCaptionPx * lobbyPage.lobbyUiScale))
                width: lobbyDetailTip.availableWidth
            }
        }
    }
}
