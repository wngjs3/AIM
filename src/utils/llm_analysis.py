import io
import os
import sys
import glob
import json
import subprocess
import base64
import requests
from datetime import datetime
from PIL import Image


from PyQt6.QtGui import QPainter, QPen, QColor
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal, QObject
from PyQt6.QtWidgets import QWidget, QApplication


from ..config.constants import (
    CAPTURE_INTERVAL,
    LLM_INVOKE_INTERVAL,
    LLM_ANALYSIS_IMAGE_COUNT,
    LOCAL_MODE_LLM_API_ENDPOINT,
    DEFAULT_STORAGE_DIR,
    IMAGE_QUALITY,
    APP_MODE,
)


class LLMAnalysisThread(QThread):
    analysis_complete = pyqtSignal(dict)
    analysis_error = pyqtSignal(str)

    def __init__(self, prompt, images, user_info, parent=None):
        super().__init__(parent)
        self.prompt = prompt
        self.images = images
        self.user_info = user_info
        self.setObjectName(f"LLMThread_{id(self)}")
        # Add thread termination flag
        self._is_stopping = False
        # Add timeout for network requests
        self._request_timeout = 10  # 10 seconds max
        self._session = None

    def __del__(self):
        """Safe destructor to prevent crash during garbage collection"""
        try:
            if hasattr(self, "_is_stopping"):
                self._is_stopping = True
            if self.isRunning():
                self.terminate()
                self.wait(100)  # Short wait
        except:
            pass  # Ignore any errors during destruction

    def safe_quit(self):
        """Safe method to quit the thread"""
        try:
            print(f"[LLM_THREAD] Safely quitting thread {self.objectName()}")
            self._is_stopping = True

            # Close network session first
            if hasattr(self, "_session") and self._session:
                try:
                    self._session.close()
                    print(f"[LLM_THREAD] Session closed for {self.objectName()}")
                except Exception as e:
                    print(f"[LLM_THREAD] Error closing session: {e}")

            if self.isRunning():
                # Try graceful quit first
                self.quit()
                if not self.wait(1000):  # Wait 1 second for graceful quit
                    print(
                        f"[LLM_THREAD] Graceful quit failed, using terminate for {self.objectName()}"
                    )
                    self.terminate()
                    if not self.wait(1000):  # Wait another second for terminate
                        print(
                            f"[LLM_THREAD] Thread {self.objectName()} did not terminate gracefully"
                        )
                    else:
                        print(
                            f"[LLM_THREAD] Thread {self.objectName()} terminated successfully"
                        )
                else:
                    print(f"[LLM_THREAD] Thread {self.objectName()} quit gracefully")

            self.deleteLater()
        except Exception as e:
            print(f"[LLM_THREAD] Error in safe_quit: {e}")

    def run(self):
        try:
            # Only show analysis status, not full prompt details
            prompt_length = len(self.prompt) if self.prompt else 0

            # Simple processing status
            for img_path in self.images:
                img_size_kb = os.path.getsize(img_path) / 1024
                print(
                    f"[ANALYSIS] Processing: {os.path.basename(img_path)} ({img_size_kb:.1f} KB)"
                )

            # Prepare image data
            image_info = (
                []
            )  # Store image information including filenames and encoded data

            print("\n=== Processing Images for Analysis ===")
            # Copy image file list (to prevent modifying original)
            images_to_process = self.images.copy()

            for img_path in images_to_process:
                # Check for thread termination request
                if self._is_stopping:
                    print("Thread termination requested, stopping image processing")
                    return

                try:
                    with open(img_path, "rb") as img_file:
                        file_size = os.path.getsize(img_path)
                        if file_size > 5 * 1024 * 1024:
                            print(
                                f"Skipping large image: {img_path} ({file_size/1024/1024:.2f} MB)"
                            )
                            continue

                        # Encode image
                        encoded = base64.b64encode(img_file.read()).decode("utf-8")

                        # Save file information
                        file_name = os.path.basename(img_path)
                        print(
                            f"Processing image: {file_name} ({file_size/1024:.1f} KB)"
                        )

                        image_info.append(
                            {"file_name": file_name, "encoded_data": encoded}
                        )

                        # Memory optimization: Run garbage collection after processing each image
                        import gc

                        gc.collect()
                except Exception as e:
                    print(f"Error processing image {img_path}: {e}")
                    continue

            # Check for thread termination request
            if self._is_stopping:
                print("Thread termination requested, stopping analysis")
                return

            if not image_info:
                self.analysis_error.emit("No valid images to analyze")
                return

            print(
                f"[LLM] Requesting analysis for: {self.user_info.get('current_task', 'No task')}"
            )

            # Prepare session info for new backend schema
            session_info = {
                "user_id": self.user_info.get("name", "default_user"),
                "session_id": self.user_info.get("session_id", "unknown_session"),
                "task_name": self.user_info.get("current_task", "No task specified"),
                "intention": self.user_info.get(
                    "current_task", "No task specified"
                ),  # intention = task_name for now
                "device_name": self.user_info.get("device_name", "mac_os_device"),
                "app_mode": APP_MODE,
                "notification": self.user_info.get(
                    "notification", False
                ),  # Add notification flag
            }

            # Prepare frontmost app information (single object)
            frontmost_app = self.user_info.get("frontmost_app", None)

            # Prepare request data for new /analyze endpoint schema (single image)
            request_data = {
                "prompt": self.prompt,
                "image": image_info[0]["encoded_data"],  # Single image instead of array
                "image_file": image_info[0]["file_name"],  # Single filename
                "image_num": self.user_info.get(
                    "image_num", 1
                ),  # Session-based image counter
                "app_change": self.user_info.get(
                    "app_change", False
                ),  # App change detection flag
                "session_info": session_info,
                "frontmost_app": frontmost_app,  # Single app info instead of array
                "opacity": self.user_info.get(
                    "opacity", 1.0
                ),  # Dashboard opacity as separate field
            }

            # Check for thread termination request
            if self._is_stopping:
                print("Thread termination requested, stopping before server request")
                return

            # Set request timeout and create session for better control
            try:
                # Create session for better connection control
                if not self._session:
                    import requests

                    self._session = requests.Session()

                # Check termination before network request
                if self._is_stopping:
                    print("Thread termination requested before network call")
                    return

                # Send request to server with shorter timeout
                response = self._session.post(
                    LOCAL_MODE_LLM_API_ENDPOINT,
                    json=request_data,
                    headers={"Content-Type": "application/json"},
                    timeout=self._request_timeout,  # Use configurable timeout
                )

                # Check for thread termination request
                if self._is_stopping:
                    print("Thread termination requested, stopping after server request")
                    return

                # Memory optimization: Run garbage collection after sending request
                import gc

                gc.collect()

                self.process_server_response(response)
            except requests.exceptions.Timeout:
                if not self._is_stopping:
                    print("Server request timed out")
                    self.analysis_error.emit("Server request timed out")
                else:
                    print("[LLM_THREAD] Thread stopped, suppressing timeout error")
            except requests.exceptions.RequestException as e:
                if not self._is_stopping:
                    print(f"Request error: {e}")
                    self.analysis_error.emit(f"Request error: {str(e)}")
                else:
                    print(
                        f"[LLM_THREAD] Thread stopped, suppressing network error: {str(e)}"
                    )

        except Exception as e:
            if not self._is_stopping:  # Only emit error signal if not terminating
                error_msg = f"Analysis error: {str(e)}"
                print(f"Error: {error_msg}")
                self.analysis_error.emit(error_msg)
            else:
                print(f"[LLM_THREAD] Thread stopped, suppressing error: {str(e)}")

    def terminate(self):
        """Override method for safe thread termination"""
        print(f"Thread {self.objectName()} terminating...")
        self._is_stopping = True
        # Call parent terminate
        super().terminate()

    def process_server_response(self, response):
        """Process server response and update status"""
        # Check for thread termination request
        if self._is_stopping:
            print("Thread termination requested, stopping response processing")
            return

        if response.status_code == 200:
            result = response.json()
            output_score = result.get("output", "Unknown")
            reason = result.get("reason", "No reason")
            print(f"[LLM] Analysis complete (Score: {output_score}): {reason}")

            # Add analyzed image paths to the result for feedback tracking
            result["analyzed_images"] = (
                self.images.copy()
            )  # Include original image paths
            result["analyzed_image_count"] = len(self.images)

            # For single image analysis, set primary analyzed image
            if len(self.images) == 1:
                result["primary_analyzed_image"] = self.images[0]
            else:
                # For multiple images, use the most recent one as primary
                result["primary_analyzed_image"] = (
                    self.images[0] if self.images else None
                )

            # Update intention status with enhanced server response
            if self.analysis_complete and not self._is_stopping:
                self.analysis_complete.emit(result)
        else:
            print(f"Error: {response.status_code}")
            print(response.text)
            if not self._is_stopping:  # Only emit error signal if not terminating
                self.analysis_error.emit(response.text)
