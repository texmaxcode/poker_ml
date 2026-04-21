import QtQuick
import QtQuick.Controls
import Theme 1.0

/// SpinBox styled for training / lobby forms (matches `Theme.inputBg`, avoids default light widgets).
SpinBox {
    id: root
    property int labelPixelSize: Theme.trainerCaptionPx
    font.family: Theme.fontFamilyUi
    font.pixelSize: labelPixelSize
    editable: true
    implicitHeight: 34
    palette.base: Theme.inputBg
    palette.text: Theme.textPrimary
    palette.button: Theme.panelElevated
    palette.buttonText: Theme.textPrimary
    palette.highlight: Theme.focusGold
    palette.highlightedText: Theme.insetDark
}
