import pytest


@pytest.fixture
def home(tmp_path, monkeypatch):
    """Point ~ at a temp dir on every OS (expanduser reads USERPROFILE on Windows)."""
    h = tmp_path / "home"
    h.mkdir()
    monkeypatch.setenv("HOME", str(h))
    monkeypatch.setenv("USERPROFILE", str(h))
    monkeypatch.delenv("AI_GRIMOIRE_CONFIG", raising=False)
    return h
