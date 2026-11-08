import QtQuick 2.0;
import calamares.slideshow 1.0;

Presentation
{
    id: presentation

    Slide {
        Column {
            anchors.centerIn: parent
            spacing: 24
            Image {
                anchors.horizontalCenter: parent.horizontalCenter
                source: "welcome.png"
                width: 320
                fillMode: Image.PreserveAspectFit
                smooth: true
            }
            Text {
                anchors.horizontalCenter: parent.horizontalCenter
                horizontalAlignment: Text.AlignHCenter
                font.pixelSize: 18
                color: "#404040"
                text: "SoftglowOS wird installiert. Lehn dich zurück, das dauert ein paar Minuten.\nSoftglowOS is being installed. Sit back, this takes a few minutes."
            }
        }
    }
}
