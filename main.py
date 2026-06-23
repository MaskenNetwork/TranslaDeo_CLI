import argparse
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Tuple

from cache_store import CacheStore
from config import LANGUAGE_MAP, REGION_SENSITIVE_LANGUAGE_CODES, Settings
from translator_client import MetadataTranslator
from video_ids import load_video_ids
from youtube_client import YouTubeClient


logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Translate and safely upload YouTube localizations.")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done without writing to YouTube.")
    parser.add_argument("--force-fetch", action="store_true", help="Fetch source metadata from YouTube again.")
    parser.add_argument("--force-retranslate", action="store_true", help="Translate languages already marked as completed.")
    return parser.parse_args()


def normalize_language_code(language_code: str) -> str:
    if language_code in REGION_SENSITIVE_LANGUAGE_CODES:
        return language_code

    return language_code.split("-", 1)[0].lower()


def is_same_language(first_code: str, second_code: str) -> bool:
    return normalize_language_code(first_code) == normalize_language_code(second_code)


def choose_source_language(video_id: str, default_language: str | None, default_audio_language: str | None) -> str | None:
    if default_language and default_audio_language:
        if is_same_language(default_language, default_audio_language):
            return default_language

        logging.warning(
            "Video %s has defaultLanguage=%s and defaultAudioLanguage=%s.",
            video_id,
            default_language,
            default_audio_language,
        )
        while True:
            choice = input(
                "Which language do you want to use as the translation source? "
                f"[1] defaultLanguage ({default_language}) / "
                f"[2] defaultAudioLanguage ({default_audio_language}): "
            ).strip()
            if choice == "1":
                return default_language
            if choice == "2":
                return default_audio_language
            logging.warning("Invalid choice. Enter 1 or 2.")

    if default_language:
        return default_language

    if default_audio_language:
        return default_audio_language

    logging.error(
        "Il video %s non ha ne defaultLanguage ne defaultAudioLanguage. "
        "Set the video language in YouTube Studio and run the CLI again.",
        video_id,
    )
    return None


def get_or_fetch_video_data(
    youtube: YouTubeClient,
    video_id: str,
    cache: Dict[str, Any],
    cache_store: CacheStore,
    settings: Settings,
    force_fetch: bool,
) -> Tuple[Dict[str, Any], bool]:
    if video_id not in cache:
        cache[video_id] = {}

    has_cached_defaults = (
        "default_metadata" in cache[video_id]
        and "source_language_code" in cache[video_id]
        and "youtube_channel_id" in cache[video_id]
    )

    if not force_fetch and has_cached_defaults:
        return cache[video_id], True

    result = youtube.get_default_metadata(video_id)
    if not result:
        return {}, False

    source_language_code = choose_source_language(
        video_id,
        result["default_language"],
        result["default_audio_language"],
    )
    if not source_language_code:
        return {}, False

    cache[video_id]["source_language_code"] = source_language_code
    cache[video_id]["youtube_default_language"] = result["default_language"]
    cache[video_id]["youtube_default_audio_language"] = result["default_audio_language"]
    cache[video_id]["youtube_channel_id"] = result["channel_id"]
    cache[video_id]["default_data_timestamp_utc"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    cache[video_id]["default_metadata"] = {
        "title": result["title"],
        "description": result["description"],
    }
    translated_languages = cache[video_id].setdefault("translated_languages", {})
    for language_code in LANGUAGE_MAP:
        translated_languages.setdefault(language_code, False)

    cache_store.save(cache)
    return cache[video_id], True


def process_video(
    youtube: YouTubeClient,
    translator: MetadataTranslator,
    video_id: str,
    cache: Dict[str, Any],
    cache_store: CacheStore,
    settings: Settings,
    force_fetch: bool,
    force_retranslate: bool,
) -> None:
    video_data, ok = get_or_fetch_video_data(
        youtube,
        video_id,
        cache,
        cache_store,
        settings,
        force_fetch,
    )
    if not ok:
        logging.error("Skipping %s: video data is not available.", video_id)
        return

    source_language_code = video_data["source_language_code"]
    source_metadata = video_data["default_metadata"]
    channel_id = video_data.get("youtube_channel_id", "")
    if channel_id and not settings.dry_run and not youtube.can_update_video(video_id, channel_id):
        return

    translated_languages = video_data.get("translated_languages", {})
    localizations_to_upload: Dict[str, Dict[str, str]] = {}
    uploaded_language_codes = set()

    for language_code, language_name in LANGUAGE_MAP.items():
        if is_same_language(language_code, source_language_code):
            logging.info(
                "Skipping %s (%s): it matches the video's source language (%s).",
                language_name,
                language_code,
                source_language_code,
            )
            translated_languages[language_code] = True
            continue

        if translated_languages.get(language_code) and not force_retranslate:
            continue

        logging.info("Translating %s (%s) for %s.", language_name, language_code, video_id)
        translated_metadata = translator.translate(
            source_metadata["title"],
            source_metadata["description"],
            language_code,
        )
        if translated_metadata:
            localizations_to_upload[language_code] = translated_metadata
            uploaded_language_codes.add(language_code)

    if not localizations_to_upload:
        logging.info("No new localizations to upload for %s.", video_id)
        return

    if not youtube.update_localizations_only(video_id, localizations_to_upload, dry_run=settings.dry_run):
        logging.error("Upload failed for %s. Translated languages were not marked as completed.", video_id)
        return

    for language_code in uploaded_language_codes:
        translated_languages[language_code] = True

    cache[video_id]["translated_languages"] = translated_languages
    cache_store.save(cache)


def main() -> None:
    args = parse_args()
    settings = Settings(dry_run=args.dry_run)
    cache_store = CacheStore(settings.cache_file)
    cache = cache_store.load()
    video_ids = load_video_ids(settings.video_ids_file)

    if not video_ids:
        logging.info("No video IDs found.")
        return

    youtube = YouTubeClient(settings)
    translator = MetadataTranslator(settings)
    try:
        for video_id in video_ids:
            logging.info("Starting video %s.", video_id)
            try:
                process_video(
                    youtube,
                    translator,
                    video_id,
                    cache,
                    cache_store,
                    settings,
                    force_fetch=args.force_fetch,
                    force_retranslate=args.force_retranslate,
                )
            except Exception as error:
                logging.exception("Unexpected error while processing %s: %s", video_id, error)
                logging.info("Continuing with the next video.")
    finally:
        translator.close()


if __name__ == "__main__":
    main()
