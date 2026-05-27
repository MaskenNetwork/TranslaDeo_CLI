import logging
import os
from typing import Dict, Optional, TypedDict

from config import YOUTUBE_SCOPES, Settings


class VideoMetadata(TypedDict):
    default_language: Optional[str]
    default_audio_language: Optional[str]
    title: str
    description: str


class YouTubeClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.youtube = self._authenticate()

    def _authenticate(self):
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build

        creds = None
        if os.path.exists(self.settings.youtube_token_file):
            creds = Credentials.from_authorized_user_file(
                self.settings.youtube_token_file,
                YOUTUBE_SCOPES,
            )

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                logging.info("Refreshing YouTube credentials...")
                creds.refresh(Request())
            else:
                if not os.path.exists(self.settings.youtube_credentials_file):
                    raise FileNotFoundError("YouTube credentials file not found.")
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.settings.youtube_credentials_file,
                    YOUTUBE_SCOPES,
                )
                creds = flow.run_local_server(port=0)

            with open(self.settings.youtube_token_file, "w", encoding="utf-8") as token:
                token.write(creds.to_json())

        return build("youtube", "v3", credentials=creds, cache_discovery=False)

    def get_default_metadata(self, video_id: str) -> Optional[VideoMetadata]:
        from googleapiclient.errors import HttpError

        try:
            response = self.youtube.videos().list(part="snippet", id=video_id).execute()
        except HttpError as error:
            logging.error("Error fetching metadata for %s: %s", video_id, error)
            return None

        items = response.get("items", [])
        if not items:
            logging.error("Video %s not found.", video_id)
            return None

        snippet = items[0]["snippet"]
        return {
            "default_language": snippet.get("defaultLanguage"),
            "default_audio_language": snippet.get("defaultAudioLanguage"),
            "title": snippet.get("title", ""),
            "description": snippet.get("description", ""),
        }

    def get_localizations(self, video_id: str) -> Dict[str, Dict[str, str]]:
        from googleapiclient.errors import HttpError

        try:
            response = self.youtube.videos().list(part="localizations", id=video_id).execute()
        except HttpError as error:
            logging.error("Error fetching localizations for %s: %s", video_id, error)
            return {}

        items = response.get("items", [])
        if not items:
            logging.error("Video %s not found.", video_id)
            return {}

        return items[0].get("localizations", {})

    def update_localizations_only(
        self,
        video_id: str,
        localizations: Dict[str, Dict[str, str]],
        dry_run: bool = False,
    ) -> None:
        current_localizations = self.get_localizations(video_id)
        merged_localizations = {**current_localizations, **self._clean_localizations(localizations)}

        if dry_run:
            logging.info(
                "DRY RUN: would upload %s localizations for %s.",
                len(localizations),
                video_id,
            )
            return

        from googleapiclient.errors import HttpError

        try:
            self.youtube.videos().update(
                part="localizations",
                body={"id": video_id, "localizations": merged_localizations},
            ).execute()
        except HttpError as error:
            details = error.content.decode() if hasattr(error, "content") else str(error)
            logging.error("Error updating localizations for %s: %s", video_id, details)
            return

        logging.info("Localizations uploaded for video %s.", video_id)

    @staticmethod
    def _clean_localizations(localizations: Dict[str, Dict[str, str]]) -> Dict[str, Dict[str, str]]:
        cleaned = {}
        for language_code, metadata in localizations.items():
            cleaned[language_code] = {
                "title": metadata.get("title", "")[:100],
                "description": metadata.get("description", "")[:5000],
            }
        return cleaned
