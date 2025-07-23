"""
Screen lock detection utility for macOS
"""

import platform
import logging
from typing import Optional

# Only import macOS-specific modules if running on macOS
if platform.system() == "Darwin":
    try:
        import Quartz

        QUARTZ_AVAILABLE = True
    except ImportError:
        QUARTZ_AVAILABLE = False
        logging.warning(
            "Quartz framework not available. Screen lock detection disabled."
        )
else:
    QUARTZ_AVAILABLE = False

logger = logging.getLogger(__name__)


class ScreenLockDetector:
    """
    Simple screen lock detector for macOS
    """

    def __init__(self):
        self._is_supported = QUARTZ_AVAILABLE and platform.system() == "Darwin"
        if not self._is_supported:
            logger.warning("Screen lock detection not supported on this platform")

    def is_screen_locked(self) -> Optional[bool]:
        """
        Check if the screen is locked

        Returns:
            True if screen is locked
            False if screen is unlocked
            None if detection is not supported or failed
        """
        if not self._is_supported:
            return None

        try:
            # Get current session dictionary
            session_dict = Quartz.CGSessionCopyCurrentDictionary()

            if not session_dict:
                logger.warning("Failed to get CGSession dictionary")
                return None

            # Check if screen is locked
            screen_locked = session_dict.get("CGSSessionScreenIsLocked", 0)

            # Convert to boolean (0 = unlocked, 1 = locked)
            return bool(screen_locked)

        except Exception as e:
            logger.error(f"Error checking screen lock status: {e}")
            return None

    @property
    def is_supported(self) -> bool:
        """
        Check if screen lock detection is supported on this platform
        """
        return self._is_supported


# Convenience function for easy usage
def is_screen_locked() -> Optional[bool]:
    """
    Quick check if screen is locked

    Returns:
        True if locked, False if unlocked, None if not supported
    """
    detector = ScreenLockDetector()
    return detector.is_screen_locked()
