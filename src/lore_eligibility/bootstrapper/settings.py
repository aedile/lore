"""Application settings loaded from environment variables.

See .env.example for the canonical reference of every variable, its
defaults, and its validation rules.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration sourced from environment variables.

    Pydantic-settings reads values from .env (when present) and the
    process environment. Extra variables in .env are ignored to keep
    forward compatibility with future config additions.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    environment: str = "dev"
    database_url: str = ""
    secret_key: str = ""
    audit_key: str = ""
    pii_encryption_key: str = ""
    artifact_signing_key: str = ""
    auth_mode: str = "jwt"
    database_tls_enabled: bool = False
    telemetry_enabled: bool = True


def get_settings() -> Settings:
    """Construct and return the active Settings instance.

    Returns:
        Settings populated from .env and the process environment.
    """
    return Settings()
