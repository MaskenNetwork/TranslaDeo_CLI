from dataclasses import dataclass
from typing import Dict, List


@dataclass(frozen=True)
class Settings:
    youtube_credentials_file: str = "client_secret_youtube.json"
    youtube_token_file: str = "token.json"
    cache_file: str = "translation_cache.json"
    video_ids_file: str = "video_ids.csv"
    default_video_language: str = "it"
    max_retries: int = 5
    retry_wait_seconds: int = 15
    dry_run: bool = False


YOUTUBE_SCOPES: List[str] = ["https://www.googleapis.com/auth/youtube.force-ssl"]

REGION_SENSITIVE_LANGUAGE_CODES = {"zh-CN", "zh-TW"}

LANGUAGE_MAP: Dict[str, str] = {
    "en": "English",
    "fr": "French",
    "de": "German",
    "it": "Italian",
    "es": "Spanish"
}
