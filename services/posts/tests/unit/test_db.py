from types import SimpleNamespace

from sqlalchemy import text

from posts import db


def test_engine_and_session_use_the_configured_database_url(monkeypatch) -> None:
    db.get_engine.cache_clear()
    monkeypatch.setattr(
        db,
        "get_settings",
        lambda: SimpleNamespace(database_url="sqlite+pysqlite:///:memory:"),
    )

    engine = db.get_engine()
    sessions = db.get_session()
    session = next(sessions)

    try:
        assert engine.url.drivername == "sqlite+pysqlite"
        assert session.scalar(text("select 1")) == 1
    finally:
        sessions.close()
        engine.dispose()
        db.get_engine.cache_clear()
