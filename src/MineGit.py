import logging
import threading
import tkinter as tk
from pathlib import Path
from queue import Empty, SimpleQueue
from tkinter import filedialog, messagebox
from typing import Callable, Optional, Tuple

from controller.GitController import GitController, GitControllerError
from controller.SettingsController import SettingsController
from services.logging_service import (
    clear_tkinter_log_console,
    configure_tkinter_logging,
    set_debug_logs_visible,
)
from view import build_main_layout, update_play_buttons_state, update_status_indicator

StatusState = Tuple[str, str, bool, bool, str]


class MineGitApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("MineGit")
        self.geometry("760x420")
        self.minsize(640, 360)
        self.settings_controller = SettingsController("./minegitSettings.ini")

        saved_repository_path = self.settings_controller.load_repository_path() or str(Path.cwd())
        show_debug_logs = self.settings_controller.load_show_debug_logs(default=False)
        self.repo_path_var = tk.StringVar(value=saved_repository_path)
        self.lock_path_var = tk.StringVar(value="player.lock")
        self.status_icon_var = tk.StringVar(value="[... ]")
        self.status_var = tk.StringVar(value="Ready.")
        self.show_debug_logs_var = tk.BooleanVar(value=show_debug_logs)
        self._ui_events: SimpleQueue[Callable[[], None]] = SimpleQueue()
        self._busy = False
        self._desired_start_enabled = False
        self._desired_stop_enabled = False
        self._last_repository_path_for_logs = saved_repository_path

        self.ui = build_main_layout(
            parent=self,
            repo_path_var=self.repo_path_var,
            lock_path_var=self.lock_path_var,
            status_icon_var=self.status_icon_var,
            status_var=self.status_var,
            on_browse_repository=self.on_browse_repository,
            on_refresh_clicked=self.on_refresh_clicked,
            on_start_playing=self.on_start_playing,
            on_stop_playing=self.on_stop_playing,
            show_debug_var=self.show_debug_logs_var,
            on_toggle_debug_logs=self.on_toggle_debug_logs,
        )
        self.logger = configure_tkinter_logging(self.ui.log_widget)
        set_debug_logs_visible(self.logger, self.show_debug_logs_var.get())
        self.logger.info("MineGit UI initialized.")
        if saved_repository_path:
            self.logger.debug("Initial repository path value: %s", saved_repository_path)
        self.logger.debug("Initial show_debug_logs value: %s", self.show_debug_logs_var.get())
        self.after(40, self._drain_ui_events)
        self.after(120, self.initialize_status)

    def _build_controller(self, repository: str, lock_path: str) -> GitController:
        if not repository:
            raise GitControllerError("Please provide a repository path.")
        return GitController(repository_path=repository, lock_file_relative_path=lock_path)

    def _capture_controller_inputs(self) -> Tuple[str, str]:
        repository = self.repo_path_var.get().strip()
        lock_path = self.lock_path_var.get().strip() or "player.lock"
        self._handle_repository_path_change_for_logs(repository)
        self.logger.debug("Captured controller inputs repo='%s' lock='%s'.", repository, lock_path)
        return repository, lock_path

    def _handle_repository_path_change_for_logs(self, repository: str) -> None:
        if repository == self._last_repository_path_for_logs:
            return

        clear_tkinter_log_console(self.logger)
        self._last_repository_path_for_logs = repository
        self.logger.info("Console cleared because repository path changed to: %s", repository)

    def _post_ui_event(self, callback: Callable[[], None]) -> None:
        self._ui_events.put(callback)

    def _drain_ui_events(self) -> None:
        while True:
            try:
                callback = self._ui_events.get_nowait()
            except Empty:
                break
            callback()
        self.after(40, self._drain_ui_events)

    def _apply_controls_state(self) -> None:
        refresh_state = tk.DISABLED if self._busy else tk.NORMAL
        self.ui.refresh_button.config(state=refresh_state)
        start_enabled = self._desired_start_enabled and not self._busy
        stop_enabled = self._desired_stop_enabled and not self._busy
        update_play_buttons_state(
            start_button=self.ui.start_button,
            stop_button=self.ui.stop_button,
            start_enabled=start_enabled,
            stop_enabled=stop_enabled,
        )

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        self.logger.debug("Busy state updated to %s.", busy)
        self._apply_controls_state()

    def _start_background_task(
        self,
        name: str,
        worker: Callable[[], object],
        on_success: Callable[[object], None],
        on_error: Optional[Callable[[Exception], None]] = None,
    ) -> bool:
        if self._busy:
            self.logger.debug("Ignored '%s' because another task is in progress.", name)
            return False

        self.logger.debug("Starting background task '%s'.", name)
        self._set_busy(True)

        def run() -> None:
            try:
                result = worker()
            except Exception as error:
                def fail_callback() -> None:
                    self._set_busy(False)
                    if on_error is not None:
                        on_error(error)
                    else:
                        self.logger.exception("Unhandled error in task '%s'.", name)

                self._post_ui_event(fail_callback)
                return

            def success_callback() -> None:
                self._set_busy(False)
                on_success(result)

            self._post_ui_event(success_callback)

        threading.Thread(target=run, daemon=True).start()
        return True

    def on_browse_repository(self) -> None:
        selected_directory = filedialog.askdirectory(
            title="Select repository directory",
            initialdir=self.repo_path_var.get().strip() or str(Path.cwd()),
        )
        if selected_directory:
            self.repo_path_var.set(selected_directory)
            self.logger.info("Repository selected: %s", selected_directory)
            try:
                self.settings_controller.save_repository_path(selected_directory)
            except Exception as error:
                self.logger.error("Failed to persist selected repository path: %s", error)
            self.refresh_status_async(run_fetch=True)
        else:
            self.logger.debug("Repository browse canceled by user.")

    def on_refresh_clicked(self) -> None:
        self.logger.debug("Manual refresh requested.")
        self.refresh_status_async(run_fetch=True)

    def on_toggle_debug_logs(self) -> None:
        show_debug = self.show_debug_logs_var.get()
        set_debug_logs_visible(self.logger, show_debug)
        try:
            self.settings_controller.save_show_debug_logs(show_debug)
        except Exception as error:
            self.logger.error("Failed to persist show_debug_logs preference: %s", error)
        self.logger.info("Debug logs %s.", "enabled" if show_debug else "hidden")

    def _set_status(self, icon: str, text: str, start_enabled: bool, stop_enabled: bool) -> None:
        self.logger.debug(
            "Applying UI status icon=%s start_enabled=%s stop_enabled=%s text=%s",
            icon,
            start_enabled,
            stop_enabled,
            text,
        )
        self.status_icon_var.set(icon)
        self.status_var.set(text)
        update_status_indicator(
            status_container=self.ui.status_container,
            status_icon_label=self.ui.status_icon_label,
            status_text_label=self.ui.status_text_label,
            icon=icon,
        )
        self._desired_start_enabled = start_enabled
        self._desired_stop_enabled = stop_enabled
        self._apply_controls_state()

    def initialize_status(self) -> None:
        self.logger.debug("Running initial repository status check.")
        self.refresh_status_async(run_fetch=True)

    def _compute_status(self, repository: str, lock_path: str, run_fetch: bool, allow_auto_pull: bool = True) -> StatusState:
        self.logger.debug(
            "Refreshing status asynchronously run_fetch=%s allow_auto_pull=%s",
            run_fetch,
            allow_auto_pull,
        )
        controller = self._build_controller(repository=repository, lock_path=lock_path)
        attempted_auto_pull = False

        if run_fetch:
            self.logger.debug("Running fetch before computing status.")
            controller.fetch()

        while True:
            ahead, behind = controller.get_sync_counts()
            local_owner = controller.get_local_lock_owner()
            remote_owner = controller.get_remote_lock_owner()
            username = controller.get_git_username()
            lock_is_mine = local_owner == username or remote_owner == username
            self.logger.debug(
                "Status snapshot ahead=%s behind=%s local_owner=%s remote_owner=%s username=%s",
                ahead,
                behind,
                local_owner,
                remote_owner,
                username,
            )

            if lock_is_mine:
                return ("[PLAY]", f"You are already playing as {username}.", False, True, "info")

            if behind > 0 and ahead == 0:
                if remote_owner:
                    message = f"{remote_owner} is hosting now. Pull is blocked until their session ends."
                    return ("[WAIT]", message, False, False, "warning")

                if allow_auto_pull and not attempted_auto_pull:
                    attempted_auto_pull = True
                    self.logger.debug("Behind remote with no lock owner. Pulling updates automatically.")
                    controller.pull_latest()
                    continue

                return (
                    "[ERR]",
                    "Auto-pull did not converge. Resolve repository state manually.",
                    False,
                    False,
                    "error",
                )

            if ahead > 0 and behind > 0:
                message = "Local and remote branches diverged. Resolve conflicts manually."
                return ("[ERR]", message, False, False, "error")

            if ahead > 0:
                message = (
                    "Repository is ahead but player.lock is not yours. "
                    "Resolve this state manually before continuing."
                )
                return ("[ERR]", message, False, False, "warning")

            return ("[OK]", "Repository is in sync. You can start playing.", True, False, "info")

    def refresh_status_async(self, run_fetch: bool, allow_auto_pull: bool = True) -> None:
        repository, lock_path = self._capture_controller_inputs()

        def worker() -> StatusState:
            return self._compute_status(
                repository=repository,
                lock_path=lock_path,
                run_fetch=run_fetch,
                allow_auto_pull=allow_auto_pull,
            )

        def on_success(result: object) -> None:
            icon, message, start_enabled, stop_enabled, level_name = result  # type: ignore[misc]
            self._set_status(icon, message, start_enabled=start_enabled, stop_enabled=stop_enabled)
            getattr(self.logger, level_name)(message)

        def on_error(error: Exception) -> None:
            if isinstance(error, GitControllerError):
                self._set_status("[ERR]", str(error), start_enabled=False, stop_enabled=False)
                self.logger.error("Git controller error while checking status: %s", error)
                messagebox.showerror("MineGit", str(error))
                return

            self._set_status(
                "[ERR]",
                "Unexpected error while checking repository status.",
                start_enabled=False,
                stop_enabled=False,
            )
            self.logger.exception("Unexpected error while checking repository status.")
            messagebox.showerror("MineGit", str(error))

        self._start_background_task("refresh_status", worker, on_success, on_error)

    def on_start_playing(self) -> None:
        self.logger.debug("Start button clicked.")
        repository, lock_path = self._capture_controller_inputs()

        def worker() -> object:
            controller = self._build_controller(repository=repository, lock_path=lock_path)
            return controller.start_playing()

        def on_success(result: object) -> None:
            result = result  # type: ignore[assignment]
            if result.success:
                self.logger.info(result.message)
            else:
                self.logger.warning(result.message)
            if not result.success:
                self._set_status("[WAIT]", result.message, start_enabled=False, stop_enabled=False)
                messagebox.showwarning("MineGit", result.message)
            else:
                self.refresh_status_async(run_fetch=True)

        def on_error(error: Exception) -> None:
            if isinstance(error, GitControllerError):
                self._set_status("[ERR]", str(error), start_enabled=False, stop_enabled=False)
                self.logger.error("Git controller error while starting play session: %s", error)
                messagebox.showerror("MineGit", str(error))
                return

            self._set_status(
                "[ERR]",
                "Unexpected error while starting play session.",
                start_enabled=False,
                stop_enabled=False,
            )
            self.logger.exception("Unexpected error while starting play session.")
            messagebox.showerror("MineGit", str(error))

        self._start_background_task("start_playing", worker, on_success, on_error)

    def on_stop_playing(self) -> None:
        self.logger.debug("Stop button clicked.")
        repository, lock_path = self._capture_controller_inputs()

        def worker() -> object:
            controller = self._build_controller(repository=repository, lock_path=lock_path)
            return controller.stop_playing()

        def on_success(result: object) -> None:
            result = result  # type: ignore[assignment]
            if result.success:
                self.logger.info(result.message)
            else:
                self.logger.warning(result.message)
            if not result.success:
                self._set_status("[WAIT]", result.message, start_enabled=False, stop_enabled=False)
                messagebox.showwarning("MineGit", result.message)
            else:
                self.refresh_status_async(run_fetch=True)

        def on_error(error: Exception) -> None:
            if isinstance(error, GitControllerError):
                self._set_status("[ERR]", str(error), start_enabled=False, stop_enabled=False)
                self.logger.error("Git controller error while stopping play session: %s", error)
                messagebox.showerror("MineGit", str(error))
                return

            self._set_status(
                "[ERR]",
                "Unexpected error while stopping play session.",
                start_enabled=False,
                stop_enabled=False,
            )
            self.logger.exception("Unexpected error while stopping play session.")
            messagebox.showerror("MineGit", str(error))

        self._start_background_task("stop_playing", worker, on_success, on_error)


def main() -> None:
    logging.getLogger("minegit").setLevel(logging.DEBUG)
    app = MineGitApp()
    app.mainloop()


if __name__ == "__main__":
    main()
