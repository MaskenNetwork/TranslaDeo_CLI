import asyncio
import logging
import time
from typing import Dict, Optional

from config import Settings, TRANSLATION_LANGUAGE_ALIASES


def translation_language_code(language_code: str) -> str:
    code = language_code.replace("_", "-").lower()
    aliases = {key.lower(): value for key, value in TRANSLATION_LANGUAGE_ALIASES.items()}
    return aliases.get(code, code.split("-", 1)[0])


def serbian_latin(text: str) -> str:
    letters = dict(zip(
        "абвгдђежзијклљмнњопрстћуфхцчџш",
        ("a", "b", "v", "g", "d", "đ", "e", "ž", "z", "i", "j", "k", "l", "lj", "m",
         "n", "nj", "o", "p", "r", "s", "t", "ć", "u", "f", "h", "c", "č", "dž", "š"),
    ))
    converted = []
    for index, character in enumerate(text):
        replacement = letters.get(character.lower(), character)
        if character.isupper():
            next_is_upper = index + 1 < len(text) and text[index + 1].isupper()
            replacement = replacement.upper() if next_is_upper else replacement.title()
        converted.append(replacement)
    return "".join(converted)


class TranslationServiceBlocked(RuntimeError):
    """The translation service is rejecting requests for this run."""


class MetadataTranslator:
    def __init__(self, settings: Settings) -> None:
        from googletrans import Translator

        self.settings = settings
        # Otherwise googletrans silently returns the source text on HTTP errors.
        self.translator = Translator(raise_exception=True, transport="curl")
        self.loop = asyncio.new_event_loop()
        self._last_request_time: float | None = None

    def close(self) -> None:
        try:
            self.loop.run_until_complete(self.translator.aclose())
        finally:
            self.loop.close()

    def translate(
        self,
        title: str,
        description: str,
        language_code: str,
        source_language_code: str = "auto",
    ) -> Optional[Dict[str, str]]:
        destination_code = translation_language_code(language_code)
        source_language_code = translation_language_code(source_language_code)
        source_metadata = {"title": title, "description": description}

        async def _translate():
            translated_metadata = {}
            for field, text in source_metadata.items():
                if not text.strip():
                    translated_metadata[field] = text
                    continue
                if self._last_request_time is not None:
                    wait = self.settings.translation_request_interval_seconds - (
                        time.monotonic() - self._last_request_time
                    )
                    if wait > 0:
                        await asyncio.sleep(wait)
                self._last_request_time = time.monotonic()
                result = await self.translator.translate(
                    text, dest=destination_code, src=source_language_code,
                )
                if not result or not isinstance(result.text, str) or not result.text.strip():
                    raise ValueError(f"Empty translation for {field}.")
                translated_metadata[field] = (
                    serbian_latin(result.text)
                    if language_code.lower() == "sr-latn"
                    else result.text
                )

            if (
                any(character.isalpha() for text in source_metadata.values() for character in text)
                and all(
                    translated_metadata[field].strip() == text.strip()
                    for field, text in source_metadata.items()
                )
            ):
                raise ValueError("Title and description are unchanged; refusing to upload an unverified translation.")
            return translated_metadata

        for attempt in range(self.settings.max_retries):
            try:
                logging.info(
                    "Translating metadata to %s (%s/%s)...",
                    language_code,
                    attempt + 1,
                    self.settings.max_retries,
                )
                translated_metadata = self.loop.run_until_complete(_translate())
                logging.info("Translated title (%s): %s", language_code, translated_metadata["title"])
                return translated_metadata
            except Exception as error:
                status_code = getattr(error, "status_code", None)
                if status_code in (403, 429):
                    raise TranslationServiceBlocked(
                        f"Google Translate is blocking requests (HTTP {status_code}). "
                        "Stopped to avoid retrying every language. Wait before retrying; "
                        "check availability with --check-translation."
                    ) from error
                logging.error("Error while translating to %s: %s", language_code, error)

            if attempt + 1 < self.settings.max_retries:
                time.sleep(self.settings.retry_wait_seconds)

        logging.error("Translation to %s failed; this language will not be uploaded.", language_code)
        return None
