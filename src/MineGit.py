import logging
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from controller.GitController import GitController, GitControllerError
from services.logging_service import configure_tkinter_logging


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

        self._build_ui()
        self.logger = configure_tkinter_logging(self.log)
        self.logger.info("MineGit UI initialized.")
        self.after(120, self.initialize_status)

    def _build_ui(self) -> None:
        root = ttk.Frame(self, padding=14)
        root.pack(fill=tk.BOTH, expand=True)

        ttk.Label(root, text="Repository path").grid(row=0, column=0, sticky=tk.W)
        ttk.Entry(root, textvariable=self.repo_path_var).grid(row=1, column=0, columnspan=2, sticky=tk.EW, pady=(3, 10))
        ttk.Button(root, text="Browse...", command=self.on_browse_repository).grid(
            row=1, column=2, sticky=tk.EW, pady=(3, 10), padx=(8, 0)
        )

        ttk.Label(root, text="Lock file (relative to repository)").grid(row=2, column=0, sticky=tk.W)
        ttk.Entry(root, textvariable=self.lock_path_var).grid(
            row=3, column=0, columnspan=3, sticky=tk.EW, pady=(3, 10)
        )

        self.refresh_button = tk.Button(
            root,
            text="Refresh",
            command=self.on_refresh_clicked,
            bg="#1976D2",
            fg="white",
            activebackground="#1565C0",
            activeforeground="white",
            relief=tk.FLAT,
        )
        self.refresh_button.grid(row=4, column=0, sticky=tk.EW, padx=(0, 4))
        self.start_button = tk.Button(
            root,
            text="Start playing",
            command=self.on_start_playing,
            bg="#2E7D32",
            fg="white",
            activebackground="#1B5E20",
            activeforeground="white",
            relief=tk.FLAT,
        )
        self.start_button.grid(row=4, column=1, sticky=tk.EW)
        self.stop_button = tk.Button(
            root,
            text="Stop playing",
            command=self.on_stop_playing,
            bg="#C62828",
            fg="white",
            activebackground="#B71C1C",
            activeforeground="white",
            disabledforeground="#F5F5F5",
            relief=tk.FLAT,
        )
        self.stop_button.grid(row=4, column=2, sticky=tk.EW, padx=(4, 0))

        indicator = ttk.Frame(root)
        indicator.grid(row=5, column=0, columnspan=3, sticky=tk.EW, pady=(12, 6))
        ttk.Label(indicator, textvariable=self.status_icon_var, width=8).grid(row=0, column=0, sticky=tk.W)
        ttk.Label(indicator, textvariable=self.status_var).grid(row=0, column=1, sticky=tk.W)

        self.log = tk.Text(root, height=12, wrap=tk.WORD, state=tk.DISABLED)
        self.log.grid(row=6, column=0, columnspan=3, sticky=tk.NSEW)

        root.columnconfigure(0, weight=1)
        root.columnconfigure(1, weight=1)
        root.columnconfigure(2, weight=1)
        root.rowconfigure(6, weight=1)

    def _new_controller(self) -> GitController:
        repository = self.repo_path_var.get().strip()
        lock_path = self.lock_path_var.get().strip() or "player.lock"

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

    def on_refresh_clicked(self) -> None:
        self.logger.info("Manual refresh requested.")
        self.refresh_status(run_fetch=True)

    def _set_status(self, icon: str, text: str, start_enabled: bool, stop_enabled: bool) -> None:
        self.status_icon_var.set(icon)
        self.status_var.set(text)
        self.start_button.config(
            state=tk.NORMAL if start_enabled else tk.DISABLED,
            bg="#2E7D32" if start_enabled else "#A5D6A7",
            activebackground="#1B5E20" if start_enabled else "#A5D6A7",
            disabledforeground="#F5F5F5",
        )
        self.stop_button.config(
            state=tk.NORMAL if stop_enabled else tk.DISABLED,
            bg="#C62828" if stop_enabled else "#EF9A9A",
            activebackground="#B71C1C" if stop_enabled else "#EF9A9A",
            disabledforeground="#F5F5F5",
        )

    def initialize_status(self) -> None:
        self.logger.info("Running initial repository status check.")
        self.refresh_status(run_fetch=True)

    def refresh_status(self, run_fetch: bool, allow_auto_pull: bool = True) -> None:
        try:
            controller = self._new_controller()
            if run_fetch:
                controller.fetch()

            ahead, behind = controller.get_sync_counts()
            local_owner = controller.get_local_lock_owner()
            remote_owner = controller.get_remote_lock_owner()
            username = controller.get_git_username()
            lock_is_mine = local_owner == username or remote_owner == username

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
                    self.logger.info("Behind remote with no lock owner. Pulling updates automatically.")
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
                self.logger.warning(message)
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
    logging.getLogger("minegit").setLevel(logging.INFO)
    app = MineGitApp()
    app.mainloop()


if __name__ == "__main__":
    main()
