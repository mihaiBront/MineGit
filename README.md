# MineGit

MineGit is a desktop app (Tkinter + GitPython) that lets a group use a Git repository as a lightweight Minecraft world host workflow.

Instead of running a dedicated Minecraft server, players sync a shared world folder through Git and coordinate play sessions with a lock file (`player.lock`).

## Concept

MineGit treats Git as the source of truth for a world save and enforces a simple "one active host at a time" flow:

- A player clicks **Start playing**.
- MineGit fetches remote changes and checks `player.lock`.
- If another player is listed in `player.lock`, MineGit blocks pull/start and tells you who is hosting.
- If lock is empty, MineGit pulls, writes your username into `player.lock`, commits, and pushes.
- When done, player clicks **Stop playing**.
- MineGit clears `player.lock`, commits world changes, and pushes.

This gives you:

- versioned world history
- clear ownership of active sessions
- simple collaboration without maintaining a server

## Features

- Tkinter GUI for world sync/start/stop flow
- Git status/state aware controls
- asynchronous UI (no freezing during git operations)
- color-coded status panel
- in-app log console with severity colors
- toggle to show/hide debug logs (persisted in settings)
- persistent app settings in `minegitSettings.ini`

## Prerequisites

- Git
- Python 3
- Tkinter available in your Python install

Configure git username on each machine:

```bash
git config --global user.name "Your Name"
```

## Quick Start

### Linux

```bash
./run.sh
```

### Windows

```bat
run.bat
```

Both scripts:

- create a local `.venv` if missing
- install dependencies from `src/requirements.txt`
- run `src/MineGit.py`

## Usage Guide

1. **Prepare your world repository**
   - Put your Minecraft world files in a Git repository.
   - Push it to a shared remote (GitHub/GitLab/etc).

2. **Use the world gitignore template**
   - Start from `minecraft-world.gitignore.template`.
   - Copy/adjust it inside the world repo as `.gitignore`.

3. **Open MineGit**
   - Set **Repository path** to your local world repo.
   - Keep lock file path as `player.lock` (or customize it).

4. **Start a session**
   - Click **Start playing**.
   - MineGit acquires lock (if available), commits, and pushes.
   - Launch Minecraft and play that world locally.

5. **Finish a session**
   - Exit Minecraft first.
   - Click **Stop playing**.
   - MineGit clears lock, commits your world changes, and pushes.

6. **If lock is owned by someone else**
   - Do not pull/start.
   - Join that player or wait for them to stop.

## Build Scripts

- `build_appimage.sh`: build Linux AppImage
- `build_exe.bat`: build Windows `.exe` on Windows
- `build_exe.sh`: build Windows `.exe` from Linux using Docker
- `clean_build_products.sh`: remove generated build artifacts

## Notes

- This tool is designed around a cooperative workflow, not concurrent world editing.
- Avoid editing the same world simultaneously on multiple machines.
- Keep commits and pushes frequent by always using Start/Stop in MineGit.
