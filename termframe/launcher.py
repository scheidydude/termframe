"""Windows Terminal command construction and process launching.

Kept isolated from HWND discovery and session bookkeeping so the command
line can be unit tested without actually spawning wt.exe.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
import uuid

log = logging.getLogger(__name__)

WT_EXECUTABLE = "wt.exe"

SUPPORTED_SHELLS = ("pwsh.exe", "powershell.exe", "cmd.exe")


def default_shell() -> str:
    """The first SUPPORTED_SHELLS entry actually found on PATH.

    PowerShell 7 (pwsh.exe) isn't installed by default on every Windows
    machine — falling back through the supported list avoids defaulting the
    New Terminal dialog to a shell that doesn't exist here.
    """
    for shell in SUPPORTED_SHELLS:
        if shutil.which(shell):
            return shell
    return SUPPORTED_SHELLS[0]


def generate_launch_title(name: str) -> str:
    """A title that is both human-readable and unique enough to search for.

    The uuid suffix guarantees EnumWindows-based discovery never matches an
    unrelated window (including a previous TermFrame session's leftovers),
    while the visible "<name> — TermFrame" prefix keeps it recognizable in
    Alt+Tab and the taskbar.
    """
    return f"{name} — TermFrame [{uuid.uuid4().hex[:8]}]"


def build_wt_command(title: str, shell: str, cwd: str | None = None) -> list[str]:
    """Build the wt.exe argv that opens a new *window* (not a new tab).

    `-w new` forces window targeting rather than delegating to an existing
    Windows Terminal window/tab, which is required so DEV/PROD/AWS end up as
    separate top-level windows.
    """
    args = [WT_EXECUTABLE, "-w", "new", "--title", title]
    if cwd:
        args += ["-d", cwd]
    args.append(shell)
    return args


def launch_windows_terminal(title: str, shell: str = "pwsh.exe", cwd: str | None = None) -> subprocess.Popen:
    command = build_wt_command(title=title, shell=shell, cwd=cwd)
    log.info("Launching: %s", " ".join(command))
    return subprocess.Popen(command, shell=False)
