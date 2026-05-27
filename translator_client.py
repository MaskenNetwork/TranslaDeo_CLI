import asyncio
import logging
import time
from typing import Dict, Optional

from config import Settings


class MetadataTranslator:
    def __init__(self, settings: Settings) -> None:
        from googletrans import Translator

        self.settings = settings
        self.translator = Translator()
        self.loop = asyncio.get_event_loop()

    def close(self) -> None:
        self.loop.close()

    def translate(self, title: str, description: str, language_code: str) -> Optional[Dict[str, str]]:
        async def _translate():
            return await asyncio.gather(
                self.translator.translate(title, dest=language_code),
                self.translator.translate(description, dest=language_code),
            )

        for attempt in range(self.settings.max_retries):
            try:
                logging.info(
                    "Translating metadata to %s (%s/%s)...",
                    language_code,
                    attempt + 1,
                    self.settings.max_retries,
                )
                title_translation, description_translation = self.loop.run_until_complete(_translate())
                if title_translation and description_translation:
                    return {
                        "title": title_translation.text,
                        "description": description_translation.text,
                    }
            except Exception as error:
                logging.error("Error while translating to %s: %s", language_code, error)

            time.sleep(self.settings.retry_wait_seconds)

        return None
