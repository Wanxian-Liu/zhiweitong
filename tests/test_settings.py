from config.settings import load_settings


def test_load_settings_defaults() -> None:
    s = load_settings()
    assert "sqlite" in s.database_url
    assert s.redis_url.startswith("redis://")
