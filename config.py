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

TRANSLATION_LANGUAGE_ALIASES: Dict[str, str] = {
    "zh-CN": "zh-cn",
    "zh-TW": "zh-tw",
}

LANGUAGE_MAP: Dict[str, str] = {
    'af': 'Afrikaans',
    'am': 'Amharic',
    'ar': 'Arabic',
    'as': 'Assamese',
    'az': 'Azerbaijani',
    'be': 'Belarusian',
    'bg': 'Bulgarian',
    'bn': 'Bangla',
    'bs': 'Bosnian',
    'ca': 'Catalan',
    'cs': 'Czech',
    'da': 'Danish',
    'de': 'German',
    'el': 'Greek',
    'en': 'English',
    'es': 'Spanish',
    'et': 'Estonian',
    'eu': 'Basque',
    'fa': 'Persian',
    'fi': 'Finnish',
    'fil': 'Filipino',
    'fr': 'French',
    'gl': 'Galician',
    'gu': 'Gujarati',
    'hi': 'Hindi',
    'hr': 'Croatian',
    'hu': 'Hungarian',
    'hy': 'Armenian',
    'id': 'Indonesian',
    'is': 'Icelandic',
    'it': 'Italian',
    'iw': 'Hebrew',
    'ja': 'Japanese',
    'ka': 'Georgian',
    'kk': 'Kazakh',
    'km': 'Khmer',
    'kn': 'Kannada',
    'ko': 'Korean',
    'ky': 'Kyrgyz',
    'lo': 'Lao',
    'lt': 'Lithuanian',
    'lv': 'Latvian',
    'mk': 'Macedonian',
    'ml': 'Malayalam',
    'mn': 'Mongolian',
    'mr': 'Marathi',
    'ms': 'Malay',
    'my': 'Burmese',
    'no': 'Norwegian',
    'ne': 'Nepali',
    'nl': 'Dutch',
    'or': 'Odia',
    'pa': 'Punjabi',
    'pl': 'Polish',
    'pt': 'Portuguese',
    'ro': 'Romanian',
    'ru': 'Russian',
    'si': 'Sinhala',
    'sk': 'Slovak',
    'sl': 'Slovenian',
    'sq': 'Albanian',
    'sr': 'Serbian',
    'sv': 'Swedish',
    'sw': 'Swahili',
    'ta': 'Tamil',
    'te': 'Telugu',
    'th': 'Thai',
    'tr': 'Turkish',
    'uk': 'Ukrainian',
    'ur': 'Urdu',
    'uz': 'Uzbek',
    'vi': 'Vietnamese',
    'zh-CN': 'Chinese (China)',
    'zh-TW': 'Chinese (Taiwan)',
    'zu': 'Zulu'
}
