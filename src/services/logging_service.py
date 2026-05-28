import logging
import tkinter as tk
from queue import Empty, SimpleQueue
from typing import Tuple


class TkTextHandler(logging.Handler):
    def __init__(self, text_widget: tk.Text, poll_interval_ms: int = 60) -> None:
        super().__init__()
        self.text_widget = text_widget
        self.poll_interval_ms = poll_interval_ms
        self._queue: SimpleQueue[Tuple[str, str]] = SimpleQueue()
        self._is_streaming = False

    def emit(self, record: logging.LogRecord) -> None:
        message = self.format(record)
        level_tag = record.levelname.upper()
        self._queue.put((message, level_tag))

    def start_streaming(self) -> None:
        if self._is_streaming:
            return
        self._is_streaming = True
        self._schedule_flush()

    def _schedule_flush(self) -> None:
        self.text_widget.after(self.poll_interval_ms, self._flush_logs)

    def _flush_logs(self) -> None:
        had_new_logs = False
        _, bottom_fraction = self.text_widget.yview()
        was_at_bottom = bottom_fraction >= 0.999

        self.text_widget.config(state=tk.NORMAL)
        while True:
            try:
                message, level_tag = self._queue.get_nowait()
            except Empty:
                break
            had_new_logs = True
            self.text_widget.insert(tk.END, f"{message}\n", level_tag)

        if had_new_logs and was_at_bottom:
            self.text_widget.see(tk.END)

        self.text_widget.config(state=tk.DISABLED)
        self._schedule_flush()


def configure_tkinter_logging(text_widget: tk.Text, logger_name: str = "minegit") -> logging.Logger:
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    for handler in logger.handlers:
        if isinstance(handler, TkTextHandler):
            handler.start_streaming()
            return logger

    text_widget.tag_config("DEBUG", foreground="#636363")
    text_widget.tag_config("INFO", foreground="#264eff")
    text_widget.tag_config("WARNING", foreground="#b57300")
    text_widget.tag_config("ERROR", foreground="#b53000")
    text_widget.tag_config("CRITICAL", foreground="#6b0022")

    handler = TkTextHandler(text_widget)
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S"))
    logger.addHandler(handler)
    handler.start_streaming()

    return logger


def set_debug_logs_visible(logger: logging.Logger, visible: bool) -> None:
    target_level = logging.DEBUG if visible else logging.INFO
    for handler in logger.handlers:
        if isinstance(handler, TkTextHandler):
            handler.setLevel(target_level)


def clear_tkinter_log_console(logger: logging.Logger) -> None:
    for handler in logger.handlers:
        if not isinstance(handler, TkTextHandler):
            continue

        while True:
            try:
                handler._queue.get_nowait()
            except Empty:
                break

        handler.text_widget.config(state=tk.NORMAL)
        handler.text_widget.delete("1.0", tk.END)
        handler.text_widget.config(state=tk.DISABLED)
