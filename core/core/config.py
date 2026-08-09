import os
from dataclasses import dataclass
from enum import Enum


class Environment(str, Enum):
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


@dataclass
class DatabaseConfig:
    dbname: str
    user: str
    password: str
    host: str
    port: str

    @classmethod
    def from_env(cls):
        return cls(
            dbname=os.getenv("DB_NAME", "cps_engine"),
            user=os.getenv("DB_USER", "cps_user"),
            password=os.getenv("DB_PASSWORD", "cps_pass"),
            host=os.getenv("DB_HOST", "localhost"),
            port=os.getenv("DB_PORT", "5432"),
        )


@dataclass
class GeminiConfig:
    api_key: str
    model: str
    temperature: float
    max_tokens: int

    @classmethod
    def from_env(cls):
        return cls(
            api_key=os.getenv("GEMINI_API_KEY", ""),
            model=os.getenv("GEMINI_MODEL", "gemini-1.5-pro"),
            temperature=float(os.getenv("TEMPERATURE", "0.3")),
            max_tokens=int(os.getenv("MAX_TOKENS", "2048")),
        )


@dataclass
class CPSConfig:
    environment: Environment
    app_name: str
    version: str
    database: DatabaseConfig
    gemini: GeminiConfig
    graph_name: str
    enable_telemetry: bool
    enable_cache: bool
    cache_ttl: int

    @classmethod
    def from_env(cls):
        environment_value = os.getenv(
            "ENVIRONMENT",
            "development"
        ).lower()

        try:
            environment = Environment(environment_value)
        except ValueError:
            environment = Environment.DEVELOPMENT

        return cls(
            environment=environment,
            app_name=os.getenv(
                "APP_NAME",
                "CPS Engine"
            ),
            version=os.getenv(
                "APP_VERSION",
                "2.0.0"
            ),
            database=DatabaseConfig.from_env(),
            gemini=GeminiConfig.from_env(),
            graph_name=os.getenv(
                "GRAPH_NAME",
                "hausahistory"
            ),
            enable_telemetry=os.getenv(
                "ENABLE_TELEMETRY",
                "true"
            ).lower() == "true",
            enable_cache=os.getenv(
                "ENABLE_CACHE",
                "true"
            ).lower() == "true",
            cache_ttl=int(
                os.getenv(
                    "CACHE_TTL",
                    "3600"
                )
            ),
        )


config = CPSConfig.from_env()
