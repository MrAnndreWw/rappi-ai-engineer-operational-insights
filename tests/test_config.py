from pathlib import Path

from competitive_intel.config import load_settings


def test_load_default_settings():
    root = Path(__file__).resolve().parents[1]
    settings = load_settings(root / "config")
    assert "platforms" in settings
    assert "rappi" in settings["platforms"]["enabled"]
