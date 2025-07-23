import json
import os
import requests
from datetime import datetime
from PyQt6.QtCore import QThread, pyqtSignal

from ..config.user_config import UserConfig
from ..config.constants import LLM_RATING_API_ENDPOINT


class SessionRatingThread(QThread):
    """Thread for sending session rating to backend"""

    rating_sent = pyqtSignal(dict)  # Signal emitted when rating is sent successfully
    rating_error = pyqtSignal(str)  # Signal emitted when rating fails

    def __init__(self, rating_data, api_endpoint):
        super().__init__()
        self.rating_data = rating_data
        self.api_endpoint = api_endpoint
        self.setObjectName(f"SessionRatingThread_{id(self)}")
        # Add thread termination flag
        self._is_stopping = False
        # Add timeout for network requests
        self._request_timeout = 30  # 30 seconds for rating
        self._session = None

    def run(self):
        """Send session rating to backend"""
        try:
            print(f"[RATING] Sending rating to backend: {self.rating_data}")
            print(f"[RATING] API Endpoint: {self.api_endpoint}")

            # Create session for better connection control
            if not self._session:
                import requests

                self._session = requests.Session()

            # Check termination before network request
            if self._is_stopping:
                print("Rating thread termination requested before network call")
                return

            # Prepare headers
            headers = {"Content-Type": "application/json"}

            # Send POST request
            response = self._session.post(
                self.api_endpoint,
                headers=headers,
                json=self.rating_data,
                timeout=self._request_timeout,
            )

            print(f"[RATING] Response status: {response.status_code}")

            if response.status_code == 200:
                try:
                    result = response.json()
                    print(f"[RATING] Rating sent successfully: {result}")
                    self.rating_sent.emit(result)
                except json.JSONDecodeError:
                    # Handle plain text response
                    result = {"status": "success", "message": response.text}
                    print(f"[RATING] Rating sent successfully (text): {response.text}")
                    self.rating_sent.emit(result)
            else:
                error_msg = (
                    f"Server returned status {response.status_code}: {response.text}"
                )
                print(f"[RATING] Error: {error_msg}")
                self.rating_error.emit(error_msg)

        except requests.exceptions.RequestException as e:
            if not self._is_stopping:  # Only emit error if not terminating
                error_msg = f"Network error: {str(e)}"
                print(f"[RATING] Network error: {error_msg}")
                self.rating_error.emit(error_msg)
            else:
                print(
                    f"[RATING_THREAD] Thread stopped, suppressing network error: {str(e)}"
                )
        except Exception as e:
            if not self._is_stopping:  # Only emit error if not terminating
                error_msg = f"Unexpected error: {str(e)}"
                print(f"[RATING] Unexpected error: {error_msg}")
                self.rating_error.emit(error_msg)

    def safe_quit(self):
        """Safe method to quit the thread"""
        try:
            print(f"[RATING_THREAD] Safely quitting thread")
            self._is_stopping = True

            # Close network session first
            if hasattr(self, "_session") and self._session:
                try:
                    self._session.close()
                    print(f"[RATING_THREAD] Session closed")
                except Exception as e:
                    print(f"[RATING_THREAD] Error closing session: {e}")

            if self.isRunning():
                # Try graceful quit first
                self.quit()
                if not self.wait(1000):  # Wait 1 second for graceful quit
                    print(f"[RATING_THREAD] Graceful quit failed, using terminate")
                    self.terminate()
                    if not self.wait(1000):  # Wait another second for terminate
                        print(f"[RATING_THREAD] Thread did not terminate gracefully")
                    else:
                        print(f"[RATING_THREAD] Thread terminated successfully")
                else:
                    print(f"[RATING_THREAD] Thread quit gracefully")

            self.deleteLater()
        except Exception as e:
            print(f"[RATING_THREAD] Error in safe_quit: {e}")


class SessionRatingManager:
    """Manager for handling session ratings"""

    def __init__(self, user_config, dashboard=None):
        self.user_config = user_config
        self.dashboard = dashboard
        self.current_thread = None

    def send_session_rating(self, rating, session_info, task_name=None):
        """Send session rating to backend

        Args:
            rating (int): Rating from 1-5
            session_info (dict): Session information containing user_id, session_id, etc.
            task_name (str): Optional task name
        """
        try:
            # Prepare rating data for backend
            rating_data = {
                "user_id": session_info.get("user_id"),
                "session_id": session_info.get("session_id"),
                "final_rating": rating,  # 백엔드가 기대하는 필드명
                "timestamp": datetime.now().isoformat(),
                "session_info": session_info,
            }

            # Add task name if provided
            if task_name:
                rating_data["task_name"] = task_name

            print(f"[RATING] Preparing to send session rating: {rating}/5")
            print(f"[RATING] Session info: {session_info}")

            # Use dedicated rating endpoint
            api_endpoint = LLM_RATING_API_ENDPOINT

            # Clean up any existing thread
            if self.current_thread and self.current_thread.isRunning():
                self.current_thread.terminate()
                self.current_thread.wait(1000)

            # Create and start new thread
            self.current_thread = SessionRatingThread(rating_data, api_endpoint)
            self.current_thread.rating_sent.connect(self._on_rating_sent)
            self.current_thread.rating_error.connect(self._on_rating_error)
            self.current_thread.start()

        except Exception as e:
            print(f"[RATING] Error preparing rating: {e}")
            import traceback

            traceback.print_exc()

    def _on_rating_sent(self, result):
        """Handle successful rating submission"""
        print(f"[RATING] Rating submitted successfully: {result}")

        # Clean up thread properly
        if self.current_thread:
            self.current_thread.quit()
            self.current_thread.wait(2000)  # Wait up to 2 seconds
            self.current_thread.deleteLater()
            self.current_thread = None

    def _on_rating_error(self, error_message):
        """Handle rating submission error"""
        print(f"[RATING] Error submitting rating: {error_message}")

        # Clean up thread properly
        if self.current_thread:
            self.current_thread.quit()
            self.current_thread.wait(2000)  # Wait up to 2 seconds
            self.current_thread.deleteLater()
            self.current_thread = None

    def cleanup(self):
        """Clean up any running threads - Enhanced for safe shutdown"""
        print("[RATING] Cleaning up session rating threads...")
        if self.current_thread and self.current_thread.isRunning():
            print("[RATING] Safely quitting running thread...")
            # Use safe_quit if available
            if hasattr(self.current_thread, "safe_quit"):
                self.current_thread.safe_quit()
            else:
                # Fallback to old method
                self.current_thread.terminate()
                if not self.current_thread.wait(2000):  # Wait up to 2 seconds
                    print("[RATING] Thread did not terminate gracefully")
                else:
                    print("[RATING] Thread terminated successfully")
                try:
                    self.current_thread.deleteLater()
                except Exception as e:
                    print(f"[RATING] Error in deleteLater: {e}")
            self.current_thread = None
        print("[RATING] Session rating cleanup complete")
