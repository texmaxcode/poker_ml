import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Theme 1.0
import PokerUi 1.0

/// Seat bankroll table, leaderboard (table P/L vs total Δ), and on-table stack chart.
Page {
    id: statsPage
    /// Injected from `Main.qml` (`pokerGameAccess: pokerGame`); default null for tooling previews.
    property var pokerGameAccess: null
    padding: 0
    font.family: Theme.fontFamilyUi

    BotNames {
        id: botNames
    }

    background: BrandedBackground {
        anchors.fill: parent
    }

    readonly property var lineColors: Theme.chartLineColors
    /// Inset inside chart canvas — keep in sync with table row `Layout.leftMargin` (~4) + room for y-axis labels.
    readonly property int chartPadL: 20
    readonly property int chartPadR: 10
    readonly property int chartPadT: 10
    readonly property int chartPadB: 36

    property var snapTimes: []
    property int chartHoverIndex: -1
    property real chartTipX: 0
    property real chartTipY: 0
    /// Rows from `seatRankings()` sorted by seat index 0–5 (on table / off-table bankroll / total).
    property var seatBankrollDetail: []
    /// Bound to engine `statsSeq` so leaderboard / chart refresh when bankroll snapshots update.
    property int statsSeq: pokerGameAccess ? pokerGameAccess.statsSeq : 0
    property bool statsDataError: false
    readonly property int statsTablePx: 15
    readonly property int statsTableHeaderPx: 12
    /// Shared numeric column widths for seat bankrolls + leaderboard (scales together).
    readonly property int statsMoneyColMin: 56
    readonly property int statsMoneyColPref: 68
    readonly property int statsMoneyColMax: 102
    readonly property int statsTableTopSlotH: 30
    readonly property int statsTableRowSpacing: 0
    readonly property int statsRowH: 36
    readonly property color statsRowAlt: Qt.rgba(1, 1, 1, 0.03)
    readonly property int statsHeaderBodyGap: 8
    /// Table cell inset from panel body — matches chart `chartPadL` intent (axis labels use canvas x≈4).
    readonly property int statsTableContentInset: 4
    readonly property int statsPanelPadding: Theme.trainerPanelPadding + 20
    readonly property int statsTableColSpacing: 10
    readonly property int statsPanelsSpacing: 16
    /// Two-line cap for display titles — keeps the top panels’ table headers on one horizontal line.
    readonly property int statsPanelTitleMinH: Math.round((Theme.trainerSectionPx + 2) * 2.35)
    /// Width for the top stats row + chart — `ScrollView.availableWidth` is already inside horizontal padding.
    readonly property real statsTopRowInnerW: Math.max(0, scrollView.availableWidth)
    /// Seat bankrolls ~half width; leaderboard fills the rest (two panels in the top row).
    readonly property real statsSeatPanelW: {
        var w = statsPage.statsTopRowInnerW
        var sp = statsPage.statsPanelsSpacing
        var sideFloor = 120
        var maxSeat = w - sideFloor - sp
        return Math.min(620, Math.max(80, Math.min(w * 0.48, maxSeat)))
    }
    readonly property real statsSidePanelW: Math.max(72, statsPage.statsTopRowInnerW - statsPage.statsSeatPanelW - statsPage.statsPanelsSpacing)

    function formatTimeMs(ms) {
        if (ms === undefined || ms === null || ms <= 0)
            return ""
        var d = new Date(ms)
        return Qt.formatDateTime(d, "yyyy-MM-dd hh:mm:ss")
    }

    function formatTimeShort(ms) {
        if (ms === undefined || ms === null || ms <= 0)
            return ""
        var d = new Date(ms)
        return Qt.formatDateTime(d, "hh:mm:ss")
    }

    function refreshSeatBankrollTables() {
        if (!pokerGameAccess) {
            statsPage.statsDataError = true
            rankRepeater.model = []
            seatBankrollDetail = []
            return
        }
        statsPage.statsDataError = false
        var list = pokerGameAccess.seatRankings()
        if (!list || list.length === undefined) {
            statsPage.statsDataError = true
            rankRepeater.model = []
            seatBankrollDetail = []
            return
        }
        rankRepeater.model = list
        var map = {}
        for (var i = 0; i < list.length; i++) {
            var row = list[i]
            if (!row || row.seat === undefined)
                continue
            map[row.seat] = row
        }
        var out = []
        for (var s = 0; s < 6; s++) {
            if (map[s] !== undefined)
                out.push(map[s])
        }
        seatBankrollDetail = out
    }

    function refreshChartData() {
        if (!pokerGameAccess) {
            snapTimes = []
            chartHoverIndex = -1
            return
        }
        snapTimes = pokerGameAccess.bankrollSnapshotTimesMs()
        var n = pokerGameAccess.bankrollSnapshotCount()
        if (n < 1)
            chartHoverIndex = -1
        else if (chartHoverIndex >= n)
            chartHoverIndex = n - 1
        refreshChart()
    }

    function refreshChart() {
        bankCanvas.requestPaint()
    }

    function updateChartHover(mx, my) {
        if (!pokerGameAccess) {
            chartHoverIndex = -1
            return
        }
        var nSnap = pokerGameAccess.bankrollSnapshotCount()
        if (nSnap < 1) {
            chartHoverIndex = -1
            return
        }
        var padL = statsPage.chartPadL
        var plotW = bankCanvas.width - padL - statsPage.chartPadR
        if (plotW < 1)
            plotW = 1
        var rel = (mx - padL) / plotW
        if (rel < 0)
            rel = 0
        if (rel > 1)
            rel = 1
        var idx
        if (nSnap <= 1) {
            idx = 0
        } else {
            idx = Math.round(rel * (nSnap - 1))
        }
        if (idx < 0)
            idx = 0
        if (idx > nSnap - 1)
            idx = nSnap - 1
        chartHoverIndex = idx
        chartTipX = mx
        chartTipY = my
        bankCanvas.requestPaint()
    }

    function tableStackValueAt(seat, snapIdx) {
        if (snapIdx < 0 || !pokerGameAccess)
            return "—"
        var ser = pokerGameAccess.tableStackSeries(seat)
        if (ser.length <= snapIdx)
            return "—"
        return "$" + ser[snapIdx]
    }

    function totalBankrollValueAt(seat, snapIdx) {
        if (snapIdx < 0 || !pokerGameAccess)
            return "—"
        var ser = pokerGameAccess.bankrollSeries(seat)
        if (ser.length <= snapIdx)
            return "—"
        return "$" + ser[snapIdx]
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
        ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
        leftPadding: Theme.uiPagePadding + 12
        rightPadding: Theme.uiPagePadding + 12
        topPadding: Theme.uiScrollViewTopPadding
        bottomPadding: Theme.uiPagePadding + 6

        RowLayout {
            width: scrollView.availableWidth
            spacing: 0

            ColumnLayout {
                id: statsMainCol
                Layout.fillWidth: true
                Layout.minimumWidth: 320
                spacing: Theme.trainerColumnSpacing

                Text {
                    Layout.fillWidth: true
                    visible: statsPage.statsDataError
                    wrapMode: Text.WordWrap
                    text: qsTr("Could not load bankroll stats. Try leaving this screen and opening it again.")
                    color: Theme.dangerText
                    font.pixelSize: Theme.trainerBodyPx
                    lineHeight: Theme.bodyLineHeight
                }

            /// Plain row (no nested ScrollView): a horizontal ScrollView was stealing vertical wheel from the page scroll.
            RowLayout {
                id: statsTablesRow
                Layout.fillWidth: true
                spacing: statsPage.statsPanelsSpacing

                    ThemedPanel {
                        panelTitle: qsTr("Seat bankrolls")
                        panelPadding: statsPage.statsPanelPadding
                        panelExtraPaddingRight: 32
                        panelTitlePixelSize: Theme.trainerSectionPx + 2
                        panelTitleMinHeight: statsPage.statsPanelTitleMinH
                        Layout.alignment: Qt.AlignTop
                        Layout.fillWidth: false
                        Layout.fillHeight: true
                        Layout.minimumWidth: 260
                        Layout.preferredWidth: statsPage.statsSeatPanelW

                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: statsPage.statsTableRowSpacing

                            Item {
                                Layout.fillWidth: true
                                Layout.preferredHeight: statsPage.statsTableTopSlotH
                            }

                            RowLayout {
                                Layout.fillWidth: true
                                Layout.leftMargin: statsPage.statsTableContentInset
                                Layout.rightMargin: statsPage.statsTableContentInset
                                spacing: statsPage.statsTableColSpacing
                                Label {
                                    text: qsTr("PLAYER")
                                    font.family: Theme.fontFamilyDisplay
                                    font.pixelSize: statsPage.statsTableHeaderPx
                                    font.weight: Font.DemiBold
                                    font.letterSpacing: 1.2
                                    color: Theme.textMuted
                                    Layout.fillWidth: true
                                    Layout.minimumWidth: 72
                                    elide: Text.ElideRight
                                }
                                Label {
                                    text: qsTr("TABLE")
                                    font.family: Theme.fontFamilyDisplay
                                    font.pixelSize: statsPage.statsTableHeaderPx
                                    font.weight: Font.DemiBold
                                    font.letterSpacing: 1.2
                                    color: Theme.textMuted
                                    Layout.minimumWidth: statsPage.statsMoneyColMin
                                    Layout.preferredWidth: statsPage.statsMoneyColPref
                                    Layout.maximumWidth: statsPage.statsMoneyColMax
                                    horizontalAlignment: Text.AlignRight
                                }
                                Label {
                                    text: qsTr("WALLET")
                                    font.family: Theme.fontFamilyDisplay
                                    font.pixelSize: statsPage.statsTableHeaderPx
                                    font.weight: Font.DemiBold
                                    font.letterSpacing: 1.2
                                    color: Theme.textMuted
                                    Layout.minimumWidth: statsPage.statsMoneyColMin
                                    Layout.preferredWidth: statsPage.statsMoneyColPref
                                    Layout.maximumWidth: statsPage.statsMoneyColMax
                                    horizontalAlignment: Text.AlignRight
                                }
                                Label {
                                    text: qsTr("TOTAL")
                                    font.family: Theme.fontFamilyDisplay
                                    font.pixelSize: statsPage.statsTableHeaderPx
                                    font.weight: Font.DemiBold
                                    font.letterSpacing: 1.2
                                    color: Theme.textMuted
                                    Layout.minimumWidth: statsPage.statsMoneyColMin
                                    Layout.preferredWidth: statsPage.statsMoneyColPref + 4
                                    Layout.maximumWidth: statsPage.statsMoneyColMax + 6
                                    horizontalAlignment: Text.AlignRight
                                }
                            }

                            Rectangle {
                                Layout.fillWidth: true
                                Layout.preferredHeight: 1
                                Layout.leftMargin: statsPage.statsTableContentInset
                                Layout.rightMargin: statsPage.statsTableContentInset
                                color: Theme.panelBorder
                                Layout.topMargin: 2
                                Layout.bottomMargin: statsPage.statsHeaderBodyGap
                            }

                            Text {
                                Layout.fillWidth: true
                                visible: !statsPage.statsDataError && statsPage.seatBankrollDetail.length < 1
                                wrapMode: Text.WordWrap
                                text: qsTr("No seat bankroll rows yet.")
                                color: Theme.textMuted
                                font.pixelSize: Theme.trainerBodyPx
                            }

                            Repeater {
                                model: statsPage.seatBankrollDetail

                                Rectangle {
                                    required property var modelData
                                    required property int index
                                    Layout.fillWidth: true
                                    Layout.preferredHeight: statsPage.statsRowH
                                    color: index % 2 === 1 ? statsPage.statsRowAlt : "transparent"
                                    radius: 4

                                    RowLayout {
                                        anchors.fill: parent
                                        anchors.leftMargin: statsPage.statsTableContentInset
                                        anchors.rightMargin: statsPage.statsTableContentInset
                                        spacing: statsPage.statsTableColSpacing

                                        Label {
                                            text: botNames.displayName(modelData.seat !== undefined ? modelData.seat : 0)
                                            Layout.fillWidth: true
                                            Layout.minimumWidth: 72
                                            color: Theme.colorForSeat(modelData.seat !== undefined ? modelData.seat : 0)
                                            font.family: Theme.fontFamilyButton
                                            font.pixelSize: statsPage.statsTablePx
                                            font.weight: Font.Bold
                                            elide: Text.ElideRight
                                        }
                                        Label {
                                            text: modelData.stack !== undefined ? ("$" + modelData.stack) : "—"
                                            Layout.minimumWidth: statsPage.statsMoneyColMin
                                            Layout.preferredWidth: statsPage.statsMoneyColPref
                                            Layout.maximumWidth: statsPage.statsMoneyColMax
                                            color: Theme.textSecondary
                                            font.pixelSize: statsPage.statsTablePx
                                            horizontalAlignment: Text.AlignRight
                                        }
                                        Label {
                                            text: modelData.wallet !== undefined ? ("$" + modelData.wallet) : "—"
                                            Layout.minimumWidth: statsPage.statsMoneyColMin
                                            Layout.preferredWidth: statsPage.statsMoneyColPref
                                            Layout.maximumWidth: statsPage.statsMoneyColMax
                                            color: Theme.textSecondary
                                            font.pixelSize: statsPage.statsTablePx
                                            horizontalAlignment: Text.AlignRight
                                        }
                                        Label {
                                            text: modelData.total !== undefined ? ("$" + modelData.total) : "—"
                                            Layout.minimumWidth: statsPage.statsMoneyColMin
                                            Layout.preferredWidth: statsPage.statsMoneyColPref + 4
                                            Layout.maximumWidth: statsPage.statsMoneyColMax + 6
                                            color: Theme.gold
                                            font.weight: Font.Bold
                                            font.pixelSize: statsPage.statsTablePx
                                            horizontalAlignment: Text.AlignRight
                                        }
                                    }
                                }
                            }
                        }
                    }

                    ThemedPanel {
                        panelTitle: qsTr("Leaderboard")
                        panelPadding: statsPage.statsPanelPadding
                        panelTitlePixelSize: Theme.trainerSectionPx + 2
                        panelTitleMinHeight: statsPage.statsPanelTitleMinH
                        Layout.alignment: Qt.AlignTop
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        Layout.minimumWidth: 176
                        Layout.preferredWidth: statsPage.statsSidePanelW

                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: statsPage.statsTableRowSpacing

                            Item {
                                Layout.fillWidth: true
                                Layout.preferredHeight: statsPage.statsTableTopSlotH
                            }

                            RowLayout {
                                Layout.fillWidth: true
                                Layout.leftMargin: statsPage.statsTableContentInset
                                Layout.rightMargin: statsPage.statsTableContentInset
                                spacing: statsPage.statsTableColSpacing
                                Label {
                                    text: qsTr("RANK")
                                    font.family: Theme.fontFamilyDisplay
                                    font.pixelSize: statsPage.statsTableHeaderPx
                                    font.weight: Font.DemiBold
                                    font.letterSpacing: 1.2
                                    color: Theme.textMuted
                                    Layout.preferredWidth: 44
                                    horizontalAlignment: Text.AlignLeft
                                }
                                Label {
                                    text: qsTr("PLAYER")
                                    font.family: Theme.fontFamilyDisplay
                                    font.pixelSize: statsPage.statsTableHeaderPx
                                    font.weight: Font.DemiBold
                                    font.letterSpacing: 1.2
                                    color: Theme.textMuted
                                    Layout.fillWidth: true
                                    Layout.minimumWidth: 88
                                }
                                Label {
                                    text: qsTr("TOTAL")
                                    font.family: Theme.fontFamilyDisplay
                                    font.pixelSize: statsPage.statsTableHeaderPx
                                    font.weight: Font.DemiBold
                                    font.letterSpacing: 1.2
                                    color: Theme.textMuted
                                    Layout.minimumWidth: statsPage.statsMoneyColMin
                                    Layout.preferredWidth: statsPage.statsMoneyColPref + 4
                                    Layout.maximumWidth: statsPage.statsMoneyColMax + 6
                                    horizontalAlignment: Text.AlignRight
                                }
                                Label {
                                    text: qsTr("P/L")
                                    font.family: Theme.fontFamilyDisplay
                                    font.pixelSize: statsPage.statsTableHeaderPx
                                    font.weight: Font.DemiBold
                                    font.letterSpacing: 1.2
                                    color: Theme.textMuted
                                    Layout.minimumWidth: statsPage.statsMoneyColMin
                                    Layout.preferredWidth: statsPage.statsMoneyColPref
                                    Layout.maximumWidth: statsPage.statsMoneyColMax
                                    horizontalAlignment: Text.AlignRight
                                }
                                Label {
                                    text: qsTr("Δ TOTAL")
                                    font.family: Theme.fontFamilyDisplay
                                    font.pixelSize: statsPage.statsTableHeaderPx
                                    font.weight: Font.DemiBold
                                    font.letterSpacing: 1.2
                                    color: Theme.textMuted
                                    Layout.minimumWidth: statsPage.statsMoneyColMin
                                    Layout.preferredWidth: statsPage.statsMoneyColPref
                                    Layout.maximumWidth: statsPage.statsMoneyColMax
                                    horizontalAlignment: Text.AlignRight
                                }
                            }

                            Rectangle {
                                Layout.fillWidth: true
                                Layout.preferredHeight: 1
                                Layout.leftMargin: statsPage.statsTableContentInset
                                Layout.rightMargin: statsPage.statsTableContentInset
                                color: Theme.panelBorder
                                Layout.topMargin: 2
                                Layout.bottomMargin: statsPage.statsHeaderBodyGap
                            }

                            Text {
                                Layout.fillWidth: true
                                visible: rankRepeater.count < 1 && !statsPage.statsDataError
                                wrapMode: Text.WordWrap
                                text: qsTr("No leaderboard data yet.")
                                color: Theme.textMuted
                                font.pixelSize: Theme.trainerBodyPx
                            }

                            Repeater {
                                id: rankRepeater
                                model: []

                                Rectangle {
                                    required property var modelData
                                    required property int index
                                    Layout.fillWidth: true
                                    Layout.preferredHeight: statsPage.statsRowH
                                    color: index % 2 === 1 ? statsPage.statsRowAlt : "transparent"
                                    radius: 4

                                    RowLayout {
                                        anchors.fill: parent
                                        anchors.leftMargin: statsPage.statsTableContentInset
                                        anchors.rightMargin: statsPage.statsTableContentInset
                                        spacing: statsPage.statsTableColSpacing

                                        Label {
                                            text: modelData.rank !== undefined ? ("#" + modelData.rank) : "—"
                                            Layout.preferredWidth: 44
                                            color: Theme.textMuted
                                            font.pixelSize: statsPage.statsTablePx
                                        }
                                        Label {
                                            text: botNames.displayName(modelData.seat !== undefined ? modelData.seat : 0)
                                            Layout.fillWidth: true
                                            Layout.minimumWidth: 88
                                            color: Theme.colorForSeat(modelData.seat !== undefined ? modelData.seat : 0)
                                            font.family: Theme.fontFamilyButton
                                            font.pixelSize: statsPage.statsTablePx
                                            font.weight: Font.Bold
                                            elide: Text.ElideRight
                                        }
                                        Label {
                                            text: (function () {
                                                var t = modelData.total !== undefined ? modelData.total : modelData.stack
                                                return t !== undefined ? ("$" + t) : "—"
                                            })()
                                            Layout.minimumWidth: statsPage.statsMoneyColMin
                                            Layout.preferredWidth: statsPage.statsMoneyColPref + 4
                                            Layout.maximumWidth: statsPage.statsMoneyColMax + 6
                                            color: Theme.textSecondary
                                            font.pixelSize: statsPage.statsTablePx
                                            horizontalAlignment: Text.AlignRight
                                        }
                                        Label {
                                            text: (function () {
                                                var p = modelData.profit
                                                if (p === undefined || isNaN(Number(p)))
                                                    return "—"
                                                p = Number(p)
                                                return (p >= 0 ? "+" : "") + p
                                            })()
                                            Layout.minimumWidth: statsPage.statsMoneyColMin
                                            Layout.preferredWidth: statsPage.statsMoneyColPref
                                            Layout.maximumWidth: statsPage.statsMoneyColMax
                                            color: modelData.profit === undefined || isNaN(Number(modelData.profit))
                                                    ? Theme.textMuted
                                                    : (Number(modelData.profit) >= 0 ? Theme.profitUp : Theme.profitDown)
                                            font.pixelSize: statsPage.statsTablePx
                                            font.weight: Font.DemiBold
                                            horizontalAlignment: Text.AlignRight
                                        }
                                        Label {
                                            text: (function () {
                                                var p = modelData.totalDelta
                                                if (p === undefined || isNaN(Number(p)))
                                                    return "—"
                                                p = Number(p)
                                                return (p >= 0 ? "+" : "") + p
                                            })()
                                            Layout.minimumWidth: statsPage.statsMoneyColMin
                                            Layout.preferredWidth: statsPage.statsMoneyColPref
                                            Layout.maximumWidth: statsPage.statsMoneyColMax
                                            color: modelData.totalDelta === undefined || isNaN(Number(modelData.totalDelta))
                                                    ? Theme.textMuted
                                                    : (Number(modelData.totalDelta) >= 0 ? Theme.profitUp : Theme.profitDown)
                                            font.pixelSize: statsPage.statsTablePx
                                            font.weight: Font.DemiBold
                                            horizontalAlignment: Text.AlignRight
                                        }
                                    }
                                }
                            }
                        }
                    }
                }

            ThemedPanel {
                Layout.fillWidth: true
                panelTitle: qsTr("On-table chips over time")
                panelPadding: statsPage.statsPanelPadding

                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: Theme.uiGroupInnerSpacing

                    RowLayout {
                        Layout.fillWidth: true
                        Layout.leftMargin: statsPage.statsTableContentInset
                        Layout.rightMargin: statsPage.statsTableContentInset
                        spacing: 16
                        Repeater {
                            model: 6
                            RowLayout {
                                spacing: 6
                                required property int index
                                Rectangle {
                                    width: 10
                                    height: 10
                                    radius: 5
                                    color: statsPage.lineColors[index]
                                }
                                Label {
                                    text: botNames.displayName(index)
                                    font.family: Theme.fontFamilyButton
                                    font.pixelSize: 13
                                    font.weight: Font.Bold
                                    color: Theme.colorForSeat(index)
                                }
                            }
                        }
                    }

                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 8

                        Item {
                            id: chartPanelItem
                            Layout.fillWidth: true
                            Layout.preferredHeight: 380

                            Label {
                                anchors.centerIn: parent
                                visible: pokerGameAccess ? pokerGameAccess.bankrollSnapshotCount() < 1 : true
                                text: qsTr("No data yet — play a hand to see on-table chips over time.")
                                color: Theme.textMuted
                                font.pixelSize: Theme.trainerBodyPx
                            }

                            Canvas {
                                id: bankCanvas
                                anchors.fill: parent
                                renderTarget: Canvas.FramebufferObject
                                renderStrategy: Canvas.Immediate

                                onPaint: {
                                    if (!statsPage.pokerGameAccess)
                                        return
                                    var ctx = getContext("2d")
                                    ctx.reset()
                                    var w = width
                                    var h = height
                                    ctx.fillStyle = Theme.chartPlotFill
                                    ctx.fillRect(0, 0, w, h)

                                    var nSnap = statsPage.pokerGameAccess.bankrollSnapshotCount()
                                    if (nSnap < 1)
                                        return

                                    var minY = Number.POSITIVE_INFINITY
                                    var maxY = Number.NEGATIVE_INFINITY
                                    var s
                                    for (s = 0; s < 6; s++) {
                                        var ser = statsPage.pokerGameAccess.tableStackSeries(s)
                                        for (var j = 0; j < ser.length; j++) {
                                            var v = Number(ser[j])
                                            if (v < minY)
                                                minY = v
                                            if (v > maxY)
                                                maxY = v
                                        }
                                    }
                                    if (!isFinite(minY) || !isFinite(maxY))
                                        return
                                    var span0 = maxY - minY
                                    if (span0 <= 0) {
                                        minY -= 1
                                        maxY += 1
                                    } else {
                                        var yPad = span0 * 0.08
                                        minY -= yPad
                                        maxY += yPad
                                    }
                                    var ySpan = maxY - minY
                                    if (ySpan < 1e-6) {
                                        var mid = (minY + maxY) * 0.5
                                        minY = mid - 0.5
                                        maxY = mid + 0.5
                                        ySpan = maxY - minY
                                    }

                                    var padL = statsPage.chartPadL
                                    var padR = statsPage.chartPadR
                                    var padT = statsPage.chartPadT
                                    var padB = statsPage.chartPadB
                                    if (nSnap > 4)
                                        padB = Math.max(padB, 48)
                                    var plotW = w - padL - padR
                                    var plotH = h - padT - padB

                                    function xAt(i) {
                                        if (nSnap <= 1)
                                            return padL + plotW * 0.5
                                        return padL + i * plotW / (nSnap - 1)
                                    }
                                    function yAt(stack) {
                                        return padT + plotH - (stack - minY) / ySpan * plotH
                                    }

                                    ctx.strokeStyle = Theme.chartGridLine
                                    ctx.lineWidth = 1
                                    ctx.globalAlpha = 0.45
                                    for (var g = 1; g <= 3; g++) {
                                        var gy = padT + plotH * g / 4
                                        ctx.beginPath()
                                        ctx.moveTo(padL, gy)
                                        ctx.lineTo(padL + plotW, gy)
                                        ctx.stroke()
                                    }
                                    ctx.globalAlpha = 1
                                    ctx.beginPath()
                                    ctx.moveTo(padL, padT)
                                    ctx.lineTo(padL, padT + plotH)
                                    ctx.lineTo(padL + plotW, padT + plotH)
                                    ctx.stroke()

                                    ctx.fillStyle = Theme.chartAxisText
                                    ctx.font = (Theme.uiChartCanvasPx + 3) + "px \"" + Theme.fontFamilyUi + "\""
                                    ctx.fillText(String(Math.round(minY)), 4, padT + plotH + 4)
                                    ctx.fillText(String(Math.round(maxY)), 4, padT + 10)

                                    var times = statsPage.snapTimes
                                    var nticks = Math.min(5, nSnap)
                                    ctx.textAlign = "center"
                                    ctx.font = (Theme.uiChartCanvasPx + 2) + "px \"" + Theme.fontFamilyUi + "\""
                                    var timeY = h - 8
                                    if (nSnap > 4)
                                        timeY = h - 22
                                    for (var ti = 0; ti < nticks; ti++) {
                                        var ii = nSnap <= 1 ? 0 : Math.round(ti * (nSnap - 1) / Math.max(1, nticks - 1))
                                        if (times.length <= ii)
                                            continue
                                        if (nSnap > 2 && (ii === 0 || ii === nSnap - 1))
                                            continue
                                        var tx = xAt(ii)
                                        ctx.fillText(statsPage.formatTimeShort(times[ii]), tx, timeY)
                                    }
                                    if (times.length >= 1) {
                                        ctx.textAlign = "left"
                                        ctx.font = (Theme.uiChartCanvasPx + 1) + "px \"" + Theme.fontFamilyUi + "\""
                                        ctx.fillText(statsPage.formatTimeMs(times[0]), padL, h - 6)
                                    }
                                    if (times.length >= 2) {
                                        ctx.textAlign = "right"
                                        ctx.fillText(statsPage.formatTimeMs(times[times.length - 1]), padL + plotW, h - 6)
                                        ctx.textAlign = "left"
                                    }

                                    var bubbleR = nSnap > 24 ? 3.2 : (nSnap > 12 ? 3.8 : 4.5)
                                    for (s = 0; s < 6; s++) {
                                        ser = statsPage.pokerGameAccess.tableStackSeries(s)
                                        if (ser.length < 1)
                                            continue
                                        var col = statsPage.lineColors[s]
                                        ctx.strokeStyle = col
                                        ctx.globalAlpha = 0.2
                                        ctx.lineWidth = 1
                                        ctx.beginPath()
                                        for (var i = 0; i < ser.length; i++) {
                                            var px = xAt(i)
                                            var py = yAt(ser[i])
                                            if (i === 0)
                                                ctx.moveTo(px, py)
                                            else
                                                ctx.lineTo(px, py)
                                        }
                                        ctx.stroke()
                                        ctx.globalAlpha = 1
                                        for (i = 0; i < ser.length; i++) {
                                            px = xAt(i)
                                            py = yAt(ser[i])
                                            ctx.beginPath()
                                            ctx.arc(px, py, bubbleR, 0, 2 * Math.PI)
                                            ctx.fillStyle = col
                                            ctx.globalAlpha = 0.88
                                            ctx.fill()
                                            ctx.globalAlpha = 1
                                            ctx.strokeStyle = Qt.rgba(0, 0, 0, 0.4)
                                            ctx.lineWidth = 1
                                            ctx.stroke()
                                        }
                                    }

                                    var hi = statsPage.chartHoverIndex
                                    if (hi >= 0 && hi < nSnap) {
                                        var hx = xAt(hi)
                                        ctx.strokeStyle = Qt.rgba(1, 1, 1, 0.22)
                                        ctx.lineWidth = 1
                                        ctx.setLineDash([4, 4])
                                        ctx.beginPath()
                                        ctx.moveTo(hx, padT)
                                        ctx.lineTo(hx, padT + plotH)
                                        ctx.stroke()
                                        ctx.setLineDash([])
                                        var hoverR = bubbleR + 2
                                        for (s = 0; s < 6; s++) {
                                            ser = statsPage.pokerGameAccess.tableStackSeries(s)
                                            if (ser.length <= hi)
                                                continue
                                            var cx = xAt(hi)
                                            var cy = yAt(ser[hi])
                                            var hc = statsPage.lineColors[s]
                                            ctx.beginPath()
                                            ctx.arc(cx, cy, hoverR, 0, 2 * Math.PI)
                                            ctx.fillStyle = Qt.alpha(hc, 0.38)
                                            ctx.fill()
                                            ctx.beginPath()
                                            ctx.arc(cx, cy, bubbleR, 0, 2 * Math.PI)
                                            ctx.fillStyle = hc
                                            ctx.globalAlpha = 0.95
                                            ctx.fill()
                                            ctx.globalAlpha = 1
                                            ctx.strokeStyle = Qt.rgba(1, 1, 1, 0.55)
                                            ctx.lineWidth = 1
                                            ctx.stroke()
                                        }
                                    }
                                }
                            }

                            MouseArea {
                                id: chartHitArea
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.CrossCursor
                                acceptedButtons: Qt.NoButton
                                onPositionChanged: function (mouse) {
                                    statsPage.updateChartHover(mouse.x, mouse.y)
                                }
                                onEntered: {
                                    statsPage.updateChartHover(chartHitArea.mouseX, chartHitArea.mouseY)
                                }
                            }

                            Popup {
                                id: chartHoverBubble
                                parent: chartPanelItem
                                z: 100
                                padding: 10
                                modal: false
                                focus: false
                                closePolicy: Popup.CloseOnEscape
                                visible: chartHitArea.containsMouse
                                        && statsPage.pokerGameAccess
                                        && statsPage.pokerGameAccess.bankrollSnapshotCount() >= 1
                                        && statsPage.chartHoverIndex >= 0
                                        && statsPage.snapTimes.length > statsPage.chartHoverIndex

                                x: Math.max(4, Math.min(statsPage.chartTipX + 14,
                                                        chartPanelItem.width - chartHoverBubble.width - 4))
                                y: Math.max(4, Math.min(statsPage.chartTipY + 14,
                                                        chartPanelItem.height - chartHoverBubble.height - 4))

                                background: Rectangle {
                                    radius: 10
                                    color: Theme.panelElevated
                                    border.width: 1
                                    border.color: Theme.panelBorder
                                }

                                ColumnLayout {
                                    id: chartBubbleCol
                                    spacing: 10
                                    width: Math.min(340, chartPanelItem.width - 24)

                                    Label {
                                        Layout.fillWidth: true
                                        wrapMode: Text.WordWrap
                                        font.family: Theme.fontFamilyDisplay
                                        font.pixelSize: 13
                                        font.bold: true
                                        font.capitalization: Font.AllUppercase
                                        font.letterSpacing: 0.5
                                        color: Theme.gold
                                        text: {
                                            var t = statsPage.formatTimeMs(
                                                    statsPage.snapTimes[statsPage.chartHoverIndex])
                                            return qsTr("Hand #%1 · %2").arg(statsPage.chartHoverIndex + 1).arg(t)
                                        }
                                    }

                                    GridLayout {
                                        Layout.fillWidth: true
                                        rowSpacing: 6
                                        columnSpacing: 14
                                        columns: 3

                                        Repeater {
                                            model: 6

                                            RowLayout {
                                                required property int index
                                                spacing: 6
                                                Layout.fillWidth: true

                                                Rectangle {
                                                    width: 10
                                                    height: 10
                                                    radius: 5
                                                    color: statsPage.lineColors[index]
                                                }
                                                ColumnLayout {
                                                    spacing: 0
                                                    Label {
                                                        text: botNames.displayName(index)
                                                        font.family: Theme.fontFamilyButton
                                                        font.pixelSize: Theme.trainerCaptionPx
                                                        font.weight: Font.Bold
                                                        color: Theme.colorForSeat(index)
                                                    }
                                                    Label {
                                                        font.pixelSize: Theme.trainerCaptionPx + 1
                                                        font.bold: true
                                                        color: Theme.textPrimary
                                                        text: statsPage.tableStackValueAt(index,
                                                                statsPage.chartHoverIndex)
                                                    }
                                                    Label {
                                                        font.pixelSize: Theme.trainerCaptionPx
                                                        font.bold: false
                                                        color: Theme.textSecondary
                                                        text: qsTr("Total %1").arg(
                                                            statsPage.totalBankrollValueAt(index,
                                                                    statsPage.chartHoverIndex))
                                                    }
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }

                    RowLayout {
                        spacing: Theme.uiGroupInnerSpacing
                        ResetButton {
                            text: qsTr("Reset chart & session baselines")
                            onClicked: {
                                if (!statsPage.pokerGameAccess)
                                    return
                                statsPage.pokerGameAccess.resetBankrollSession()
                                statsPage.refreshChartData()
                            }
                        }
                    }
                }
            }
            }
        }
    }

    Connections {
        target: pokerGameAccess
        function onPot_changed() {
            statsPage.refreshSeatBankrollTables()
        }
        function onSessionStatsChanged() {
            statsPage.refreshChartData()
            statsPage.refreshSeatBankrollTables()
        }
    }

    onVisibleChanged: {
        if (visible)
            statsPage.refreshSeatBankrollTables()
    }

    Component.onCompleted: {
        statsPage.refreshSeatBankrollTables()
        Qt.callLater(statsPage.refreshChartData)
    }
}
