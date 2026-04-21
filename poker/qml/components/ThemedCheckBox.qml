import QtQuick
import QtQuick.Controls
import Theme 1.0

/// Sit out / advanced options — same palette as `ThemedSwitch` for a consistent HUD.
CheckBox {
    id: root

    font.family: Theme.fontFamilyUi
    palette.window: Theme.panelElevated
    palette.windowText: Theme.textPrimary
    palette.base: Theme.inputBg
    palette.text: Theme.textPrimary
    palette.button: Theme.panelBorderMuted
    palette.buttonText: Theme.textPrimary
    palette.highlight: Theme.focusGold
    palette.highlightedText: Theme.insetDark
    palette.mid: Theme.panelBorder
    palette.light: Theme.chromeLineGold
    palette.dark: Theme.bgGradientBottom
}
