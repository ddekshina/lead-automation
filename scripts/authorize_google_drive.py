#!/usr/bin/env python3
"""
One-time setup: authorize Google Drive uploads for your personal Gmail account.

1. Google Cloud Console -> APIs & Services -> Credentials
2. Enable Google Drive API
3. Create OAuth client ID (Desktop app) -> save as google_oauth_client.json
4. Run: python scripts/authorize_google_drive.py
5. Add to .env: GOOGLE_DRIVE_TOKEN_JSON=google_drive_token.json
"""

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv

load_dotenv(PROJECT_ROOT / ".env")

from app.bootstrap import configure_ssl

configure_ssl()

try:
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
except ImportError:
    print("Install dependencies: pip install google-auth-oauthlib google-api-python-client")
    sys.exit(1)

# Full drive scope required to upload into an existing user-owned folder.
SCOPES = ["https://www.googleapis.com/auth/drive"]
CLIENT_FILE = PROJECT_ROOT / "google_oauth_client.json"
TOKEN_FILE = PROJECT_ROOT / "google_drive_token.json"


def _verify_folder(service, folder_id: str) -> bool:
    try:
        folder = service.files().get(
            fileId=folder_id,
            fields="id, name",
            supportsAllDrives=True,
        ).execute()
        print(f"Folder OK: {folder.get('name')} ({folder_id})")
        return True
    except Exception as e:
        print(f"Cannot access folder {folder_id}: {e}")
        return False


def main():
    if not CLIENT_FILE.exists():
        print(f"Missing {CLIENT_FILE.name}")
        print("Download OAuth Desktop credentials from Google Cloud Console.")
        sys.exit(1)

    flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_FILE), SCOPES)
    creds = flow.run_local_server(port=0)

    TOKEN_FILE.write_text(creds.to_json(), encoding="utf-8")
    print(f"\nSaved token to: {TOKEN_FILE}")

    service = build("drive", "v3", credentials=creds)
    folder_id = os.getenv("GOOGLE_DRIVE_FOLDER_ID", "").strip()

    if folder_id:
        if not _verify_folder(service, folder_id):
            print(
                "\nFix GOOGLE_DRIVE_FOLDER_ID: open your Drive folder in the browser, "
                "copy the ID from the URL, and update .env"
            )
    else:
        print("\nTip: set GOOGLE_DRIVE_FOLDER_ID in .env to your target folder ID.")

    print("\nAdd to your .env file:")
    print(f"  GOOGLE_DRIVE_TOKEN_JSON={TOKEN_FILE.name}")


if __name__ == "__main__":
    main()
