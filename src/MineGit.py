import logging
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox

from controller.GitController import GitController, GitControllerError
from services.logging_service import configure_tkinter_logging
from view import build_main_layout, update_play_buttons_state


class MineGitApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("MineGit")
        self.geometry("760x420")
        self.minsize(640, 360)

        self.repo_path_var = tk.StringVar(value=str(Path.cwd()))
        self.lock_path_var = tk.StringVar(value="player.lock")
        self.status_icon_var = tk.StringVar(value="[... ]")
        self.status_var = tk.StringVar(value="Ready.")

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
        )
        self.logger = configure_tkinter_logging(self.ui.log_widget)
        self.logger.info("MineGit UI initialized.")
        self.after(120, self.initialize_status)

    def _new_controller(self) -> GitController:
        repository = self.repo_path_var.get().strip()
        lock_path = self.lock_path_var.get().strip() or "player.lock"
        self.logger.debug("Creating controller with repo='%s' lock='%s'.", repository, lock_path)

        if not repository:
            raise GitControllerError("Please provide a repository path.")

        return GitController(repository_path=repository, lock_file_relative_path=lock_path)

    def on_browse_repository(self) -> None:
        selected_directory = filedialog.askdirectory(
            title="Select repository directory",
            initialdir=self.repo_path_var.get().strip() or str(Path.cwd()),
        )
        if selected_directory:
            self.repo_path_var.set(selected_directory)
            self.logger.info("Repository selected: %s", selected_directory)
            self.refresh_status(run_fetch=True)
        else:
            self.logger.debug("Repository browse canceled by user.")

    def on_refresh_clicked(self) -> None:
        self.logger.debug("Manual refresh requested.")
        self.refresh_status(run_fetch=True)

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
        update_play_buttons_state(
            start_button=self.ui.start_button,
            stop_button=self.ui.stop_button,
            start_enabled=start_enabled,
            stop_enabled=stop_enabled,
        )

    def initialize_status(self) -> None:
        self.logger.debug("Running initial repository status check.")
        self.refresh_status(run_fetch=True)

    def refresh_status(self, run_fetch: bool, allow_auto_pull: bool = True) -> None:
        self.logger.debug(
            "Refreshing status run_fetch=%s allow_auto_pull=%s",
            run_fetch,
            allow_auto_pull,
        )
        try:
            controller = self._new_controller()
            if run_fetch:
                self.logger.debug("Running fetch before computing status.")
                controller.fetch()

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
                message = f"You are already playing as {username}."
                self._set_status("[PLAY]", message, start_enabled=False, stop_enabled=True)
                self.logger.info(message)
                return

            if behind > 0 and ahead == 0:
                if remote_owner:
                    message = f"{remote_owner} is hosting now. Pull is blocked until their session ends."
                    self._set_status("[WAIT]", message, start_enabled=False, stop_enabled=False)
                    self.logger.warning(message)
                    return

                if allow_auto_pull:
                    self.logger.debug("Behind remote with no lock owner. Pulling updates automatically.")
                    controller.pull_latest()
                    self.refresh_status(run_fetch=False, allow_auto_pull=False)
                    return

                self._set_status(
                    "[ERR]",
                    "Auto-pull did not converge. Resolve repository state manually.",
                    start_enabled=False,
                    stop_enabled=False,
                )
                self.logger.error("Auto-pull did not converge. Manual intervention required.")
                return

            if ahead > 0 and behind > 0:
                message = "Local and remote branches diverged. Resolve conflicts manually."
                self._set_status("[ERR]", message, start_enabled=False, stop_enabled=False)
                self.logger.error(message)
                return

            if ahead > 0:
                if local_owner == username:
                    message = f"You are already playing as {username}."
                    self._set_status("[PLAY]", message, start_enabled=False, stop_enabled=True)
                else:
                    message = (
                        "Repository is ahead but player.lock is not yours. "
                        "Resolve this state manually before continuing."
                    )
                    self._set_status("[ERR]", message, start_enabled=False, stop_enabled=False)
                self.logger.info(message)
                return

            message = "Repository is in sync. You can start playing."
            self._set_status("[OK]", message, start_enabled=True, stop_enabled=False)
            self.logger.info(message)
            return
        except GitControllerError as error:
            self._set_status("[ERR]", str(error), start_enabled=False, stop_enabled=False)
            self.logger.error("Git controller error while checking status: %s", error)
            messagebox.showerror("MineGit", str(error))
        except Exception as error:
            self._set_status(
                "[ERR]",
                "Unexpected error while checking repository status.",
                start_enabled=False,
                stop_enabled=False,
            )
            self.logger.exception("Unexpected error while checking repository status.")
            messagebox.showerror("MineGit", str(error))

    def on_start_playing(self) -> None:
        self.logger.debug("Start button clicked.")
        try:
            controller = self._new_controller()
            result = controller.start_playing()
            if result.success:
                self.logger.info(result.message)
            else:
                self.logger.warning(result.message)
            if not result.success:
                self._set_status("[WAIT]", result.message, start_enabled=False, stop_enabled=False)
                messagebox.showwarning("MineGit", result.message)
            else:
                self.refresh_status(run_fetch=True)
        except GitControllerError as error:
            self._set_status("[ERR]", str(error), start_enabled=False, stop_enabled=False)
            self.logger.error("Git controller error while starting play session: %s", error)
            messagebox.showerror("MineGit", str(error))
        except Exception as error:
            self._set_status(
                "[ERR]",
                "Unexpected error while starting play session.",
                start_enabled=False,
                stop_enabled=False,
            )
            self.logger.exception("Unexpected error while starting play session.")
            messagebox.showerror("MineGit", str(error))

    def on_stop_playing(self) -> None:
        self.logger.debug("Stop button clicked.")
        try:
            controller = self._new_controller()
            result = controller.stop_playing()
            if result.success:
                self.logger.info(result.message)
            else:
                self.logger.warning(result.message)
            if not result.success:
                self._set_status("[WAIT]", result.message, start_enabled=False, stop_enabled=False)
                messagebox.showwarning("MineGit", result.message)
            else:
                self.refresh_status(run_fetch=True)
        except GitControllerError as error:
            self._set_status("[ERR]", str(error), start_enabled=False, stop_enabled=False)
            self.logger.error("Git controller error while stopping play session: %s", error)
            messagebox.showerror("MineGit", str(error))
        except Exception as error:
            self._set_status(
                "[ERR]",
                "Unexpected error while stopping play session.",
                start_enabled=False,
                stop_enabled=False,
            )
            self.logger.exception("Unexpected error while stopping play session.")
            messagebox.showerror("MineGit", str(error))


def main() -> None:
    logging.getLogger("minegit").setLevel(logging.DEBUG)
    app = MineGitApp()
    app.mainloop()


if __name__ == "__main__":
    main()
