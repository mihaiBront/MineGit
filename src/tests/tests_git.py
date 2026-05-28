import tempfile
import unittest
from pathlib import Path

import git

from controller.GitController import GitController


class TestGitController(unittest.TestCase):
    def test_normalize_lock_content(self) -> None:
        self.assertIsNone(GitController.normalize_lock_content(""))
        self.assertIsNone(GitController.normalize_lock_content("   \n"))
        self.assertEqual(GitController.normalize_lock_content("Alex\n"), "Alex")

    def test_get_local_lock_owner(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_path = Path(tmp)
            repo = git.Repo.init(repo_path)
            repo.create_remote("origin", repo_path.as_uri())

            controller = GitController(str(repo_path))
            self.assertIsNone(controller.get_local_lock_owner())

            (repo_path / "player.lock").write_text("Steve\n", encoding="utf-8")
            self.assertEqual(controller.get_local_lock_owner(), "Steve")


if __name__ == "__main__":
    unittest.main()
