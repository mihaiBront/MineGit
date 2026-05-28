import logging
import tkinter as tk


class TkTextHandler(logging.Handler):
    def __init__(self, text_widget: tk.Text) -> None:
        super().__init__()
        self.text_widget = text_widget

    def emit(self, record: logging.LogRecord) -> None:
        message = self.format(record)
        level_tag = record.levelname.upper()

        def append() -> None:
            self.text_widget.config(state=tk.NORMAL)
            self.text_widget.insert(tk.END, f"{message}\n", level_tag)
            self.text_widget.see(tk.END)
            self.text_widget.config(state=tk.DISABLED)

        self.text_widget.after(0, append)


def configure_tkinter_logging(text_widget: tk.Text, logger_name: str = "minegit") -> logging.Logger:
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    for handler in logger.handlers:
        if isinstance(handler, TkTextHandler):
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

    return logger
