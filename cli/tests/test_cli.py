"""P3: CLI 子命令 smoke test (不执行网络/文件操作).

Uses subprocess instead of click.testing.CliRunner because `main` is a
function (click.group decorator), not a click.Group instance.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def _zhihu2obsidian(*args: str) -> tuple[int, str]:
    result = subprocess.run(
        [sys.executable, "-m", "zhihu2obsidian", *args],
        capture_output=True,
        text=True,
        cwd=str(Path(__file__).parent.parent),
    )
    return result.returncode, result.stdout + result.stderr


def test_cli_help() -> None:
    """--help 应正常输出."""
    code, out = _zhihu2obsidian("--help")
    assert code == 0
    assert "usage:" in out.lower()
    assert "config" in out
    assert "auth" in out
    assert "sync" in out
    assert "knowledge" in out
    assert "search" in out
    assert "write" in out
    assert "check" in out


def test_cli_config_help() -> None:
    """config 子命令应正常."""
    code, out = _zhihu2obsidian("config", "--help")
    assert code == 0
    for cmd in ("init", "set", "show"):
        assert cmd in out


def test_cli_auth_help() -> None:
    """auth 子命令应正常."""
    code, out = _zhihu2obsidian("auth", "--help")
    assert code == 0
    for cmd in ("login", "status", "import"):
        assert cmd in out


def test_cli_knowledge_help() -> None:
    """knowledge 子命令应正常."""
    code, out = _zhihu2obsidian("knowledge", "--help")
    assert code == 0
    for cmd in ("build", "rebuild", "status", "cards", "topics"):
        assert cmd in out


def test_cli_write_help() -> None:
    """write 子命令应正常."""
    code, out = _zhihu2obsidian("write", "--help")
    assert code == 0
    assert "--package" in out
    assert "--draft" in out
    assert "--check" in out


def test_cli_check_help() -> None:
    """check 子命令应正常."""
    code, out = _zhihu2obsidian("check", "--help")
    assert code == 0


def test_cli_monthly_help() -> None:
    """monthly 子命令应正常."""
    code, out = _zhihu2obsidian("monthly", "--help")
    assert code == 0
