from unittest.mock import patch

from termframe.config import AppSettings, Config, SessionPreset, load_config, save_config


def test_load_config_missing_file_returns_defaults(tmp_path):
    with patch("termframe.launcher.default_shell", return_value="powershell.exe"):
        config = load_config(tmp_path / "does-not-exist.yaml")

    assert config.application.border_thickness == 6
    assert config.application.default_shell == "powershell.exe"
    assert config.sessions == []


def test_save_and_load_roundtrip(tmp_path):
    path = tmp_path / "config.yaml"
    original = Config(
        application=AppSettings(border_thickness=8, default_shell="cmd.exe", show_tray_icon=False),
        sessions=[
            SessionPreset(name="DEV", shell="pwsh.exe", cwd="C:\\Repos\\App", color="#3B82F6"),
            SessionPreset(name="PROD", shell="pwsh.exe", cwd=None, color="#EF4444"),
        ],
    )

    save_config(original, path)
    loaded = load_config(path)

    assert loaded == original


def test_load_config_creates_parent_directory(tmp_path):
    path = tmp_path / "nested" / "dir" / "config.yaml"
    save_config(Config(), path)

    assert path.exists()


def test_load_config_ignores_unknown_fields_and_missing_keys(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text("application:\n  border_thickness: 9\nsessions:\n  - name: AWS\n", encoding="utf-8")

    config = load_config(path)

    assert config.application.border_thickness == 9
    assert config.application.default_shell == "pwsh.exe"
    assert config.sessions == [SessionPreset(name="AWS")]


def test_load_config_recovers_from_corrupt_yaml(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text("not: valid: yaml: [", encoding="utf-8")

    with patch("termframe.launcher.default_shell", return_value="powershell.exe"):
        config = load_config(path)

    assert config == Config(application=AppSettings(default_shell="powershell.exe"))


def test_border_thickness_is_clamped():
    assert AppSettings(border_thickness=0).border_thickness == 2
    assert AppSettings(border_thickness=99).border_thickness == 12
