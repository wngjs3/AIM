import rumps
from PyQt6.QtWidgets import (
    QMessageBox,
    QDialog,
    QVBoxLayout,
    QLabel,
    QPushButton,
    QApplication,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
import subprocess
import sys
from ..config.language import get_text


class MultiDisplayDialog(QDialog):
    """Custom dialog for multiple display detection with prominent display"""

    def __init__(self, display_count, display_list, parent=None):
        super().__init__(parent)
        self.setWindowTitle(get_text("multiple_display_title"))
        self.setModal(True)
        self.setFixedSize(600, 450)  # Increased size for better text visibility

        # Always on top and center on screen
        self.setWindowFlags(
            Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Dialog
            | Qt.WindowType.Tool  # Better visibility on macOS
        )

        # Center the dialog on the primary screen
        self.center_on_screen()

        # Set dark theme background
        self.setStyleSheet(
            """
            QDialog {
                background-color: #202020;
                color: white;
            }
        """
        )

        # Setup UI
        self.setup_ui(display_count, display_list)

    def center_on_screen(self):
        """Center the dialog on the primary screen"""
        screen = QApplication.primaryScreen()
        if screen:
            screen_geometry = screen.geometry()
            x = (screen_geometry.width() - self.width()) // 2
            y = (screen_geometry.height() - self.height()) // 2
            self.move(x, y)

    def setup_ui(self, display_count, display_list):
        """Setup the dialog UI"""
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(30, 30, 30, 30)

        # Title
        title_label = QLabel(get_text("multiple_display_title"))
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setStyleSheet("color: #FF3B30; margin-bottom: 10px;")
        layout.addWidget(title_label)

        # Main message
        # Get base message from translation and add display info
        base_message = get_text("multiple_display_message")
        display_info = (
            f"\n\n현재 연결된 디스플레이 ({display_count}):\n{display_list}"
            if get_text("multiple_display_title") == "다중 디스플레이 감지"
            else f"\n\nCurrently connected displays ({display_count}):\n{display_list}"
        )

        # Additional instructions based on language
        additional_instructions = (
            (
                "\n\n📋 다음 중 하나를 선택하세요:\n"
                "• 외부 모니터 케이블 연결 해제\n"
                "• 노트북 덮개를 닫아 외부 모니터만 사용 (클램셸 모드)\n"
                "• 시스템 설정 > 디스플레이에서 하나의 디스플레이 비활성화\n\n"
                "그 다음 앱을 다시 시작하세요."
            )
            if get_text("multiple_display_title") == "다중 디스플레이 감지"
            else (
                "\n\n📋 Please choose one of these options:\n"
                "• Disconnect external monitor cable\n"
                "• Close laptop lid (clamshell mode) to use external monitor only\n"
                "• Use System Settings > Displays to disable one display\n\n"
                "Then restart the app."
            )
        )

        full_message = base_message + display_info + additional_instructions
        main_message = QLabel(full_message)
        main_message.setWordWrap(True)
        main_message.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_message.setStyleSheet(
            """
            QLabel {
                background-color: #2c2c2c;
                color: white;
                border: 2px solid #FF3B30;
                border-radius: 8px;
                padding: 20px;
                font-size: 14px;
                line-height: 1.6;
            }
        """
        )
        layout.addWidget(main_message)

        # OK button
        ok_button = QPushButton(get_text("exit_app_button"))
        ok_button.setFixedHeight(40)
        ok_button.setStyleSheet(
            """
            QPushButton {
                background-color: #FF3B30;
                color: white;
                border: none;
                border-radius: 8px;
                font-size: 14px;
                font-weight: bold;
                padding: 10px 20px;
            }
            QPushButton:hover {
                background-color: #FF5E57;
            }
            QPushButton:pressed {
                background-color: #D12B20;
            }
        """
        )
        ok_button.clicked.connect(self.accept)
        layout.addWidget(ok_button)

        # Focus on the button for immediate Enter key response
        ok_button.setFocus()

    def showEvent(self, event):
        """Override showEvent to ensure dialog is brought to front"""
        super().showEvent(event)
        self.activateWindow()
        self.raise_()


class Dialogs:
    @staticmethod
    def show_notification(title, subtitle, message, sound=False):
        """Show a notification using rumps (system notifications - always show)"""
        print(f"[DIALOGS] System notification: {title} - {subtitle}")
        rumps.notification(title, subtitle, message, sound=sound)

    @staticmethod
    def show_error(title, message):
        """Show an error dialog"""
        dialog = QMessageBox()
        dialog.setIcon(QMessageBox.Icon.Critical)
        dialog.setWindowTitle(title)
        dialog.setText(message)
        dialog.setStandardButtons(QMessageBox.StandardButton.Ok)
        dialog.exec()

    @staticmethod
    def show_multiple_display_error(display_count, display_list):
        """Show a prominent modal dialog for multiple display detection"""
        print(f"[DIALOGS] ===== STARTING MULTIPLE DISPLAY ERROR DIALOG =====")
        print(f"[DIALOGS] Display count: {display_count}")
        print(f"[DIALOGS] Display list: {display_list}")

        try:
            # Force bring to front and ensure visibility
            app = QApplication.instance()
            if app:
                print(f"[DIALOGS] Processing QApplication events...")
                app.processEvents()  # Process pending events first
                print(f"[DIALOGS] QApplication events processed")

            # Use Qt dialog only (no native macOS alert to avoid app icon)
            print(f"[DIALOGS] Creating MultiDisplayDialog...")
            dialog = MultiDisplayDialog(display_count, display_list)
            print(f"[DIALOGS] MultiDisplayDialog created")

            # Force dialog to be on top and visible
            dialog.setWindowFlags(
                Qt.WindowType.WindowStaysOnTopHint
                | Qt.WindowType.Dialog
                | Qt.WindowType.Tool
            )
            dialog.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, False)

            # Show dialog first
            dialog.show()
            print(f"[DIALOGS] Dialog shown")

            # Force to front multiple times with processing events between
            if app:
                app.processEvents()

            dialog.activateWindow()
            dialog.raise_()
            print(f"[DIALOGS] Dialog activated and raised")

            # Process events again after activation
            if app:
                app.processEvents()

            # Force focus on the dialog
            dialog.setFocus()
            print(f"[DIALOGS] Dialog focused")

            print(f"[DIALOGS] Dialog window flags set and shown")

            # Show the dialog
            print(f"[DIALOGS] Calling dialog.exec()...")
            result = dialog.exec()
            print(f"[DIALOGS] Dialog closed with result: {result}")

            # Process events after dialog closes
            if app:
                print(f"[DIALOGS] Processing events after dialog close...")
                app.processEvents()

            print(f"[DIALOGS] ===== DIALOG COMPLETED SUCCESSFULLY =====")
            return result

        except Exception as e:
            print(f"[ERROR] Failed to show multiple display dialog: {e}")
            import traceback

            print(f"[ERROR] Full traceback: {traceback.format_exc()}")

            # Fallback to system notification if dialog fails
            print(f"[DIALOGS] Falling back to system notification...")
            title = get_text("multiple_display_title")
            subtitle = get_text("exit_app_button")
            message = (
                f"Detected {display_count} displays. App will exit in 3 seconds."
                if title != "다중 디스플레이 감지"
                else f"{display_count}개의 디스플레이가 감지되었습니다. 3초 후 앱이 종료됩니다."
            )

            print(f"[DIALOGS] Showing system notification: {title} - {message}")
            rumps.notification(
                title,
                subtitle,
                message,
                sound=True,
            )
            print(f"[DIALOGS] System notification sent")
            return None

    @staticmethod
    def _show_native_macos_alert(display_count, display_list):
        """Show native macOS alert dialog using osascript"""
        # Get translated texts
        title = get_text("multiple_display_title")
        base_message = get_text("multiple_display_message")
        button_text = get_text("exit_app_button")

        # Build full message with display info and instructions based on language
        if title == "다중 디스플레이 감지":  # Korean
            display_info = (
                f"\\n\\n현재 연결된 디스플레이 ({display_count}):\\n\\n{display_list}"
            )
            instructions = "\\n\\n📋 다음 중 하나를 선택하세요:\\n• 외부 모니터 케이블 연결 해제\\n• 노트북 덮개를 닫아 외부 모니터만 사용 (클램셸 모드)\\n• 시스템 설정 > 디스플레이에서 하나의 디스플레이 비활성화\\n\\n그 다음 앱을 다시 시작하세요."
        else:  # English
            display_info = f"\\n\\nCurrently connected displays ({display_count}):\\n\\n{display_list}"
            instructions = "\\n\\n📋 Please choose one of these options:\\n• Disconnect external monitor cable\\n• Close laptop lid (clamshell mode) to use external monitor only\\n• Use System Settings > Displays to disable one display\\n\\nThen restart the app."

        alert_text = base_message.replace("\n", "\\n") + display_info + instructions

        script = f"""
        tell application "System Events"
            display alert "{title}" message "{alert_text}" buttons {{"{button_text}"}} default button "{button_text}" giving up after 30
        end tell
        """

        result = subprocess.run(
            ["osascript", "-e", script], capture_output=True, text=True, timeout=35
        )

        print(f"[DIALOGS] Native alert result: {result.returncode}")
        return result.returncode == 0
