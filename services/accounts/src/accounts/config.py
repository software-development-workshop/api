from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Both the routes and the link in the verification email hang off this, and they have to
# agree: a link nobody serves is a dead account.
API_PREFIX = "/api/v1"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    db_host: str
    db_port: int
    db_name: str
    db_user: str
    db_password: str

    resend_api_key: str

    # Resend refuses any address whose domain is not verified in the account behind the key.
    mail_from: str

    # Where the link in the verification email points. It is the client's address, not this
    # service's: in production a reverse proxy sits in front.
    public_base_url: str

    jwt_secret: str = Field(min_length=32)

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+psycopg://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
