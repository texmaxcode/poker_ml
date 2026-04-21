pragma Singleton
import QtQuick

/// Texas Hold'em Gym — palette aligned with brand logo (charcoal stone, burgundy banner,
/// gold/chrome type, fire accents).
QtObject {
    readonly property color bgWindow: "#0b090a"
    readonly property color bgGradientTop: "#16100e"
    readonly property color bgGradientMid: "#0a0809"
    readonly property color bgGradientBottom: "#060508"

    readonly property color panel: "#161218"
    readonly property color panelElevated: "#1c1820"
    readonly property color panelBorder: "#3d3028"
    readonly property color panelBorderMuted: "#2a2428"
    readonly property color chromeLine: "#6b5030"
    readonly property color chromeLineGold: "#8a6028"

    /// Primary accent — muted brass (was brighter #d4af37; toned down for less glare on dark UI).
    readonly property color gold: "#b89a52"
    readonly property color goldMuted: "#8a6f38"
    readonly property color fire: "#ff6a1a"
    readonly property color fireDeep: "#c2410c"
    readonly property color ember: "#dc2626"
    readonly property color textPrimary: "#f2ebe4"
    readonly property color textSecondary: "#a89890"
    readonly property color textMuted: "#7a7068"

    /// Bundled Google Fonts — registered at startup (`appFontFamily*` root-context strings).
    /// Merriweather — body copy, forms, labels (default app font).
    readonly property string fontFamilyUi: appFontFamily
    /// Rye — logo / panel & toolbar titles.
    readonly property string fontFamilyDisplay: appFontFamilyDisplay
    /// Holtwood One SC — `GameButton` and action chrome.
    readonly property string fontFamilyButton: appFontFamilyButton
    /// Roboto Mono — chips, stacks, pot, sliders, monospace fields.
    readonly property string fontFamilyMono: appFontFamilyMono

    readonly property color headerBg: "#141016"
    readonly property color headerRule: "#5c4020"

    readonly property color feltHighlight: "#1a4538"
    readonly property color feltMid: "#123028"
    readonly property color feltShadow: "#081810"
    readonly property color feltBorder: "#0a2820"
    readonly property color railOuter: "#121018"
    readonly property color railBezel: "#1a1018"
    readonly property color railWood0: "#352218"
    readonly property color railWood1: "#1c1008"
    readonly property color railWood2: "#0c0604"
    /// Muted trim on the felt oval (was bright copper; keep separation from wood without a harsh ring).
    readonly property color railEdge: "#342018"

    readonly property color hudBg0: "#2a1c14"
    readonly property color hudBg1: "#140e0a"
    readonly property color hudBorder: "#7a5020"
    /// Table pot strip — slightly darker than `hudBorder` so the rim stays readable on the felt.
    readonly property color potHudBorder: "#523018"
    readonly property color inputBg: "#222028"
    readonly property color inputBorder: "#4a4048"
    readonly property color accentBlue: "#7eb8e8"
    readonly property color hudActionLabel: "#8b93a8"
    readonly property color hudActionPanel: "#3a4a6a"
    readonly property color hudActionBright: "#d0e4ff"
    readonly property color insetDark: "#222"
    readonly property color dangerBg: "#4a2020"
    readonly property color dangerText: "#f5d0d0"
    /// Solid red for destructive primary actions (factory reset, clear-all).
    readonly property color dangerRed: "#b71c1c"
    readonly property color successGreen: "#1a6b45"
    readonly property color focusGold: "#a89248"
    /// Seat street-action strip (Call / Raise / Check / All-in / Fold).
    readonly property color streetActionCall: "#e8d040"
    readonly property color streetActionRaise: "#4ade80"
    readonly property color streetActionAllIn: "#ef4444"
    readonly property color streetActionCheck: "#7eb8e8"
    readonly property color streetActionFold: "#a89890"

    readonly property color seatPanel: "#15151c"
    readonly property color seatStackTint: "#2a1f18"
    readonly property color seatBorderIdle: "#4a3a32"
    readonly property color seatBorderAct: "#ff8c42"
    readonly property color progressTrack: "#1e1e26"

    /// Per-seat accents (names, setup tabs, stats, bankroll chart) — subdued metallics + burgundy + gunmetal
    /// to match the logo banner, chrome “GYM” type, and dumbbell steel (not neon primaries).
    readonly property var chartLineColors: [
        "#c6a86c",
        "#a07078",
        "#8b93a4",
        "#a8926a",
        "#6d8a7c",
        "#9e7a82"
    ]

    /// Text / accent color for seat `0`…`5` — matches `chartLineColors` and the bankroll chart legend.
    function colorForSeat(seat) {
        var c = chartLineColors
        if (seat === undefined || seat < 0 || seat >= c.length)
            return textPrimary
        return c[seat]
    }

    /// Scale form/lobby controls: slightly larger on small windows, slightly smaller on very large ones.
    function compactUiScale(shortSide) {
        var s = shortSide > 0 ? shortSide : 720
        return Math.min(1.2, Math.max(0.88, 720 / Math.max(s, 420)))
    }

    /// Hex strings for Canvas2D (`fillStyle` / `strokeStyle`).
    readonly property string chartPlotFill: "#141016"
    readonly property string chartGridLine: "#2a3040"
    readonly property string chartAxisText: "#6a7080"

    readonly property color profitUp: "#6fdc8c"
    readonly property color profitDown: "#ff8a8a"

    readonly property color sectionTitle: gold
    readonly property real bodyLineHeight: 1.35
    readonly property int formLabelPx: 14
    readonly property int formRowSpacing: 10
    readonly property int formColGap: 12
    readonly property int panelGap: 16

    /// Playing cards (~1 : 1.48 width:height). Pair width matches 204px seat inner (margins 4).
    readonly property int holeCardWidth:  96
    readonly property int holeCardHeight: 135
    readonly property int holeCardGap: 2
    readonly property int holePairTotalWidth: 2 * (holeCardWidth + holeCardGap)
    /// Board / default `Card` footprint — five across + spacing fits centered on typical table width.
    readonly property int boardCardWidth: 128
    readonly property int boardCardHeight: 179

    /// Training / drill screens: keep readable line length and controls off ultra-wide edges.
    readonly property int trainerContentMaxWidth: 720
    /// Extra inset below the app header on training drill pages (keeps content off the toolbar rule).
    readonly property int trainerPageTopPadding: 15
    /// Floor for `GameControls.hudScale` on trainers — must stay below ~0.5 or the action dock steals too much height on short windows.
    readonly property real trainerHudMinScale: 0.38
    /// Flop trainer: community cards match table scale so pot + board + seat fit without overlap.
    readonly property int trainerFlopBoardCardWidth: 100
    readonly property int trainerFlopBoardCardHeight: 149
    /// Gap between drill cards and between HUD action rows — matches `GameControls` action spacing (12).
    readonly property int trainerDrillHudSpacing: 12
    /// Hero seat is centered; action dock sits below (no side-floating HUD).
    readonly property int trainerDrillSeatCenterOffset: 0

    /// Turn spot ids like `btnbb_turn_AK72_brick_KQo` into short UI titles (not internal debug strings).
    function trainerSpotDisplayTitle(spotId) {
        if (spotId === undefined || spotId === null)
            return ""
        var raw = String(spotId).trim()
        if (raw.length === 0)
            return ""
        function noise(tok) {
            if (tok.length < 2)
                return false
            var t = tok
            if (/^[AKQJT2-9][akqjt0-9hcds]+$/i.test(t) && t.length <= 24)
                return true
            if (/^[AKQJT0-9]{3,12}[a-z]?$/i.test(t))
                return true
            return false
        }
        var parts = raw.split("_")
        var out = []
        var i = 0
        while (i < parts.length) {
            var p = parts[i]
            if (p.length === 0) {
                i++
                continue
            }
            var pl = p.toLowerCase()
            if (noise(p)) {
                i++
                continue
            }
            if (pl === "btnbb") {
                out.push("BTN vs BB")
                i++
                continue
            }
            if (pl === "srp") {
                out.push("SRP")
                i++
                continue
            }
            if (pl === "turn") {
                out.push("Turn")
                i++
                continue
            }
            if (pl === "river") {
                out.push("River")
                i++
                continue
            }
            if (pl === "flop") {
                out.push("Flop")
                i++
                continue
            }
            if (pl === "four" && i + 1 < parts.length && parts[i + 1].toLowerCase() === "flush") {
                out.push("Four-flush board")
                i += 2
                continue
            }
            if (pl === "dry" || pl === "wet") {
                out.push(pl.charAt(0).toUpperCase() + pl.slice(1))
                i++
                continue
            }
            if (pl === "runout") {
                out.push("Runout")
                i++
                continue
            }
            if (pl === "brick") {
                out.push("Brick")
                i++
                continue
            }
            if (pl === "four" || pl === "flush") {
                i++
                continue
            }
            var pretty = p.charAt(0).toUpperCase() + p.slice(1).toLowerCase()
            out.push(pretty)
            i++
        }
        if (out.length === 0)
            return raw.replace(/_/g, " ")
        var dedup = []
        for (var j = 0; j < out.length; j++) {
            if (j === 0 || out[j] !== out[j - 1])
                dedup.push(out[j])
        }
        return dedup.join(" · ")
    }

    /// Human-friendly label for preflop scenario mode keys (e.g. "call_vs_UTG" → "Call vs UTG").
    function trainerModeDisplayLabel(mode) {
        if (!mode)
            return ""
        var m = String(mode).trim()
        if (m === "open")
            return "Open (RFI)"
        if (m === "call")
            return "Call"
        if (m === "defend")
            return "Defend"
        if (m === "vs3bet")
            return "vs 3-Bet"
        if (m.indexOf("call_vs_") === 0)
            return "Call vs " + m.substring(8).toUpperCase()
        if (m.indexOf("3bet_vs_") === 0)
            return "3-Bet vs " + m.substring(8).toUpperCase()
        if (m === "3bet")
            return "3-Bet"
        return m.charAt(0).toUpperCase() + m.slice(1)
    }

    /// Typography for training copy — sized for Merriweather (wider serif; Oswald was condensed so read smaller).
    readonly property int trainerPageHeadlinePt: 19
    readonly property int trainerSectionPx: 16
    readonly property int trainerBodyPx: 14
    readonly property int trainerCaptionPx: 14
    readonly property int trainerMetricLabelPx: 12
    readonly property int trainerMetricValuePx: 20
    readonly property int trainerToolButtonPx: 14
    readonly property int trainerButtonLabelPx: 15
    readonly property int trainerColumnSpacing: 6
    readonly property int trainerPanelPadding: 14
    readonly property int trainerPanelRadius: 10
    /// Drill panel: minimum height — pot + tiny board + compact seat at smallest drillScale.
    readonly property int trainerDrillPanelMinH: 100
    /// Drill panel: maximum height — prevents the drill from dominating ultra-tall windows.
    readonly property int trainerDrillPanelMaxH: 580
    /// Clamp drill height so headers + full-width trainer HUD still fit (e.g. at `Metrics.windowMinHeight`).
    function trainerDrillPanelMaxHeightForViewport(viewportHeight, chromeReserve) {
        var vh = Number(viewportHeight)
        var cr = Number(chromeReserve)
        if (!(vh > 0) || cr < 0)
            return trainerDrillPanelMaxH
        if (vh <= cr) {
            // Reserve already exceeds viewport — never return the tall design max or layout blows past min window.
            return Math.max(trainerDrillPanelMinH, Math.min(trainerDrillPanelMaxH, Math.floor(vh * 0.42)))
        }
        var avail = vh - cr
        return Math.max(trainerDrillPanelMinH, Math.min(trainerDrillPanelMaxH, Math.floor(avail)))
    }
    /// Shrinks seat `uiScale` when the seat row is shorter than the design-height seat (avoids clipping).
    function trainerSeatUiScaleClamped(seatScale, wrapHeight) {
        var s = seatScale > 0 ? seatScale : 1.0
        var h = wrapHeight
        if (!(h > 1))
            return Math.max(0.28, Math.min(1.0, s))
        var designH = 288.0
        return Math.max(0.28, Math.min(s, h / designH))
    }
    /// Same formula as `GameScreen` `tableArea.tableScale` — hero seat + HUD scale with viewport size.
    function tableScaleForViewport(w, h) {
        var ww = Math.max(1, w)
        var hh = Math.max(1, h)
        return Math.min(1.0, Math.min(ww, hh) / 1024.0)
    }
    /// Seat `uiScale` for training drills: match table scaling, then shrink if the row is narrower than 218×scale.
    function trainerSeatUiScale(viewportW, viewportH, seatRowWidth) {
        var ts = tableScaleForViewport(viewportW, viewportH)
        var row = Math.max(1, seatRowWidth)
        var need = 218.0 * ts + 8.0
        if (row >= need)
            return ts
        return Math.max(0.34, Math.min(ts, (row - 8.0) / 218.0))
    }
    /// Embedded `GameControls` must fit FOLD/CALL/RAISE (or CHECK / bet / bet) in one row (~300px + margins).
    readonly property int trainerEmbeddedHudMinWidth: 280
    /// Win-line banner: mini cards beside one-line result text (`GameControls` embedded HUD).
    /// Showdown strip in HUD status — slightly larger than before; aspect ~1 : 1.45 (hole cards).

    readonly property int resultBannerCardW: 78
    readonly property int resultBannerCardH: 100
    readonly property int trainerSpinBoxWidth: 140

    /// Lobby / setup / stats / solver / training scroll pages (not the in-game table/HUD).
    readonly property int uiPagePadding: 13
    /// Space between the toolbar (or window top on lobby) and the first line of scroll content.
    readonly property int uiScrollViewTopPadding: 15
    /// GroupBox and grouped panels outside the poker table (matches training panel padding).
    readonly property int uiGroupedPanelPadding: 13
    /// Vertical spacing inside GroupBox ColumnLayouts (setup, stats, solver).
    readonly property int uiGroupInnerSpacing: 5
    /// Application-wide UI (lobby, stats, setup, solver, table, HUD).
    readonly property int uiBasePt: 12
    readonly property int uiToolBarTitlePt: 14
    /// Lobby chrome chip label + icon (smaller than centered page title).
    readonly property int uiToolBarChromePt: 5
    readonly property int uiBodyPx: 13
    readonly property int uiSmallPx: 12
    readonly property int uiMicroPx: 11
    readonly property int uiMonoPx: 12
    /// Lobby framed panel heading (“What would you like to do?”).
    readonly property int uiLobbyPanelTitlePx: 18
    /// Nav tiles: title + sub use `pixelSize`; two-line caps; fixed block heights keep every tile aligned.
    readonly property int uiLobbyNavTileTitlePx: 15
    readonly property int uiLobbyNavSubPx: 10
    readonly property real uiLobbyNavTileTitleLineHeight: 1.2
    readonly property real uiLobbyNavTileSubLineHeight: 1.2
    /// Fixed content height for title block (two lines at `titlePx` × line height).
    readonly property int uiLobbyNavTitleBlockH: 30
    /// Sub block must fit two wrapped lines at `uiLobbyNavSubPx` × `uiLobbyNavTileSubLineHeight` (display fonts are wide).
    readonly property int uiLobbyNavSubBlockH: 30
    readonly property int uiLobbyNavTilePadding: 8
    /// Space between icon / title / sub stacks inside a tile.
    readonly property int uiLobbyNavTileStackSpacing: 7
    /// Gap between lobby nav tiles (lobby nav row).
    readonly property int uiLobbyNavRowSpacing: 10
    readonly property int uiLobbyNavTileMinHeight: 136
    readonly property int uiLobbyNavIconPx: 40
    readonly property int uiPotMainPt: 22
    readonly property int uiPotSepPt: 18
    readonly property int uiPotCallPt: 18
    readonly property int uiSeatFoldPt: 12
    readonly property int uiSeatStreetPt: 9
    readonly property int uiSeatNamePt: 13
    readonly property int uiSeatPosPt: 11
    readonly property int uiStackPt: 16
    readonly property int uiHudButtonPt: 10
    readonly property int uiChartCanvasPx: 12
    readonly property int uiRangeGridAxisPx: 14
    readonly property int uiRangeGridLegendPx: 13
    /// 13×13 cell size (axis labels use row/col header widths below).
    readonly property int uiRangeGridCellW: 40
    readonly property int uiRangeGridCellH: 32
    readonly property int uiRangeGridRowHeaderW: 28
    readonly property int uiRangeGridCornerW: 22
    readonly property int uiRangeGridCornerH: 24
    readonly property int uiSizingPresetPt: 11
    /// `SizingPresetBar`: gap between Min / ⅓ / … chips (table + training `GameControls`).
    readonly property int sizingPresetBarSpacing: 10
    /// Tap height for preset chips — room for label + vertical padding.
    readonly property int sizingPresetButtonHeight: 40
    /// Inset inside the grey raise panel (slider + presets) above/below and left/right.
    readonly property int sizingRaisePanelPadV: 14
    readonly property int sizingRaisePanelPadH: 12
    /// Space between the amount slider row and the preset button row.
    readonly property int sizingRaiseSliderToPresetGap: 12

    /// 13×13 range editor: heatmap and composite layers (gold / fire / burgundy — matches logo banner & type).
    readonly property color rangeHeatLo: panel
    readonly property color rangeHeatHi: gold
    /// Muted heat top — blends into `panel` for a quieter single-layer heatmap.
    readonly property color rangeHeatHiSubdued: Qt.tint(panel, Qt.alpha(gold, 0.55))
    /// Call layer — warm gold (passive / continue).
    readonly property color rangeLayerCall: "#d4b84a"
    /// Raise layer — fire orange (aggression).
    readonly property color rangeLayerRaise: fire
    /// Open layer — burgundy rose (distinct from raise, readable on dark felt).
    readonly property color rangeLayerOpen: "#a85868"
    /// Composite strips: tinted into `panel` so the grid reads quieter than full accent fills.
    readonly property color rangeLayerCallSubdued: Qt.tint(panel, Qt.alpha(rangeLayerCall, 0.56))
    readonly property color rangeLayerRaiseSubdued: Qt.tint(panel, Qt.alpha(rangeLayerRaise, 0.52))
    readonly property color rangeLayerOpenSubdued: Qt.tint(panel, Qt.alpha(rangeLayerOpen, 0.54))
    /// Region underlays: upper triangle = suited, lower = offsuit, diagonal = pairs.
    readonly property color rangeGridPairTint: Qt.rgba(1, 1, 1, 0.08)
    readonly property color rangeGridSuitedTint: Qt.rgba(0.42, 0.58, 0.75, 0.16)
    readonly property color rangeGridOffsuitTint: Qt.rgba(0.68, 0.52, 0.42, 0.14)

    /// Text color for labels on accent-colored buttons (gold, green, etc.).
    readonly property color onAccentText: "#ffffff"
}
