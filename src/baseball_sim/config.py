from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "baseball-sim"
    app_env: str = "dev"
    api_prefix: str = "/api/v1"
    db_dsn: str = "postgresql://postgres:postgres@localhost:5432/baseball"
    migrations_dir: str = "migrations"
    raw_data_dir: str = "data/raw"
    mlb_stats_api_base_url: str = "https://statsapi.mlb.com/api/v1"
    mlb_stats_timeout_seconds: float = 15.0
    mlb_stats_max_attempts: int = 3
    mlb_stats_backoff_seconds: float = 0.25
    mlb_stats_sport_id: int = 1
    simulator_ruleset_path: str = "rulesets/mlb_2026_regular.json"
    stats_source: str = "synthetic"
    stats_season: int = 2026
    default_seed: int = 42
    default_model_version: str = "baseline-v1"
    default_data_snapshot_id: str = "snapshot-bootstrap-0001"
    response_rounding_decimals: int = 4

    model_config = SettingsConfigDict(
        env_prefix="BASEBALL_",
        env_file=".env",
        extra="ignore",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
