import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

import git

logger = logging.getLogger("minegit.controller")


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
        logger.debug("Initialized controller for repo: %s", self.repository_path)

    def fetch(self) -> None:
        logger.debug("Fetching from remote '%s'.", self.remote.name)
        self.remote.fetch()

    def pull_latest(self) -> None:
        logger.debug("Pulling latest changes for branch '%s'.", self.repo.active_branch.name)
        self.remote.pull(self.repo.active_branch.name)

    def get_sync_counts(self) -> Tuple[int, int]:
        branch_name = self.repo.active_branch.name
        remote_ref_name = f"{self.remote.name}/{branch_name}"

        try:
            self.repo.refs[remote_ref_name]
        except IndexError:
            logger.debug("Remote ref '%s' does not exist yet.", remote_ref_name)
            return (0, 0)

        counts = self.repo.git.rev_list("--left-right", "--count", f"{branch_name}...{remote_ref_name}")
        ahead_raw, behind_raw = counts.strip().split()
        logger.debug("Sync status for '%s': ahead=%s behind=%s", branch_name, ahead_raw, behind_raw)
        return (int(ahead_raw), int(behind_raw))

    def start_playing(self) -> OperationResult:
        player_name = self.get_git_username()
        logger.info("Start playing requested by '%s'.", player_name)
        self.fetch()

        remote_lock_owner = self.get_remote_lock_owner()
        if remote_lock_owner and remote_lock_owner != player_name:
            logger.warning("Start blocked; lock is currently owned by '%s'.", remote_lock_owner)
            return OperationResult(
                success=False,
                message=f"{remote_lock_owner} is currently playing. Join their match first.",
                lock_owner=remote_lock_owner,
            )

        if self.repo.is_dirty(untracked_files=True):
            logger.error("Start blocked; local repository has uncommitted changes.")
            raise GitControllerError(
                "Local repository has uncommitted changes. Commit or stash before starting."
            )

        self.pull_latest()
        logger.debug("Writing local lock for '%s' at '%s'.", player_name, self.lock_file_relative_path)

        self.write_local_lock(player_name)
        self.repo.index.add([self.lock_file_relative_path])

        if not self.repo.is_dirty(untracked_files=True):
            logger.debug("No changes after writing lock; already playing as '%s'.", player_name)
            return OperationResult(
                success=True,
                message=f"Already playing as {player_name}. Lock was already up-to-date.",
                lock_owner=player_name,
            )

        logger.debug("Committing and pushing start-playing state for '%s'.", player_name)
        self.repo.index.commit(f"started playing as {player_name}")
        self.remote.push(self.repo.active_branch.name)
        logger.info("Lock acquired and pushed for '%s'.", player_name)
        return OperationResult(
            success=True,
            message=f"Lock acquired. Started playing as {player_name}.",
            lock_owner=player_name,
        )

    def stop_playing(self) -> OperationResult:
        player_name = self.get_git_username()
        logger.info("Stop playing requested by '%s'.", player_name)
        self.fetch()

        remote_lock_owner = self.get_remote_lock_owner()
        if remote_lock_owner and remote_lock_owner != player_name:
            logger.warning("Stop blocked; lock is currently owned by '%s'.", remote_lock_owner)
            return OperationResult(
                success=False,
                message=f"Cannot stop this session. Current lock owner is {remote_lock_owner}.",
                lock_owner=remote_lock_owner,
            )

        logger.debug("Clearing local lock at '%s'.", self.lock_file_relative_path)
        self.write_local_lock(None)
        self.repo.git.add(A=True)

        if not self.repo.is_dirty(untracked_files=True):
            logger.debug("No changes to commit when stopping as '%s'.", player_name)
            return OperationResult(
                success=True,
                message=f"No changes to commit. Lock already clear for {player_name}.",
                lock_owner=None,
            )

        logger.debug("Committing and pushing stop-playing state for '%s'.", player_name)
        self.repo.index.commit(f"stopped playing as {player_name}")
        self.remote.push(self.repo.active_branch.name)
        logger.info("Stop playing changes pushed for '%s'.", player_name)
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
            logger.debug("Remote lock owner unavailable; missing ref '%s'.", remote_ref_name)
            return None
        owner = self.read_lock_from_commit(remote_ref.commit)
        logger.debug("Remote lock owner resolved as '%s'.", owner)
        return owner

    def get_local_lock_owner(self) -> Optional[str]:
        if not self.lock_file_path.exists():
            logger.debug("Local lock file does not exist at '%s'.", self.lock_file_path)
            return None

        owner = self.normalize_lock_content(self.lock_file_path.read_text(encoding="utf-8"))
        logger.debug("Local lock owner resolved as '%s'.", owner)
        return owner

    def get_git_username(self) -> str:
        try:
            username = self.repo.config_reader().get_value("user", "name")
            logger.debug("Resolved git username from repository config: '%s'.", username)
            return username
        except Exception:
            pass

        try:
            global_name = self.repo.git.config("--global", "--get", "user.name").strip()
            if global_name:
                logger.debug("Resolved git username from global config: '%s'.", global_name)
                return global_name
        except Exception:
            pass

        fallback_name = os.environ.get("USER", "").strip()
        if fallback_name:
            logger.debug("Resolved git username from USER env var: '%s'.", fallback_name)
            return fallback_name

        raise GitControllerError(
            "Unable to determine git username. Set git config user.name first."
        )

    def read_lock_from_commit(self, commit) -> Optional[str]:
        try:
            blob = commit.tree / self.lock_file_relative_path
        except KeyError:
            logger.debug("Lock file '%s' not found in commit '%s'.", self.lock_file_relative_path, commit)
            return None

        raw_value = blob.data_stream.read().decode("utf-8")
        owner = self.normalize_lock_content(raw_value)
        logger.debug("Read lock owner '%s' from commit '%s'.", owner, commit)
        return owner

    def write_local_lock(self, player_name: Optional[str]) -> None:
        self.lock_file_path.parent.mkdir(parents=True, exist_ok=True)
        value = "" if player_name is None else player_name
        self.lock_file_path.write_text(f"{value}\n", encoding="utf-8")
        logger.debug("Wrote local lock value '%s' to '%s'.", value, self.lock_file_path)

    @staticmethod
    def normalize_lock_content(raw_value: str) -> Optional[str]:
        cleaned = raw_value.strip()
        return cleaned if cleaned else None
