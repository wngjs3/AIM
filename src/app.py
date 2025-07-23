import os
import sys
import rumps
import random
import logging
import subprocess
import threading
import time
import regex as re

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication, QDialog

from .ui.menu import AppMenu
from .ui.dialogs import Dialogs
from .ui.dashboard import Dashboard
from .ui.notification import NotificationManager

from .config.constants import *
from .config.user_config import UserConfig
from .config.prompt_config import PromptConfig

from .manager import ThreadManager

from .logging.cloud import CloudUploader
from .logging.storage import LocalStorage

from .utils.launch_at_login import ensure_login_item

# Hide IMK related logs
logging.getLogger().setLevel(logging.ERROR)
os.environ["QT_LOGGING_RULES"] = "*.debug=false;qt.qpa.*=false"


class IntentionalComputingApp(rumps.App):
    def __init__(self):
        # Print app version and config info
        print(f"\n=== Intentional Computing v{APP_VERSION} ===")
        print(f"Config directory: {CONFIG_DIR}")
        print(f"Storage directory: {DEFAULT_STORAGE_DIR}")
        print(f"App mode: {APP_MODE}")

        # Initialize rumps app with minimal visibility
        super().__init__(
            "", icon=None, quit_button=None
        )  # Empty name to hide from menu bar

        # Initialize configuration
        self.config = UserConfig()

        # Initialize storage
        self.storage = LocalStorage()

        # Initialize notification system
        self.notifications = NotificationManager()

        # Initialize dashboard
        self.dashboard = None

        # Initialize manager
        self.manager = None

        # Initialize notification context storage
        self.notification_context = {}

        # Add notification flag for next LLM analysis
        self.next_analysis_has_notification = False

        # Initialize state tracking variables
        self.reset_state_tracking()

        # Initialize timers
        self.capture_timer = QTimer()
        self.llm_timer = QTimer()
        self.reminder_timer = None

        # Connect timer signals
        self.capture_timer.timeout.connect(self.do_capture)
        self.llm_timer.timeout.connect(self.invoke_llm)

        # Initialize other variables
        self.current_message = None
        self.last_server_message = None
        self.reminder_counter = 0

        # Initialize icons first
        assets_dir = os.path.join(os.path.dirname(__file__), "assets")
        self.default_icon = os.path.join(assets_dir, "icon.png")
        self.recording_icon = os.path.join(assets_dir, "icon_recording.png")

        # Initialize PyQt application FIRST
        self.qt_app = QApplication.instance()
        if self.qt_app is None:
            self.qt_app = QApplication(sys.argv)

        # Connect aboutToQuit signal for safe thread cleanup
        self.qt_app.aboutToQuit.connect(self._safe_shutdown)

        # Set up display change monitoring AFTER QApplication is ready
        print("[INIT] Setting up display monitoring...")
        print(f"[INIT] QApplication instance: {self.qt_app}")
        print(f"[INIT] Initial screen count: {len(self.qt_app.screens())}")

        # Connect screen change signals
        self.qt_app.screenAdded.connect(self._on_screen_added)
        self.qt_app.screenRemoved.connect(self._on_screen_removed)
        print("[INIT] Display monitoring signals connected")

        # Check initial setup
        self.check_initial_setup()

        # Check display count after QApplication is ready
        self._check_display_count()
        self.uploader = CloudUploader(CLOUD_STORAGE_ENDPOINT)
        self.prompt_config = PromptConfig(self.storage)  # Pass storage to prompt_config

        # Get selected display from settings - but force to 0 for single display
        settings = self.config.get_settings()
        selected_display = 0  # Always use first display in single display environment

        # Create ThreadManager first
        self.manager = ThreadManager(
            self.storage,
            self.uploader,
            self.prompt_config,
            None,  # Dashboard will be set later
            self.config,
            selected_display=selected_display,
        )

        # Now create Dashboard with required arguments
        self.dashboard = Dashboard(self.manager, self.config, self.storage)

        # Set dashboard reference in manager
        self.manager.dashboard = self.dashboard

        # Show dashboard
        self.dashboard.show()

        # Store notification context for feedback
        self.notification_context = {}

        # Setup reminder timer for reminder mode
        self.reminder_counter = 0  # 리마인더 카운터 초기화 (25분 간격)

        if APP_MODE == APP_MODE_REMINDER:
            print("Setting up reminder timer for reminder mode")
            self.reminder_timer = QTimer()
            self.reminder_timer.setInterval(25 * 60 * 1000)  # 25 minutes
            self.reminder_timer.timeout.connect(self._handle_reminder)
            print(f"Reminder timer setup complete for {APP_MODE} mode")

        # Setup menu and initialize state
        self.menu = AppMenu.create_menu(self)
        self.reset_state_tracking()
        self.check_initial_setup()

        # Connect dashboard signals
        self.dashboard.capture_started.connect(self._handle_capture_start)
        self.dashboard.capture_stopped.connect(self._handle_capture_stop)
        # play_sound_requested signal removed - sound functionality disabled

        # Show startup notification
        Dialogs.show_notification(
            f"IntentionalComputing v{APP_VERSION}",
            "App started",
            APP_START_MESSAGE,
        )

        # Run a test capture at startup to request screen capture permissions
        try:
            print("[INIT] Requesting screen capture permissions...")
            # Execute after 1 second (when UI is fully loaded)
            QTimer.singleShot(1000, self._perform_test_capture)
        except Exception as e:
            print(f"[ERROR] Failed to setup initial capture: {e}")

        # Setup auto-login after app is fully initialized
        QTimer.singleShot(2000, self._setup_auto_login)

    def _perform_test_capture(self):
        """Performs a test screen capture to request permissions when app starts"""
        try:
            from PyQt6.QtWidgets import QApplication

            # Capture from the main display (result won't be saved)
            screens = QApplication.screens()
            if screens:
                screen = screens[0]  # Use main screen
                screenshot = screen.grabWindow(0)
                print("[INIT] Screen capture permissions granted")

                # Delete capture result immediately (only used in memory)
                del screenshot

                # Run garbage collection
                import gc

                gc.collect()
            else:
                print("[ERROR] No screens available for test capture")
        except Exception as e:
            print(f"[ERROR] Test capture failed: {e}")

    def _check_display_count(self):
        """Check if multiple displays are connected and exit if so"""
        try:
            screens = QApplication.screens()
            display_count = len(screens)

            if display_count == 1:
                # Single display detected - automatically select it
                screen = screens[0]
                geometry = screen.geometry()
                name = screen.name() or "Primary Display"
                resolution = f"{geometry.width()}x{geometry.height()}"

                print(f"[INIT] Display: {name} ({resolution})")

                # Force set the display selection to 0 (the only available display)
                self.config.update_settings({"selected_display": 0})
                # Only set manager's selected_display if manager exists
                if hasattr(self, "manager") and self.manager is not None:
                    self.manager.selected_display = 0
                    print("[INIT] Manager display setting updated")
                else:
                    print(
                        "[INIT] Manager not yet initialized, display setting saved to config"
                    )

            elif display_count > 1:
                # Show error message with display information
                display_info = []
                for i, screen in enumerate(screens):
                    geometry = screen.geometry()
                    name = screen.name() or f"Display {i+1}"
                    resolution = f"{geometry.width()}x{geometry.height()}"
                    display_info.append(f"• {name}: {resolution}")

                display_list = "\n".join(display_info)

                print(
                    f"[ERROR] Multiple displays detected ({display_count}). App will exit."
                )

                # Show prominent center dialog instead of system notification
                Dialogs.show_multiple_display_error(display_count, display_list)

                # Exit the application immediately after dialog closes
                print("[INIT] Exiting due to multiple display configuration")
                QApplication.quit()
                sys.exit(1)

        except Exception as e:
            print(f"[ERROR] Display check failed: {e}")
            import traceback

            print(f"[ERROR] Traceback: {traceback.format_exc()}")

    def _on_screen_added(self, screen):
        """Handle when a new screen is connected during runtime"""
        print(f"[DISPLAY] ===== SCREEN ADDED =====")
        print(f"[DISPLAY] Screen added: {screen.name()}")
        print(f"[DISPLAY] Current screen count: {len(QApplication.screens())}")
        print(f"[DISPLAY] Calling _check_display_count_runtime")
        self._check_display_count_runtime("added")
        print(f"[DISPLAY] ===== SCREEN ADDED END =====")

    def _on_screen_removed(self, screen):
        """Handle when a screen is disconnected during runtime"""
        print(f"Screen removed: {screen.name()}")
        # We don't need to check when displays are removed, only when added
        # But let's log the current count for debugging
        screens = QApplication.screens()
        print(f"Remaining displays after removal: {len(screens)}")

    def _check_display_count_runtime(self, change_type):
        """Check display count during runtime and exit if multiple displays detected"""
        try:
            screens = QApplication.screens()
            display_count = len(screens)

            print(f"Display {change_type}: Now {display_count} display(s) connected")

            # Show immediate system notification for debugging
            if display_count > 1:
                print("[IMMEDIATE] Sending immediate system notification...")
                title = (
                    "멀티 디스플레이 감지"
                    if change_type == "added"
                    else "Multiple Display Detected"
                )
                rumps.notification(
                    title,
                    (
                        "앱이 곧 종료됩니다"
                        if title.startswith("멀티")
                        else "App will exit soon"
                    ),
                    (
                        f"{display_count}개의 디스플레이가 감지되었습니다."
                        if title.startswith("멀티")
                        else f"Detected {display_count} displays."
                    ),
                    sound=True,
                )
                print("[IMMEDIATE] Immediate notification sent")

            if display_count > 1:
                # Show error message with display information
                display_info = []
                for i, screen in enumerate(screens):
                    geometry = screen.geometry()
                    name = screen.name() or f"Display {i+1}"
                    resolution = f"{geometry.width()}x{geometry.height()}"
                    display_info.append(f"• {name}: {resolution}")

                display_list = "\n".join(display_info)

                print(
                    f"ERROR: Multiple displays detected during runtime ({display_count}). App will exit."
                )
                print(f"Displays:\n{display_list}")

                # Use QTimer to ensure dialog is shown in main thread
                def show_dialog_and_exit():
                    try:
                        print("[DIALOG] ===== SHOWING MULTI-DISPLAY DIALOG =====")
                        print(f"[DIALOG] Display count: {display_count}")
                        print(f"[DIALOG] Display list: {display_list}")

                        # Force bring QApplication to front
                        if self.qt_app:
                            self.qt_app.processEvents()
                            # QApplication doesn't have activateWindow, just process events

                        # Show prominent center dialog
                        print("[DIALOG] Calling Dialogs.show_multiple_display_error...")
                        result = Dialogs.show_multiple_display_error(
                            display_count, display_list
                        )
                        print(f"[DIALOG] Dialog result: {result}")
                        print("[DIALOG] Dialog closed, proceeding to exit...")

                        # Exit the application immediately after dialog closes
                        print(
                            "[APP] Exiting due to multiple display configuration during runtime..."
                        )
                        self._force_quit_app()

                    except Exception as e:
                        print(f"[ERROR] Error showing dialog: {e}")
                        import traceback

                        print(f"[ERROR] Traceback: {traceback.format_exc()}")
                        # Force exit even if dialog fails
                        self._force_quit_app()

                print("[TIMER] Setting QTimer.singleShot for dialog...")
                # Use QTimer to ensure proper execution in main thread
                QTimer.singleShot(100, show_dialog_and_exit)
                print("[TIMER] QTimer.singleShot set successfully")

        except Exception as e:
            print(f"Error checking display count during runtime: {e}")
            import traceback

            print(traceback.format_exc())

    def _force_quit_app(self):
        """Force quit the application"""
        print("Force quitting application...")
        QApplication.quit()
        sys.exit(1)

    def _handle_capture_start(self):
        """Handle capture start event"""
        print("\n=== Handling Capture Start ===")
        self.reset_state_tracking()

        # 리마인더 카운터 초기화
        self.reminder_counter = 0
        print("Reminder counter reset to 0")

        # Start auto capture
        self.manager.start(self.do_capture, self.update_intention_status)

        # Start reminder timer if in reminder mode
        if APP_MODE == APP_MODE_REMINDER and self.reminder_timer:
            print("Starting reminder timer in capture start...")
            self.reminder_timer.start()
            print(
                f"Reminder timer started - Interval: {self.reminder_timer.interval()}ms"
            )
            print(f"Timer is active: {self.reminder_timer.isActive()}")

        self.set_recording_icon()
        print("=== Capture Start Handling Complete ===\n")

    def _handle_capture_stop(self):
        """Handle capture stop event"""
        print("\n=== Handling Capture Stop ===")

        # Stop auto capture
        self.manager.stop()

        # 리마인더 카운터 초기화
        self.reminder_counter = 0

        # Stop reminder timer if active
        if self.reminder_timer and self.reminder_timer.isActive():
            print("Stopping reminder timer...")
            self.reminder_timer.stop()
            print("Reminder timer stopped")

        self.set_default_icon()
        print("=== Capture Stop Handling Complete ===\n")

    def reset_state_tracking(self):
        """Reset all state tracking variables"""
        self.message_update_flag = 0
        self.consecutive_focus_count = 0
        self.focus_notification_threshold = 15
        self.acquire_threshold = 2
        self.release_threshold = 2
        self.current_state = 0
        self.consecutive_ones = 0
        self.consecutive_zeros = 0
        self.current_message = None
        self.last_server_message = None

    def check_initial_setup(self):
        """Check if initial setup is completed"""
        try:
            # Ensure storage directories exist
            self.storage.setup_storage_directory()

            # Check user configuration
            user_info = self.config.get_user_info()
            has_user_config = user_info.get("name") and user_info.get("device_name")

            if not has_user_config:
                print("[INIT] User configuration incomplete - will prompt for setup")
            else:
                print(f"[INIT] User configuration found: {user_info.get('name')}")

            return has_user_config

        except Exception as e:
            print(f"[ERROR] Initial setup check failed: {e}")
            return False

    def do_capture(self):
        """Execute capture"""
        self.manager.do_activity_capture()

    @rumps.clicked("Settings", "User Settings")
    def show_user_settings(self, _):
        """Handle user settings menu click"""
        from .ui.settings_dialog import UserSettingsDialog

        dialog = UserSettingsDialog(self.config.get_user_info())

        if dialog.exec() == QDialog.DialogCode.Accepted:
            user_input = dialog.get_user_input()
            name, password, device = (
                user_input["name"],
                user_input["password"],
                user_input["device"],
            )

            if name and password and device:
                self.config.set_user_info(
                    name=name, password=password, device_name=device
                )
                Dialogs.show_notification(
                    "Settings Updated",
                    "User credentials have been saved",
                    f"User ID: {name}\nDevice: {device}",
                )
            else:
                Dialogs.show_notification(
                    "Settings Error",
                    "Credentials Required",
                    "Please enter both User ID and Password.",
                )

    @rumps.clicked("Settings", "Language Settings")
    def show_language_settings(self, _):
        """Handle language settings menu click"""
        from .ui.settings_dialog import LanguageSettingsDialog

        dialog = LanguageSettingsDialog()

        # Connect language change signal
        dialog.language_changed.connect(self._on_language_changed)

        dialog.exec()

    def _on_language_changed(self, new_language):
        """Handle language change event"""
        print(f"[LANGUAGE] Language changed to: {new_language}")

        # For rumps, we need to update menu items
        try:
            # Clear existing menu items
            self.menu.clear()

            # Recreate the menu with new language
            new_menu = AppMenu.create_menu(self)

            # Add new menu items
            for item in new_menu:
                if item is None:
                    # Separator
                    self.menu.add(rumps.separator)
                else:
                    self.menu.add(item)

        except Exception as e:
            print(f"[LANGUAGE] Error updating menu: {e}")

        # Refresh dashboard UI
        if hasattr(self, "dashboard") and self.dashboard:
            self.dashboard.refresh_ui_language()

    # Display Settings menu removed - single display auto-selection

    # Sound Settings menu removed - sound functionality disabled

    def update_intention_status(self, server_response):
        """Update intention status from server response"""
        try:
            # Get output value and message
            output_raw = float(server_response.get("output", 0))
            output = 1 if output_raw > 0.6 else 0
            current_message = server_response.get("message", "")
            sentences = re.split(r"(?<=[.!?])\s+", current_message)
            if len(sentences) > 1:
                current_message = "\n".join(sentences)

            # Simple status log
            status = "FOCUSED" if output == 0 else "DISTRACTED"
            print(f"[{status}] {current_message}")

            # In basic and reminder modes, we only process the response but don't update UI or show notifications
            if APP_MODE in [APP_MODE_BASIC, APP_MODE_REMINDER]:
                return

            if not current_message:
                current_message = (
                    "Focus: Stay on task!"
                    if output == 0
                    else "Distracted: Return to your goal!"
                )

            # Store server message for later use
            self.last_server_message = current_message

            # Update consecutive counters
            if output == 1:  # Now distracted state
                self.consecutive_ones += 1
                self.consecutive_zeros = 0
            else:  # Now focused state
                self.consecutive_zeros += 1
                self.consecutive_ones = 0

            # Check if this is the first message
            is_first_message = self.current_message is None

            self.message_update_flag += 1

            # For the first message, set the initial state based on the first output
            if is_first_message:
                self.current_state = output

                # Start sound playback first (async)
                # if self.current_state == 0:  # Now focused state
                #     self.play_sound()
                # else:  # Now distracted state
                #     self.play_sound()

                # Then update the UI
                print(f"[UI] Update intention level on dashboard")
                self.dashboard.update_intention_level(
                    level=self.current_state,
                    message=current_message,
                    raw_value=output_raw,
                )
                self.message_update_flag = 0

                # Show notification
                notification_id = f"intention_status_{int(time.time() * 1000)}"

                # Set notification flag for next LLM analysis
                self.next_analysis_has_notification = True
                if self.manager:
                    self.manager.set_notification_flag(True)

                # Store notification context (same data as dashboard feedback uses)
                context_data = {
                    "ai_judgement": self.current_state,  # 0=focused, 1=distracted
                    "llm_response": getattr(self.dashboard, "last_llm_response", None),
                    "image_path": getattr(self.dashboard, "last_analyzed_image", None),
                    "image_id": getattr(
                        self.dashboard, "last_llm_response_image_id", None
                    ),
                    "current_task": self.dashboard.current_task,
                    "message": current_message,
                    "timestamp": time.time(),
                }
                self._store_notification_context(notification_id, context_data)

                # Only show feedback buttons in Treatment mode
                if APP_MODE == APP_MODE_FULL:
                    self.notifications.show_notification(
                        "알림",
                        self.dashboard.current_task,
                        current_message,
                        self.current_state,
                        on_good=lambda nid=notification_id: self._handle_notification_feedback(
                            "good", nid
                        ),
                        on_bad=lambda nid=notification_id: self._handle_notification_feedback(
                            "bad", nid
                        ),
                        dashboard=self.dashboard,
                        notification_context=context_data,
                    )
                else:
                    # Reminder and Basic modes: no feedback buttons
                    self.notifications.show_notification(
                        "알림",
                        self.dashboard.current_task,
                        current_message,
                        self.current_state,
                        dashboard=self.dashboard,
                    )
                self.current_message = current_message
            else:
                # Handle state transitions for subsequent messages
                state_changed = self._handle_state_transition(output)

                if state_changed or self.message_update_flag > 5:
                    print(f"[UI] Update intention level on dashboard")
                    self.dashboard.update_intention_level(
                        level=self.current_state,
                        message=current_message,
                        raw_value=output_raw,
                    )
                    self.message_update_flag = 0

                # Update dashboard and show notification only on state change
                if state_changed:
                    # Start sound playback first (async)
                    # if self.current_state == 0:  # Now focused state
                    #     self.play_sound()
                    # else:  # Now distracted state
                    #     self.play_sound()

                    # Show notification
                    notification_id = f"intention_status_{int(time.time() * 1000)}"

                    # Set notification flag for next LLM analysis
                    self.next_analysis_has_notification = True
                    if self.manager:
                        self.manager.set_notification_flag(True)

                    # Store notification context (use displayed message for accurate feedback)
                    context_data = {
                        "ai_judgement": self.current_state,  # 0=focused, 1=distracted
                        "llm_response": getattr(
                            self.dashboard, "displayed_message_response", None
                        )
                        or getattr(self.dashboard, "last_llm_response", None),
                        "image_path": getattr(
                            self.dashboard, "last_analyzed_image", None
                        ),
                        "image_id": getattr(
                            self.dashboard, "displayed_message_image_id", None
                        )
                        or getattr(self.dashboard, "last_llm_response_image_id", None),
                        "current_task": self.dashboard.current_task,
                        "message": current_message,
                        "timestamp": time.time(),
                    }
                    self._store_notification_context(notification_id, context_data)

                    # Only show feedback buttons in Treatment mode
                    if APP_MODE == APP_MODE_FULL:
                        self.notifications.show_notification(
                            "알림",
                            self.dashboard.current_task,
                            current_message,
                            self.current_state,
                            on_good=lambda nid=notification_id: self._handle_notification_feedback(
                                "good", nid
                            ),
                            on_bad=lambda nid=notification_id: self._handle_notification_feedback(
                                "bad", nid
                            ),
                            dashboard=self.dashboard,
                            notification_context=context_data,
                        )
                    else:
                        # Reminder and Basic modes: no feedback buttons
                        self.notifications.show_notification(
                            "알림",
                            self.dashboard.current_task,
                            current_message,
                            self.current_state,
                            dashboard=self.dashboard,
                        )
                    self.current_message = current_message

            # Handle focus reminders
            self._handle_focus_reminders(output, current_message)

        except Exception as e:
            print(f"[ERROR] {e}")

    def _handle_state_transition(self, output):
        """Handle state transition logic"""
        # Transition to distracted state when consecutive ones reach threshold
        if self.current_state == 0 and self.consecutive_ones >= self.acquire_threshold:
            self.current_state = 1
            print(
                f"[STATE] Changed to DISTRACTED (consecutive: {self.consecutive_ones}/{self.acquire_threshold})"
            )
            return True
        # Transition back to focused state when consecutive zeros reach threshold
        elif (
            self.current_state == 1 and self.consecutive_zeros >= self.release_threshold
        ):
            self.current_state = 0
            self.consecutive_focus_count = 1
            print(
                f"[STATE] Changed to FOCUSED (consecutive: {self.consecutive_zeros}/{self.release_threshold})"
            )
            return True
        return False

    def _handle_focus_reminders(self, output, message):
        """Handle reminder logic for distracted state"""
        # Skip reminders in basic and reminder modes
        if APP_MODE in [APP_MODE_BASIC, APP_MODE_REMINDER]:
            return

        # Check for distracted state reminders
        if self.current_state == 1 and output == 1:
            self.consecutive_focus_count += 1

            if self.consecutive_focus_count >= self.focus_notification_threshold:
                print(
                    f"[REMINDER] Triggered after {self.consecutive_focus_count} consecutive distracted messages"
                )

                # Ensure we have a valid message for the reminder
                reminder_message = message
                if not reminder_message or reminder_message.strip() == "":
                    reminder_message = "Still distracted! Try to refocus on your task."

                # Start sound playback first (async)
                # self.play_sound()

                # Update the UI
                current_raw_value = getattr(
                    self.dashboard, "current_raw_value", 0.5
                )  # Use existing raw value or neutral default
                self.dashboard.update_intention_level(1, message, current_raw_value)

                # Use the dashboard's current task
                task = self.dashboard.current_task
                if not task or task.strip() == "":
                    task = "your task"

                try:
                    # Show notification with task context
                    notification_id = f"intention_reminder_{int(time.time() * 1000)}"

                    # Set notification flag for next LLM analysis
                    self.next_analysis_has_notification = True
                    if self.manager:
                        self.manager.set_notification_flag(True)

                    # Store notification context (use displayed message for accurate feedback)
                    context_data = {
                        "ai_judgement": 1,  # Always distracted state for reminders
                        "llm_response": getattr(
                            self.dashboard, "displayed_message_response", None
                        )
                        or getattr(self.dashboard, "last_llm_response", None),
                        "image_path": getattr(
                            self.dashboard, "last_analyzed_image", None
                        ),
                        "image_id": getattr(
                            self.dashboard, "displayed_message_image_id", None
                        )
                        or getattr(self.dashboard, "last_llm_response_image_id", None),
                        "current_task": task,
                        "message": reminder_message,
                        "timestamp": time.time(),
                    }
                    self._store_notification_context(notification_id, context_data)

                    # Only show feedback buttons in Treatment mode
                    if APP_MODE == APP_MODE_FULL:
                        self.notifications.show_notification(
                            "알림",
                            task,
                            reminder_message,
                            1,  # Always distracted state for reminders
                            on_good=lambda nid=notification_id: self._handle_notification_feedback(
                                "good", nid
                            ),
                            on_bad=lambda nid=notification_id: self._handle_notification_feedback(
                                "bad", nid
                            ),
                            dashboard=self.dashboard,
                            notification_context=context_data,
                        )
                    else:
                        # Reminder and Basic modes: no feedback buttons
                        self.notifications.show_notification(
                            "알림",
                            task,
                            reminder_message,
                            1,  # Always distracted state for reminders
                            dashboard=self.dashboard,
                        )
                except Exception as e:
                    print(f"[ERROR] Notification failed: {e}")

                # Reset counter
                self.consecutive_focus_count = 0
                self.current_message = message

    def set_recording_icon(self):
        """Change icon to recording state"""
        self.icon = self.recording_icon

    def set_default_icon(self):
        """Restore default icon"""
        self.icon = self.default_icon

    def play_sound(self):
        """Play notification sound"""
        # Skip sound only in basic mode
        if APP_MODE == APP_MODE_BASIC:
            print("[SOUND] Basic mode: Skipping sound playback")
            return

        try:
            sound_settings = self.config.get_sound_settings()

            # Get current state (0 = focused, 1 = distracted)
            if hasattr(self, "current_state") and self.current_state == 1:
                # Distracted state - use distract sound
                sound_file = sound_settings.get("distract_sound", "focus_1.mp3")
                state_text = "DISTRACTED"
            else:
                # Focused state (default) - use focus sound
                sound_file = sound_settings.get("focus_sound", "good_1.mp3")
                state_text = "FOCUSED"

            # Construct full path - fix the path issue
            sound_path = os.path.join(
                os.path.dirname(os.path.abspath(__file__)), "assets", sound_file
            )

            print(f"[SOUND] Playing {state_text} sound: {sound_file}")

            if os.path.exists(sound_path):
                print(f"[SOUND] Sound file found: {sound_path}")
                # Play sound in background
                threading.Thread(
                    target=self._play_sound_background, args=(sound_path,)
                ).start()
            else:
                print(f"[SOUND] Sound file not found: {sound_path}")

        except Exception as e:
            print(f"[SOUND] Error: {e}")

    def _play_sound_background(self, sound_path):
        """Play sound in background"""
        try:
            # Play sound asynchronously (no UI blocking)
            result = subprocess.run(
                ["afplay", sound_path], capture_output=True, text=True
            )
            if result.returncode == 0:
                print(f"[SOUND] Successfully played: {os.path.basename(sound_path)}")
            else:
                print(f"[SOUND] Failed to play: {result.stderr}")
        except Exception as e:
            print(f"[SOUND] Background playback error: {e}")

    def quit(self, _):
        """Quit the application"""
        print("[APP] Manual quit requested...")
        self._safe_shutdown()

    def start_auto_capture(self, capture_callback, analysis_callback):
        """Start auto capture with proper task directory setup"""
        # Check if user ID and password are set
        user_info = self.config.get_user_info()
        if not user_info or not user_info.get("name") or not user_info.get("password"):
            from .ui.dialogs import Dialogs

            Dialogs.show_error(
                "Credentials Required",
                "Please enter your assigned User ID and Password in Settings > User Settings before starting.",
            )
            return False

        # Update task directory before starting capture
        if self.dashboard and self.dashboard.current_task:
            self.update_task(self.dashboard.current_task)

        # Start capture process
        self.capture_callback = capture_callback
        self.analysis_callback = analysis_callback

        print("\n=== Starting Auto Capture ===")
        print(f"Current APP_MODE: {APP_MODE}")

        # Start timers
        self.capture_timer.start(CAPTURE_INTERVAL * 1000)
        self.llm_timer.start(LLM_INVOKE_INTERVAL * 1000)
        print("Capture and LLM timers started")

        # Start reminder timer if in reminder mode
        print(f"\n=== Reminder Timer Status ===")
        print(f"APP_MODE: {APP_MODE}")
        print(f"APP_MODE == APP_MODE_REMINDER: {APP_MODE == APP_MODE_REMINDER}")
        print(f"self.reminder_timer exists: {self.reminder_timer is not None}")

        if APP_MODE == APP_MODE_REMINDER:
            if self.reminder_timer:
                print("Starting reminder timer...")
                self.reminder_timer.start()
                print("Reminder timer started successfully")
                print(f"Timer interval: {self.reminder_timer.interval()} ms")
                print(f"Timer is active: {self.reminder_timer.isActive()}")
            else:
                print("ERROR: reminder_timer is None!")
        else:
            print("Not in reminder mode, skipping reminder timer")

        # Show recording indicator
        self.update_recording_indicator()
        return True

    def _is_korean_text(self, text):
        """Check if text contains Korean characters"""
        import re

        return bool(re.search(r"[가-힣]", text))

    def _handle_control_group_reminder(self):
        """Handle reminder notification"""
        print("\n=== Control Group Reminder Timer Triggered ===")
        if not self.dashboard.current_task:
            print("No current task, skipping reminder")
            return

        # 리마인더 메시지 생성 (언어별 구분) - 시간 정보 제거
        task = self.dashboard.current_task
        if self._is_korean_text(task):
            # 한글이 포함된 경우
            message = f'당신이 정한 목표는 "{task}" 입니다!'
        else:
            # 영어만 있는 경우
            message = f'Your intention is "{task}"!'

        print(f"Sending Control Group Reminder notification for task: {task}")
        print(f"Message: {message}")

        # self.play_sound()

        current_raw_value = getattr(
            self.dashboard, "current_raw_value", 0.5
        )  # Use existing raw value or neutral default
        self.dashboard.update_intention_level(0, message, current_raw_value)

        notification_id = f"focus_reminder_{int(time.time() * 1000)}"

        # Set notification flag for next LLM analysis
        self.next_analysis_has_notification = True
        if self.manager:
            self.manager.set_notification_flag(True)

        # Store notification context (use displayed message for accurate feedback)
        context_data = {
            "ai_judgement": 0,  # Always focused state for control group reminders
            "llm_response": getattr(self.dashboard, "displayed_message_response", None)
            or getattr(self.dashboard, "last_llm_response", None),
            "image_path": getattr(self.dashboard, "last_analyzed_image", None),
            "image_id": getattr(self.dashboard, "displayed_message_image_id", None)
            or getattr(self.dashboard, "last_llm_response_image_id", None),
            "current_task": task,
            "message": message,
            "timestamp": time.time(),
        }
        self._store_notification_context(notification_id, context_data)

        # Only show feedback buttons in Treatment mode
        if APP_MODE == APP_MODE_FULL:
            self.notifications.show_notification(
                "알림",
                task,
                message,
                0,  # Always show green for reminder notifications
                on_good=lambda nid=notification_id: self._handle_notification_feedback(
                    "good", nid
                ),
                on_bad=lambda nid=notification_id: self._handle_notification_feedback(
                    "bad", nid
                ),
                dashboard=self.dashboard,
                notification_context=context_data,
            )
        else:
            # Reminder and Basic modes: no feedback buttons
            self.notifications.show_notification(
                "알림",
                task,
                message,
                0,  # Always show green for reminder notifications
                dashboard=self.dashboard,
            )

            # 🔥 CRITICAL: Clean up old notification contexts in Reminder mode
            # (since no feedback buttons mean _clear_old_notification_contexts is never called)
            print("[NOTIFICATION] Cleaning up old contexts in Reminder mode...")
            self._clear_old_notification_contexts()

        print("Control Group Reminder notification sent")

    def _handle_reminder(self):
        """Handle timer-based reminder"""
        print("\n=== Reminder Timer Triggered ===")
        print(f"Current app mode: {APP_MODE}")
        print("25-minute reminder interval")

        # 🔥 CRITICAL: Proactive memory cleanup before reminder in Reminder mode
        print("[REMINDER] Performing proactive memory cleanup...")

        # Force cleanup of old notification contexts
        self._clear_old_notification_contexts()

        # Force garbage collection to free memory
        import gc

        before_gc = len(gc.get_objects())
        gc.collect()
        after_gc = len(gc.get_objects())
        print(
            f"[REMINDER] Garbage collection: {before_gc} -> {after_gc} objects ({before_gc - after_gc} freed)"
        )

        self._handle_control_group_reminder()

    # _handle_dashboard_sound_request method removed - sound functionality disabled

    def _handle_notification_feedback(self, feedback_type, notification_id):
        """Handle feedback from notification buttons - connects to dashboard feedback system"""
        try:
            print(
                f"[NOTIFICATION] Feedback received: {feedback_type} for notification: {notification_id}"
            )

            # Get stored notification context
            context = self._get_notification_context(notification_id)
            if not context:
                print(
                    f"[NOTIFICATION] Error: No context found for notification {notification_id}"
                )

                return

            # Use stored context data (same as dashboard feedback logic)
            current_task = context.get("current_task", "Unknown Task")
            ai_judgement_value = context.get("ai_judgement", 1)  # Default to distracted
            ai_judgement = "focused" if ai_judgement_value == 0 else "distracted"

            print(
                f"[NOTIFICATION] Using stored AI judgment: {ai_judgement_value} ({ai_judgement})"
            )
            print(
                f"[NOTIFICATION] Context timestamp: {context.get('timestamp', 'unknown')}"
            )

            print(f"[NOTIFICATION] Processing feedback: {ai_judgement}_{feedback_type}")
            # Get the feedback manager from dashboard
            if self.dashboard and hasattr(self.dashboard, "feedback_manager"):
                feedback_manager = self.dashboard.feedback_manager

                # 🔥 CRITICAL: 버튼 클릭 시점의 dashboard 상태 사용 (메시지 피드백과 일치시키기 위해)
                button_click_image_id = getattr(
                    self.dashboard, "displayed_message_image_id", None
                ) or getattr(self.dashboard, "last_llm_response_image_id", None)
                button_click_response = getattr(
                    self.dashboard, "displayed_message_response", None
                ) or getattr(self.dashboard, "last_llm_response", None)
                button_click_image_path = getattr(
                    self.dashboard, "last_analyzed_image", None
                )

                print(f"[NOTIFICATION] Button click image ID: {button_click_image_id}")
                print(
                    f"[NOTIFICATION] vs Stored context ID: {context.get('image_id', 'None')}"
                )

                if button_click_image_id != context.get("image_id"):
                    print(
                        f"[NOTIFICATION] ⚠️  Using button click ID instead of stored context ID!"
                    )

                # Use button click data instead of stored context data
                last_llm_response = button_click_response
                last_image_path = button_click_image_path
                last_image_id = button_click_image_id

                # Debug logging for data availability
                print(f"[NOTIFICATION] Context data check:")
                print(
                    f"  - llm_response: {'Available' if last_llm_response else 'Missing'}"
                )
                print(
                    f"  - image_path: {'Available' if last_image_path else 'Missing'}"
                )
                print(f"  - image_id: {'Available' if last_image_id else 'Missing'}")

                # Process feedback using the same system as dashboard buttons
                feedback_manager.process_feedback(
                    task_name=current_task,
                    llm_response=(
                        last_llm_response
                        if last_llm_response
                        else "```json"
                        "{"
                        "   'reason': 'No response, which have been processed as output: 0.0 (aligned)'"
                        "   'output': 0.0"
                        "}"
                        "```"
                    ),
                    image_path=last_image_path,
                    ai_judgement=ai_judgement,
                    feedback_type=feedback_type,
                    image_id=last_image_id,
                )
                print(
                    f"[NOTIFICATION] Feedback processed successfully: {ai_judgement}_{feedback_type}"
                )

                # Clean up old contexts
                self._clear_old_notification_contexts()

            else:
                print(
                    "[NOTIFICATION] Error: Dashboard or feedback_manager not available"
                )

        except Exception as e:
            print(f"[NOTIFICATION] Error processing feedback: {e}")
            import traceback

            traceback.print_exc()

    def _store_notification_context(self, notification_id, context_data):
        """Store notification context data for later feedback use"""
        self.notification_context[notification_id] = context_data
        print(
            f"[NOTIFICATION] Stored context for {notification_id}: {list(context_data.keys())}"
        )

    def _get_notification_context(self, notification_id):
        """Get stored notification context data"""
        return self.notification_context.get(notification_id, {})

    def _clear_old_notification_contexts(self):
        """Clear old notification contexts to prevent memory leaks"""
        # 🔥 CRITICAL: Different limits for different modes to prevent memory accumulation
        if APP_MODE == APP_MODE_REMINDER:
            # Reminder mode: Keep only last 3 contexts (no feedback needed)
            limit = 3
        elif APP_MODE == APP_MODE_BASIC:
            # Basic mode: Keep only last 5 contexts (minimal feedback)
            limit = 3
        else:
            # Full mode: Keep last 10 contexts (full feedback support)
            limit = 10

        if len(self.notification_context) > limit:
            # Remove oldest contexts
            sorted_keys = sorted(self.notification_context.keys())
            contexts_to_remove = len(self.notification_context) - limit
            for key in sorted_keys[:contexts_to_remove]:
                del self.notification_context[key]
            print(
                f"[NOTIFICATION] Cleaned up {contexts_to_remove} old contexts, kept {limit} for {APP_MODE} mode"
            )

    def invoke_llm(self):
        """Invoke LLM analysis through manager"""
        if self.manager:
            # Pass notification flag to manager and reset it
            has_notification = self.next_analysis_has_notification
            self.next_analysis_has_notification = False

            self.manager.invoke_llm(has_notification=has_notification)

    def _setup_auto_login(self):
        """Setup auto-login after app is fully initialized"""
        try:
            # Determine app name based on APP_MODE for auto-login registration
            if APP_MODE == APP_MODE_FULL:
                app_name = "Purple(new)"
            elif APP_MODE == APP_MODE_REMINDER:
                app_name = "Blue(new)"
            elif APP_MODE == APP_MODE_BASIC:
                app_name = "Orange(new)"
            else:
                app_name = "Intention(new)"

            print(f"[INIT] Setting up auto-login for: {app_name}")
            ensure_login_item(app_name)
        except Exception as e:
            print(f"[ERROR] Failed to setup auto-login: {e}")

    def _safe_shutdown(self):
        """Handle safe shutdown - Enhanced for thread safety"""
        print("[APP] Starting comprehensive safe shutdown...")

        # Set shutdown flag to prevent new threads from starting
        import threading

        shutdown_event = threading.Event()
        shutdown_event.set()

        # Clean up dashboard first (this will clean up all managers)
        if self.dashboard:
            print("[APP] Cleaning up dashboard and all managers...")
            self.dashboard.cleanup()

        # Stop manager second (redundant but safe)
        if self.manager:
            print("[APP] Stopping thread manager...")
            self.manager.stop()

        # 🔥 CRITICAL: Clean up reminder timer in Reminder mode to prevent memory leak
        if hasattr(self, "reminder_timer") and self.reminder_timer:
            print("[APP] Cleaning up reminder timer...")
            try:
                if self.reminder_timer.isActive():
                    self.reminder_timer.stop()
                    print("[APP] Reminder timer stopped")
                self.reminder_timer.timeout.disconnect()
                self.reminder_timer.deleteLater()
                self.reminder_timer = None
                print("[APP] Reminder timer cleaned up successfully")
            except Exception as e:
                print(f"[APP] Error cleaning up reminder timer: {e}")

        # Additional cleanup: ensure all QThread objects are properly terminated
        print("[APP] Performing final thread cleanup...")
        self._cleanup_remaining_threads()

        # Wait longer for threads to fully terminate
        from PyQt6.QtCore import QTimer
        import time

        print("[APP] Waiting for threads to complete...")
        time.sleep(1.5)  # Give threads more time to cleanup

        # Force Python GC to run multiple times with delays
        import gc

        print("[APP] Running garbage collection...")
        for i in range(3):
            before_gc = len(gc.get_objects())
            gc.collect()
            after_gc = len(gc.get_objects())
            print(
                f"[APP] GC round {i+1}: {before_gc} -> {after_gc} objects ({before_gc - after_gc} freed)"
            )
            time.sleep(0.2)

        # 🔥 CRITICAL: Final memory usage report for debugging
        import threading

        final_thread_count = threading.active_count()
        final_object_count = len(gc.get_objects())
        print(f"[APP] Final memory state:")
        print(f"[APP]   Active threads: {final_thread_count}")
        print(f"[APP]   Python objects: {final_object_count}")
        print(
            f"[APP]   Notification contexts: {len(getattr(self, 'notification_context', {}))}"
        )

        print("[APP] Safe shutdown complete, quitting Qt application...")

        # Final check for any remaining threads before quitting
        remaining_threads = threading.active_count()
        if remaining_threads > 1:  # Main thread is always counted
            print(f"[APP] Warning: {remaining_threads - 1} threads still active")

        self.qt_app.quit()
        rumps.quit_application()

    def _cleanup_remaining_threads(self):
        """Final cleanup for any remaining QThread objects"""
        try:
            from PyQt6.QtCore import QThread
            import gc

            # Force garbage collection to find all objects
            gc.collect()

            # Find all QThread objects
            thread_objects = []
            for obj in gc.get_objects():
                if isinstance(obj, QThread) and obj.isRunning():
                    thread_objects.append(obj)

            if thread_objects:
                print(
                    f"[APP] Found {len(thread_objects)} running QThread objects, cleaning up..."
                )

                for thread in thread_objects:
                    try:
                        thread_name = getattr(thread, "objectName", lambda: "Unknown")()
                        print(f"[APP] Cleaning up thread: {thread_name}")

                        # Try safe_quit if available
                        if hasattr(thread, "safe_quit"):
                            thread.safe_quit()
                        else:
                            # Fallback to standard cleanup
                            thread.quit()
                            if not thread.wait(2000):
                                print(
                                    f"[APP] Thread {thread_name} did not quit gracefully, terminating..."
                                )
                                thread.terminate()
                                thread.wait(2000)
                            thread.deleteLater()

                    except Exception as e:
                        print(f"[APP] Error cleaning up thread: {e}")

                print("[APP] Final thread cleanup complete")
            else:
                print("[APP] No running QThread objects found")

        except Exception as e:
            print(f"[APP] Error in final thread cleanup: {e}")
