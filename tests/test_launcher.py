import re
from unittest.mock import patch

from termframe.launcher import SUPPORTED_SHELLS, build_wt_command, default_shell, generate_launch_title


def test_generate_launch_title_contains_name():
    title = generate_launch_title("DEV")

    assert title.startswith("DEV — TermFrame [")
    assert re.search(r"\[[0-9a-f]{8}\]$", title)


def test_generate_launch_title_is_unique():
    titles = {generate_launch_title("DEV") for _ in range(100)}

    assert len(titles) == 100


def test_build_wt_command_without_cwd():
    command = build_wt_command(title="DEV — TermFrame [abcd1234]", shell="pwsh.exe")

    assert command == ["wt.exe", "-w", "new", "--title", "DEV — TermFrame [abcd1234]", "pwsh.exe"]


def test_build_wt_command_with_cwd():
    command = build_wt_command(title="PROD — TermFrame [abcd1234]", shell="cmd.exe", cwd="C:\\Repos\\Infra")

    assert command == [
        "wt.exe",
        "-w",
        "new",
        "--title",
        "PROD — TermFrame [abcd1234]",
        "-d",
        "C:\\Repos\\Infra",
        "cmd.exe",
    ]


def test_build_wt_command_omits_dir_flag_when_cwd_is_none():
    command = build_wt_command(title="DEV", shell="pwsh.exe", cwd=None)

    assert "-d" not in command


def test_default_shell_prefers_first_available_on_path():
    with patch("termframe.launcher.shutil.which", side_effect=lambda name: None if name == "pwsh.exe" else name):
        assert default_shell() == "powershell.exe"


def test_default_shell_falls_back_when_nothing_found():
    with patch("termframe.launcher.shutil.which", return_value=None):
        assert default_shell() == SUPPORTED_SHELLS[0]
