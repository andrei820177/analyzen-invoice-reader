import logging
import os
import threading
import time
from typing import Callable

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

logger = logging.getLogger(__name__)

_DEBOUNCE_SECONDS = 2.0


class _PDFHandler(FileSystemEventHandler):
    def __init__(self, callback: Callable[[str], None]) -> None:
        super().__init__()
        self._callback = callback
        self._pending: dict[str, float] = {}
        self._lock = threading.Lock()
        self._timer: threading.Timer | None = None

    def on_created(self, event):
        if not event.is_directory and event.src_path.lower().endswith(".pdf"):
            self._schedule(event.src_path)

    def on_modified(self, event):
        if not event.is_directory and event.src_path.lower().endswith(".pdf"):
            self._schedule(event.src_path)

    def _schedule(self, path: str) -> None:
        with self._lock:
            self._pending[path] = time.time() + _DEBOUNCE_SECONDS
            if self._timer:
                self._timer.cancel()
            self._timer = threading.Timer(_DEBOUNCE_SECONDS + 0.1, self._flush)
            self._timer.daemon = True
            self._timer.start()

    def _flush(self) -> None:
        now = time.time()
        with self._lock:
            ready = [p for p, t in self._pending.items() if now >= t]
            for p in ready:
                del self._pending[p]
        for path in ready:
            if os.path.isfile(path):
                logger.info("Watcher: new PDF detected: %s", path)
                try:
                    self._callback(path)
                except Exception as e:
                    logger.error("Watcher callback error for %s: %s", path, e)


class FolderWatcher:
    def __init__(self) -> None:
        self._observer: Observer | None = None
        self._folder: str = ""

    def start(self, folder_path: str, callback: Callable[[str], None]) -> None:
        self.stop()
        self._folder = folder_path
        handler = _PDFHandler(callback)
        self._observer = Observer()
        self._observer.schedule(handler, folder_path, recursive=False)
        self._observer.start()
        logger.info("Watcher started on: %s", folder_path)

    def stop(self) -> None:
        if self._observer and self._observer.is_alive():
            self._observer.stop()
            self._observer.join(timeout=3)
            logger.info("Watcher stopped")
        self._observer = None

    @property
    def is_running(self) -> bool:
        return self._observer is not None and self._observer.is_alive()
