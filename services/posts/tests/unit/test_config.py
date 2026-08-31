import importlib


def test_database_url_uses_every_database_setting() -> None:
    config = importlib.import_module("posts.config")
    settings = config.Settings(
        db_host="database.internal",
        db_port=5544,
        db_name="posts_test",
        db_user="posts_user",
        db_password="secret",
        accounts_base_url="http://accounts.internal:8000",
        accounts_timeout_seconds=1.5,
    )

    assert settings.database_url == (
        "postgresql+psycopg://posts_user:secret@database.internal:5544/posts_test"
    )


def test_accounts_connection_has_an_explicit_positive_timeout() -> None:
    config = importlib.import_module("posts.config")
    settings = config.Settings(
        db_host="database.internal",
        db_port=5544,
        db_name="posts_test",
        db_user="posts_user",
        db_password="secret",
        accounts_base_url="http://accounts.internal:8000",
        accounts_timeout_seconds=1.5,
    )

    assert str(settings.accounts_base_url) == "http://accounts.internal:8000/"
    assert settings.accounts_timeout_seconds == 1.5
