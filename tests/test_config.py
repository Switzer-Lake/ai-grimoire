import pytest

from grimoire.config import RESOLVERS, config_path, load, render
from grimoire.errors import GrimoireError


def test_defaults_when_no_file(home):
    cfg = load()
    assert cfg.backend == "files"
    assert cfg.loaded_from is None
    assert cfg.files_dir == home / "grimoire"
    assert cfg.handoffs_dir == home / "grimoire" / "handoffs"
    assert cfg.handoffs_index == home / "grimoire" / "handoffs.md"
    assert cfg.reminders_path == home / "grimoire" / "reminders.md"
    assert cfg.identity_order == list(RESOLVERS)


def test_config_path_env_override(home, monkeypatch, tmp_path):
    monkeypatch.setenv("AI_GRIMOIRE_CONFIG", str(tmp_path / "x.toml"))
    assert config_path() == tmp_path / "x.toml"


def test_default_config_path(home):
    assert config_path() == home / ".config" / "ai-grimoire" / "config.toml"


def test_files_overrides(home, tmp_path):
    p = tmp_path / "c.toml"
    p.write_text(
        '[storage]\nbackend = "files"\n'
        '[storage.files]\ndir = "~/vault"\n'
        'handoff_dir = "~/work/handoffs"\n'
        'handoff_index = "~/vault/_idx/handoffs.md"\n'
        'reminders = "~/vault/_idx/reminders.md"\n',
        encoding="utf-8",
    )
    cfg = load(p)
    assert cfg.loaded_from == p
    assert cfg.handoffs_dir == home / "work" / "handoffs"
    assert cfg.handoffs_index == home / "vault" / "_idx" / "handoffs.md"
    assert cfg.reminders_path == home / "vault" / "_idx" / "reminders.md"


def test_postgres_dsn_from_env(home, tmp_path, monkeypatch):
    p = tmp_path / "c.toml"
    p.write_text('[storage]\nbackend = "postgres"\n[storage.postgres]\ndsn_env = "MY_DSN"\n', encoding="utf-8")
    cfg = load(p)
    monkeypatch.delenv("MY_DSN", raising=False)
    with pytest.raises(GrimoireError, match=r"\$MY_DSN"):
        cfg.dsn()
    monkeypatch.setenv("MY_DSN", "postgresql://u:secret@h/db")
    assert cfg.dsn() == "postgresql://u:secret@h/db"
    assert "secret" not in cfg.describe()
    assert cfg.describe() == "postgres ($MY_DSN)"


def test_bad_backend(home, tmp_path):
    p = tmp_path / "c.toml"
    p.write_text('[storage]\nbackend = "redis"\n', encoding="utf-8")
    with pytest.raises(GrimoireError, match="redis"):
        load(p)


def test_bad_resolver(home, tmp_path):
    p = tmp_path / "c.toml"
    p.write_text('[identity]\norder = ["wmux", "screen"]\n', encoding="utf-8")
    with pytest.raises(GrimoireError, match="screen"):
        load(p)


def test_invalid_toml(home, tmp_path):
    p = tmp_path / "c.toml"
    p.write_text("[storage\n", encoding="utf-8")
    with pytest.raises(GrimoireError, match="c.toml"):
        load(p)


def test_render_round_trips_windows_path(home, tmp_path):
    p = tmp_path / "c.toml"
    p.write_text(render("files", files_dir=r"C:\Users\me\My Vault"), encoding="utf-8")
    cfg = load(p)
    assert str(cfg.files_dir) == r"C:\Users\me\My Vault"


def test_render_sql(home, tmp_path):
    p = tmp_path / "c.toml"
    p.write_text(render("mysql", dsn_env="GRIM_DSN"), encoding="utf-8")
    cfg = load(p)
    assert cfg.backend == "mysql"
    assert cfg.dsn_env == "GRIM_DSN"
