import logging
import os
from json import JSONDecodeError
from typing import Dict, Optional, TypedDict

from config import YOUTUBE_SCOPES, Settings


class VideoMetadata(TypedDict):
    default_language: Optional[str]
    default_audio_language: Optional[str]
    channel_id: str
    title: str
    description: str


class YouTubeClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.youtube = self._authenticate()

    def _authenticate(self):
        from google.auth.transport.requests import Request
        from google.auth.exceptions import RefreshError
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build

        def run_authorization_flow():
            if not os.path.exists(self.settings.youtube_credentials_file):
                raise FileNotFoundError("YouTube credentials file not found.")
            flow = InstalledAppFlow.from_client_secrets_file(
                self.settings.youtube_credentials_file,
                YOUTUBE_SCOPES,
            )
            return flow.run_local_server(port=0)

        creds = None
        if os.path.exists(self.settings.youtube_token_file):
            try:
                creds = Credentials.from_authorized_user_file(
                    self.settings.youtube_token_file,
                    YOUTUBE_SCOPES,
                )
            except (JSONDecodeError, ValueError) as error:
                logging.warning(
                    "Ignoring invalid YouTube token file %s (%s). "
                    "Starting a new authorization flow...",
                    self.settings.youtube_token_file,
                    error,
                )

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                logging.info("Refreshing YouTube credentials...")
                try:
                    creds.refresh(Request())
                except RefreshError as error:
                    logging.warning(
                        "Stored YouTube token could not be refreshed (%s). "
                        "Starting a new authorization flow...",
                        error,
                    )
                    creds = run_authorization_flow()
            else:
                creds = run_authorization_flow()

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
            "channel_id": snippet.get("channelId", ""),
            "title": snippet.get("title", ""),
            "description": snippet.get("description", ""),
        }

    def can_update_video(self, video_id: str, channel_id: str) -> bool:
        from googleapiclient.errors import HttpError

        try:
            response = self.youtube.channels().list(part="id", mine=True).execute()
        except HttpError as error:
            details = error.content.decode() if hasattr(error, "content") else str(error)
            logging.error("Could not verify authenticated YouTube channel: %s", details)
            return False

        authenticated_channel_ids = {
            item["id"]
            for item in response.get("items", [])
            if item.get("id")
        }
        if channel_id in authenticated_channel_ids:
            return True

        logging.error(
            "Authenticated account cannot update video %s. "
            "Video channelId is %s, authenticated channel IDs are: %s. "
            "Delete token.json and authorize with the Google/YouTube account that owns this video.",
            video_id,
            channel_id or "unknown",
            ", ".join(sorted(authenticated_channel_ids)) or "none",
        )
        return False

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
    ) -> bool:
        current_localizations = self.get_localizations(video_id)
        merged_localizations = {**current_localizations, **self._clean_localizations(localizations)}

        if dry_run:
            logging.info(
                "DRY RUN: would upload %s localizations for %s.",
                len(localizations),
                video_id,
            )
            return True

        from googleapiclient.errors import HttpError

        try:
            self.youtube.videos().update(
                part="localizations",
                body={"id": video_id, "localizations": merged_localizations},
            ).execute()
        except HttpError as error:
            details = error.content.decode() if hasattr(error, "content") else str(error)
            logging.error("Error updating localizations for %s: %s", video_id, details)
            return False

        logging.info("Localizations uploaded for video %s.", video_id)
        return True

    @staticmethod
    def _clean_localizations(localizations: Dict[str, Dict[str, str]]) -> Dict[str, Dict[str, str]]:
        cleaned = {}
        for language_code, metadata in localizations.items():
            cleaned[language_code] = {
                "title": metadata.get("title", "")[:100],
                "description": metadata.get("description", "")[:5000],
            }
        return cleaned
