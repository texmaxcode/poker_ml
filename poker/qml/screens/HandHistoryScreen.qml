import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Theme 1.0
import PokerUi 1.0

/// Browse previously played hands (SQLite `hands`/`actions`). List on the left, detail panel on the right.
Page {
    id: historyPage
    padding: 0
    font.family: Theme.fontFamilyUi

    property StackLayout stackLayout: null

    /// Same body size as `StatsScreen` name cells (`statsTablePx`).
    readonly property int playerNameTablePx: 15

    background: BrandedBackground { anchors.fill: parent }

    BotNames {
        id: botNames
    }

    property var recentHands: []
    property int selectedHandId: -1
    property var selectedHandDetail: ({})
    property int refreshTick: 0

    function formatTime(ms) {
        if (!ms || ms <= 0) return ""
        var d = new Date(Number(ms))
        return Qt.formatDateTime(d, "yyyy-MM-dd hh:mm:ss")
    }

    function streetName(n) {
        switch (Number(n)) {
        case 0: return qsTr("Preflop")
        case 1: return qsTr("Flop")
        case 2: return qsTr("Turn")
        case 3: return qsTr("River")
        case 4: return qsTr("Showdown")
        }
        return qsTr("?")
    }

    function winnersLabel(arr) {
        if (!arr || arr.length === 0) return qsTr("—")
        var parts = []
        for (var i = 0; i < arr.length; ++i)
            parts.push(botNames.displayName(Number(arr[i])))
        return parts.join(", ")
    }

    function handPotWonChips(detail) {
        if (detail.totalHandWonChips !== undefined)
            return Number(detail.totalHandWonChips)
        var pd = detail.playersDetail || []
        var t = 0
        for (var i = 0; i < pd.length; ++i) {
            var w = pd[i].won
            if (w !== undefined)
                t += Number(w)
        }
        return t
    }

    function scrollDetailToTop() {
        var flick = detailScroll.contentItem
        if (flick) {
            flick.contentY = 0
            flick.contentX = 0
        }
    }

    onSelectedHandIdChanged: {
        if (selectedHandId > 0)
            Qt.callLater(function () { historyPage.scrollDetailToTop() })
    }

    function refreshList() {
        if (typeof handHistory === "undefined") return
        recentHands = handHistory.listRecent(200, 0) || []
        refreshTick++
        if (selectedHandId > 0) {
            var detail = handHistory.hand(selectedHandId)
            selectedHandDetail = (detail && detail.id) ? detail : ({})
            if (!selectedHandDetail.id) selectedHandId = -1
        }
        if (selectedHandId <= 0 && recentHands.length > 0) {
            selectHand(Number(recentHands[0].id))
        }
    }

    function selectHand(hid) {
        selectedHandId = Number(hid)
        var d = handHistory.hand(selectedHandId)
        selectedHandDetail = (d && d.id) ? d : ({})
    }

    Connections {
        target: (typeof handHistory !== "undefined") ? handHistory : null
        ignoreUnknownSignals: true
        function onHistoryChanged() { historyPage.refreshList() }
    }

    onVisibleChanged: {
        if (visible) refreshList()
    }

    Component.onCompleted: refreshList()

    RowLayout {
        anchors.fill: parent
        anchors.margins: 12
        spacing: 12

        // Left: list of hands (~half of row; same `preferredWidth` as detail for an even split)
        Rectangle {
            Layout.fillHeight: true
            Layout.fillWidth: true
            Layout.minimumWidth: 200
            Layout.preferredWidth: 1
            radius: Theme.trainerPanelRadius
            color: Qt.alpha(Theme.panel, 0.5)
            border.width: 1
            border.color: Qt.alpha(Theme.chromeLine, 0.5)

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: Theme.trainerPanelPadding
                spacing: 8

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 10

                    Label {
                        Layout.fillWidth: true
                        text: qsTr("Recent hands") + " (" + recentHands.length + ")"
                        font.family: Theme.fontFamilyDisplay
                        font.bold: true
                        font.capitalization: Font.AllUppercase
                        font.pixelSize: Theme.trainerSectionPx
                        font.letterSpacing: 0.5
                        color: Theme.sectionTitle
                    }

                    GameButton {
                        text: qsTr("Refresh")
                        pillWidth: 86
                        overrideHeight: 28
                        fontSize: Theme.uiHudButtonPt
                        buttonColor: Theme.panelElevated
                        textColor: Theme.textPrimary
                        onClicked: historyPage.refreshList()
                    }

                    GameButton {
                        text: qsTr("Clear")
                        pillWidth: 76
                        overrideHeight: 28
                        fontSize: Theme.uiHudButtonPt
                        buttonColor: Theme.dangerRed
                        textColor: Theme.onAccentText
                        onClicked: clearConfirm.open()
                    }
                }

                Label {
                    Layout.fillWidth: true
                    visible: recentHands.length === 0
                    wrapMode: Text.WordWrap
                    text: qsTr("No hands recorded yet. Play a hand on the table and it will show up here.")
                    color: Theme.textMuted
                    font.pixelSize: Theme.trainerBodyPx
                }

                // Header row
                Rectangle {
                    Layout.fillWidth: true
                    visible: recentHands.length > 0
                    height: 26
                    color: Theme.panelElevated
                    radius: 6
                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: 10
                        anchors.rightMargin: 10
                        spacing: 8
                        Label {
                            text: qsTr("#"); Layout.preferredWidth: 60
                            color: Theme.textMuted; font.pixelSize: Theme.trainerCaptionPx
                        }
                        Label {
                            text: qsTr("Time"); Layout.fillWidth: true
                            color: Theme.textMuted; font.pixelSize: Theme.trainerCaptionPx
                        }
                        Label {
                            text: qsTr("P"); Layout.preferredWidth: 20
                            horizontalAlignment: Text.AlignRight
                            color: Theme.textMuted; font.pixelSize: Theme.trainerCaptionPx
                        }
                        Label {
                            text: qsTr("Board"); Layout.preferredWidth: 120
                            color: Theme.textMuted; font.pixelSize: Theme.trainerCaptionPx
                        }
                        Label {
                            text: qsTr("Win"); Layout.preferredWidth: 100
                            color: Theme.textMuted; font.pixelSize: Theme.trainerCaptionPx
                        }
                    }
                }

                ListView {
                    id: handsList
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    clip: true
                    model: recentHands
                    spacing: 2
                    ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

                    delegate: Rectangle {
                        width: handsList.width
                        height: 30
                        color: (Number(modelData.id) === historyPage.selectedHandId)
                               ? Qt.alpha(Theme.gold, 0.18)
                               : (index % 2 === 0 ? Qt.alpha(Theme.panelElevated, 0.6) : "transparent")
                        radius: 4
                        RowLayout {
                            anchors.fill: parent
                            anchors.leftMargin: 10
                            anchors.rightMargin: 10
                            spacing: 8
                            Label {
                                text: "#" + modelData.id
                                Layout.preferredWidth: 60
                                color: Theme.textSecondary
                                font.family: Theme.fontFamilyMono
                                font.pixelSize: Theme.trainerCaptionPx
                            }
                            Label {
                                text: historyPage.formatTime(modelData.startedMs)
                                Layout.fillWidth: true
                                elide: Text.ElideRight
                                color: Theme.textPrimary
                                font.family: Theme.fontFamilyMono
                                font.pixelSize: Theme.trainerCaptionPx
                            }
                            Label {
                                text: "" + modelData.numPlayers
                                Layout.preferredWidth: 20
                                horizontalAlignment: Text.AlignRight
                                color: Theme.textPrimary
                                font.pixelSize: Theme.trainerCaptionPx
                            }
                            Label {
                                text: modelData.boardDisplay && modelData.boardDisplay.length > 0
                                      ? modelData.boardDisplay
                                      : qsTr("(no flop)")
                                Layout.preferredWidth: 120
                                elide: Text.ElideRight
                                color: Theme.textSecondary
                                font.family: Theme.fontFamilyMono
                                font.pixelSize: Theme.trainerCaptionPx
                            }
                            Label {
                                readonly property var _w: modelData.winners || []
                                text: historyPage.winnersLabel(modelData.winners)
                                Layout.preferredWidth: 100
                                elide: Text.ElideRight
                                color: _w.length === 1 ? Theme.colorForSeat(Number(_w[0])) : Theme.textPrimary
                                font.family: Theme.fontFamilyButton
                                font.pixelSize: historyPage.playerNameTablePx
                                font.weight: Font.Bold
                            }
                        }
                        MouseArea {
                            anchors.fill: parent
                            cursorShape: Qt.PointingHandCursor
                            onClicked: historyPage.selectHand(Number(modelData.id))
                        }
                    }
                }
            }
        }

        // Right: selected hand detail (~half of row)
        Rectangle {
            Layout.fillHeight: true
            Layout.fillWidth: true
            Layout.minimumWidth: 200
            Layout.preferredWidth: 1
            radius: Theme.trainerPanelRadius
            color: Qt.alpha(Theme.panel, 0.5)
            border.width: 1
            border.color: Qt.alpha(Theme.chromeLine, 0.5)

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: Theme.trainerPanelPadding
                spacing: 8

                Label {
                    Layout.fillWidth: true
                    text: historyPage.selectedHandDetail.id
                          ? (qsTr("Hand #") + historyPage.selectedHandDetail.id)
                          : qsTr("Select a hand")
                    font.family: Theme.fontFamilyDisplay
                    font.bold: true
                    font.capitalization: Font.AllUppercase
                    font.pixelSize: Theme.trainerSectionPx
                    font.letterSpacing: 0.5
                    color: Theme.sectionTitle
                }

                ScrollView {
                    id: detailScroll
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    clip: true
                    ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

                    ColumnLayout {
                        width: detailScroll.availableWidth
                        spacing: 8

                        GridLayout {
                            Layout.fillWidth: true
                            columns: 4
                            columnSpacing: 14
                            rowSpacing: 4
                            visible: !!historyPage.selectedHandDetail.id

                            Label { text: qsTr("Started"); color: Theme.textMuted; font.pixelSize: Theme.trainerCaptionPx }
                            Label {
                                text: historyPage.formatTime(historyPage.selectedHandDetail.startedMs)
                                color: Theme.textPrimary; font.family: Theme.fontFamilyMono
                                font.pixelSize: Theme.trainerCaptionPx
                            }
                            Label { text: qsTr("Ended"); color: Theme.textMuted; font.pixelSize: Theme.trainerCaptionPx }
                            Label {
                                text: historyPage.formatTime(historyPage.selectedHandDetail.endedMs)
                                color: Theme.textPrimary; font.family: Theme.fontFamilyMono
                                font.pixelSize: Theme.trainerCaptionPx
                            }

                            Label { text: qsTr("Players"); color: Theme.textMuted; font.pixelSize: Theme.trainerCaptionPx }
                            Label {
                                text: "" + (historyPage.selectedHandDetail.numPlayers || 0)
                                color: Theme.textPrimary; font.pixelSize: Theme.trainerCaptionPx
                            }
                            Label { text: qsTr("Blinds"); color: Theme.textMuted; font.pixelSize: Theme.trainerCaptionPx }
                            Label {
                                text: "$" + (historyPage.selectedHandDetail.sbSize || 0)
                                      + " / $" + (historyPage.selectedHandDetail.bbSize || 0)
                                color: Theme.textPrimary; font.family: Theme.fontFamilyMono
                                font.pixelSize: Theme.trainerCaptionPx
                            }

                            Label { text: qsTr("Button"); color: Theme.textMuted; font.pixelSize: Theme.trainerCaptionPx }
                            Label {
                                readonly property bool _hasBtn: historyPage.selectedHandDetail.buttonSeat !== undefined
                                text: _hasBtn
                                      ? botNames.displayName(Number(historyPage.selectedHandDetail.buttonSeat))
                                      : "—"
                                color: _hasBtn
                                       ? Theme.colorForSeat(Number(historyPage.selectedHandDetail.buttonSeat))
                                       : Theme.textMuted
                                font.family: _hasBtn ? Theme.fontFamilyButton : Theme.fontFamilyUi
                                font.pixelSize: _hasBtn ? historyPage.playerNameTablePx : Theme.trainerCaptionPx
                                font.weight: _hasBtn ? Font.Bold : Font.Normal
                            }
                            Label { text: qsTr("Winner"); color: Theme.textMuted; font.pixelSize: Theme.trainerCaptionPx }
                            Label {
                                readonly property var _win: historyPage.selectedHandDetail.winners || []
                                text: historyPage.winnersLabel(historyPage.selectedHandDetail.winners)
                                color: _win.length === 1 ? Theme.colorForSeat(Number(_win[0])) : Theme.textPrimary
                                font.family: Theme.fontFamilyButton
                                font.pixelSize: historyPage.playerNameTablePx
                                font.weight: Font.Bold
                            }

                            Label { text: qsTr("Winning hand"); color: Theme.textMuted; font.pixelSize: Theme.trainerCaptionPx }
                            Label {
                                Layout.columnSpan: 3
                                readonly property string _wh: historyPage.selectedHandDetail.winningHandName !== undefined
                                        ? String(historyPage.selectedHandDetail.winningHandName) : ""
                                text: _wh.length > 0 ? _wh : qsTr("—")
                                color: Theme.textPrimary
                                font.pixelSize: Theme.trainerCaptionPx
                                wrapMode: Text.WordWrap
                            }

                            Label { text: qsTr("Chips won (this hand)"); color: Theme.textMuted; font.pixelSize: Theme.trainerCaptionPx }
                            Label {
                                Layout.columnSpan: 3
                                text: qsTr("$%1").arg(historyPage.handPotWonChips(historyPage.selectedHandDetail))
                                color: Theme.gold
                                font.family: Theme.fontFamilyMono
                                font.pixelSize: Theme.trainerCaptionPx
                            }
                        }

                        Label {
                            Layout.fillWidth: true
                            visible: !!historyPage.selectedHandDetail.id
                                    && (historyPage.selectedHandDetail.playersDetail || []).length > 0
                            text: qsTr("Players (dealt in)")
                            font.family: Theme.fontFamilyDisplay
                            font.bold: true
                            font.capitalization: Font.AllUppercase
                            font.pixelSize: Theme.trainerSectionPx - 2
                            font.letterSpacing: 0.5
                            color: Theme.sectionTitle
                        }

                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 4
                            visible: !!historyPage.selectedHandDetail.id
                                    && (historyPage.selectedHandDetail.playersDetail || []).length > 0

                            Repeater {
                                model: historyPage.selectedHandDetail.playersDetail || []

                                RowLayout {
                                    required property var modelData
                                    Layout.fillWidth: true
                                    spacing: 10

                                    Label {
                                        text: botNames.displayName(modelData.seat !== undefined ? modelData.seat : 0)
                                        Layout.preferredWidth: 120
                                        elide: Text.ElideRight
                                        color: Theme.colorForSeat(modelData.seat !== undefined ? modelData.seat : 0)
                                        font.family: Theme.fontFamilyButton
                                        font.pixelSize: historyPage.playerNameTablePx
                                        font.weight: Font.Bold
                                    }
                                    Row {
                                        spacing: 4
                                        Image {
                                            readonly property string _h1: modelData.hole_svg1 !== undefined ? String(modelData.hole_svg1) : ""
                                            readonly property string _asset: _h1.length && _h1.indexOf("qrc:") !== 0
                                                  ? ("qrc:/assets/cards/" + _h1) : _h1
                                            source: _asset
                                            width: 72
                                            height: 100
                                            fillMode: Image.PreserveAspectFit
                                            smooth: true
                                            mipmap: true
                                        }
                                        Image {
                                            readonly property string _h2: modelData.hole_svg2 !== undefined ? String(modelData.hole_svg2) : ""
                                            readonly property string _asset: _h2.length && _h2.indexOf("qrc:") !== 0
                                                  ? ("qrc:/assets/cards/" + _h2) : _h2
                                            source: _asset
                                            width: 72
                                            height: 100
                                            fillMode: Image.PreserveAspectFit
                                            smooth: true
                                            mipmap: true
                                        }
                                    }
                                    ColumnLayout {
                                        Layout.fillWidth: true
                                        spacing: 2
                                        Label {
                                            text: (modelData.contrib !== undefined)
                                                  ? (qsTr("In pot $%1").arg(modelData.contrib))
                                                  : "—"
                                            Layout.fillWidth: true
                                            color: Theme.textSecondary
                                            font.pixelSize: Theme.trainerCaptionPx
                                        }
                                        Label {
                                            visible: modelData.won !== undefined && Number(modelData.won) > 0
                                            text: qsTr("Won $%1").arg(modelData.won)
                                            Layout.fillWidth: true
                                            color: Theme.gold
                                            font.pixelSize: Theme.trainerCaptionPx
                                        }
                                    }
                                }
                            }
                        }

                        // Board card thumbnails
                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 6
                            visible: !!(historyPage.selectedHandDetail.boardAssets
                                        && historyPage.selectedHandDetail.boardAssets.length > 0)

                            Repeater {
                                model: historyPage.selectedHandDetail.boardAssets || []
                                Image {
                                    // Card assets are bare `*.svg` names; resources live under `qrc:/assets/cards/`.
                                    readonly property string _asset: (modelData && String(modelData).length)
                                        ? (String(modelData).indexOf("qrc:") === 0
                                           ? String(modelData)
                                           : ("qrc:/assets/cards/" + modelData))
                                        : ""
                                    source: _asset
                                    fillMode: Image.PreserveAspectFit
                                    Layout.preferredWidth: 92
                                    Layout.preferredHeight: 128
                                    smooth: true
                                    mipmap: true
                                }
                            }
                            Item { Layout.fillWidth: true }
                        }

                        Label {
                            Layout.fillWidth: true
                            text: qsTr("Actions")
                            font.family: Theme.fontFamilyDisplay
                            font.bold: true
                            font.capitalization: Font.AllUppercase
                            font.pixelSize: Theme.trainerSectionPx
                            font.letterSpacing: 0.5
                            color: Theme.sectionTitle
                            visible: !!historyPage.selectedHandDetail.id
                        }

                        // Actions table header
                        Rectangle {
                            Layout.fillWidth: true
                            visible: !!historyPage.selectedHandDetail.id
                            height: 24
                            color: Theme.panelElevated
                            radius: 6
                            RowLayout {
                                anchors.fill: parent
                                anchors.leftMargin: 10
                                anchors.rightMargin: 10
                                spacing: 8
                                Label {
                                    text: qsTr("#"); Layout.preferredWidth: 36
                                    color: Theme.textMuted; font.pixelSize: Theme.trainerCaptionPx
                                }
                                Label {
                                    text: qsTr("Street"); Layout.preferredWidth: 80
                                    color: Theme.textMuted; font.pixelSize: Theme.trainerCaptionPx
                                }
                                Label {
                                    text: qsTr("Player"); Layout.preferredWidth: 88
                                    color: Theme.textMuted; font.pixelSize: Theme.trainerCaptionPx
                                }
                                Label {
                                    text: qsTr("Action"); Layout.fillWidth: true
                                    color: Theme.textMuted; font.pixelSize: Theme.trainerCaptionPx
                                }
                                Label {
                                    text: qsTr("Chips"); Layout.preferredWidth: 70
                                    horizontalAlignment: Text.AlignRight
                                    color: Theme.textMuted; font.pixelSize: Theme.trainerCaptionPx
                                }
                            }
                        }

                        Repeater {
                            model: historyPage.selectedHandDetail.actions || []

                            delegate: Rectangle {
                                required property int index
                                required property var modelData
                                Layout.fillWidth: true
                                height: 24
                                color: index % 2 === 0 ? Qt.alpha(Theme.panelElevated, 0.4) : "transparent"
                                RowLayout {
                                    anchors.fill: parent
                                    anchors.leftMargin: 10
                                    anchors.rightMargin: 10
                                    spacing: 8
                                    Label {
                                        text: "" + modelData.seq
                                        Layout.preferredWidth: 36
                                        color: Theme.textMuted
                                        font.family: Theme.fontFamilyMono
                                        font.pixelSize: Theme.trainerCaptionPx
                                    }
                                    Label {
                                        text: historyPage.streetName(modelData.street)
                                        Layout.preferredWidth: 80
                                        color: Theme.textSecondary
                                        font.pixelSize: Theme.trainerCaptionPx
                                    }
                                    Label {
                                        text: botNames.displayName(modelData.seat !== undefined ? modelData.seat : 0)
                                        Layout.preferredWidth: 88
                                        elide: Text.ElideRight
                                        color: Theme.colorForSeat(modelData.seat !== undefined ? modelData.seat : 0)
                                        font.family: Theme.fontFamilyButton
                                        font.pixelSize: historyPage.playerNameTablePx
                                        font.weight: Font.Bold
                                    }
                                    Label {
                                        text: modelData.isBlind
                                              ? (modelData.kindLabel + " " + qsTr("(blind)"))
                                              : modelData.kindLabel
                                        Layout.fillWidth: true
                                        color: Theme.textPrimary
                                        font.pixelSize: Theme.trainerCaptionPx
                                    }
                                    Label {
                                        text: modelData.chips > 0 ? ("$" + modelData.chips) : ""
                                        Layout.preferredWidth: 70
                                        horizontalAlignment: Text.AlignRight
                                        color: Theme.gold
                                        font.family: Theme.fontFamilyMono
                                        font.pixelSize: Theme.trainerCaptionPx
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    Dialog {
        id: clearConfirm
        title: qsTr("Clear hand history?")
        modal: true
        anchors.centerIn: parent
        // Explicit width avoids Fusion `Dialog` sizing feedback with `contentItem`.
        width: Math.min(Math.max(historyPage.width - 48, 280), 480)
        standardButtons: Dialog.Yes | Dialog.No
        onAccepted: {
            handHistory.clearAll()
            historyPage.selectedHandId = -1
            historyPage.selectedHandDetail = ({})
            historyPage.refreshList()
        }
        // Fusion `Dialog` ties `implicitHeight` to `contentItem`; a bare wrapped `Label` using
        // `availableWidth` can still cycle. Use a `Column` sized only from the dialog's explicit `width`.
        contentItem: Column {
            spacing: 0
            width: Math.max(200, clearConfirm.width - 64)
            Label {
                width: parent.width
                text: qsTr("This permanently deletes every recorded hand and action.")
                wrapMode: Text.WordWrap
                color: Theme.textPrimary
            }
        }
    }
}
