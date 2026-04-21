import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Theme 1.0
import PokerUi 1.0

Page {
    id: setup
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

    property string strategyPopupTitle: ""
    property string strategyPopupBody: ""
    /// Shown from the "?" next to Engine parameters (same popup as strategy help).
    readonly property string engineParamsHelpText: qsTr(
            "These numbers tune the bot heuristic that turns chart weights and hand strength into fold / call / raise decisions. "
            + "They are not a GTO solver; they adjust aggression and how tightly the bot sticks to its ranges.\n\n")
            + qsTr("Preflop exponent — Curves how strongly the bot follows the 13×13 chart weights. Above 1 favors high-weight cells; below 1 flattens toward mixed play.\n\n")
            + qsTr("Postflop exponent — Same idea after the flop, using the engine’s hand-strength score instead of the chart.\n\n")
            + qsTr("Facing raise bonus — Added to the base tendency to continue with a raise or re-raise after an opponent has raised.\n\n")
            + qsTr("Facing raise tight × — Multiplier on that tendency (below 1 plays tighter vs raises).\n\n")
            + qsTr("Open raise bonus — Adjusts how often the bot stabs or opens when checked to postflop.\n\n")
            + qsTr("Open raise tight × — Multiplier on that open / probe tendency.\n\n")
            + qsTr("BB check-raise bonus — Extra weight for check-raising from the big blind preflop.\n\n")
            + qsTr("BB check-raise tight × — Multiplier on BB check-raise frequency.\n\n")
            + qsTr("Buy-in (× BB) — For bots (and when you use “Play as bot”), target stack and automatic rebuys use this many big blinds (not dollars), capped by “Max on table (BB)” below.\n\n")
            + qsTr("Tap Set to apply. The engine clamps values to safe ranges.")
    /// True while `playAsBotCheck.checked` is assigned from the engine — `toggled` must not write back.
    property bool _syncingPlayAsBot: false
    /// True while `slowBotsCheck.checked` is assigned from `pokerGameAccess.botSlowActions` — avoid spurious writes.
    /// Must start **true**: `StackLayout` builds Setup before `Component.onCompleted`, and the checkbox defaults
    /// to `checked: false`; an early `checkedChanged` would otherwise call `setBotSlowActions(false)` and wipe
    /// the value restored by `loadPersistedSettings()` (main runs load **before** QML loads).
    property bool _syncingSlowBots: true
    /// Same pattern for `winningHandSecSpin` vs `pokerGameAccess.winningHandShowMs`.
    property bool _syncingWinningHandSec: true
    /// `botDecisionDelaySecSpin` vs `pokerGameAccess.botDecisionDelaySec`.
    property bool _syncingBotDecisionDelaySec: true
    /// False until first frame after sync so `onCheckedChanged` does not overwrite `interactiveHuman` on startup.
    property bool playAsBotUserInputEnabled: false
    /// Collapsed: “Range as text” only; expanded: compact row (textarea + Apply/Full), then hide after apply.
    property bool rangeTextEditorOpen: false

    function persistSave() {
        if (!pokerGameAccess)
            return
        pokerGameAccess.savePersistedSettings()
        const w = ApplicationWindow.window
        if (w && typeof w.showAppToast === "function")
            w.showAppToast(qsTr("Settings saved"))
    }

    function openStrategyLogPopup(title, body) {
        strategyPopupTitle = title
        strategyPopupBody = body
        strategyLogPopup.open()
    }

    Popup {
        id: strategyLogPopup
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
                text: setup.strategyPopupTitle
                font.family: Theme.fontFamilyDisplay
                font.bold: true
                font.capitalization: Font.AllUppercase
                font.pointSize: Theme.trainerSectionPx
                font.letterSpacing: 0.5
                color: Theme.gold
                wrapMode: Text.WordWrap
                Layout.fillWidth: true
            }

            ScrollView {
                id: strategyLogScroll
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.minimumHeight: 200
                clip: true
                ScrollBar.horizontal.policy: ScrollBar.AlwaysOff

                TextArea {
                    width: strategyLogScroll.availableWidth
                    readOnly: true
                    wrapMode: TextArea.Wrap
                    font.family: Theme.fontFamilyMono
                    font.pixelSize: Theme.uiMonoPx
                    color: Theme.textPrimary
                    text: setup.strategyPopupBody
                    padding: 10
                    selectByMouse: true
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
                onClicked: strategyLogPopup.close()
            }
        }
    }

    readonly property int selectedSeat: seatTabBar.currentIndex
    readonly property bool humanSeatAutoplay: selectedSeat === 0 && playAsBotCheck.checked
    /// Bots: always edit ranges. You: show hand ranges + engine params only while “Play as bot” is checked.
    readonly property bool showFullRangeEditor: selectedSeat > 0
            || (selectedSeat === 0 && playAsBotCheck.checked)
    /// Seat 0: engine params when configuring autoplay strategy (same visibility as the range editor).
    readonly property bool canEditHumanEngineParams: selectedSeat === 0 && playAsBotCheck.checked

    readonly property var strategyNames: pokerGameAccess ? pokerGameAccess.strategyDisplayNames() : []

    function formatParamNum(x) {
        if (x === undefined || x === null || isNaN(x))
            return ""
        return Number(x).toFixed(3)
    }

    function loadParamFields() {
        if (setup.selectedSeat < 1 && !setup.canEditHumanEngineParams)
            return
        var m = pokerGameAccess.seatStrategyParams(setup.selectedSeat)
        strat_pf_pre.text = formatParamNum(m.preflopExponent)
        strat_pf_post.text = formatParamNum(m.postflopExponent)
        strat_fr_bonus.text = formatParamNum(m.facingRaiseBonus)
        strat_fr_tight.text = formatParamNum(m.facingRaiseTightMul)
        strat_ob_bonus.text = formatParamNum(m.openBetBonus)
        strat_ob_tight.text = formatParamNum(m.openBetTightMul)
        strat_bb_bonus.text = formatParamNum(m.bbCheckraiseBonus)
        strat_bb_tight.text = formatParamNum(m.bbCheckraiseTightMul)
        strat_buy_bb.value = (m.buyInBb !== undefined && m.buyInBb !== null) ? m.buyInBb : 100
    }

    function applyParamFields() {
        if (setup.selectedSeat < 1 && !setup.canEditHumanEngineParams)
            return
        var m = {}
        function put(key, v) {
            var x = parseFloat(v)
            if (isFinite(x))
                m[key] = x
        }
        put("preflopExponent", strat_pf_pre.text)
        put("postflopExponent", strat_pf_post.text)
        put("facingRaiseBonus", strat_fr_bonus.text)
        put("facingRaiseTightMul", strat_fr_tight.text)
        put("openBetBonus", strat_ob_bonus.text)
        put("openBetTightMul", strat_ob_tight.text)
        put("bbCheckraiseBonus", strat_bb_bonus.text)
        put("bbCheckraiseTightMul", strat_bb_tight.text)
        var bi = parseInt(strat_buy_bb.value, 10)
        if (isFinite(bi))
            m["buyInBb"] = bi
        if (Object.keys(m).length < 1)
            return
        pokerGameAccess.setSeatStrategyParams(setup.selectedSeat, m)
        if (!pokerGameAccess.gameInProgress())
            pokerGameAccess.applySeatBuyInsToStacks()
        setup.persistSave()
        loadParamFields()
    }

    function refreshRangeGrids() {
        rng.refreshFromGame()
    }

    function applyRangeTextFromField() {
        if (!setup.showFullRangeEditor)
            return
        const t = textArea.text.trim()
        const ok = pokerGameAccess.applySeatRangeText(setup.selectedSeat, t, rangeLayerTab.currentIndex)
        setup.persistSave()
        /// Defer grid pull so `seatIndex` / bindings match the applied seat+layer (same as seat tab / strategy).
        Qt.callLater(function () {
            setup.refreshRangeGrids()
            /// Always re-export from the grid so invalid input reverts to the last parsed range.
            textArea.text = pokerGameAccess.exportSeatRangeText(setup.selectedSeat, rangeLayerTab.currentIndex)
        })
    }

    function reloadSeatEditor() {
        stratCombo._stratSyncFromEngine = true
        stratCombo.currentIndex = pokerGameAccess.seatStrategyIndex(setup.selectedSeat)
        stratCombo._stratSyncFromEngine = false
        Qt.callLater(function () {
            textArea.text = pokerGameAccess.exportSeatRangeText(setup.selectedSeat, rangeLayerTab.currentIndex)
            setup.refreshRangeGrids()
            setup.loadParamFields()
        })
        rangeTextEditorOpen = false
    }

    function applyFactoryReset() {
        pokerGameAccess.factoryResetToDefaultsAndClearHistory()
        if (typeof handHistory !== "undefined" && handHistory.notifyHistoryChanged)
            handHistory.notifyHistoryChanged()
        sbSpin.value = pokerGameAccess.configuredSmallBlind()
        bbSpin.value = pokerGameAccess.configuredBigBlind()
        streetSpin.value = pokerGameAccess.configuredStreetBet()
        maxTableBbSpin.value = pokerGameAccess.configuredMaxOnTableBb()
        syncPlayAsBotCheckboxFromEngine()
        totalBankSpin.refreshFromGame()
        seatBankSpin.refreshFromGame()
        reloadSeatEditor()
        const w = ApplicationWindow.window
        if (w && typeof w.showAppToast === "function")
            w.showAppToast(qsTr("All session data cleared. Defaults restored ($0 bankrolls, GTO heuristic bots)."))
    }

    function reloadAllGrids() {
        reloadSeatEditor()
    }

    /// Pending cap from the Game settings spins (max on table BB × BB); call after `maxTableBbSpin` exists.
    function buyInCapChipsValue() {
        return Math.max(1, maxTableBbSpin.value * bbSpin.value)
    }

    Component.onCompleted: {
        sbSpin.value = pokerGameAccess.configuredSmallBlind()
        bbSpin.value = pokerGameAccess.configuredBigBlind()
        streetSpin.value = pokerGameAccess.configuredStreetBet()
        maxTableBbSpin.value = pokerGameAccess.configuredMaxOnTableBb()
        setup._syncingSlowBots = true
        slowBotsCheck.checked = pokerGameAccess.botSlowActions
        setup._syncingSlowBots = false
        setup._syncingWinningHandSec = true
        winningHandSecSpin.value = Math.max(1, Math.min(60, Math.round(pokerGameAccess.winningHandShowMs / 1000)))
        setup._syncingWinningHandSec = false
        setup._syncingBotDecisionDelaySec = true
        botDecisionDelaySecSpin.value = Math.max(1, Math.min(30, pokerGameAccess.botDecisionDelaySec))
        setup._syncingBotDecisionDelaySec = false
        syncPlayAsBotCheckboxFromEngine()
        /// After sync’s deferred `_syncing` clear; avoids `toggled` applying stale engine state on startup.
        Qt.callLater(function () {
            setup.playAsBotUserInputEnabled = true
        })
        Qt.callLater(reloadSeatEditor)
    }

    onVisibleChanged: {
        if (visible) {
            /// Re-read stakes from the engine whenever Setup is shown (persisted values load before QML binds).
            sbSpin.value = pokerGameAccess.configuredSmallBlind()
            bbSpin.value = pokerGameAccess.configuredBigBlind()
            streetSpin.value = pokerGameAccess.configuredStreetBet()
            maxTableBbSpin.value = pokerGameAccess.configuredMaxOnTableBb()
            setup._syncingSlowBots = true
            slowBotsCheck.checked = pokerGameAccess.botSlowActions
            setup._syncingSlowBots = false
            setup._syncingWinningHandSec = true
            winningHandSecSpin.value = Math.max(1, Math.min(60, Math.round(pokerGameAccess.winningHandShowMs / 1000)))
            setup._syncingWinningHandSec = false
            setup._syncingBotDecisionDelaySec = true
            botDecisionDelaySecSpin.value = Math.max(1, Math.min(30, pokerGameAccess.botDecisionDelaySec))
            setup._syncingBotDecisionDelaySec = false
            totalBankSpin.refreshFromGame()
            seatBankSpin.refreshFromGame()
            syncPlayAsBotCheckboxFromEngine()
            reloadSeatEditor()
        }
    }

    function syncPlayAsBotCheckboxFromEngine() {
        setup._syncingPlayAsBot = true
        const wantChecked = !pokerGameAccess.interactiveHuman
        if (playAsBotCheck.checked !== wantChecked)
            playAsBotCheck.checked = wantChecked
        /// Defer clearing so any asynchronously delivered `toggled` from the assignment still sees `_syncing`.
        Qt.callLater(function () {
            setup._syncingPlayAsBot = false
        })
    }

    Connections {
        target: pokerGameAccess
        function onSessionStatsChanged() {
            totalBankSpin.refreshFromGame()
            seatBankSpin.refreshFromGame()
        }
    }

    Connections {
        target: pokerGameAccess
        function onWinningHandShowMsChanged() {
            setup._syncingWinningHandSec = true
            winningHandSecSpin.value = Math.max(1, Math.min(60, Math.round(pokerGameAccess.winningHandShowMs / 1000)))
            setup._syncingWinningHandSec = false
        }
    }

    Connections {
        target: pokerGameAccess
        function onBotDecisionDelaySecChanged() {
            setup._syncingBotDecisionDelaySec = true
            botDecisionDelaySecSpin.value = Math.max(1, Math.min(30, pokerGameAccess.botDecisionDelaySec))
            setup._syncingBotDecisionDelaySec = false
        }
    }

    Connections {
        target: pokerGameAccess
        function onRangeRevisionChanged() {
            if (!setup.showFullRangeEditor)
                return
            /// Grid edits emit this; keep the text field in sync (export lists any cell with weight > 0).
            textArea.text = pokerGameAccess.exportSeatRangeText(setup.selectedSeat, rangeLayerTab.currentIndex)
        }
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
        topPadding: Theme.uiScrollViewTopPadding

        RowLayout {
            width: scrollView.availableWidth
            spacing: 0

            Item {
                Layout.fillWidth: true
                Layout.minimumWidth: 0
            }

            ColumnLayout {
                id: setupColumn
                Layout.preferredWidth: Math.min(Theme.trainerContentMaxWidth, Math.max(300, scrollView.availableWidth - 40))
                Layout.maximumWidth: Theme.trainerContentMaxWidth
                spacing: Theme.trainerColumnSpacing

            ThemedPanel {
                panelTitle: qsTr("Bots and pricing")
                Layout.fillWidth: true

                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: Theme.uiGroupInnerSpacing

                    Label {
                        Layout.fillWidth: true
                        wrapMode: Text.WordWrap
                        font.pixelSize: Theme.trainerBodyPx
                        lineHeight: Theme.bodyLineHeight
                        color: Theme.textSecondary
                        text: qsTr("When a bot is off, they sit out (not dealt in) until you turn them back on.")
                    }

                    Flow {
                        Layout.fillWidth: true
                        spacing: Theme.uiGroupInnerSpacing

                        Repeater {
                            model: 5

                            ColumnLayout {
                                spacing: 4
                                required property int index

                                Label {
                                    text: botNames.displayName(index + 1)
                                    font.family: Theme.fontFamilyButton
                                    font.pixelSize: Theme.trainerCaptionPx
                                    font.weight: Font.ExtraBold
                                    color: Theme.colorForSeat(index + 1)
                                }
                                ThemedSwitch {
                                    checked: pokerGameAccess ? pokerGameAccess.seatParticipating(index + 1) : false
                                    onToggled: {
                                        if (!pokerGameAccess)
                                            return
                                        pokerGameAccess.setSeatParticipating(index + 1, checked)
                                        setup.persistSave()
                                    }
                                }
                            }
                        }
                    }

                    Label {
                        Layout.fillWidth: true
                        Layout.topMargin: 8
                        text: qsTr("Game settings")
                        font.family: Theme.fontFamilyDisplay
                        font.bold: true
                        font.capitalization: Font.AllUppercase
                        font.pixelSize: Theme.trainerCaptionPx
                        font.letterSpacing: 0.5
                        color: Theme.sectionTitle
                    }

                    ColumnLayout {
                        Layout.fillWidth: true
                        //spacing: 10

                        RowLayout {
                          RowLayout {
                            spacing: 4
                            Label {
                                text: qsTr("SB ($)")
                                font.pixelSize: Theme.trainerCaptionPx
                                font.bold: true
                            }
                            SpinBox {
                                id: sbSpin
                                from: 1
                                to: 50
                                value: 1
                                editable: true
                                Layout.preferredWidth: 94
                                Layout.maximumWidth: 110
                            }
                          }
                          RowLayout {
                            spacing: 4
                            Label {
                                text: qsTr("BB ($)")
                                font.pixelSize: Theme.trainerCaptionPx
                                font.bold: true
                            }
                            SpinBox {
                                id: bbSpin
                                from: 1
                                to: 100
                                value: 3
                                editable: true
                                Layout.preferredWidth: 94
                                Layout.maximumWidth: 110
                            }
                          }
                        }
                        RowLayout {
                          RowLayout {
                            spacing: 4
                            Label {
                                text: qsTr("Min open ($)")
                                font.pixelSize: Theme.trainerCaptionPx
                                font.bold: true
                            }
                            SpinBox {
                                id: streetSpin
                                from: 1
                                to: 200
                                value: 9
                                editable: true
                                Layout.preferredWidth: 94
                                Layout.maximumWidth: 110
                            }
                          }
                          RowLayout {
                            spacing: 4
                            Label {
                                text: qsTr("Max on table (BB)")
                                font.pixelSize: Theme.trainerCaptionPx
                                font.bold: true
                            }
                            SpinBox {
                                id: maxTableBbSpin
                                from: 1
                                to: 5000
                                value: 100
                                editable: true
                                Layout.preferredWidth: 94
                                Layout.maximumWidth: 110
                            }
                          }
                        }
                        RangeActionButton {
                            text: qsTr("SET")
                            compact: true
                            dense: true
                            fillCol: Qt.tint(Theme.panelElevated, "#42c9a227")
                            borderCol: Theme.goldMuted
                            Layout.leftMargin: 4
                            onClicked: {
                                pokerGameAccess.setMaxOnTableBb(maxTableBbSpin.value)
                                pokerGameAccess.configure(sbSpin.value, bbSpin.value, streetSpin.value,
                                        pokerGameAccess.configuredStartStack())
                                setup.persistSave()
                                reloadAllGrids()
                            }
                        }
                    }

                    Label {
                        Layout.fillWidth: true
                        font.pixelSize: Theme.trainerCaptionPx
                        color: Theme.textSecondary
                        wrapMode: Text.WordWrap
                        text: qsTr("SB $%1 · BB $%2").arg(sbSpin.value).arg(bbSpin.value)
                    }

                    Label {
                        Layout.fillWidth: true
                        Layout.topMargin: 4
                        text: qsTr("Timing")
                        font.family: Theme.fontFamilyDisplay
                        font.bold: true
                        font.capitalization: Font.AllUppercase
                        font.pixelSize: Theme.trainerCaptionPx
                        font.letterSpacing: 0.5
                        color: Theme.sectionTitle
                    }

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 10

                        Label {
                            text: qsTr("Winning hand display")
                            font.pixelSize: Theme.trainerCaptionPx
                            font.bold: true
                        }
                        SpinBox {
                            id: winningHandSecSpin
                            from: 1
                            to: 60
                            stepSize: 1
                            editable: true
                            Layout.preferredWidth: 104
                            Layout.maximumWidth: 120
                            onValueChanged: {
                                if (setup._syncingWinningHandSec)
                                    return
                                pokerGameAccess.setWinningHandShowMs(value * 1000)
                                setup.persistSave()
                            }
                        }
                        Label {
                            text: qsTr("seconds before next hand (auto-deal)")
                            font.pixelSize: Theme.trainerCaptionPx
                            color: Theme.textSecondary
                            Layout.fillWidth: true
                            wrapMode: Text.WordWrap
                        }
                    }

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 10

                        ThemedCheckBox {
                            id: slowBotsCheck
                            text: qsTr("Slow down bots!")
                            /// Use `onCheckedChanged` (fires after `checked` updates). `toggled` / stale `checked`
                            /// in `onToggled` can race and write the wrong value; early emissions before sync must
                            /// be ignored via `_syncingSlowBots` (defaults true until `Component.onCompleted`).
                            onCheckedChanged: {
                                if (setup._syncingSlowBots)
                                    return
                                pokerGameAccess.setBotSlowActions(slowBotsCheck.checked)
                                setup.persistSave()
                            }
                        }

                        SpinBox {
                            id: botDecisionDelaySecSpin
                            from: 1
                            to: 30
                            stepSize: 1
                            editable: true
                            Layout.preferredWidth: 104
                            Layout.maximumWidth: 120
                            onValueChanged: {
                                if (setup._syncingBotDecisionDelaySec)
                                    return
                                pokerGameAccess.setBotDecisionDelaySec(value)
                                setup.persistSave()
                            }
                        }

                        Label {
                            text: qsTr("seconds between bot actions")
                            font.pixelSize: Theme.trainerCaptionPx
                            color: Theme.textSecondary
                            Layout.fillWidth: true
                            wrapMode: Text.WordWrap
                        }
                    }
                }
            }

            TabBar {
                id: seatTabBar
                Layout.fillWidth: true
                font.family: Theme.fontFamilyButton
                font.pixelSize: Theme.trainerCaptionPx

                TabButton {
                    text: qsTr("You")
                    font.weight: Font.ExtraBold
                    topPadding: 10
                    bottomPadding: 10
                    leftPadding: 14
                    rightPadding: 14
                    contentItem: Label {
                        text: parent.text
                        font.family: parent.font.family
                        font.pixelSize: parent.font.pixelSize
                        font.weight: parent.font.weight
                        font.bold: parent.font.bold
                        font.italic: parent.font.italic
                        font.capitalization: Font.AllUppercase
                        color: Theme.colorForSeat(0)
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                        elide: Text.ElideRight
                    }
                }
                Repeater {
                    model: 5
                    TabButton {
                        required property int index
                        text: botNames.displayName(index + 1)
                        font.weight: Font.ExtraBold
                        topPadding: 10
                        bottomPadding: 10
                        leftPadding: 14
                        rightPadding: 14
                        contentItem: Label {
                            text: parent.text
                            font.family: parent.font.family
                            font.pixelSize: parent.font.pixelSize
                            font.weight: parent.font.weight
                            font.bold: parent.font.bold
                            font.italic: parent.font.italic
                            font.capitalization: Font.AllUppercase
                            color: Theme.colorForSeat(index + 1)
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                            elide: Text.ElideRight
                        }
                    }
                }
            }

            ThemedPanel {
                Layout.fillWidth: true
                panelTitle: ""

                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 6

                    Label {
                        Layout.fillWidth: true
                        text: botNames.displayName(setup.selectedSeat)
                        font.family: Theme.fontFamilyButton
                        font.weight: Font.ExtraBold
                        font.capitalization: Font.AllUppercase
                        font.pixelSize: Theme.trainerSectionPx
                        color: Theme.colorForSeat(setup.selectedSeat)
                    }

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 6
                        Label {
                            text: qsTr("Wallet ($)")
                            font.bold: true
                            font.pixelSize: Theme.trainerCaptionPx
                        }
                        SpinBox {
                            id: totalBankSpin
                            from: 0
                            to: 2000000000
                            stepSize: 1
                            editable: true
                            Layout.fillWidth: false
                            Layout.preferredWidth: 160
                            Layout.maximumWidth: 200

                            property bool _applyingFromGame: false
                            property bool _ready: false

                            function refreshFromGame() {
                                _applyingFromGame = true
                                value = Math.max(0, pokerGameAccess.seatBankrollTotal(setup.selectedSeat))
                                _applyingFromGame = false
                            }

                            function pushTotalToEngine() {
                                pokerGameAccess.setSeatBankrollTotal(setup.selectedSeat, value)
                            }

                            Component.onCompleted: {
                                refreshFromGame()
                                _ready = true
                            }

                            Connections {
                                target: seatTabBar
                                function onCurrentIndexChanged() {
                                    totalBankSpin.refreshFromGame()
                                }
                            }

                            onValueChanged: {
                                if (!totalBankSpin._ready || totalBankSpin._applyingFromGame)
                                    return
                                totalBankSpin.pushTotalToEngine()
                            }
                        }
                        Label {
                            visible: setup.selectedSeat === 0 && !playAsBotCheck.checked
                            text: qsTr("On table ($)")
                            font.bold: true
                            font.pixelSize: Theme.trainerCaptionPx
                            Layout.leftMargin: 8
                        }
                        SpinBox {
                            id: seatBankSpin
                            visible: setup.selectedSeat === 0 && !playAsBotCheck.checked
                            from: 0
                            to: Math.max(1, maxTableBbSpin.value * bbSpin.value)
                            stepSize: 1
                            editable: true
                            Layout.fillWidth: false
                            Layout.preferredWidth: 160
                            Layout.maximumWidth: 200

                            /// Skip pushing to the engine when syncing from `pokerGameAccess` (tab change / init).
                            property bool _applyingFromGame: false
                            /// Avoid applying default `SpinBox` value before the first `refreshFromGame()`.
                            property bool _ready: false

                            function refreshFromGame() {
                                _applyingFromGame = true
                                value = Math.min(pokerGameAccess.seatBuyIn(setup.selectedSeat), setup.buyInCapChipsValue())
                                _applyingFromGame = false
                            }

                            function pushBuyInToEngine() {
                                pokerGameAccess.setSeatBuyIn(setup.selectedSeat, value)
                                if (!pokerGameAccess.gameInProgress()) {
                                    pokerGameAccess.applySeatBuyInsToStacks()
                                    setup.persistSave()
                                } else {
                                    setup.persistSave()
                                }
                            }

                            Component.onCompleted: {
                                refreshFromGame()
                                _ready = true
                            }

                            Connections {
                                target: seatTabBar
                                function onCurrentIndexChanged() {
                                    seatBankSpin.refreshFromGame()
                                }
                            }

                            Connections {
                                target: bbSpin
                                function onValueChanged() {
                                    if (seatBankSpin.value > setup.buyInCapChipsValue())
                                        seatBankSpin.value = setup.buyInCapChipsValue()
                                }
                            }

                            Connections {
                                target: maxTableBbSpin
                                function onValueChanged() {
                                    if (seatBankSpin.value > setup.buyInCapChipsValue())
                                        seatBankSpin.value = setup.buyInCapChipsValue()
                                }
                            }

                            Connections {
                                target: pokerGameAccess
                                function onSessionStatsChanged() {
                                    if (seatBankSpin._ready)
                                        seatBankSpin.refreshFromGame()
                                }
                            }

                            /// Use `valueChanged`, not only `valueModified`: the latter can miss updates for
                            /// editable SpinBox / focus edge cases; `value` is the source of truth.
                            onValueChanged: {
                                if (!seatBankSpin._ready || seatBankSpin._applyingFromGame)
                                    return
                                seatBankSpin.pushBuyInToEngine()
                            }
                        }
                        Item {
                            Layout.fillWidth: true
                        }
                    }

                    Label {
                        Layout.topMargin: 4
                        text: qsTr("Strategy selection")
                        font.family: Theme.fontFamilyDisplay
                        font.bold: true
                        font.capitalization: Font.AllUppercase
                        font.pixelSize: Theme.trainerSectionPx
                        font.letterSpacing: 0.5
                        color: Theme.sectionTitle
                    }
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 4

                        ComboBox {
                            id: stratCombo
                            /// While syncing from `reloadSeatEditor` — do not call `setSeatStrategy` (would wipe loaded ranges).
                            property bool _stratSyncFromEngine: false
                            model: strategyNames
                            currentIndex: 0
                            Layout.fillWidth: true
                            onCurrentIndexChanged: {
                                if (stratCombo._stratSyncFromEngine)
                                    return
                                if (!pokerGameAccess)
                                    return
                                pokerGameAccess.setSeatStrategy(setup.selectedSeat, currentIndex)
                                Qt.callLater(function () {
                                    if (!pokerGameAccess)
                                        return
                                    setup.refreshRangeGrids()
                                    textArea.text = pokerGameAccess.exportSeatRangeText(setup.selectedSeat, rangeLayerTab.currentIndex)
                                    setup.loadParamFields()
                                })
                            }
                        }

                        GameButton {
                            style: "form"
                            formFlat: true
                            text: qsTr("?")
                            formBold: true
                            formFontPixelSize: Theme.trainerCaptionPx
                            textColor: Theme.textPrimary
                            padH: 10
                            overrideHeight: 30
                            onClicked: setup.openStrategyLogPopup(
                                    qsTr("%1 — strategy").arg(setup.strategyNames[stratCombo.currentIndex]),
                                    pokerGameAccess.getStrategySummary(stratCombo.currentIndex))
                        }
                    }

                    ThemedCheckBox {
                        id: playAsBotCheck
                        visible: selectedSeat === 0
                        Layout.fillWidth: true
                        text: qsTr("Play as bot (autoplay my seat with the strategy above)")
                        /// Update the engine in this signal (sync), not in Qt.callLater — deferred updates race
                        /// `syncPlayAsBotCheckboxFromEngine()` and can re-apply stale `interactiveHuman` to the checkbox.
                        onToggled: function (checked) {
                            if (!setup.playAsBotUserInputEnabled || setup._syncingPlayAsBot)
                                return
                            const playAsBotOn = (checked !== undefined) ? checked : playAsBotCheck.checked
                            /// Block only with zero bankroll — engine no longer invents chips; short-stack autoplay is OK.
                            if (playAsBotOn && pokerGameAccess.seatBankrollTotal(0) < 1) {
                                setup._syncingPlayAsBot = true
                                playAsBotCheck.checked = false
                                setup._syncingPlayAsBot = false
                                const w = ApplicationWindow.window
                                if (w && typeof w.showAppToast === "function")
                                    w.showAppToast(qsTr("Add chips to your bankroll above before autoplay."))
                                return
                            }
                            pokerGameAccess.setInteractiveHuman(!playAsBotOn)
                            setup.persistSave()
                            setup.refreshRangeGrids()
                            setup.loadParamFields()
                        }
                    }

                    ThemedPanel {
                        panelTitle: ""
                        visible: selectedSeat >= 1
                                || (selectedSeat === 0 && playAsBotCheck.checked)
                        Layout.fillWidth: true

                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: Theme.uiGroupInnerSpacing

                            RowLayout {
                                Layout.fillWidth: true
                                spacing: 8
                                Label {
                                    Layout.fillWidth: true
                                    text: qsTr("Engine parameters")
                                    font.family: Theme.fontFamilyDisplay
                                    font.bold: true
                                    font.capitalization: Font.AllUppercase
                                    font.pixelSize: Theme.trainerSectionPx
                                    font.letterSpacing: 0.5
                                    color: Theme.sectionTitle
                                    wrapMode: Text.WordWrap
                                }
                                GameButton {
                                    style: "form"
                                    formFlat: true
                                    text: qsTr("?")
                                    formBold: true
                                    formFontPixelSize: Theme.trainerCaptionPx
                                    textColor: Theme.textSecondary
                                    padH: 10
                                    overrideHeight: 30
                                    onClicked: setup.openStrategyLogPopup(
                                            qsTr("Engine parameters"),
                                            setup.engineParamsHelpText)
                                }
                            }

                            RowLayout {
                                Layout.fillWidth: true
                                visible: setup.selectedSeat >= 1
                                        || (setup.selectedSeat === 0 && playAsBotCheck.checked)
                                spacing: 8
                                Label {
                                    text: qsTr("Buy-in (× BB)")
                                    font.pixelSize: Theme.trainerCaptionPx
                                }
                                SpinBox {
                                    id: strat_buy_bb
                                    from: 1
                                    to: 10000
                                    value: 100
                                    editable: true
                                    Layout.preferredWidth: 120
                                    Layout.maximumWidth: 140
                                }
                            }

                            GridLayout {
                                columns: 2
                                columnSpacing: Theme.formColGap
                                rowSpacing: Theme.formRowSpacing
                                Layout.fillWidth: true

                                Label {
                                    text: qsTr("Preflop exponent")
                                    font.pixelSize: Theme.trainerCaptionPx
                                }
                                TextField {
                                    id: strat_pf_pre
                                    font.pixelSize: Theme.trainerBodyPx
                                    Layout.fillWidth: true
                                    Layout.maximumWidth: 120
                                }
                                Label {
                                    text: qsTr("Postflop exponent")
                                    font.pixelSize: Theme.trainerCaptionPx
                                }
                                TextField {
                                    id: strat_pf_post
                                    font.pixelSize: Theme.trainerBodyPx
                                    Layout.fillWidth: true
                                    Layout.maximumWidth: 120
                                }
                                Label {
                                    text: qsTr("Facing raise bonus")
                                    font.pixelSize: Theme.trainerCaptionPx
                                }
                                TextField {
                                    id: strat_fr_bonus
                                    font.pixelSize: Theme.trainerBodyPx
                                    Layout.fillWidth: true
                                    Layout.maximumWidth: 120
                                }
                                Label {
                                    text: qsTr("Facing raise tight ×")
                                    font.pixelSize: Theme.trainerCaptionPx
                                }
                                TextField {
                                    id: strat_fr_tight
                                    font.pixelSize: Theme.trainerBodyPx
                                    Layout.fillWidth: true
                                    Layout.maximumWidth: 120
                                }
                                Label {
                                    text: qsTr("Open raise bonus")
                                    font.pixelSize: Theme.trainerCaptionPx
                                }
                                TextField {
                                    id: strat_ob_bonus
                                    font.pixelSize: Theme.trainerBodyPx
                                    Layout.fillWidth: true
                                    Layout.maximumWidth: 120
                                }
                                Label {
                                    text: qsTr("Open raise tight ×")
                                    font.pixelSize: Theme.trainerCaptionPx
                                }
                                TextField {
                                    id: strat_ob_tight
                                    font.pixelSize: Theme.trainerBodyPx
                                    Layout.fillWidth: true
                                    Layout.maximumWidth: 120
                                }
                                Label {
                                    text: qsTr("BB check-raise bonus")
                                    font.pixelSize: Theme.trainerCaptionPx
                                }
                                TextField {
                                    id: strat_bb_bonus
                                    font.pixelSize: Theme.trainerBodyPx
                                    Layout.fillWidth: true
                                    Layout.maximumWidth: 120
                                }
                                Label {
                                    text: qsTr("BB check-raise tight ×")
                                    font.pixelSize: Theme.trainerCaptionPx
                                }
                                TextField {
                                    id: strat_bb_tight
                                    font.pixelSize: Theme.trainerBodyPx
                                    Layout.fillWidth: true
                                    Layout.maximumWidth: 120
                                }
                            }

                            GameButton {
                                Layout.alignment: Qt.AlignLeft
                                style: "form"
                                text: qsTr("Set")
                                textColor: Theme.textSecondary
                                formBold: false
                                formFontPixelSize: Theme.trainerCaptionPx
                                formBackgroundColor: Qt.tint(Theme.panelElevated, "#10101010")
                                padH: 22
                                overrideHeight: 34
                                onClicked: setup.applyParamFields()
                            }
                        }
                    }
                }
            }

            ThemedPanel {
                visible: showFullRangeEditor
                Layout.fillWidth: true
                panelTitle: qsTr("Hand ranges")
                panelOpacity: 0.5
                borderOpacity: 0.5

                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: Theme.uiGroupInnerSpacing

                    TabBar {
                        id: rangeLayerTab
                        Layout.fillWidth: true
                        font.family: Theme.fontFamilyButton
                        font.pixelSize: Theme.trainerCaptionPx

                        TabButton {
                            id: callLayerTabBtn
                            text: qsTr("Call")
                            font.bold: true
                            topPadding: 10
                            bottomPadding: 10
                            leftPadding: 14
                            rightPadding: 14
                            background: Rectangle {
                                anchors.fill: parent
                                radius: 7
                                color: rangeLayerTab.currentIndex === 0
                                        ? Qt.tint(Theme.panelElevated, Qt.alpha(Theme.rangeLayerCallSubdued, 0.92))
                                        : Qt.tint(Theme.panel, Qt.alpha(Theme.rangeLayerCallSubdued, 0.28))
                                border.width: rangeLayerTab.currentIndex === 0 ? 1 : 0
                                border.color: Qt.alpha(Theme.rangeLayerCall, 0.6)
                            }
                            contentItem: Label {
                                text: parent.text
                                font.family: Theme.fontFamilyButton
                                font.pixelSize: Theme.trainerCaptionPx
                                font.weight: Font.Bold
                                font.capitalization: Font.AllUppercase
                                color: rangeLayerTab.currentIndex === 0 ? Theme.textPrimary : Theme.textMuted
                                horizontalAlignment: Text.AlignHCenter
                                verticalAlignment: Text.AlignVCenter
                            }
                        }
                        TabButton {
                            id: raiseLayerTabBtn
                            text: qsTr("Raise")
                            font.bold: true
                            topPadding: 10
                            bottomPadding: 10
                            leftPadding: 14
                            rightPadding: 14
                            background: Rectangle {
                                anchors.fill: parent
                                radius: 7
                                color: rangeLayerTab.currentIndex === 1
                                        ? Qt.tint(Theme.panelElevated, Qt.alpha(Theme.rangeLayerRaiseSubdued, 0.92))
                                        : Qt.tint(Theme.panel, Qt.alpha(Theme.rangeLayerRaiseSubdued, 0.28))
                                border.width: rangeLayerTab.currentIndex === 1 ? 1 : 0
                                border.color: Qt.alpha(Theme.rangeLayerRaise, 0.55)
                            }
                            contentItem: Label {
                                text: parent.text
                                font.family: Theme.fontFamilyButton
                                font.pixelSize: Theme.trainerCaptionPx
                                font.weight: Font.Bold
                                font.capitalization: Font.AllUppercase
                                color: rangeLayerTab.currentIndex === 1 ? Theme.textPrimary : Theme.textMuted
                                horizontalAlignment: Text.AlignHCenter
                                verticalAlignment: Text.AlignVCenter
                            }
                        }
                        TabButton {
                            id: openLayerTabBtn
                            text: qsTr("Open")
                            font.bold: true
                            topPadding: 10
                            bottomPadding: 10
                            leftPadding: 14
                            rightPadding: 14
                            background: Rectangle {
                                anchors.fill: parent
                                radius: 7
                                color: rangeLayerTab.currentIndex === 2
                                        ? Qt.tint(Theme.panelElevated, Qt.alpha(Theme.rangeLayerOpenSubdued, 0.92))
                                        : Qt.tint(Theme.panel, Qt.alpha(Theme.rangeLayerOpenSubdued, 0.28))
                                border.width: rangeLayerTab.currentIndex === 2 ? 1 : 0
                                border.color: Qt.alpha(Theme.rangeLayerOpen, 0.55)
                            }
                            contentItem: Label {
                                text: parent.text
                                font.family: Theme.fontFamilyButton
                                font.pixelSize: Theme.trainerCaptionPx
                                font.weight: Font.Bold
                                font.capitalization: Font.AllUppercase
                                color: rangeLayerTab.currentIndex === 2 ? Theme.textPrimary : Theme.textMuted
                                horizontalAlignment: Text.AlignHCenter
                                verticalAlignment: Text.AlignVCenter
                            }
                        }
                    }

                    Connections {
                        target: rangeLayerTab
                        function onCurrentIndexChanged() {
                            if (setup.showFullRangeEditor) {
                                textArea.text = pokerGameAccess.exportSeatRangeText(setup.selectedSeat, rangeLayerTab.currentIndex)
                                setup.refreshRangeGrids()
                            }
                        }
                    }

                    RangeGrid {
                        id: rng
                        seatIndex: setup.selectedSeat
                        composite: true
                        editLayer: rangeLayerTab.currentIndex
                        pokerGameRef: pokerGameAccess
                        Layout.fillWidth: true
                        Layout.topMargin: 2
                    }

                    RangeActionButton {
                        visible: !setup.rangeTextEditorOpen
                        Layout.topMargin: 4
                        compact: true
                        text: qsTr("Range as text")
                        fillCol: Qt.tint(Theme.panelElevated, "#32c9a21a")
                        borderCol: Theme.goldMuted
                        onClicked: setup.rangeTextEditorOpen = true
                    }

                    Item {
                        id: rangeTextExpandHost
                        Layout.fillWidth: true
                        implicitHeight: setup.rangeTextEditorOpen ? rangeTextEditRow.implicitHeight : 0
                        clip: true

                        Behavior on implicitHeight {
                            NumberAnimation {
                                duration: 220
                                easing.type: Easing.OutCubic
                            }
                        }

                        ColumnLayout {
                            id: rangeTextEditRow
                            width: parent.width
                            spacing: 10

                            TextArea {
                                id: textArea
                                Layout.fillWidth: true
                                Layout.minimumHeight: 120
                                Layout.preferredHeight: 156
                                Layout.maximumHeight: 280
                                wrapMode: TextArea.Wrap
                                font.family: Theme.fontFamilyUi
                                font.pixelSize: Theme.trainerBodyPx
                                color: Theme.textPrimary
                                placeholderText: "AA,AKs,AKo,TT+"
                                placeholderTextColor: Theme.textSecondary
                                onEditingFinished: setup.applyRangeTextFromField()
                            }
                            RowLayout {
                                Layout.fillWidth: true
                                spacing: 10
                                RangeActionButton {
                                    compact: true
                                    text: qsTr("Apply")
                                    fillCol: Qt.tint(Theme.panelElevated, "#42c9a227")
                                    borderCol: Theme.goldMuted
                                    onClicked: {
                                        setup.applyRangeTextFromField()
                                        setup.rangeTextEditorOpen = false
                                    }
                                }
                                RangeActionButton {
                                    compact: true
                                    text: qsTr("Full")
                                    fillCol: Qt.tint(Theme.panelElevated, "#38dc2626")
                                    borderCol: Theme.ember
                                    onClicked: {
                                        pokerGameAccess.resetSeatRangeFull(setup.selectedSeat)
                                        setup.persistSave()
                                        setup.refreshRangeGrids()
                                        textArea.text = pokerGameAccess.exportSeatRangeText(setup.selectedSeat, rangeLayerTab.currentIndex)
                                        setup.rangeTextEditorOpen = false
                                    }
                                }
                                Item {
                                    Layout.fillWidth: true
                                }
                            }
                        }
                    }
                }
            }

            RowLayout {
                Layout.alignment: Qt.AlignLeft
                spacing: 10
                GameButton {
                    text: qsTr("Reset app & clear data")
                    pillWidth: 220
                    overrideHeight: 32
                    fontSize: Theme.trainerCaptionPx
                    buttonColor: Theme.dangerRed
                    textColor: Theme.onAccentText
                    onClicked: factoryResetDialog.open()
                }
            }
            }

            Item {
                Layout.fillWidth: true
                Layout.minimumWidth: 0
            }
        }
    }

    Connections {
        target: seatTabBar
        function onCurrentIndexChanged() {
            setup.syncPlayAsBotCheckboxFromEngine()
            setup.reloadSeatEditor()
        }
    }

    Dialog {
        id: factoryResetDialog
        title: qsTr("Reset everything?")
        modal: true
        anchors.centerIn: parent
        width: Math.min(Math.max(setup.width - 48, 280), 520)
        standardButtons: Dialog.Yes | Dialog.No
        onAccepted: setup.applyFactoryReset()
        contentItem: Column {
            spacing: 0
            width: Math.max(200, factoryResetDialog.width - 64)
            Label {
                width: parent.width
                text: qsTr(
                    "This deletes recorded hands, bankroll history, and all chip balances. "
                    + "Stakes return to $1 / $3 ($9 opens); max on-table stays at 100 BB; seat 0 is Always-call; "
                    + "every bot uses the GTO (heuristic) preset. You can set buy-ins again and tap Apply.")
                wrapMode: Text.WordWrap
                color: Theme.textPrimary
            }
        }
    }

    /// Setup action chips (Apply / Full / Range as text).
    component RangeActionButton: Button {
        id: rangeActBtn
        property color fillCol: Theme.panelElevated
        property color borderCol: Theme.chromeLineGold
        property bool compact: false
        /// Smaller padding than `compact` (e.g. SET stakes).
        property bool dense: false

        flat: false
        focusPolicy: Qt.NoFocus
        font.family: Theme.fontFamilyButton
        font.pixelSize: (dense && compact) ? Math.max(10, Theme.trainerCaptionPx - 1)
                : (compact ? Theme.trainerCaptionPx : Theme.trainerButtonLabelPx)
        font.bold: true
        leftPadding: dense ? 10 : (compact ? 14 : 22)
        rightPadding: dense ? 10 : (compact ? 14 : 22)
        topPadding: dense ? 4 : (compact ? 6 : 12)
        bottomPadding: dense ? 4 : (compact ? 6 : 12)

        background: Rectangle {
            implicitWidth: rangeActBtn.contentItem.implicitWidth + rangeActBtn.leftPadding + rangeActBtn.rightPadding
            implicitHeight: rangeActBtn.contentItem.implicitHeight + rangeActBtn.topPadding + rangeActBtn.bottomPadding
            radius: rangeActBtn.compact ? 7 : 9
            color: rangeActBtn.pressed ? Qt.darker(rangeActBtn.fillCol, 1.14)
                    : (rangeActBtn.hovered ? Qt.lighter(rangeActBtn.fillCol, 1.06) : rangeActBtn.fillCol)
            border.width: 1
            border.color: rangeActBtn.hovered ? Qt.lighter(rangeActBtn.borderCol, 1.12) : rangeActBtn.borderCol
        }

        contentItem: Label {
            text: rangeActBtn.text
            font: rangeActBtn.font
            color: Theme.textPrimary
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
        }
    }
}
