import QtQuick
import Theme 1.0

/// Vector table playfield: room wash + oval rail + felt (no bitmaps).
Item {
    id: root
    anchors.fill: parent

    property real feltOvalW: Math.min(parent.width - 8, parent.height * 1.42)
    property real feltOvalH: Math.min(parent.height - 8, parent.width * 0.58)

    Rectangle {
        anchors.fill: parent
        gradient: Gradient {
            GradientStop {
                position: 0
                color: Theme.bgGradientTop
            }
            GradientStop {
                position: 0.5
                color: Theme.bgGradientMid
            }
            GradientStop {
                position: 1
                color: Theme.bgGradientBottom
            }
        }
    }

    Item {
        id: shadowHost
        anchors.centerIn: parent
        width: Math.min(root.feltOvalW, parent.width - 4) + 10
        height: Math.min(root.feltOvalH, parent.height - 4) + 10
        property real scr: height / 2

        Rectangle {
            anchors.centerIn: parent
            anchors.horizontalCenterOffset: 5
            anchors.verticalCenterOffset: 7
            width: parent.width - 10
            height: parent.height - 10
            radius: parent.scr
            color: "#80000000"
        }
    }

    Item {
        id: ovalHost
        anchors.centerIn: parent
        width: Math.min(root.feltOvalW, parent.width - 4)
        height: Math.min(root.feltOvalH, parent.height - 4)
        property real cr: height / 2
        z: 0

        Rectangle {
            anchors.fill: parent
            radius: parent.cr
            color: Theme.railOuter
            border.width: 2
            border.color: Theme.railBezel
        }

        Rectangle {
            anchors.fill: parent
            anchors.margins: 10
            radius: Math.max(4, parent.cr - 10)
            gradient: Gradient {
                GradientStop {
                    position: 0
                    color: Theme.railWood0
                }
                GradientStop {
                    position: 0.5
                    color: Theme.railWood1
                }
                GradientStop {
                    position: 1
                    color: Theme.railWood2
                }
            }
            border.width: 1
            border.color: Theme.railEdge
        }

        Rectangle {
            id: feltFace
            anchors.fill: parent
            anchors.margins: 34
            radius: Math.max(4, parent.cr - 34)
            gradient: Gradient {
                GradientStop {
                    position: 0
                    color: Theme.feltHighlight
                }
                GradientStop {
                    position: 0.45
                    color: Theme.feltMid
                }
                GradientStop {
                    position: 1
                    color: Theme.feltShadow
                }
            }
            border.width: 1
            border.color: Theme.feltBorder
            clip: true

            /// Subtle fiber noise — 1×1 only, hues from the felt gradient (no light “wear” streaks).
            Canvas {
                id: feltGrain
                anchors.fill: parent
                opacity: 0.22

                /// Coalesce rapid resize events so we do not repaint the grain canvas dozens of times per frame.
                Timer {
                    id: grainPaintDebounce
                    interval: 48
                    repeat: false
                    onTriggered: feltGrain.requestPaint()
                }
                function scheduleGrainPaint() {
                    grainPaintDebounce.restart()
                }

                onPaint: {
                    if (width < 4 || height < 4)
                        return
                    var ctx = getContext("2d")
                    ctx.clearRect(0, 0, width, height)
                    var n = Math.min(6000, Math.floor(width * height * 0.012))
                    var i
                    for (i = 0; i < n; ++i) {
                        var x = Math.random() * width
                        var y = Math.random() * height
                        var t = Math.random()
                        // Darker fibers (shadow side of nap)
                        ctx.fillStyle = Qt.rgba(0.02 + t * 0.04, 0.08 + t * 0.1, 0.06 + t * 0.08, 0.08 + Math.random() * 0.14)
                        ctx.fillRect(Math.floor(x), Math.floor(y), 1, 1)
                    }
                    var nh = Math.floor(n * 0.35)
                    for (i = 0; i < nh; ++i) {
                        var x3 = Math.random() * width
                        var y3 = Math.random() * height
                        // Rare lighter green flecks (still on-felt, not yellow)
                        ctx.fillStyle = Qt.rgba(0.12 + Math.random() * 0.1, 0.28 + Math.random() * 0.12, 0.2 + Math.random() * 0.1, 0.05 + Math.random() * 0.08)
                        ctx.fillRect(Math.floor(x3), Math.floor(y3), 1, 1)
                    }
                }
                onWidthChanged: scheduleGrainPaint()
                onHeightChanged: scheduleGrainPaint()
                Component.onCompleted: scheduleGrainPaint()
            }
        }

        /// Single soft playing-line inset (was two stacked white rings that could read as harsh lines).
        Rectangle {
            anchors.fill: parent
            anchors.margins: 44
            radius: Math.max(4, parent.cr - 44)
            color: "transparent"
            border.width: 1
            border.color: Qt.rgba(0.55, 0.72, 0.62, 0.12)
        }
    }
}
