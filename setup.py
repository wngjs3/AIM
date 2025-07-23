from setuptools import setup
import os
import sys

# Get app name from environment variable or use default
app_name = os.environ.get("APP_NAME", "Intention(new)")

# 번들 ID 환경변수에서 가져오기
bundle_id = os.environ.get("BUNDLE_ID", "com.intention.app")

# Get icon path from environment variable or use default
icon_path = os.environ.get("ICON_PATH", "src/assets/icon.png")
recording_icon_path = os.environ.get(
    "RECORDING_ICON_PATH", "src/assets/icon_recording.png"
)

# Get all sound files from assets directory
assets_dir = "src/assets"
sound_files = []
if os.path.exists(assets_dir):
    for file in os.listdir(assets_dir):
        if file.endswith((".mp3", ".wav")):
            sound_files.append(os.path.join(assets_dir, file))

APP = ["main.py"]
DATA_FILES = [
    ("assets", [icon_path, recording_icon_path] + sound_files),
]
OPTIONS = {
    "argv_emulation": True,
    "iconfile": icon_path,
    "plist": {
        "CFBundleName": app_name,
        "CFBundleDisplayName": app_name,
        "CFBundleIdentifier": bundle_id,
        "CFBundleVersion": "2.0.0",
        "CFBundleShortVersionString": "2.0.0",
        "LSMinimumSystemVersion": "10.15",
        "NSHighResolutionCapable": True,
        "NSRequiresAquaSystemAppearance": False,
        "NSMicrophoneUsageDescription": "This app does not use the microphone.",
        "NSCameraUsageDescription": "This app does not use the camera.",
        "NSAppleEventsUsageDescription": "This app requires access to send notifications.",
        "NSUserNotificationAlertStyle": "alert",
        "NSScreenCaptureUsageDescription": "Screen capture permission is required for app functionality.",
    },
    "packages": ["rumps", "PyQt6", "desktop_notifier", "charset_normalizer"],
    "includes": [
        "src",
        "src.ui",
        "src.capture",
        "src.config",
        "src.upload",
        "desktop_notifier.resources",
    ],
    "site_packages": True,
}

setup(
    name=app_name,
    app=APP,
    data_files=DATA_FILES,
    options={"py2app": OPTIONS},
    setup_requires=["py2app"],
)
