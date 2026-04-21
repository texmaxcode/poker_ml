import QtQuick
import QtQuick.Controls
import Theme 1.0

/// Bot on/off toggles — palette matches charcoal + gold theme (Fusion/default styles use `palette`).
Switch {
    id: root

    font.family: Theme.fontFamilyUi
    palette.window: Theme.panelElevated
    palette.windowText: Theme.textPrimary
    palette.base: Theme.inputBg
    palette.alternateBase: Theme.panel
    palette.text: Theme.textPrimary
    palette.button: Theme.panelBorderMuted
    palette.buttonText: Theme.textPrimary
    palette.highlight: Theme.focusGold
    palette.highlightedText: Theme.insetDark
    palette.mid: Theme.panelBorder
    palette.light: Theme.chromeLineGold
    palette.dark: Theme.bgGradientBottom
}
