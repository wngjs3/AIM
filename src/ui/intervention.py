import sys
from PyQt6.QtWidgets import QWidget, QApplication
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPainter, QColor


class Intervention(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowTransparentForInput
            | Qt.WindowType.WindowDoesNotAcceptFocus
            | Qt.WindowType.NoDropShadowWindowHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)

        # ✅ 화면 전체 geometry 가져오기 + 적용
        screen = QGuiApplication.primaryScreen()
        geometry = screen.geometry()
        self.setGeometry(geometry)  # 핵심!

        if sys.platform == "darwin":
            try:
                from AppKit import (
                    NSApp,
                    NSScreenSaverWindowLevel,
                    NSWindowCollectionBehaviorCanJoinAllSpaces,
                    NSWindowCollectionBehaviorStationary,
                    NSWindowCollectionBehaviorIgnoresCycle,
                )

                self.show()
                window = NSApp.windows()[-1]
                window.setLevel_(NSScreenSaverWindowLevel + 1)
                behavior = (
                    NSWindowCollectionBehaviorCanJoinAllSpaces
                    | NSWindowCollectionBehaviorStationary
                    | NSWindowCollectionBehaviorIgnoresCycle
                )
                window.setCollectionBehavior_(behavior)
                window.setStyleMask_(window.styleMask() & ~(1 << 3))
                window.setHidesOnDeactivate_(False)
            except ImportError:
                self.show()
        else:
            self.show()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(
            self.rect(), QColor(0, 0, 0, int(255 * 8.5 / 10))
        )  # 반투명 검정


# 사용 예시
if __name__ == "__main__":
    app = QApplication(sys.argv)
    overlay = Intervention()
    sys.exit(app.exec())
