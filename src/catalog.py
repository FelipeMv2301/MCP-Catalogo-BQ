import time
import os
import httpx
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # extra="ignore": el mismo .env trae MCP_API_KEY/MCP_TRANSPORT/PORT para
    # el transporte (los lee server.py directo de os.environ) — sin esto,
    # Settings() falla con "Extra inputs are not permitted".
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    catalog_api_url: str
    catalog_api_key: str
    cache_ttl_seconds: int = 900


settings = Settings()

_cache: list[dict] = []
_cache_timestamp: float = 0.0


async def get_catalog() -> list[dict]:
    global _cache, _cache_timestamp

    now = time.monotonic()
    if _cache and (now - _cache_timestamp) < settings.cache_ttl_seconds:
        return _cache

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            settings.catalog_api_url,
            params={"limit": 0},
            headers={"X-API-Key": settings.catalog_api_key},
        )
        response.raise_for_status()

    data = response.json()
    _cache = data.get("items", [])
    _cache_timestamp = now
    return _cache
