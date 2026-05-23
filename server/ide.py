"""Detect which workspaces are currently open in VSCode.

Claude Code's VSCode integration drops a lock file per connected window at
~/.claude/ide/<pid>.lock, holding the window's pid and workspace folders. We
read those to answer one question: is this session's cwd open in a live VSCode
window right now?

That gate matters — a vscode://file/<folder> link focuses an open window but
opens a NEW one if the folder is not open. We only ever want to focus, never
spawn, so a session is "focusable" only when its workspace is already open.
"""

import glob
import json
import os

IDE_LOCK_GLOB = os.path.expanduser("~/.claude/ide/*.lock")


def _pid_alive(pid):
    try:
        os.kill(int(pid), 0)
    except (OSError, TypeError, ValueError):
        return False
    return True


def open_workspaces():
    """Return the set of workspace folders open in live VSCode windows."""
    folders = set()
    for lock_path in glob.glob(IDE_LOCK_GLOB):
        try:
            with open(lock_path, encoding="utf-8") as fh:
                lock = json.load(fh)
        except (OSError, json.JSONDecodeError):
            continue
        if not _pid_alive(lock.get("pid")):
            continue  # stale lock — VSCode window is gone
        for folder in lock.get("workspaceFolders", []):
            if folder:
                folders.add(os.path.normpath(folder))
    return folders


def is_open(cwd, folders):
    """True if cwd is, or sits inside, one of the open workspace folders."""
    if not cwd:
        return False
    cwd = os.path.normpath(cwd)
    for folder in folders:
        if cwd == folder or cwd.startswith(folder + os.sep):
            return True
    return False
