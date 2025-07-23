from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTextEdit,
    QPushButton,
    QScrollArea,
    QLabel,
    QFrame,
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QFont
import sys
import objc
from AppKit import NSWindow, NSWindowSharingNone
from ctypes import c_void_p

# UI Constants
CLARIFICATION_WIDTH = 500
CLARIFICATION_HEIGHT = 600
MESSAGE_MARGIN = 20
BUBBLE_PADDING = 15
INPUT_HEIGHT = 50


class MessageBubble(QFrame):
    """Individual message bubble widget"""

    def __init__(self, text, is_user=False, parent=None):
        super().__init__(parent)
        self.is_user = is_user
        self.setup_ui(text)

    def setup_ui(self, text):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            BUBBLE_PADDING, BUBBLE_PADDING, BUBBLE_PADDING, BUBBLE_PADDING
        )

        # Message text
        message_label = QLabel(text)
        message_label.setWordWrap(True)
        message_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )

        # Set font
        font = QFont()
        font.setPointSize(13)
        message_label.setFont(font)

        layout.addWidget(message_label)

        # Apply styling based on sender
        if self.is_user:
            self.setObjectName("userBubble")
        else:
            self.setObjectName("aiBubble")


class ClarificationDialog(QWidget):
    """Clarification dialog with chat interface"""

    # Signals
    task_clarified = pyqtSignal(str)  # Emitted when task is clarified
    dialog_closed = pyqtSignal()  # Emitted when dialog is closed

    def __init__(self, initial_task="", parent=None):
        super().__init__(parent)
        self.initial_task = initial_task
        self.conversation_history = []
        self.oldPos = None  # For window dragging
        self.setup_window()
        self.init_ui()
        self.start_conversation()

    def setup_window(self):
        """Setup window properties"""
        from ..config.language import get_text

        self.setWindowTitle(get_text("clarification_title"))
        self.setFixedSize(CLARIFICATION_WIDTH, CLARIFICATION_HEIGHT)

        # Set window flags - frameless like other windows
        self.setWindowFlags(
            Qt.WindowType.Dialog
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.NoDropShadowWindowHint
        )
        # Remove translucent background for better visibility
        # self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

    def init_ui(self):
        """Initialize the user interface"""
        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Container widget for styling
        container = QWidget()
        container.setObjectName("clarificationContainer")
        main_layout.addWidget(container)

        # Container layout
        layout = QVBoxLayout(container)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # Title bar
        title_bar = self.create_title_bar()
        layout.addWidget(title_bar)

        # Chat area (scrollable)
        self.chat_scroll = QScrollArea()
        self.chat_scroll.setObjectName("chatScroll")
        self.chat_scroll.setWidgetResizable(True)
        self.chat_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.chat_scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )

        # Chat container
        self.chat_container = QWidget()
        self.chat_layout = QVBoxLayout(self.chat_container)
        self.chat_layout.setContentsMargins(0, 0, 0, 0)
        self.chat_layout.setSpacing(10)
        self.chat_layout.addStretch()  # Push messages to bottom initially

        self.chat_scroll.setWidget(self.chat_container)
        layout.addWidget(self.chat_scroll)

        # Input area
        input_area = self.create_input_area()
        layout.addWidget(input_area)

        # Apply styling
        self.apply_styles()

    def create_title_bar(self):
        """Create the title bar with close button"""
        title_bar = QWidget()
        title_layout = QHBoxLayout(title_bar)
        title_layout.setContentsMargins(0, 0, 0, 0)

        # Title
        title_label = QLabel(get_text("clarification_title").upper())
        title_label.setObjectName("clarificationTitle")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Close button
        close_button = QPushButton(get_text("close_button"))
        close_button.setObjectName("closeButton")
        close_button.setFixedSize(30, 30)
        close_button.clicked.connect(self.close_dialog)

        title_layout.addStretch()
        title_layout.addWidget(title_label)
        title_layout.addStretch()
        title_layout.addWidget(close_button)

        return title_bar

    def create_input_area(self):
        """Create the input area with text field and send button"""
        input_widget = QWidget()
        input_layout = QHBoxLayout(input_widget)
        input_layout.setContentsMargins(0, 0, 0, 0)
        input_layout.setSpacing(10)

        # Input field
        self.input_field = QTextEdit()
        self.input_field.setObjectName("messageInput")
        self.input_field.setFixedHeight(INPUT_HEIGHT)
        self.input_field.setPlaceholderText(get_text("clarification_placeholder"))

        # Connect enter key
        self.input_field.keyPressEvent = self.input_key_press

        # Handle IME composition events for better Korean input support
        self.input_field.inputMethodEvent = self.input_ime_event

        # Send button
        self.send_button = QPushButton(get_text("send_button"))
        self.send_button.setObjectName("sendButton")
        self.send_button.setFixedSize(80, INPUT_HEIGHT)
        self.send_button.clicked.connect(self.send_message)

        input_layout.addWidget(self.input_field)
        input_layout.addWidget(self.send_button)

        return input_widget

    def input_key_press(self, event):
        """Handle key press in input field"""
        if event.key() == Qt.Key.Key_Return and not (
            event.modifiers() & Qt.KeyboardModifier.ShiftModifier
        ):
            # For Korean (and other IME) input, delay message sending to ensure composition is finished
            QTimer.singleShot(10, self.send_message)
        else:
            QTextEdit.keyPressEvent(self.input_field, event)

    def input_ime_event(self, event):
        """Handle IME composition events for better Korean input support"""
        # Call the default implementation to handle composition
        QTextEdit.inputMethodEvent(self.input_field, event)

        # If composition is finished, update the text display
        if event.commitString():
            # Composition is complete, text has been committed
            pass

    def start_conversation(self):
        """Start the conversation with initial AI message"""
        initial_message = f"Hey! Could you be a bit more specific about your intention?\n{self.initial_task}?"
        self.add_message(initial_message, is_user=False)

    def add_message(self, text, is_user=False):
        """Add a message to the chat"""
        # Remove the stretch from the end
        if self.chat_layout.count() > 0:
            last_item = self.chat_layout.itemAt(self.chat_layout.count() - 1)
            if last_item.spacerItem():
                self.chat_layout.removeItem(last_item)

        # Create message bubble
        bubble = MessageBubble(text, is_user)

        # Create container for alignment
        message_container = QWidget()
        container_layout = QHBoxLayout(message_container)
        container_layout.setContentsMargins(0, 0, 0, 0)

        if is_user:
            # User messages align right
            container_layout.addStretch()
            container_layout.addWidget(bubble)
            container_layout.addSpacing(MESSAGE_MARGIN)
        else:
            # AI messages align left
            container_layout.addSpacing(MESSAGE_MARGIN)
            container_layout.addWidget(bubble)
            container_layout.addStretch()

        self.chat_layout.addWidget(message_container)

        # Add stretch at the end
        self.chat_layout.addStretch()

        # Scroll to bottom
        QTimer.singleShot(50, self.scroll_to_bottom)

        # Store in conversation history
        self.conversation_history.append({"text": text, "is_user": is_user})

    def scroll_to_bottom(self):
        """Scroll chat to bottom"""
        scrollbar = self.chat_scroll.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def send_message(self):
        """Send user message"""
        text = self.input_field.toPlainText().strip()
        if not text:
            return

        # Add user message
        self.add_message(text, is_user=True)
        self.input_field.clear()

        # Simulate AI response (for now)
        QTimer.singleShot(1000, lambda: self.simulate_ai_response(text))

    def simulate_ai_response(self, user_message):
        """Simulate AI response (placeholder for future chat integration)"""
        # Simple response logic for demo
        if "RL" in user_message or "reinforcement learning" in user_message.lower():
            response = "OK, got it! Let's get started."
            self.add_message(response, is_user=False)

            # Emit signal with clarified task
            QTimer.singleShot(1500, lambda: self.finalize_task(user_message))
        else:
            response = "Could you be more specific? What exactly do you want to study?"
            self.add_message(response, is_user=False)

    def finalize_task(self, clarified_task):
        """Finalize the task and close dialog"""
        self.task_clarified.emit(clarified_task)
        self.close_dialog()

    def close_dialog(self):
        """Close the dialog"""
        self.dialog_closed.emit()
        self.hide()

    def apply_styles(self):
        """Apply CSS styling"""
        self.setStyleSheet(
            """
            /* Main dialog window */
            ClarificationDialog {
                background-color: #2D2D2D;
                border: 3px solid #007AFF;
                border-radius: 15px;
            }
            
            /* Main container */
            #clarificationContainer {
                background-color: #2D2D2D;
                border-radius: 12px;
            }
            
            /* Title */
            #clarificationTitle {
                color: white;
                font-size: 18px;
                font-weight: bold;
                padding: 10px 0px;
            }
            
            /* Close button */
            #closeButton {
                background-color: #ff3b30;
                color: white;
                font-size: 14px;
                font-weight: bold;
                border: none;
                border-radius: 15px;
            }
            #closeButton:hover {
                background-color: #ff5e57;
            }
            
            /* Chat scroll area */
            #chatScroll {
                background-color: transparent;
                border: none;
            }
            
            /* Message bubbles */
            #userBubble {
                background-color: #E5E5EA;
                border-radius: 18px;
                max-width: 300px;
            }
            #userBubble QLabel {
                color: #000000;
            }
            
            #aiBubble {
                background-color: #007AFF;
                border-radius: 18px;
                max-width: 300px;
            }
            #aiBubble QLabel {
                color: #FFFFFF;
            }
            
            /* Input field */
            #messageInput {
                background-color: #3C3C3C;
                border: 2px solid #555555;
                border-radius: 25px;
                padding: 10px 15px;
                font-size: 14px;
                color: white;
            }
            #messageInput:focus {
                border-color: #007AFF;
            }
            
            /* Send button */
            #sendButton {
                background-color: #FFD60A;
                color: #000000;
                font-size: 14px;
                font-weight: bold;
                border: none;
                border-radius: 25px;
            }
            #sendButton:hover {
                background-color: #FFED4E;
            }
            
            /* Scrollbar styling */
            QScrollBar:vertical {
                background-color: #3C3C3C;
                width: 8px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical {
                background-color: #666666;
                border-radius: 4px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #888888;
            }
        """
        )

    def makeWindowSecure(self):
        """Make window secure from screen capture"""
        if sys.platform == "darwin":
            try:
                native_view = objc.objc_object(c_void_p=int(self.winId()))
                ns_window = native_view.window()
                ns_window.setSharingType_(NSWindowSharingNone)
                print(
                    "Clarification 창이 보안 모드로 설정되어 스크린 캡처에서 제외됩니다."
                )
            except Exception as e:
                print(f"Clarification 창 보안 모드 설정 중 오류 발생: {e}")

    def showEvent(self, event):
        """Handle show event"""
        super().showEvent(event)
        # Apply security after window is shown
        QTimer.singleShot(100, self.makeWindowSecure)
        # Focus on input field
        self.input_field.setFocus()

    # Mouse drag handlers for moving the popup
    def mousePressEvent(self, event):
        """Handle mouse press to start window dragging"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.oldPos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event):
        """Handle mouse movement to move window"""
        if self.oldPos:
            delta = event.globalPosition().toPoint() - self.oldPos
            self.move(self.pos() + delta)
            self.oldPos = event.globalPosition().toPoint()

    def mouseReleaseEvent(self, event):
        """Handle mouse release to end window dragging"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.oldPos = None
