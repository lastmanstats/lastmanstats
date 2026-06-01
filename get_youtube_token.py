"""
Script one-time per ottenere il YouTube refresh token.
Esegui una sola volta dal tuo Mac, poi copia il token nel .env e nei GitHub Secrets.

Richiede nel .env (o come env vars):
  YOUTUBE_CLIENT_ID=...
  YOUTUBE_CLIENT_SECRET=...
"""

import os
import sys

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from google_auth_oauthlib.flow import InstalledAppFlow

CLIENT_ID = os.environ.get("YOUTUBE_CLIENT_ID", "").strip()
CLIENT_SECRET = os.environ.get("YOUTUBE_CLIENT_SECRET", "").strip()

if not CLIENT_ID or not CLIENT_SECRET:
    print("Errore: YOUTUBE_CLIENT_ID e YOUTUBE_CLIENT_SECRET devono essere nel .env")
    sys.exit(1)

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

client_config = {
    "installed": {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "redirect_uris": ["urn:ietf:wg:oauth:2.0:oob", "http://localhost"],
    }
}

flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
credentials = flow.run_local_server(port=0)

print("\n" + "="*60)
print("YOUTUBE_REFRESH_TOKEN:")
print(credentials.refresh_token)
print("="*60)
print("\nCopia questo valore nel .env e nei GitHub Secrets.")
