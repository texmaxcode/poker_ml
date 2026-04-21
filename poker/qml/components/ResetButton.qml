import QtQuick
import QtQuick.Controls
import Theme 1.0

/// Subdued ember styling for destructive / session-reset actions (chart baseline, training stats, etc.).
Button {
    id: root
    flat: false
    focusPolicy: Qt.NoFocus
    font.family: Theme.fontFamilyButton
    font.pixelSize: Theme.trainerCaptionPx
    font.bold: false
    font.weight: Font.Normal
    leftPadding: 16
    rightPadding: 16
    topPadding: 8
    bottomPadding: 8
    readonly property color fillCol: Qt.tint(Theme.panelElevated, Qt.alpha(Theme.ember, 0.42))
    readonly property color borderCol: Qt.alpha(Theme.ember, 0.52)
    background: Rectangle {
        implicitWidth: root.contentItem.implicitWidth + root.leftPadding + root.rightPadding
        implicitHeight: root.contentItem.implicitHeight + root.topPadding + root.bottomPadding
        radius: 7
        color: root.pressed ? Qt.darker(root.fillCol, 1.12)
                : (root.hovered ? Qt.lighter(root.fillCol, 1.06) : root.fillCol)
        border.width: 1
        border.color: root.hovered ? Qt.lighter(root.borderCol, 1.1) : root.borderCol
    }
    contentItem: Label {
        text: root.text
        font: root.font
        color: Theme.textPrimary
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
    }
}
