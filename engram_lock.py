"""
File locking for lightweight concurrency safety.
"""
import time
from pathlib import Path


class FileLock:
    def __init__(self, lock_path: Path, timeout: float = 5.0):
        self.lock_path = lock_path
        self.timeout = timeout

    def __enter__(self):
        start_time = time.time()
        while self.lock_path.exists():
            if time.time() - start_time > self.timeout:
                try:
                    self.lock_path.unlink()
                except OSError:
                    pass
                break
            time.sleep(0.1)
        self.lock_path.touch()

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            self.lock_path.unlink()
        except OSError:
            pass
