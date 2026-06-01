"""
upload_youtube.py
Scopo: Carica il video YouTube usando le credenziali OAuth2 dalle env vars.
Dipendenze: google-api-python-client, google-auth-httplib2
"""

import os
import sys
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

try:
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    from googleapiclient.errors import HttpError
except ImportError:
    logger.error("Installa: pip install google-api-python-client google-auth-httplib2")
    sys.exit(1)


def get_credentials() -> Optional[Credentials]:
    client_id = os.environ.get("YOUTUBE_CLIENT_ID", "").strip()
    client_secret = os.environ.get("YOUTUBE_CLIENT_SECRET", "").strip()
    refresh_token = os.environ.get("YOUTUBE_REFRESH_TOKEN", "").strip()

    if not all([client_id, client_secret, refresh_token]):
        logger.error("Credenziali YouTube mancanti nelle env vars.")
        return None

    creds = Credentials(
        token=None,
        refresh_token=refresh_token,
        client_id=client_id,
        client_secret=client_secret,
        token_uri="https://oauth2.googleapis.com/token",
    )
    try:
        creds.refresh(Request())
        return creds
    except Exception as e:
        logger.error(f"Refresh token YouTube fallito: {e}")
        return None


def upload_video(
    video_path: str,
    title: str,
    description: str,
    tags: list,
    privacy: str = "public"
) -> Optional[str]:
    """
    Carica un video su YouTube. Restituisce il video_id o None in caso di errore.
    """
    if not Path(video_path).exists():
        logger.error(f"File video non trovato: {video_path}")
        return None

    creds = get_credentials()
    if not creds:
        return None

    try:
        youtube = build("youtube", "v3", credentials=creds)

        body = {
            "snippet": {
                "title": title[:100],
                "description": description[:5000],
                "tags": tags,
                "categoryId": "17",  # Sports
                "defaultLanguage": "en",
            },
            "status": {
                "privacyStatus": privacy,
                "selfDeclaredMadeForKids": False,
            }
        }

        media = MediaFileUpload(
            video_path,
            mimetype="video/mp4",
            chunksize=4 * 1024 * 1024,
            resumable=True
        )

        request = youtube.videos().insert(
            part="snippet,status",
            body=body,
            media_body=media
        )

        logger.info(f"Upload in corso: {Path(video_path).name}")
        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                logger.info(f"  {int(status.progress() * 100)}%")

        video_id = response.get("id")
        logger.info(f"[OK] YouTube: https://youtu.be/{video_id}")
        return video_id

    except HttpError as e:
        logger.error(f"Errore YouTube API: {e}")
        return None
    except Exception as e:
        logger.error(f"Errore upload: {e}")
        return None
