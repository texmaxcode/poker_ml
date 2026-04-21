import QtQuick
import QtQuick.Window
import Theme 1.0

Flipable {
    id: flipable
    width: Theme.boardCardWidth
    height: Theme.boardCardHeight

    /// SVGs rasterize at `sourceSize`; match physical pixels so cards stay sharp on HiDPI.
    readonly property real paintDpr: {
        var w = flipable.Window.window
        return (w && w.devicePixelRatio > 0) ? w.devicePixelRatio : 1.0
    }
    /// Extra shrink from **parent** transforms only (e.g. board `Row` `scale` &lt; 1, HUD `ez` on a full-size card item).
    /// Combined with `layoutShrink` so hole cards and banner minis get supersampling even when this stays 1.
    property real displayScaleFactor: 1.0
    /// vs reference board footprint — smaller items (holes, result banner, drills) need higher `_rasterMul`.
    readonly property real layoutShrink: {
        if (flipable.width < 1 || flipable.height < 1)
            return 1.0
        return Math.min(flipable.width / Theme.boardCardWidth, flipable.height / Theme.boardCardHeight)
    }
    readonly property real _rasterMul: {
        var f = Math.min(flipable.layoutShrink, flipable.displayScaleFactor)
        if (f >= 0.995)
            return 1.0
        return Math.min(3.5, 1.0 / Math.max(f, 0.17))
    }
    /// Light extra raster for HiDPI / `smooth` sampling — keeps hole + banner faces crisp without huge textures.
    readonly property real _sharpBoost: 1.14

    property bool flipped: false
    property string card: "spades_ace.svg"
    /// Community cards are always face-up; holes use flipped/show_cards from Player.
    property bool tableCard: false
    /// Skip flip animation (training / instant reveal).
    property bool instantFace: false
    /// Bumps each new hand (`Game.handSeq`) so rotation snaps to match concealed/revealed state.
    property int dealEpoch: 0

    front: Image {
        source: "qrc:/assets/cards/blue2.svg"
        anchors.fill: parent
        fillMode: Image.Stretch
        /// Mipmaps soften minified SVGs; board row uses `scale` &lt; 1.
        mipmap: false
        smooth: true
        sourceSize.width: Math.max(1, Math.ceil(flipable.width * flipable.paintDpr * flipable._rasterMul * flipable._sharpBoost))
        sourceSize.height: Math.max(1, Math.ceil(flipable.height * flipable.paintDpr * flipable._rasterMul * flipable._sharpBoost))
    }
    back: Image {
        source: (card.length === 0)
                ? "qrc:/assets/cards/blue2.svg"
                : ("qrc:/assets/cards/" + card)
        anchors.fill: parent
        fillMode: Image.Stretch
        mipmap: false
        smooth: true
        sourceSize.width: Math.max(1, Math.ceil(flipable.width * flipable.paintDpr * flipable._rasterMul * flipable._sharpBoost))
        sourceSize.height: Math.max(1, Math.ceil(flipable.height * flipable.paintDpr * flipable._rasterMul * flipable._sharpBoost))
    }

    transform: Rotation {
        id: rotation
        origin.x: flipable.width / 2
        origin.y: flipable.height / 2
        axis {
            x: 0
            y: 1
            z: 0
        }
        angle: 0
    }

    states: State {
        name: "back"
        PropertyChanges {
            target: rotation
            angle: 180
        }
        /// Hole cards: never rotate to the rank/suit side without a real card string (avoids stuck / phantom faces).
        when: tableCard || (flipable.flipped && card.length > 0)
    }

    transitions: [
        Transition {
            to: "back"
            NumberAnimation {
                target: rotation
                property: "angle"
                duration: flipable.instantFace ? 0 : 620
                easing.type: Easing.InOutCubic
            }
        },
        Transition {
            from: "back"
            NumberAnimation {
                target: rotation
                property: "angle"
                duration: 0
            }
        }
    ]

    onDealEpochChanged: {
        if (tableCard)
            return
        /// Training: skip the “deal face-down” snap — stay revealed (see `instantFace` on `Player`).
        if (instantFace && flipped && card.length > 0) {
            rotation.angle = 180
            return
        }
        /// New hand: snap concealed unless this slot should already show a face (same rule as `states[0].when`).
        /// Unconditional `angle = 0` here used to run after bindings and leave one hole stuck face-down.
        if (flipped && card.length > 0)
            rotation.angle = 180
        else
            rotation.angle = 0
    }

    onCardChanged: {
        if (tableCard)
            return
        if (card.length === 0) {
            rotation.angle = 0
            return
        }
        if (flipped)
            rotation.angle = 180
    }
}
