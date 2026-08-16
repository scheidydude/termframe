from dataclasses import dataclass
from typing import Literal

SessionStatus = Literal["starting", "running", "closed", "error"]


@dataclass
class TerminalSession:
    id: str
    name: str
    shell: str
    cwd: str | None = None
    color: str = "#3B82F6"
    process_id: int | None = None
    hwnd: int | None = None
    status: SessionStatus = "starting"
