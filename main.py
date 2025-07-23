import os
import sys
from datetime import datetime
from src.app import IntentionalComputingApp
from src.config.constants import DEFAULT_STORAGE_DIR


class TeeOutput:
    """Redirect stdout to both console and file - simple version without rotation"""

    def __init__(self, file_path):
        self.terminal = sys.stdout
        self.log_file_path = file_path
        self.log_file = open(file_path, "w", encoding="utf-8")

    def write(self, message):
        self.terminal.write(message)
        self.log_file.write(message)
        self.log_file.flush()  # Ensure immediate write to file

    def flush(self):
        self.terminal.flush()
        self.log_file.flush()

    def close(self):
        if hasattr(self, "log_file") and not self.log_file.closed:
            self.log_file.close()


if __name__ == "__main__":
    # Setup log file
    storage_dir = os.path.expanduser(DEFAULT_STORAGE_DIR)
    logs_dir = os.path.join(storage_dir, "logs")
    os.makedirs(logs_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file_path = os.path.join(logs_dir, f"intention_app_{timestamp}.log")

    # Redirect stdout to both console and file
    tee = TeeOutput(log_file_path)
    sys.stdout = tee

    print(f"=== Intention App Starting ===")
    print(f"Log file: {log_file_path}")
    print(f"Log rotation disabled - single log file")

    try:
        app = IntentionalComputingApp()
        app.run()
    except Exception as e:
        print(f"App failed to start: {e}")
        import traceback

        print(f"Traceback: {traceback.format_exc()}")
        raise
    finally:
        # Restore original stdout and close log file
        sys.stdout = tee.terminal
        tee.close()
