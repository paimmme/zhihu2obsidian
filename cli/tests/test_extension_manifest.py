"""Browser extension MVP manifest checks."""

from __future__ import annotations

import json
from pathlib import Path


def test_extension_manifest_declares_local_analysis_flow() -> None:
    root = Path(__file__).resolve().parents[2]
    manifest = json.loads((root / "extension" / "manifest.json").read_text(encoding="utf-8"))

    assert manifest["manifest_version"] == 3
    assert "contextMenus" in manifest["permissions"]
    assert "http://127.0.0.1:8765/*" in manifest["host_permissions"]
    assert manifest["background"]["service_worker"] == "background.js"
    assert manifest["content_scripts"][0]["js"] == ["content.js"]
    assert manifest["side_panel"]["default_path"] == "sidebar.html"
