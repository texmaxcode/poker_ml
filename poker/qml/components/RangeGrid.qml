import QtQuick
import QtQuick.Window
import QtQuick.Controls
import QtQuick.Layouts
import Theme 1.0

/// 13×13 weight matrix: row/col 0 = Ace … 12 = Two.
/// `composite`: three layers (call / raise / open) as stacked strips; click cycles the active `editLayer`.
Item {
    id: root
    property int seatIndex: 0
    property bool readOnly: false
    /// Single-layer weights (reference preset or simple mode).
    property var weights: []
    /// When true, show call / raise / open stacks from `wCall`, `wRaise`, `wBet`.
    property bool composite: false
    property var wCall: []
    property var wRaise: []
    property var wBet: []
    /// When `false`, `wCall` / `wRaise` / `wBet` (and optional `wFold`) are controlled by the parent instead of `pokerGame`.
    property bool bindToGame: true
    /// Optional fold weights (e.g. bundled JSON) for tooltips when `bindToGame` is false and `composite` is true.
    property var wFold: []
    /// 0 = call, 1 = raise, 2 = open (first raise). Used when `composite` and not read-only.
    property int editLayer: 0
    property var rankLabels: ["A", "K", "Q", "J", "T", "9", "8", "7", "6", "5", "4", "3", "2"]

    /// When set (e.g. from Setup `pokerGameAccess`), used for `getRangeGrid` / signals; avoids missing context `pokerGame` in some trees.
    property var pokerGameRef: null
    readonly property var engine: (pokerGameRef !== null && pokerGameRef !== undefined)
            ? pokerGameRef
            : (typeof pokerGame !== "undefined" ? pokerGame : null)

    onPokerGameRefChanged: {
        if (bindToGame && composite && engine !== null)
            Qt.callLater(function () { root.refreshFromGame() })
    }

    /// Gap between grid cells (matches `RowLayout` `spacing` below).
    readonly property int gridGap: 2
    /// Row/column header width — align top-left corner with row labels.
    readonly property real labelColW: Math.max(Theme.uiRangeGridCornerW, Theme.uiRangeGridRowHeaderW)
    /// Cell size grows with available width so the matrix spans the parent when `Layout.fillWidth` is set.
    /// Prefer laid-out width; during the first frames `width` can be 0 while the parent row already has width.
    readonly property real layoutWidth: {
        const w = root.width
        if (w > 1)
            return w
        const pw = parent ? parent.width : 0
        return pw > 1 ? pw : w
    }
    readonly property real cellW: {
        const w = layoutWidth
        const g = gridGap
        const lw = labelColW
        if (!w || w < lw + 13 * 20 + 13 * g)
            return Theme.uiRangeGridCellW
        return Math.max(18, Math.floor((w - lw - 13 * g) / 13))
    }
    readonly property real cellH: Math.max(20, cellW * (Theme.uiRangeGridCellH / Theme.uiRangeGridCellW))
    readonly property real cornerH: Theme.uiRangeGridCornerH * (cellW / Theme.uiRangeGridCellW)
    readonly property int axisPx: Math.max(10, Math.round(Theme.uiRangeGridAxisPx * Math.min(1.15, cellW / Theme.uiRangeGridCellW)))

    implicitWidth: labelColW + 13 * Theme.uiRangeGridCellW + 13 * gridGap
    implicitHeight: body.implicitHeight

    readonly property color layerCallColor: Theme.rangeLayerCallSubdued
    readonly property color layerRaiseColor: Theme.rangeLayerRaiseSubdued
    readonly property color layerBetColor: Theme.rangeLayerOpenSubdued

    function cellWeight(idx) {
        const w = (weights.length > idx) ? weights[idx] : 0
        return (w === undefined || w === null) ? 0 : w
    }

    function cellColor(w) {
        const v = (w === undefined || w === null) ? 0 : w
        const base = Qt.color(Theme.rangeHeatLo)
        const hi = Qt.color(Theme.rangeHeatHiSubdued)
        return Qt.rgba(
            base.r + (hi.r - base.r) * v,
            base.g + (hi.g - base.g) * v,
            base.b + (hi.b - base.b) * v,
            1)
    }

    function handNotation(row, col) {
        if (row === col)
            return rankLabels[row] + rankLabels[row]
        if (row < col)
            return rankLabels[row] + rankLabels[col] + "s"
        return rankLabels[col] + rankLabels[row] + "o"
    }

    function cellRegionColor(row, col) {
        if (row === col)
            return Theme.rangeGridPairTint
        if (row < col)
            return Theme.rangeGridSuitedTint
        return Theme.rangeGridOffsuitTint
    }

    function cellRegionName(row, col) {
        if (row === col)
            return qsTr("Pair")
        if (row < col)
            return qsTr("Suited")
        return qsTr("Offsuit")
    }

    function rankIndexToSvgRank(i) {
        const m = ["ace", "king", "queen", "jack", "10", "9", "8", "7", "6", "5", "4", "3", "2"]
        const idx = Math.max(0, Math.min(12, Math.floor(i)))
        return m[idx]
    }

    function cardFileName(rankIdx, suit) {
        return suit + "_" + rankIndexToSvgRank(rankIdx) + ".svg"
    }

    /// Two `qrc:/assets/cards/*.svg` names for the hovered cell (spades+hearts pairs; spades suited; spades+hearts offsuit).
    function cardFileNamesForCell(row, col) {
        const r = Math.max(0, Math.min(12, Math.floor(row)))
        const c = Math.max(0, Math.min(12, Math.floor(col)))
        if (r === c)
            return [cardFileName(r, "spades"), cardFileName(r, "hearts")]
        if (r < c)
            return [cardFileName(r, "spades"), cardFileName(c, "spades")]
        return [cardFileName(c, "spades"), cardFileName(r, "hearts")]
    }

    /// Hover card popup (single instance); `tipAnchor` is the hovered cell `Item`.
    property int tipRow: -1
    property int tipCol: -1
    property Item tipAnchor: null
    property real tipPopupX: 0
    property real tipPopupY: 0
    /// Bumped when parent-driven weights change (`bindToGame` false) so composite cells repaint.
    property int _parentWeightsEpoch: 0

    function cellTipPopupX(anchor, popup) {
        if (!anchor || !popup)
            return 0
        const target = popup.parent
        if (!target)
            return 0
        const p = anchor.mapToItem(target, 0, 0)
        const w = popup.width > 2 ? popup.width : Math.max(popup.implicitWidth, 200)
        const cx = p.x + anchor.width / 2 - w / 2
        return Math.min(target.width - w - 12, Math.max(12, cx))
    }

    function cellTipPopupY(anchor, popup) {
        if (!anchor || !popup)
            return 0
        const target = popup.parent
        if (!target)
            return 0
        const p = anchor.mapToItem(target, 0, 0)
        const h = popup.height > 2 ? popup.height : Math.max(popup.implicitHeight, 120)
        const margin = 10
        const edge = 12
        const aboveY = p.y - h - margin
        const maxY = target.height - h - edge
        // Prefer above the cell; top rows don't have room — place below so the bubble stays tied to the cell.
        if (aboveY >= edge)
            return Math.max(edge, Math.min(maxY, aboveY))
        const belowY = p.y + anchor.height + margin
        if (belowY <= maxY)
            return Math.max(edge, belowY)
        return Math.max(edge, Math.min(maxY, belowY))
    }

    function syncTipPopupPos() {
        if (!tipAnchor)
            return
        tipPopupX = cellTipPopupX(tipAnchor, rangeCellTip)
        tipPopupY = cellTipPopupY(tipAnchor, rangeCellTip)
    }

    function refreshFromGame() {
        if (!root.bindToGame) {
            root._parentWeightsEpoch++
            return
        }
        if (!root.composite || root.engine === null)
            return
        // Clear first so QML always sees a new assignment (avoids stale composite bindings).
        root.wCall = []
        root.wRaise = []
        root.wBet = []
        root.wCall = root.engine.getRangeGrid(root.seatIndex, 0)
        root.wRaise = root.engine.getRangeGrid(root.seatIndex, 1)
        root.wBet = root.engine.getRangeGrid(root.seatIndex, 2)
        root._parentWeightsEpoch++
    }

    function cycleWeight(row, col) {
        if (root.readOnly)
            return
        if (root.engine === null)
            return
        const idx = row * 13 + col
        let cur = 0
        if (root.composite) {
            const layer = root.editLayer
            const arr = layer === 0 ? root.wCall : (layer === 1 ? root.wRaise : root.wBet)
            cur = (arr.length > idx) ? arr[idx] : 0
        } else {
            cur = root.cellWeight(idx)
        }
        const steps = [0, 0.33, 0.66, 1.0]
        let i = 0
        for (; i < steps.length; ++i) {
            if (Math.abs(cur - steps[i]) < 0.05)
                break
        }
        const next = steps[(i + 1) % steps.length]
        if (root.composite)
            root.engine.setRangeCell(root.seatIndex, row, col, next, root.editLayer)
        else
            root.engine.setRangeCell(root.seatIndex, row, col, next, 0)
        refreshFromGame()
        if (!root.composite)
            root.weights = root.engine.getRangeGrid(root.seatIndex, 0)
    }

    onSeatIndexChanged: {
        if (bindToGame)
            Qt.callLater(refreshFromGame)
        else
            _parentWeightsEpoch++
    }
    onEditLayerChanged: {
        if (!bindToGame)
            _parentWeightsEpoch++
    }
    onWCallChanged: {
        if (!bindToGame)
            _parentWeightsEpoch++
    }
    onWRaiseChanged: {
        if (!bindToGame)
            _parentWeightsEpoch++
    }
    onWBetChanged: {
        if (!bindToGame)
            _parentWeightsEpoch++
    }
    onCompositeChanged: {
        if (composite && bindToGame)
            Qt.callLater(refreshFromGame)
    }
    onBindToGameChanged: {
        if (bindToGame)
            Qt.callLater(refreshFromGame)
        else
            _parentWeightsEpoch++
    }
    Component.onCompleted: {
        if (bindToGame)
            Qt.callLater(refreshFromGame)
    }

    Connections {
        enabled: root.bindToGame && root.engine !== null
        target: root.engine
        function onRangeRevisionChanged() {
            Qt.callLater(function () { root.refreshFromGame() })
        }
    }

    ColumnLayout {
        id: body
        anchors.left: parent.left
        anchors.right: parent.right
        spacing: 2

        RowLayout {
            spacing: gridGap
            Item {
                Layout.preferredWidth: labelColW
                Layout.preferredHeight: cornerH
            }
            Repeater {
                model: 13
                Label {
                    text: rankLabels[index]
                    horizontalAlignment: Text.AlignHCenter
                    Layout.preferredWidth: cellW
                    font.family: Theme.fontFamilyUi
                    font.bold: true
                    font.pixelSize: axisPx
                }
            }
        }

        Repeater {
            model: 13
            RowLayout {
                id: rowItem
                property int row: index
                spacing: gridGap
                Label {
                    text: rankLabels[rowItem.row]
                    Layout.preferredWidth: labelColW
                    font.family: Theme.fontFamilyUi
                    font.bold: true
                    font.pixelSize: axisPx
                }
                Repeater {
                    model: 13
                    Item {
                        id: cellItem
                        Layout.preferredWidth: cellW
                        Layout.preferredHeight: cellH
                        property int col: index
                        property int idx: rowItem.row * 13 + col

                        Rectangle {
                            anchors.fill: parent
                            visible: !root.composite
                            color: root.cellRegionColor(rowItem.row, col)
                            border.color: Qt.alpha(Theme.chromeLine, 0.35)
                            border.width: 1
                        }

                        Rectangle {
                            anchors.fill: parent
                            visible: !root.composite
                            color: root.cellColor(root.cellWeight(idx))
                            opacity: 0.9
                            border.width: 0
                        }

                        Rectangle {
                            anchors.fill: parent
                            visible: root.composite
                            color: root.cellRegionColor(rowItem.row, col)
                            border.color: Qt.alpha(Theme.chromeLine, 0.35)
                            border.width: 1

                            Column {
                                id: stackCol
                                anchors.fill: parent
                                anchors.margins: 2
                                spacing: 0
                                property real c: {
                                    root._parentWeightsEpoch
                                    const v = (root.wCall.length > idx) ? root.wCall[idx] : 0
                                    return (v === undefined || v === null) ? 0 : v
                                }
                                property real r: {
                                    root._parentWeightsEpoch
                                    const v = (root.wRaise.length > idx) ? root.wRaise[idx] : 0
                                    return (v === undefined || v === null) ? 0 : v
                                }
                                property real b: {
                                    root._parentWeightsEpoch
                                    const v = (root.wBet.length > idx) ? root.wBet[idx] : 0
                                    return (v === undefined || v === null) ? 0 : v
                                }
                                // Must use `stackCol.c` etc.: bare `c+r+b` is not in scope in all Qt/QML builds.
                                property real t: Math.max(1e-9, stackCol.c + stackCol.r + stackCol.b)

                                Rectangle {
                                    width: parent.width
                                    height: parent.height * (stackCol.c / stackCol.t)
                                    visible: height > 0.2
                                    color: root.layerCallColor
                                    border.width: (root.editLayer === 0) ? 1 : 0
                                    border.color: Qt.alpha(Theme.focusGold, 0.45)
                                }
                                Rectangle {
                                    width: parent.width
                                    height: parent.height * (stackCol.r / stackCol.t)
                                    visible: height > 0.2
                                    color: root.layerRaiseColor
                                    border.width: (root.editLayer === 1) ? 1 : 0
                                    border.color: Qt.alpha(Theme.focusGold, 0.45)
                                }
                                Rectangle {
                                    width: parent.width
                                    height: parent.height * (stackCol.b / stackCol.t)
                                    visible: height > 0.2
                                    color: root.layerBetColor
                                    border.width: (root.editLayer === 2) ? 1 : 0
                                    border.color: Qt.alpha(Theme.focusGold, 0.45)
                                }
                            }
                        }

                        Rectangle {
                            anchors.fill: parent
                            z: 1
                            visible: cellMa.containsMouse
                            color: Qt.rgba(1, 1, 1, 0.06)
                        }

                        MouseArea {
                            id: cellMa
                            z: 2
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: root.readOnly ? Qt.ArrowCursor : Qt.PointingHandCursor
                            onClicked: function (mouse) {
                                if (!root.readOnly)
                                    root.cycleWeight(rowItem.row, col)
                            }
                        }

                        Connections {
                            target: cellMa
                            function onContainsMouseChanged() {
                                if (cellMa.containsMouse) {
                                    root.tipRow = rowItem.row
                                    root.tipCol = col
                                    root.tipAnchor = cellItem
                                    tipShowTimer.restart()
                                } else if (root.tipAnchor === cellItem) {
                                    tipShowTimer.stop()
                                    rangeCellTip.close()
                                    root.tipRow = -1
                                    root.tipCol = -1
                                    root.tipAnchor = null
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    Timer {
        id: tipShowTimer
        interval: 280
        repeat: false
        onTriggered: {
            if (root.tipRow >= 0 && root.tipAnchor) {
                rangeCellTip.parent = Overlay.overlay || root
                rangeCellTip.open()
                Qt.callLater(root.syncTipPopupPos)
            }
        }
    }

    /// Keeps the overlay popup aligned while scrolling (scene position changes without `tipAnchor.x` changing).
    Timer {
        id: tipFollowTimer
        interval: 32
        repeat: true
        running: false
        onTriggered: root.syncTipPopupPos()
    }

    Popup {
        id: rangeCellTip
        parent: root
        modal: false
        focus: false
        padding: 12
        closePolicy: Popup.NoAutoClose

        x: root.tipPopupX
        y: root.tipPopupY

        onOpened: {
            Qt.callLater(root.syncTipPopupPos)
            tipFollowTimer.start()
        }
        onClosed: tipFollowTimer.stop()

        background: Rectangle {
            color: Theme.panelElevated
            border.color: Theme.panelBorder
            border.width: 1
            radius: 8
        }

        contentItem: Column {
            id: tipColumn
            spacing: 8
            width: Math.min(300, Math.max(160, root.width - 24))

            Row {
                spacing: 8
                readonly property real cardPaintDpr: (Window.window && Window.window.devicePixelRatio > 0)
                        ? Window.window.devicePixelRatio : 1.0
                Repeater {
                    model: root.tipRow >= 0 ? root.cardFileNamesForCell(root.tipRow, root.tipCol) : []
                    Image {
                        required property var modelData
                        width: 64
                        height: 92
                        fillMode: Image.Stretch
                        mipmap: true
                        sourceSize.width: Math.max(1, Math.round(64 * parent.cardPaintDpr))
                        sourceSize.height: Math.max(1, Math.round(92 * parent.cardPaintDpr))
                        asynchronous: true
                        source: "qrc:/assets/cards/" + modelData
                    }
                }
            }

            Label {
                visible: root.tipRow >= 0
                text: root.tipRow >= 0 ? root.handNotation(root.tipRow, root.tipCol) : ""
                font.family: Theme.fontFamilyUi
                font.bold: true
                font.pixelSize: Math.max(Theme.uiRangeGridAxisPx, 14)
                color: Theme.textPrimary
            }

            Label {
                visible: root.tipRow >= 0
                text: root.tipRow >= 0 ? root.cellRegionName(root.tipRow, root.tipCol) : ""
                font.pixelSize: Theme.uiRangeGridLegendPx
                color: Theme.textMuted
            }

            Label {
                visible: root.tipRow >= 0 && !root.composite
                text: {
                    if (root.tipRow < 0)
                        return ""
                    const idx = root.tipRow * 13 + root.tipCol
                    const w = root.cellWeight(idx)
                    return qsTr("Weight %1").arg(Number(w).toFixed(2))
                }
                font.family: Theme.fontFamilyUi
                font.pixelSize: Theme.uiRangeGridLegendPx
                color: Theme.textSecondary
            }

            Column {
                visible: root.tipRow >= 0 && root.composite
                spacing: 4
                width: parent.width

                RowLayout {
                    spacing: 6
                    width: parent.width
                    Rectangle {
                        width: 8
                        height: 8
                        radius: 2
                        color: root.layerCallColor
                    }
                    Label {
                        Layout.fillWidth: true
                        text: {
                            if (root.tipRow < 0)
                                return ""
                            const idx = root.tipRow * 13 + root.tipCol
                            const c = (root.wCall.length > idx) ? root.wCall[idx] : 0
                            return qsTr("Call %1").arg(Number(c).toFixed(2))
                        }
                        font.family: Theme.fontFamilyUi
                        font.pixelSize: Theme.uiRangeGridLegendPx
                        color: Theme.textSecondary
                    }
                }
                RowLayout {
                    spacing: 6
                    width: parent.width
                    Rectangle {
                        width: 8
                        height: 8
                        radius: 2
                        color: root.layerRaiseColor
                    }
                    Label {
                        Layout.fillWidth: true
                        text: {
                            if (root.tipRow < 0)
                                return ""
                            const idx = root.tipRow * 13 + root.tipCol
                            const r = (root.wRaise.length > idx) ? root.wRaise[idx] : 0
                            return qsTr("Raise %1").arg(Number(r).toFixed(2))
                        }
                        font.family: Theme.fontFamilyUi
                        font.pixelSize: Theme.uiRangeGridLegendPx
                        color: Theme.textSecondary
                    }
                }
                RowLayout {
                    spacing: 6
                    width: parent.width
                    Rectangle {
                        width: 8
                        height: 8
                        radius: 2
                        color: root.layerBetColor
                    }
                    Label {
                        Layout.fillWidth: true
                        text: {
                            if (root.tipRow < 0)
                                return ""
                            const idx = root.tipRow * 13 + root.tipCol
                            const b = (root.wBet.length > idx) ? root.wBet[idx] : 0
                            return qsTr("Open %1").arg(Number(b).toFixed(2))
                        }
                        font.family: Theme.fontFamilyUi
                        font.pixelSize: Theme.uiRangeGridLegendPx
                        color: Theme.textSecondary
                    }
                }
                Label {
                    visible: root.wFold.length === 169 && root.tipRow >= 0
                    width: parent.width
                    wrapMode: Text.WordWrap
                    text: {
                        if (root.tipRow < 0)
                            return ""
                        const idx = root.tipRow * 13 + root.tipCol
                        const f = (root.wFold.length > idx) ? root.wFold[idx] : 0
                        return qsTr("Fold %1").arg(Number(f).toFixed(2))
                    }
                    font.family: Theme.fontFamilyUi
                    font.pixelSize: Theme.uiRangeGridLegendPx
                    color: Theme.textMuted
                }
            }
        }
    }
}
