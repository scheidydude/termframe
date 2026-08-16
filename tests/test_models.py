from termframe.models import TerminalSession


def test_defaults():
    session = TerminalSession(id="abc123", name="DEV", shell="pwsh.exe")

    assert session.cwd is None
    assert session.process_id is None
    assert session.hwnd is None
    assert session.status == "starting"
    assert session.color == "#3B82F6"


def test_explicit_fields():
    session = TerminalSession(
        id="abc123",
        name="PROD",
        shell="cmd.exe",
        cwd="C:\\Repos\\Infra",
        color="#EF4444",
        process_id=1234,
        hwnd=0x00012345,
        status="running",
    )

    assert session.name == "PROD"
    assert session.cwd == "C:\\Repos\\Infra"
    assert session.hwnd == 0x00012345
    assert session.status == "running"
