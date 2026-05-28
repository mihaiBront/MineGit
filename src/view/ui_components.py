import tkinter as tk
from dataclasses import dataclass
from tkinter import ttk
from typing import Callable

START_ENABLED_BG = "#2E7D32"
START_ENABLED_ACTIVE_BG = "#1B5E20"
START_DISABLED_BG = "#A5D6A7"

STOP_ENABLED_BG = "#C62828"
STOP_ENABLED_ACTIVE_BG = "#B71C1C"
STOP_DISABLED_BG = "#EF9A9A"

REFRESH_BG = "#1976D2"
REFRESH_ACTIVE_BG = "#1565C0"
BUTTON_FG = "white"
BUTTON_DISABLED_FG = "#F5F5F5"
STATUS_TEXT_FG = "#FFFFFF"

STATUS_COLORS = {
    "[OK]": "#2E7D32",
    "[PLAY]": "#1565C0",
    "[WAIT]": "#B26A00",
    "[ERR]": "#B53000",
}
DEFAULT_STATUS_COLOR = "#455A64"


@dataclass
class MainViewComponents:
    root: ttk.Frame
    start_button: tk.Button
    stop_button: tk.Button
    refresh_button: tk.Button
    status_container: tk.Frame
    status_icon_label: tk.Label
    status_text_label: tk.Label
    log_widget: tk.Text
    show_debug_checkbutton: ttk.Checkbutton


def _create_action_button(
    parent: tk.Misc,
    text: str,
    command: Callable[[], None],
    background: str,
    active_background: str,
) -> tk.Button:
    return tk.Button(
        parent,
        text=text,
        command=command,
        bg=background,
        fg=BUTTON_FG,
        activebackground=active_background,
        activeforeground=BUTTON_FG,
        disabledforeground=BUTTON_DISABLED_FG,
        relief=tk.FLAT,
    )


def build_main_layout(
    parent: tk.Misc,
    repo_path_var: tk.StringVar,
    lock_path_var: tk.StringVar,
    status_icon_var: tk.StringVar,
    status_var: tk.StringVar,
    on_browse_repository: Callable[[], None],
    on_refresh_clicked: Callable[[], None],
    on_start_playing: Callable[[], None],
    on_stop_playing: Callable[[], None],
    show_debug_var: tk.BooleanVar,
    on_toggle_debug_logs: Callable[[], None],
) -> MainViewComponents:
    root = ttk.Frame(parent, padding=14)
    root.pack(fill=tk.BOTH, expand=True)

    ttk.Label(root, text="Repository path").grid(row=0, column=0, sticky=tk.W)
    ttk.Entry(root, textvariable=repo_path_var).grid(row=1, column=0, columnspan=2, sticky=tk.EW, pady=(3, 10))
    ttk.Button(root, text="Browse...", command=on_browse_repository).grid(
        row=1, column=2, sticky=tk.EW, pady=(3, 10), padx=(8, 0)
    )

    ttk.Label(root, text="Lock file (relative to repository)").grid(row=2, column=0, sticky=tk.W)
    ttk.Entry(root, textvariable=lock_path_var).grid(row=3, column=0, columnspan=3, sticky=tk.EW, pady=(3, 10))

    refresh_button = _create_action_button(
        root,
        text="Refresh",
        command=on_refresh_clicked,
        background=REFRESH_BG,
        active_background=REFRESH_ACTIVE_BG,
    )
    refresh_button.grid(row=4, column=0, sticky=tk.EW, padx=(0, 4))

    start_button = _create_action_button(
        root,
        text="Start playing",
        command=on_start_playing,
        background=START_ENABLED_BG,
        active_background=START_ENABLED_ACTIVE_BG,
    )
    start_button.grid(row=4, column=1, sticky=tk.EW)

    stop_button = _create_action_button(
        root,
        text="Stop playing",
        command=on_stop_playing,
        background=STOP_ENABLED_BG,
        active_background=STOP_ENABLED_ACTIVE_BG,
    )
    stop_button.grid(row=4, column=2, sticky=tk.EW, padx=(4, 0))

    status_container = tk.Frame(root, bg=DEFAULT_STATUS_COLOR, padx=12, pady=8)
    status_container.grid(row=5, column=0, columnspan=3, pady=(12, 6))
    status_icon_label = tk.Label(
        status_container,
        textvariable=status_icon_var,
        width=8,
        bg=DEFAULT_STATUS_COLOR,
        fg=STATUS_TEXT_FG,
    )
    status_icon_label.grid(row=0, column=0, sticky=tk.W)
    status_text_label = tk.Label(
        status_container,
        textvariable=status_var,
        bg=DEFAULT_STATUS_COLOR,
        fg=STATUS_TEXT_FG,
    )
    status_text_label.grid(row=0, column=1, sticky=tk.W)

    log_widget = tk.Text(root, height=12, wrap=tk.WORD, state=tk.DISABLED)
    log_widget.grid(row=6, column=0, columnspan=3, sticky=tk.NSEW)

    show_debug_checkbutton = ttk.Checkbutton(
        root,
        text="Show debug logs",
        variable=show_debug_var,
        command=on_toggle_debug_logs,
    )
    show_debug_checkbutton.grid(row=7, column=0, columnspan=3, sticky=tk.W, pady=(8, 0))

    root.columnconfigure(0, weight=1)
    root.columnconfigure(1, weight=1)
    root.columnconfigure(2, weight=1)
    root.rowconfigure(6, weight=1)

    return MainViewComponents(
        root=root,
        start_button=start_button,
        stop_button=stop_button,
        refresh_button=refresh_button,
        status_container=status_container,
        status_icon_label=status_icon_label,
        status_text_label=status_text_label,
        log_widget=log_widget,
        show_debug_checkbutton=show_debug_checkbutton,
    )


def update_play_buttons_state(
    start_button: tk.Button,
    stop_button: tk.Button,
    start_enabled: bool,
    stop_enabled: bool,
) -> None:
    start_button.config(
        state=tk.NORMAL if start_enabled else tk.DISABLED,
        bg=START_ENABLED_BG if start_enabled else START_DISABLED_BG,
        activebackground=START_ENABLED_ACTIVE_BG if start_enabled else START_DISABLED_BG,
    )
    stop_button.config(
        state=tk.NORMAL if stop_enabled else tk.DISABLED,
        bg=STOP_ENABLED_BG if stop_enabled else STOP_DISABLED_BG,
        activebackground=STOP_ENABLED_ACTIVE_BG if stop_enabled else STOP_DISABLED_BG,
    )


def update_status_indicator(
    status_container: tk.Frame,
    status_icon_label: tk.Label,
    status_text_label: tk.Label,
    icon: str,
) -> None:
    status_color = STATUS_COLORS.get(icon, DEFAULT_STATUS_COLOR)
    status_container.config(bg=status_color)
    status_icon_label.config(bg=status_color, fg=STATUS_TEXT_FG)
    status_text_label.config(bg=status_color, fg=STATUS_TEXT_FG)
