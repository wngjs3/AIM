import os
import subprocess
import uuid
import time
from PyQt6.QtWidgets import QSystemTrayIcon
from PyQt6.QtCore import QTimer

# --- Desktop Notifier for macOS Sequoia and beyond ---
import asyncio
from desktop_notifier import DesktopNotifier, Button, ReplyField

from ..config.constants import APP_MODE, APP_MODE_FULL

# Single notifier instance for the whole module
notifier = DesktopNotifier(app_name="Intention")


class NotificationManager:
    def __init__(self):
        self.last_notification_time = 0
        self.notification_cooldown = 2  # seconds

        self.setup_notification_permissions()

    def setup_notification_permissions(self):
        """Request notification permissions on macOS"""
        try:
            # Explicitly ask macOS for notification permission
            try:
                from desktop_notifier import PermissionState

                async def _ask():
                    state = await notifier.request_permission()
                    return state

                state = asyncio.run(_ask())
                if state != PermissionState.GRANTED:
                    print(
                        "[WARN] Notification permission not granted. "
                        "Open System Settings → Notifications and allow 'Python' (or your bundle name)."
                    )
            except ImportError as import_error:
                print(f"[WARN] Could not import PermissionState: {import_error}")
                print(
                    "[INFO] Notification permissions will be handled by macOS automatically"
                )
                # Continue without explicit permission request - macOS will handle it

        except Exception as e:
            print(f"[ERROR] Permission request failed: {e}")
            print("[INFO] Continuing without explicit permission request")

    def is_fullscreen_active(self):
        """Check if any window is in fullscreen mode using a more reliable method"""
        try:
            script = """
            tell application "System Events"
                set fullscreenWindow to false
                repeat with proc in (processes whose visible is true)
                    try
                        if exists (window 1 of proc) then
                            if value of attribute "AXFullScreen" of window 1 of proc is true then
                                set fullscreenWindow to true
                                exit repeat
                            end if
                        end if
                    end try
                end repeat
                return fullscreenWindow
            end tell
            """
            result = subprocess.run(
                ["osascript", "-e", script], capture_output=True, text=True
            )
            return "true" in result.stdout.lower()
        except Exception as e:
            print(f"Fullscreen check error: {e}")
            return False

    @staticmethod
    def show_notification(
        title,
        subtitle,
        message,
        state=None,
        on_good=None,
        on_bad=None,
        dashboard=None,
        notification_context=None,
    ):
        """Show notification using macOS notification center

        Args:
            title: Notification title
            subtitle: Notification subtitle
            message: Notification message
            state: AI state (0=focused, 1=distracted)
            on_good: Callback function for Good button click
            on_bad: Callback function for Bad button click
        """
        try:
            # Prepare emoji decorations
            title_with_emoji = NotificationManager._add_emoji_to_title(title, state)
            message_with_emoji = NotificationManager._add_emoji_to_message(
                message, state
            )
            # Combine subtitle into the body because DesktopNotifier.send()
            # does not have a separate 'subtitle' parameter.
            full_message = (
                f"설정한 의도: {subtitle}\n{message_with_emoji}"
                if subtitle
                else message_with_emoji
            )

            # Good/Bad buttons only for notification alerts with callbacks
            buttons = []
            # Only create feedback buttons in Treatment mode
            if title == "알림" and (on_good or on_bad) and APP_MODE == APP_MODE_FULL:
                # Generate unique ID for debugging
                button_id = str(uuid.uuid4())[:8]
                print("🔔" * 20)
                print(f"📱 CREATING NOTIFICATION BUTTONS (Treatment Mode)")
                print(f"   Title: {title}")
                print(f"   Button ID: {button_id}")
                print(f"   Has Good callback: {on_good is not None}")
                print(f"   Has Bad callback: {on_bad is not None}")
                print(f"   APP_MODE: {APP_MODE}")
                print("🔔" * 20)

                def _good():
                    print("=" * 50)
                    print(f"🟢 GOOD BUTTON CLICKED!")
                    print(f"   Button ID: {button_id}")
                    print(f"   Title: {title}")
                    print(f"   Callback exists: {on_good is not None}")
                    print("=" * 50)

                    # 🔥 CRITICAL: 버튼 클릭 시점의 dashboard 상태 저장 (메시지 피드백에서 사용할 용도)
                    current_context = None
                    if dashboard:
                        current_context = {
                            "image_id": getattr(
                                dashboard, "displayed_message_image_id", None
                            )
                            or getattr(dashboard, "last_llm_response_image_id", None),
                            "session_id": getattr(
                                dashboard, "current_session_start_time", "unknown"
                            ),
                            "task_name": getattr(
                                dashboard, "current_task", "Unknown Task"
                            ),
                            "timestamp": time.time(),
                        }
                        print(
                            f"[NOTIFICATION] Button click context - Image ID: {current_context['image_id']}"
                        )
                        print(
                            f"[NOTIFICATION] vs Original context - Image ID: {notification_context.get('image_id', 'None') if notification_context else 'None'}"
                        )

                    # 기존 콜백 실행
                    if on_good:
                        try:
                            print(f"🔄 Executing Good callback...")
                            on_good()
                            print(f"✅ Good callback completed successfully")
                        except Exception as e:
                            print(f"❌ Good callback failed: {e}")
                            import traceback

                            traceback.print_exc()

                    # 2단계: 이유 입력 요청 알림 (버튼 클릭 시점 context 사용)
                    NotificationManager._show_reason_request(
                        "good",
                        button_id,
                        dashboard,
                        current_context or notification_context,
                    )
                    print("⚠️  No Good callback provided" if not on_good else "")

                def _bad():
                    print("=" * 50)
                    print(f"🔴 BAD BUTTON CLICKED!")
                    print(f"   Button ID: {button_id}")
                    print(f"   Title: {title}")
                    print(f"   Callback exists: {on_bad is not None}")
                    print("=" * 50)

                    # 🔥 CRITICAL: 버튼 클릭 시점의 dashboard 상태 저장 (메시지 피드백에서 사용할 용도)
                    current_context = None
                    if dashboard:
                        current_context = {
                            "image_id": getattr(
                                dashboard, "displayed_message_image_id", None
                            )
                            or getattr(dashboard, "last_llm_response_image_id", None),
                            "session_id": getattr(
                                dashboard, "current_session_start_time", "unknown"
                            ),
                            "task_name": getattr(
                                dashboard, "current_task", "Unknown Task"
                            ),
                            "timestamp": time.time(),
                        }
                        print(
                            f"[NOTIFICATION] Button click context - Image ID: {current_context['image_id']}"
                        )
                        print(
                            f"[NOTIFICATION] vs Original context - Image ID: {notification_context.get('image_id', 'None') if notification_context else 'None'}"
                        )

                    # 기존 콜백 실행
                    if on_bad:
                        try:
                            print(f"🔄 Executing Bad callback...")
                            on_bad()
                            print(f"✅ Bad callback completed successfully")
                        except Exception as e:
                            print(f"❌ Bad callback failed: {e}")
                            import traceback

                            traceback.print_exc()

                    # 2단계: 이유 입력 요청 알림 (버튼 클릭 시점 context 사용)
                    NotificationManager._show_reason_request(
                        "bad",
                        button_id,
                        dashboard,
                        current_context or notification_context,
                    )
                    print("⚠️  No Bad callback provided" if not on_bad else "")

                buttons = [
                    Button("✅", on_pressed=_good),
                    Button("❌", on_pressed=_bad),
                ]
            else:
                buttons = []
                if (
                    title == "알림"
                    and (on_good or on_bad)
                    and APP_MODE != APP_MODE_FULL
                ):
                    print(
                        f"[NOTIFICATION] Feedback buttons disabled - APP_MODE: {APP_MODE} (not Treatment mode)"
                    )
                elif title == "알림":
                    print(
                        f"[NOTIFICATION] No feedback callbacks provided - notification only"
                    )

            async def _send():
                # Generate unique identifiers to prevent macOS from merging notifications
                unique_id = str(uuid.uuid4())
                timestamp = int(time.time() * 1000)  # milliseconds

                # For notification alerts, make EVERYTHING unique to force separate notifications
                if title == "알림":
                    # Create completely unique app name for each notification
                    unique_app_name = f"Intention-{unique_id[:8]}"
                    unique_notifier = DesktopNotifier(app_name=unique_app_name)

                    # Keep title clean, only add small unique suffix
                    unique_title = f"{title_with_emoji}"
                    # Keep message clean without debug info
                    unique_message = full_message
                    unique_thread = f"{unique_id}_{timestamp}"

                    await unique_notifier.send(
                        title=unique_title,
                        message=unique_message,
                        buttons=buttons,
                        thread=unique_thread,
                    )

                    print("🚀" * 15)
                    print("🚀 DISPATCHING NOTIFICATION...")
                    print("🚀" * 15)
                    print(f"📤 Notification sent with UNIQUE APP: {unique_app_name}")
                    print(f"📤 Title: {unique_title}")
                    print(f"📤 Message preview: {unique_message[:50]}...")
                    print(f"📤 Thread: {unique_thread}")
                else:
                    # For other notifications, use regular notifier
                    await notifier.send(
                        title=title_with_emoji,
                        message=full_message,
                        buttons=buttons,
                    )
                    print(f"[DEBUG] Regular notification sent: {title}")

            # Safe asyncio handling - check if event loop is already running
            try:
                loop = asyncio.get_running_loop()
                # If we're in an existing loop, schedule the coroutine
                asyncio.ensure_future(_send())
            except RuntimeError:
                # No running loop, create new one
                asyncio.run(_send())

        except Exception as e:
            print(f"[ERROR] Notification failed: {e}")

    @staticmethod
    def _show_reason_request(
        feedback_type, original_button_id, dashboard=None, notification_context=None
    ):
        """Show 2nd notification asking for reason with ReplyField"""
        try:
            # 피드백 타입에 따른 메시지
            if feedback_type == "good":
                reason_title = "✅ 정확했나요?"
                reason_message = "왜 그렇게 생각하셨나요? 이유를 알려주세요."
            else:  # bad
                reason_title = "❌ 부정확했나요?"
                reason_message = "왜 그렇게 생각하셨나요? 이유를 알려주세요."

            def on_replied(user_text):
                print(f"📝 사용자 피드백 완료!")
                print(f"   선택: {feedback_type}")
                print(f"   이유: {user_text}")

                # 🔥 CRITICAL: 버튼 클릭 시점의 context 사용 (notification_context가 이미 button click context)
                button_click_context = notification_context

                # Send feedback message using button click context (same image_id as reflection)
                if (
                    user_text.strip()
                    and dashboard
                    and hasattr(dashboard, "feedback_manager")
                    and button_click_context
                ):
                    # Use button click context for same image_id as reflection
                    print(
                        f"[NOTIFICATION] Using button click context - Image ID: {button_click_context.get('image_id', 'None')}"
                    )
                    dashboard.feedback_manager.send_feedback_message_with_context(
                        user_text.strip(), button_click_context
                    )
                    print(
                        f"[NOTIFICATION] Feedback message sent with button click context"
                    )
                elif (
                    user_text.strip()
                    and dashboard
                    and hasattr(dashboard, "feedback_manager")
                ):
                    # Fallback to current dashboard state if no context available
                    print(
                        f"[NOTIFICATION] No button context, using current dashboard state"
                    )
                    dashboard.feedback_manager.send_feedback_message(user_text.strip())
                    print(
                        f"[NOTIFICATION] Feedback message sent via dashboard (fallback)"
                    )
                else:
                    print(
                        f"[NOTIFICATION] No dashboard or empty text, skipping message send"
                    )

            async def _send_reason_request():
                unique_notifier = DesktopNotifier(
                    app_name=f"Intention-Reason-{original_button_id}"
                )

                reply_field = ReplyField(
                    title="이유",
                    button_title="전송",
                    on_replied=on_replied,
                )

                await unique_notifier.send(
                    title=reason_title,
                    message=reason_message,
                    reply_field=reply_field,
                    buttons=[
                        Button(
                            title="생략",
                            on_pressed=lambda: print("생략"),
                        )
                    ],
                )

                print(f"🔔 이유 입력 요청 알림 전송: {feedback_type}")

            # 비동기 실행
            try:
                loop = asyncio.get_running_loop()
                asyncio.ensure_future(_send_reason_request())
            except RuntimeError:
                asyncio.run(_send_reason_request())

        except Exception as e:
            print(f"[ERROR] Reason request failed: {e}")

    @staticmethod
    def _add_emoji_to_title(title, state):
        if title == "Intentional Computing":
            if state == 0:  # Focused state - use thumbs up
                return title
            else:  # Distracted state - use target
                return title
        elif title == "Intentional Computing":
            # For reminders (always distracted state), use target emoji
            return f"{title}"
        else:
            # For other notifications, keep the original format
            return title

    @staticmethod
    def _add_emoji_to_message(message, state):
        if state == 0:  # Focused state - use thumbs up
            return "📢  " + message
        else:  # Distracted state - use target
            return "‼️  " + message

    @staticmethod
    def show_capture_success(filepath, is_cloud=False):
        """Notification for successful capture"""
        rumps.notification(
            "Screen Capture",
            "Capture & Upload Successful" if is_cloud else "Capture Successful",
            f"Saved to {filepath}" + (" and uploaded to cloud" if is_cloud else ""),
            sound=False,  # Disable default sound
        )

    @staticmethod
    def show_capture_error(message="Failed to capture screen"):
        """Notification for capture failure"""
        rumps.notification(
            "Screen Capture", "Error", message, sound=False
        )  # Disable default sound

    @staticmethod
    def show_settings_update(title, subtitle, message):
        """Notification for settings update"""
        rumps.notification(
            title, subtitle, message, sound=False
        )  # Disable default sound

    @staticmethod
    def show_mode_change(mode):
        """Notification for mode change"""
        message = (
            "Captures will be uploaded to cloud"
            if mode == "Cloud"
            else "Captures will be saved locally only"
        )
        rumps.notification(
            "Mode Changed", f"Switched to {mode} Mode", message, sound=False
        )  # Disable default sound
