import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

import git


class GitControllerError(RuntimeError):
    """Raised when MineGit cannot complete a git action safely."""


@dataclass
class OperationResult:
    success: bool
    message: str
    lock_owner: Optional[str] = None


class GitController:
    def __init__(self, repository_path: str, lock_file_relative_path: str = "player.lock") -> None:
        self.repository_path = Path(repository_path).expanduser().resolve()
        self.lock_file_relative_path = lock_file_relative_path.replace("\\", "/")
        self.lock_file_path = self.repository_path / self.lock_file_relative_path

        if not self.repository_path.exists():
            raise GitControllerError(f"Repository path does not exist: {self.repository_path}")

        try:
            self.repo = git.Repo(self.repository_path)
        except git.InvalidGitRepositoryError as error:
            raise GitControllerError(f"Not a git repository: {self.repository_path}") from error

        if not self.repo.remotes:
            raise GitControllerError("Repository has no configured remotes.")
        if "origin" not in [remote.name for remote in self.repo.remotes]:
            raise GitControllerError("Repository needs an 'origin' remote configured.")

        self.remote = self.repo.remotes.origin

    def fetch(self) -> None:
        self.remote.fetch()

    def pull_latest(self) -> None:
        self.remote.pull(self.repo.active_branch.name)

    def get_sync_counts(self) -> Tuple[int, int]:
        branch_name = self.repo.active_branch.name
        remote_ref_name = f"{self.remote.name}/{branch_name}"

        try:
            self.repo.refs[remote_ref_name]
        except IndexError:
            return (0, 0)

        counts = self.repo.git.rev_list("--left-right", "--count", f"{branch_name}...{remote_ref_name}")
        ahead_raw, behind_raw = counts.strip().split()
        return (int(ahead_raw), int(behind_raw))

    def start_playing(self) -> OperationResult:
        player_name = self.get_git_username()
        self.fetch()

        remote_lock_owner = self.get_remote_lock_owner()
        if remote_lock_owner and remote_lock_owner != player_name:
            return OperationResult(
                success=False,
                message=f"{remote_lock_owner} is currently playing. Join their match first.",
                lock_owner=remote_lock_owner,
            )

        if self.repo.is_dirty(untracked_files=True):
            raise GitControllerError(
                "Local repository has uncommitted changes. Commit or stash before starting."
            )

        self.pull_latest()

        self.write_local_lock(player_name)
        self.repo.index.add([self.lock_file_relative_path])

        if not self.repo.is_dirty(untracked_files=True):
            return OperationResult(
                success=True,
                message=f"Already playing as {player_name}. Lock was already up-to-date.",
                lock_owner=player_name,
            )

        self.repo.index.commit(f"started playing as {player_name}")
        self.remote.push(self.repo.active_branch.name)
        return OperationResult(
            success=True,
            message=f"Lock acquired. Started playing as {player_name}.",
            lock_owner=player_name,
        )

    def stop_playing(self) -> OperationResult:
        player_name = self.get_git_username()
        self.fetch()

        remote_lock_owner = self.get_remote_lock_owner()
        if remote_lock_owner and remote_lock_owner != player_name:
            return OperationResult(
                success=False,
                message=f"Cannot stop this session. Current lock owner is {remote_lock_owner}.",
                lock_owner=remote_lock_owner,
            )

        self.write_local_lock(None)
        self.repo.git.add(A=True)

        if not self.repo.is_dirty(untracked_files=True):
            return OperationResult(
                success=True,
                message=f"No changes to commit. Lock already clear for {player_name}.",
                lock_owner=None,
            )

        self.repo.index.commit(f"stopped playing as {player_name}")
        self.remote.push(self.repo.active_branch.name)
        return OperationResult(
            success=True,
            message=f"Stopped playing as {player_name}. Changes were pushed.",
            lock_owner=None,
        )

    def get_remote_lock_owner(self) -> Optional[str]:
        branch_name = self.repo.active_branch.name
        remote_ref_name = f"{self.remote.name}/{branch_name}"

        try:
            remote_ref = self.repo.refs[remote_ref_name]
        except IndexError:
            return None
        return self.read_lock_from_commit(remote_ref.commit)

    def get_local_lock_owner(self) -> Optional[str]:
        if not self.lock_file_path.exists():
            return None

        return self.normalize_lock_content(self.lock_file_path.read_text(encoding="utf-8"))

    def get_git_username(self) -> str:
        try:
            return self.repo.config_reader().get_value("user", "name")
        except Exception:
            pass

        try:
            global_name = self.repo.git.config("--global", "--get", "user.name").strip()
            if global_name:
                return global_name
        except Exception:
            pass

        fallback_name = os.environ.get("USER", "").strip()
        if fallback_name:
            return fallback_name

        raise GitControllerError(
            "Unable to determine git username. Set git config user.name first."
        )

    def read_lock_from_commit(self, commit) -> Optional[str]:
        try:
            blob = commit.tree / self.lock_file_relative_path
        except KeyError:
            return None

        raw_value = blob.data_stream.read().decode("utf-8")
        return self.normalize_lock_content(raw_value)

    def write_local_lock(self, player_name: Optional[str]) -> None:
        self.lock_file_path.parent.mkdir(parents=True, exist_ok=True)
        value = "" if player_name is None else player_name
        self.lock_file_path.write_text(f"{value}\n", encoding="utf-8")

    @staticmethod
    def normalize_lock_content(raw_value: str) -> Optional[str]:
        cleaned = raw_value.strip()
        return cleaned if cleaned else None
