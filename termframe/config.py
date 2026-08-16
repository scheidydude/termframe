"""Persisted application settings and session presets.

Config lives at %APPDATA%\\TermFrame\\config.yaml. Kept independent of the
GUI/win32 modules so it stays trivially unit-testable.
"""

from __future__ import annotations

import logging
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path

import yaml

log = logging.getLogger(__name__)

MIN_THICKNESS = 2
MAX_THICKNESS = 12

_DEFAULT_COLOR = "#3B82F6"
_DEFAULT_SHELL = "pwsh.exe"


@dataclass
class AppSettings:
    border_thickness: int = 6
    default_shell: str = _DEFAULT_SHELL
    show_tray_icon: bool = True

    def __post_init__(self) -> None:
        self.border_thickness = max(MIN_THICKNESS, min(MAX_THICKNESS, self.border_thickness))


@dataclass
class SessionPreset:
    name: str
    shell: str = _DEFAULT_SHELL
    cwd: str | None = None
    color: str = _DEFAULT_COLOR


@dataclass
class Config:
    application: AppSettings = field(default_factory=AppSettings)
    sessions: list[SessionPreset] = field(default_factory=list)


def default_config_path() -> Path:
    appdata = os.environ.get("APPDATA")
    base = Path(appdata) if appdata else Path.home() / "AppData" / "Roaming"
    return base / "TermFrame" / "config.yaml"


def _default_config() -> Config:
    # Deferred import: launcher pulls in subprocess/uuid only, but this keeps
    # config.py's own import surface minimal for the common load_config() path.
    from .launcher import default_shell

    return Config(application=AppSettings(default_shell=default_shell()))


def load_config(path: Path | None = None) -> Config:
    path = path or default_config_path()
    if not path.exists():
        return _default_config()

    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        log.warning("Could not read config at %s (%s); using defaults", path, exc)
        return _default_config()

    return _from_dict(raw)


def _from_dict(raw: dict) -> Config:
    defaults = AppSettings()
    app_raw = raw.get("application") or {}
    application = AppSettings(
        border_thickness=app_raw.get("border_thickness", defaults.border_thickness),
        default_shell=app_raw.get("default_shell", defaults.default_shell),
        show_tray_icon=app_raw.get("show_tray_icon", defaults.show_tray_icon),
    )

    sessions = [
        SessionPreset(
            name=session_raw["name"],
            shell=session_raw.get("shell", _DEFAULT_SHELL),
            cwd=session_raw.get("cwd"),
            color=session_raw.get("color", _DEFAULT_COLOR),
        )
        for session_raw in raw.get("sessions") or []
        if session_raw.get("name")
    ]

    return Config(application=application, sessions=sessions)


def save_config(config: Config, path: Path | None = None) -> None:
    path = path or default_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "application": asdict(config.application),
        "sessions": [asdict(session) for session in config.sessions],
    }
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
