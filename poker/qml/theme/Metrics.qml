pragma Singleton
import QtQuick

/// Layout constants — window chrome, HUD geometry, radii. Default window matches minimum (1280×720); scales up on larger displays.
QtObject {
    /// Minimum window — table + floating HUD beside seat 0 validated at this size.
    readonly property int windowMinWidth: 1280
    readonly property int windowMinHeight: 720
    readonly property int windowWidthDefault: windowMinWidth
    readonly property int windowHeightDefault: windowMinHeight

    /// Header strip with Lobby button + page title (ApplicationWindow `header`).
    readonly property int toolbarHeight: 58
    readonly property int toolbarMarginH: 10
    readonly property int toolbarMarginV: 9
    /// Lobby / back chrome `GameButton` height — original compact size (not full toolbar height).
    readonly property int toolbarChromeHeight: 32

    /// HUD pill height — matches previous compact action buttons so layout stays stable.
    readonly property int hudButtonHeight: 38
    readonly property int chipButtonHeight: 28
    readonly property int radiusHudPill: 6
    readonly property int radiusToolbarButton: 8

    readonly property int iconToolbarChrome: 22
}
