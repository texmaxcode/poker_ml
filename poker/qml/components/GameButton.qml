import QtQuick
import QtQuick.Controls
import Theme 1.0

/// Table HUD / toolbar / form actions — implemented as `Button` so layout + text rendering use Controls pipeline
/// (avoids zero-size `Item` wrappers and palette fighting explicit `color` on raw `Text`).
Button {
    id: root

    property string style: "hud"
    property string chipKind: ""
    property string iconSource: ""
    property string chromeFontFamily: ""

    property color buttonColor: Theme.panelBorder
    property color textColor: Theme.textPrimary
    property int fontSize: Fonts.hudButtonPt
    property bool boldFont: false
    property int pillWidth: 0
    /// Horizontal inset for label (not `horizontalPadding` — that name is FINAL on `Control`).
    property int padH: 24
    property int overrideHeight: -1
    /// Toolbar chrome only: scales icon + label with the window (`Main.qml`).
    property real chromeScale: 1.0
    property bool formFlat: false
    property int formFontPixelSize: -1
    property bool formBold: false
    property color formBackgroundColor: Theme.panelElevated
    /// When set on `style === "hud"`, overrides `fontFamilyButton` for legible % / symbols (e.g. trainer bet sizing).
    property string hudLabelFontFamily: ""

    /// Maps to `enabled` (not named `interactive` — reserved on some Controls versions).
    property bool clickEnabled: true

    readonly property string _buttonTypeface: {
        var f = Theme.fontFamilyButton
        return (f !== undefined && f !== null && String(f).length > 0) ? String(f) : Theme.fontFamilyUi
    }
    readonly property string _monoTypeface: {
        var f = Theme.fontFamilyMono
        return (f !== undefined && f !== null && String(f).length > 0) ? String(f) : "monospace"
    }

    flat: true
    focusPolicy: Qt.NoFocus
    padding: 0
    leftPadding: padH / 2
    rightPadding: padH / 2
    topPadding: 0
    bottomPadding: 0

    enabled: root.clickEnabled
    text: ""

    hoverEnabled: true

    implicitWidth: {
        var w = 76
        if (contentItem)
            w = contentItem.implicitWidth + leftPadding + rightPadding
        if (style === "chrome")
            w = Math.max(w, chromeRowCalc.implicitWidth + padH)
        if (pillWidth > 0)
            return Math.max(pillWidth, w)
        return Math.max(style === "chip" ? 40 : 76, w)
    }
    implicitHeight: {
        if (overrideHeight >= 0)
            return overrideHeight
        if (style === "chrome")
            return Math.max(26, Math.round(Metrics.toolbarChromeHeight * chromeScale))
        if (style === "form")
            return Metrics.hudButtonHeight
        if (style === "chip")
            return Metrics.chipButtonHeight
        return Metrics.hudButtonHeight
    }

    /// Invisible twin of chrome layout — `Row` top-aligns children; we use verticalCenter for measurement.
    Item {
        id: chromeRowCalc
        visible: false
        implicitWidth: crIcon.width + 6 + crLabel.implicitWidth
        implicitHeight: Math.max(crIcon.height, crLabel.implicitHeight)

        Image {
            id: crIcon
            anchors.left: parent.left
            anchors.verticalCenter: parent.verticalCenter
            width: Math.max(16, Math.round(Metrics.iconToolbarChrome * root.chromeScale))
            height: Math.max(16, Math.round(Metrics.iconToolbarChrome * root.chromeScale))
            source: root.iconSource
        }
        Text {
            id: crLabel
            anchors.left: crIcon.right
            anchors.leftMargin: 6
            anchors.verticalCenter: parent.verticalCenter
            text: root.text
            font.bold: false
            font.weight: Font.Normal
            font.pointSize: Math.max(10, Math.round(Theme.uiToolBarChromePt * root.chromeScale))
            font.family: root.chromeFontFamily.length > 0 ? root.chromeFontFamily : root._buttonTypeface
        }
    }

    /// Center in the control — default `Button` top-left aligns `contentItem`, which looked broken on chrome.
    contentItem: Loader {
        anchors.centerIn: parent
        sourceComponent: root.style === "chrome" ? chromeContent : hudOrFormContent
    }

    Component {
        id: hudOrFormContent
        Text {
            text: root.text
            color: root.style === "form" ? root.textColor
                    : (root.style === "chip" ? Theme.textPrimary : root.textColor)
            font.pointSize: {
                if (root.style === "chip") {
                    return (root.chipKind === "min" || root.chipKind === "pot" || root.chipKind === "all")
                            ? Fonts.chipLabelPt
                            : Fonts.chipLabelLargePt
                }
                if (root.style === "form")
                    return root.formFontPixelSize >= 0 ? root.formFontPixelSize : Fonts.formCaptionPt
                return root.fontSize
            }
            font.bold: root.style === "form" ? root.formBold : root.boldFont
            font.weight: root.style === "chip" ? Font.Medium : Font.Normal
            font.family: {
                if (root.style === "chip")
                    return root._monoTypeface
                if (root.style === "hud" && root.hudLabelFontFamily.length > 0)
                    return root.hudLabelFontFamily
                return root._buttonTypeface
            }
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
            elide: Text.ElideRight
        }
    }

    Component {
        id: chromeContent
        Item {
            implicitWidth: chIcon.width + 6 + chLabel.implicitWidth
            implicitHeight: Math.max(chIcon.height, chLabel.implicitHeight)

            Image {
                id: chIcon
                anchors.left: parent.left
                anchors.verticalCenter: parent.verticalCenter
                width: Math.max(16, Math.round(Metrics.iconToolbarChrome * root.chromeScale))
                height: Math.max(16, Math.round(Metrics.iconToolbarChrome * root.chromeScale))
                source: root.iconSource
                opacity: root.clickEnabled ? 1 : 0.45
                fillMode: Image.PreserveAspectFit
            }
            Text {
                id: chLabel
                anchors.left: chIcon.right
                anchors.leftMargin: 6
                anchors.verticalCenter: parent.verticalCenter
                text: root.text
                font.bold: false
                font.weight: Font.Normal
                font.pointSize: Math.max(10, Math.round(Theme.uiToolBarChromePt * root.chromeScale))
                font.family: root.chromeFontFamily.length > 0 ? root.chromeFontFamily : root._buttonTypeface
                color: root.pressed ? Theme.fire : (root.hovered ? Theme.gold : Theme.textPrimary)
                elide: Text.ElideRight
            }
        }
    }

    background: Item {
        Rectangle {
            visible: root.style === "hud" || root.style === "chip"
            anchors.fill: parent
            radius: Metrics.radiusHudPill
            color: root.buttonColor
        }

        Rectangle {
            visible: root.style === "form"
            anchors.fill: parent
            radius: Metrics.radiusHudPill
            color: root.formFlat ? "transparent" : root.formBackgroundColor
            border.width: root.formFlat ? 0 : 1
            border.color: Theme.inputBorder
        }

        Rectangle {
            visible: root.style === "chrome"
            anchors.fill: parent
            radius: Metrics.radiusToolbarButton
            clip: true
            gradient: Gradient {
                GradientStop {
                    position: 0
                    color: Qt.lighter(Theme.hudBg0, 1.06)
                }
                GradientStop {
                    position: 1
                    color: Theme.hudBg1
                }
            }
            border.color: root.down ? Theme.fireDeep
                    : (root.hovered ? Theme.chromeLineGold : Qt.alpha(Theme.chromeLine, 0.88))
            border.width: 1
        }

        Rectangle {
            anchors.fill: parent
            radius: root.style === "chrome" ? Metrics.radiusToolbarButton : Metrics.radiusHudPill
            visible: root.style !== "chrome" && root.clickEnabled && (root.hovered || root.down)
            color: root.down ? Qt.rgba(0, 0, 0, 0.14) : Qt.rgba(1, 1, 1, 0.1)
        }

        Rectangle {
            anchors.fill: parent
            radius: Metrics.radiusHudPill
            visible: root.style === "form" && root.clickEnabled && (root.hovered || root.down)
            color: root.down ? Qt.rgba(0, 0, 0, 0.12) : Qt.rgba(1, 1, 1, 0.06)
        }
    }
}
