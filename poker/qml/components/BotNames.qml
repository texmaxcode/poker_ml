import QtQuick

/// Display names for six-max players (indices 0 = you, 1…5 = bots).
Item {
    width: 0
    height: 0
    visible: false

    function displayName(seatIndex) {
        if (seatIndex === 0)
            return qsTr("You")
        if (seatIndex < 1 || seatIndex > 5)
            return qsTr("Player %1").arg(seatIndex + 1)
        var names = [
            qsTr("Peter"),
            qsTr("James"),
            qsTr("John"),
            qsTr("Andrew"),
            qsTr("Philip")
        ]
        return names[seatIndex - 1]
    }
}
