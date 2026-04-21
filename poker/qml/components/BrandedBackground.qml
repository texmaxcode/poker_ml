import QtQuick
import Theme 1.0

/// Dark charcoal + burgundy wash, soft edge darkening, and fine film grain.
Item {
    id: root

    function scheduleGrainPaint() {
        grainPaintDebounce.restart()
    }
    Timer {
        id: grainPaintDebounce
        interval: 48
        repeat: false
        onTriggered: grain.requestPaint()
    }
    Rectangle {
        anchors.fill: parent
        gradient: Gradient {
            GradientStop {
                position: 0
                color: Theme.bgGradientTop
            }
            GradientStop {
                position: 0.42
                color: Theme.bgGradientMid
            }
            GradientStop {
                position: 1
                color: Qt.tint(Theme.bgGradientBottom, "#70381820")
            }
        }
    }
    Rectangle {
        anchors.fill: parent
        opacity: 0.4
        gradient: Gradient {
            GradientStop {
                position: 0.35
                color: "#00000000"
            }
            GradientStop {
                position: 1
                color: "#b0000000"
            }
        }
    }
    Canvas {
        id: grain
        anchors.fill: parent
        opacity: 0.09

        onPaint: {
            if (width < 8 || height < 8)
                return
            var ctx = getContext("2d")
            ctx.clearRect(0, 0, width, height)
            const n = Math.min(14000, Math.floor(width * height * 0.02))
            for (var i = 0; i < n; ++i) {
                const x = Math.random() * width
                const y = Math.random() * height
                const a = 0.12 + Math.random() * 0.2
                ctx.fillStyle = Qt.rgba(0.92, 0.82, 0.62, a)
                ctx.fillRect(x, y, 1, 1)
            }
            const n2 = Math.floor(n * 0.35)
            for (var j = 0; j < n2; ++j) {
                const x2 = Math.random() * width
                const y2 = Math.random() * height
                ctx.fillStyle = Qt.rgba(0.15, 0.08, 0.1, 0.06 + Math.random() * 0.08)
                ctx.fillRect(x2, y2, 2, 2)
            }
        }
        onWidthChanged: root.scheduleGrainPaint()
        onHeightChanged: root.scheduleGrainPaint()
        Component.onCompleted: Qt.callLater(requestPaint)
    }
}
