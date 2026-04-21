import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Theme 1.0

/// Shared Min / ⅓ / ½ / ⅔ / Pot / All chips for raise (facing) vs open-raise sliders.
GridLayout {
    id: root
    width: parent ? parent.width : implicitWidth

    required property var hud
    required property Slider slider
    /// `"raise"` = facing a raise; `"open"` = first raise on a street; `"bb"` = BB preflop raise (chips to add).
    property string flavor: "raise"
    /// Called after a preset updates the slider (e.g. submit bet/raise in the parent HUD).
    property var afterPreset: null

    /// One row when wide enough; two rows × three on narrow HUDs so preset cells are not overly wide.
    readonly property int presetColumns: root.width >= 360 ? 6 : 3
    readonly property real presetScale: {
        var w = root.width
        var ws = (w > 1) ? Math.min(1.0, Math.max(0.66, w / 330.0)) : 1.0
        if (hud && hud.embeddedMode && hud.ez > 0)
            ws = Math.min(ws, Math.max(0.78, hud.ez))
        return ws
    }
    readonly property int presetH: Math.max(26, Math.round(Theme.sizingPresetButtonHeight * presetScale))
    readonly property int labelPxMicro: Math.max(8, Math.round(Theme.uiMicroPx * presetScale))
    readonly property int labelPxFrac: Math.max(9, Math.round(Theme.uiSizingPresetPt * presetScale))

    columns: presetColumns
    rowSpacing: Math.max(3, Math.round(5 * presetScale))
    columnSpacing: Math.max(3, Math.round(Theme.sizingPresetBarSpacing * presetScale))

    function clampToSlider(v) {
        var lo = slider.from
        var hi = slider.to
        return Math.min(Math.max(v, lo), hi)
    }

    function applyRaiseTotal(v) {
        v = Math.max(v, hud.facingMinRaiseChips)
        slider.value = clampToSlider(v)
    }

    function applyOpenRaise(v) {
        v = Math.max(v, hud.openRaiseMinChips)
        slider.value = clampToSlider(v)
    }

    function applyBbRaise(v) {
        v = Math.max(v, hud.bbPreflopMinChips)
        slider.value = clampToSlider(v)
    }

    function applyPotFrac(num, den) {
        if (root.flavor === "raise")
            applyRaiseTotal(hud.facingNeedChips + Math.floor(hud.facingPotAmount * num / den))
        else
            applyOpenRaise(Math.floor(hud.facingPotAmount * num / den))
        if (root.afterPreset)
            root.afterPreset()
    }

    function runPreset(kind) {
        if (root.flavor === "bb") {
            switch (kind) {
            case "min":
                applyBbRaise(hud.bbPreflopMinChips)
                break
            case "third":
                applyBbRaise(Math.floor(hud.facingPotAmount / 3))
                break
            case "half":
                applyBbRaise(Math.floor(hud.facingPotAmount / 2))
                break
            case "twothirds":
                applyBbRaise(Math.floor(hud.facingPotAmount * 2 / 3))
                break
            case "pot":
                applyBbRaise(Math.min(hud.bbPreflopMaxChips,
                        Math.max(hud.bbPreflopMinChips, hud.facingPotAmount)))
                break
            case "all":
                applyBbRaise(hud.bbPreflopMaxChips)
                break
            default:
                return
            }
            if (root.afterPreset)
                root.afterPreset()
            return
        }
        switch (kind) {
        case "min":
            if (root.flavor === "raise")
                applyRaiseTotal(hud.facingMinRaiseChips)
            else
                applyOpenRaise(hud.openRaiseMinChips)
            break
        case "third":
            applyPotFrac(1, 3)
            return
        case "half":
            applyPotFrac(1, 2)
            return
        case "twothirds":
            applyPotFrac(2, 3)
            return
        case "pot":
            if (root.flavor === "raise")
                applyRaiseTotal(hud.facingNeedChips + hud.facingPotAmount)
            else
                applyOpenRaise(Math.min(hud.facingPotAmount, slider.to))
            break
        case "all":
            if (root.flavor === "raise")
                applyRaiseTotal(slider.to)
            else
                applyOpenRaise(slider.to)
            break
        default:
            return
        }
        if (root.afterPreset)
            root.afterPreset()
    }

    Repeater {
        model: [
            {
                label: qsTr("Min"),
                kind: "min"
            },
            {
                label: qsTr("⅓"),
                kind: "third"
            },
            {
                label: qsTr("½"),
                kind: "half"
            },
            {
                label: qsTr("⅔"),
                kind: "twothirds"
            },
            {
                label: qsTr("Pot"),
                kind: "pot"
            },
            {
                label: qsTr("All"),
                kind: "all"
            }
        ]

        delegate: Item {
            required property var modelData
            Layout.fillWidth: true
            Layout.minimumWidth: 22
            Layout.preferredHeight: root.presetH

            Rectangle {
                anchors.fill: parent
                anchors.margins: 1
                radius: Math.max(4, Math.round(6 * root.presetScale))
                color: Theme.hudActionPanel
                opacity: presetMa.pressed ? 0.72 : (presetMa.containsMouse ? 0.88 : 1)

                Text {
                    anchors.centerIn: parent
                    width: parent.width - 4
                    horizontalAlignment: Text.AlignHCenter
                    text: modelData.label
                    color: Theme.textPrimary
                    font.family: Theme.fontFamilyButton
                    font.pixelSize: (modelData.kind === "min" || modelData.kind === "pot" || modelData.kind === "all")
                            ? root.labelPxMicro : root.labelPxFrac
                    font.bold: true
                    elide: Text.ElideNone
                }
            }

            MouseArea {
                id: presetMa
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: root.runPreset(modelData.kind)
            }
        }
    }
}
