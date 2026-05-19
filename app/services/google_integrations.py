"""
Bonus: Google Sheets logging + Google Drive PDF archiving.

Sheets: service account (GOOGLE_SERVICE_ACCOUNT_JSON).
Drive:  OAuth user token (recommended for personal Gmail) OR service account
        uploading into a Shared Drive / user-owned shared folder.
"""

import json
import logging
import os
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

try:
    from google.oauth2 import service_account
    from google.oauth2.credentials import Credentials as UserCredentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    from googleapiclient.errors import HttpError

    GOOGLE_AVAILABLE = True
except ImportError:
    GOOGLE_AVAILABLE = False
    logger.warning(
        "google-api-python-client not installed. "
        "Google Sheets/Drive features disabled. "
        "Run: pip install google-api-python-client google-auth"
    )

SHEETS_SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
# drive.file only sees app-created files — cannot access an existing user folder.
DRIVE_SCOPES = ["https://www.googleapis.com/auth/drive"]

_HEADERS = [
    "Timestamp", "Full Name", "Work Email",
    "Company Name", "Industry", "Company Size",
    "Report Status", "Scrape Status", "Email Sent",
]


def _resolve_path(env_var: str) -> Path | None:
    raw = os.getenv(env_var, "").strip().strip('"').strip("'")
    if not raw:
        return None
    path = Path(raw)
    if not path.is_absolute():
        project_root = Path(__file__).resolve().parent.parent.parent
        path = project_root / path
    return path if path.exists() else None


def _get_service_account_credentials(scopes: list[str]):
    key_path = _resolve_path("GOOGLE_SERVICE_ACCOUNT_JSON")
    if not key_path:
        raise EnvironmentError(
            "GOOGLE_SERVICE_ACCOUNT_JSON is not set or file not found."
        )
    return service_account.Credentials.from_service_account_file(
        str(key_path), scopes=scopes
    )


def _get_drive_credentials():
    """
    Drive uploads for personal Gmail must use a user's OAuth token.
    Service accounts have no Drive storage quota on consumer accounts.
    """
    token_path = _resolve_path("GOOGLE_DRIVE_TOKEN_JSON")
    if not token_path:
        return _get_service_account_credentials(DRIVE_SCOPES)

    creds = UserCredentials.from_authorized_user_file(str(token_path), DRIVE_SCOPES)

    if not creds.valid:
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            token_path.write_text(creds.to_json(), encoding="utf-8")
        else:
            raise EnvironmentError(
                "Google Drive OAuth token is invalid. "
                "Re-run: python scripts/authorize_google_drive.py"
            )

    # Token was issued with a narrower scope (e.g. drive.file) — must re-authorize.
    if not creds.has_scopes(DRIVE_SCOPES):
        raise EnvironmentError(
            "Google Drive token has insufficient scope. "
            "Re-run: python scripts/authorize_google_drive.py"
        )

    return creds


def _get_service_account_email() -> str | None:
    key_path = _resolve_path("GOOGLE_SERVICE_ACCOUNT_JSON")
    if not key_path:
        return None
    try:
        data = json.loads(key_path.read_text(encoding="utf-8"))
        return data.get("client_email")
    except Exception:
        return None


def log_lead_to_sheet(lead_data: dict, pipeline_result: dict) -> bool:
    """Appends a lead row to the configured Google Sheet."""
    if not GOOGLE_AVAILABLE:
        logger.warning("Skipping Sheets log — google libraries not installed.")
        return False

    sheet_id = os.getenv("GOOGLE_SHEET_ID")
    if not sheet_id:
        logger.warning("GOOGLE_SHEET_ID not set — skipping Sheets log.")
        return False

    try:
        creds = _get_service_account_credentials(SHEETS_SCOPES)
        service = build("sheets", "v4", credentials=creds)
        sheet = service.spreadsheets()

        result = sheet.values().get(
            spreadsheetId=sheet_id, range="Sheet1!A1:I1"
        ).execute()
        if not result.get("values"):
            sheet.values().update(
                spreadsheetId=sheet_id,
                range="Sheet1!A1",
                valueInputOption="RAW",
                body={"values": [_HEADERS]},
            ).execute()

        row = [
            datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
            lead_data.get("full_name", ""),
            lead_data.get("work_email", ""),
            lead_data.get("company_name", ""),
            lead_data.get("industry", ""),
            lead_data.get("company_size", ""),
            "success" if pipeline_result.get("success") else "failed",
            pipeline_result.get("scrape_status", "unknown"),
            str(pipeline_result.get("email_sent", False)),
        ]

        sheet.values().append(
            spreadsheetId=sheet_id,
            range="Sheet1!A1",
            valueInputOption="RAW",
            insertDataOption="INSERT_ROWS",
            body={"values": [row]},
        ).execute()

        logger.info("Lead logged to Google Sheet for %s", lead_data.get("company_name"))
        return True

    except Exception as e:
        logger.error("Failed to log lead to Google Sheet: %s", e)
        return False


def _validate_drive_folder(service, folder_id: str) -> dict | None:
    """Verify folder exists and is writable."""
    try:
        return service.files().get(
            fileId=folder_id,
            fields="id, name, driveId, capabilities, owners",
            supportsAllDrives=True,
        ).execute()
    except HttpError as e:
        if e.resp.status == 404:
            logger.error(
                "Drive folder not found or not accessible: %s. "
                "Use a folder in the Google account you authorized, and copy "
                "the ID from: https://drive.google.com/drive/folders/<ID>",
                folder_id,
            )
        else:
            logger.error("Cannot access Drive folder %s: %s", folder_id, e)
        return None


def _upload_to_folder(service, pdf_path: Path, folder_id: str) -> dict:
    file_metadata = {"name": pdf_path.name, "parents": [folder_id]}
    media = MediaFileUpload(str(pdf_path), mimetype="application/pdf", resumable=True)
    return service.files().create(
        body=file_metadata,
        media_body=media,
        fields="id, webViewLink",
        supportsAllDrives=True,
    ).execute()


def archive_pdf_to_drive(pdf_path: Path, company_name: str) -> str | None:
    """
    Uploads a PDF to a Drive folder.

    Personal Gmail: set GOOGLE_DRIVE_TOKEN_JSON (run scripts/authorize_google_drive.py).
    Google Workspace: service account + Shared Drive folder also works.
    """
    if not GOOGLE_AVAILABLE:
        logger.warning("Skipping Drive archive — google libraries not installed.")
        return None

    folder_id = os.getenv("GOOGLE_DRIVE_FOLDER_ID", "").strip()
    if not folder_id:
        logger.warning("GOOGLE_DRIVE_FOLDER_ID not set — skipping Drive archive.")
        return None

    if not pdf_path or not pdf_path.exists():
        logger.warning("PDF path does not exist: %s", pdf_path)
        return None

    using_oauth = _resolve_path("GOOGLE_DRIVE_TOKEN_JSON") is not None

    try:
        creds = _get_drive_credentials()
        service = build("drive", "v3", credentials=creds)

        folder = _validate_drive_folder(service, folder_id)
        if not folder:
            return None

        if folder.get("driveId"):
            logger.info("Archiving to Shared Drive folder: %s", folder.get("name"))
        elif not using_oauth:
            sa_email = _get_service_account_email()
            owners = [o.get("emailAddress") for o in folder.get("owners", [])]
            if sa_email and owners == [sa_email]:
                logger.error(
                    "Drive folder is owned by the service account, which has no storage. "
                    "Create a folder in your Gmail Drive, share it with the service account, "
                    "or run: python scripts/authorize_google_drive.py"
                )
                return None

        uploaded = _upload_to_folder(service, pdf_path, folder_id)
        link = uploaded.get("webViewLink", "")
        logger.info("PDF archived to Drive for %s: %s", company_name, link)
        return link

    except HttpError as e:
        reason = ""
        if getattr(e, "resp", None) and e.resp.status == 403:
            try:
                details = json.loads(e.content.decode())
                reason = details.get("error", {}).get("errors", [{}])[0].get("reason", "")
            except Exception:
                pass

        if reason == "storageQuotaExceeded" or "storage quota" in str(e).lower():
            logger.error(
                "Drive upload failed: service accounts cannot use personal Drive storage. "
                "Fix: run `python scripts/authorize_google_drive.py` and set "
                "GOOGLE_DRIVE_TOKEN_JSON in .env (see README)."
            )
        else:
            logger.error("Failed to archive PDF to Drive: %s", e)
        return None

    except EnvironmentError as e:
        logger.error("%s", e)
        return None

    except Exception as e:
        logger.error("Failed to archive PDF to Drive: %s", e)
        return None
