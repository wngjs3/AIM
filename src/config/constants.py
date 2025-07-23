# App Version - Change this when releasing a new version
APP_VERSION = "1.0.1"

# App Modes
APP_MODE_FULL = "treatment"  ## APP1
APP_MODE_BASIC = "baseline"  ## APP3
APP_MODE_REMINDER = "control"  ## APP2
APP_MODE_PRIVATE = "private"

# Default App Mode
APP_MODE = APP_MODE_FULL

# API Settingsd
CLOUD_STORAGE_ENDPOINT = (
    # not used
)
# Base API endpoints
LOCAL_BASE_URL = (
    # enter your endpoint here
)
# LOCAL_BASE_URL = "http://0.0.0.0:8080"  # Development

# API endpoints for different services
LOCAL_MODE_LLM_API_ENDPOINT = f"{LOCAL_BASE_URL}/analyze"  # For image analysis
LLM_CLARIFICATION_API_ENDPOINT = f"{LOCAL_BASE_URL}/clarification"  # For clarification
LLM_FEEDBACK_API_ENDPOINT = f"{LOCAL_BASE_URL}/feedback"  # For feedback/reflection
LLM_FEEDBACK_MESSAGE_API_ENDPOINT = (
    f"{LOCAL_BASE_URL}/feedback_message"  # For feedback messages
)
LLM_RATING_API_ENDPOINT = f"{LOCAL_BASE_URL}/rating"  # For session rating

# Legacy endpoint (for backward compatibility)
LLM_CHAT_API_ENDPOINT = f"{LOCAL_BASE_URL}/clarification"  # Redirect to clarification


# Storage Settings
DEFAULT_STORAGE_DIR = (
    "~/ScreenCaptures_Purple(new)"
    if APP_MODE == APP_MODE_FULL
    else (
        "~/ScreenCaptures_Blue(new)"
        if APP_MODE == APP_MODE_REMINDER
        else (
            "~/ScreenCaptures_private(new)"
            if APP_MODE == APP_MODE_PRIVATE
            else "~/ScreenCaptures_Orange(new)"
        )
    )
)
CONFIG_DIR = "~/.intention_app"
USER_CONFIG_FILE = "user_config.json"
PROMPT_CONFIG_FILE = "prompt_config.json"

# Sound Settings
DEFAULT_FOCUS_SOUND = "good_1.mp3"  # For focused state (0) - focused
DEFAULT_DISTRACT_SOUND = "focus_1.mp3"  # For distracted state (1) - distracted

# Capture Settings
CAPTURE_INTERVAL = 2
IMAGE_QUALITY = 85  # JPEG compression quality (0-100)
IMAGE_SCALE = (
    3  # Screen capture downscaling factor (e.g., 3 means 1/3 of original size)
)

# LLM Settings
LLM_INVOKE_INTERVAL = 2
LLM_ANALYSIS_IMAGE_COUNT = 1  # Always analyze only 1 image (most recent)
LLM_INTERVAL = 2
MAX_CONCURRENT_ANALYSIS_THREADS = 4  # Maximum number of concurrent LLM analysis threads


# UI Settings
WINDOW_MIN_WIDTH = 300
WINDOW_MIN_HEIGHT = 300
PROMPT_WINDOW_WIDTH = 600
PROMPT_WINDOW_HEIGHT = 400

# Messages
APP_START_MESSAGE = "Click the intention app icon in the menu bar to use"
SETTINGS_REQUIRED_MESSAGE = "User ID is required to participate in the study"

# Notification Settings
NOTIFICATION_ENABLED = True  # Enable/disable notifications

DEFAULT_TONE = "neutral"
