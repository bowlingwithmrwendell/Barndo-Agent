"""Google Drive provider (Drive API v3) using a service account.

Setup:
  1. Create a service account in Google Cloud, enable the Drive API, download its JSON key.
  2. Create a root folder in Drive (or a Shared Drive) and share it with the
     service account's email as Editor. Put that folder's id in GDRIVE_ROOT_FOLDER_ID.
  3. Set GDRIVE_SERVICE_ACCOUNT_FILE to the JSON key path.

The service account only sees folders shared with it, which keeps access
scoped to the project tree (least privilege).
Requires the optional package: google-auth
"""

from __future__ import annotations

import httpx

from app.storage import SUBFOLDERS, ProvisionResult, StorageProvider, project_folder_name

API = "https://www.googleapis.com/drive/v3/files"
FOLDER_MIME = "application/vnd.google-apps.folder"
SCOPES = ["https://www.googleapis.com/auth/drive"]


class GoogleDriveStorage(StorageProvider):
    name = "gdrive"

    def __init__(
        self,
        service_account_file: str,
        root_folder_id: str,
        client: httpx.Client | None = None,
        token: str | None = None,
    ):
        if not root_folder_id:
            raise ValueError("GDRIVE_ROOT_FOLDER_ID is not set")
        self.root_id = root_folder_id
        if token is None:
            token = self._service_account_token(service_account_file)
        self.http = client or httpx.Client(timeout=30)
        self.http.headers["Authorization"] = f"Bearer {token}"

    @staticmethod
    def _service_account_token(path: str) -> str:
        if not path:
            raise ValueError("GDRIVE_SERVICE_ACCOUNT_FILE is not set")
        from google.auth.transport.requests import Request
        from google.oauth2 import service_account

        creds = service_account.Credentials.from_service_account_file(path, scopes=SCOPES)
        creds.refresh(Request())
        return creds.token

    def _find_folder(self, name: str, parent: str) -> str | None:
        escaped = name.replace("\\", "\\\\").replace("'", "\\'")
        q = f"name = '{escaped}' and '{parent}' in parents and mimeType = '{FOLDER_MIME}' and trashed = false"
        r = self.http.get(
            API,
            params={
                "q": q,
                "fields": "files(id,name)",
                "supportsAllDrives": "true",
                "includeItemsFromAllDrives": "true",
            },
        )
        r.raise_for_status()
        files = r.json().get("files", [])
        return files[0]["id"] if files else None

    def _ensure_folder(self, name: str, parent: str) -> str:
        existing = self._find_folder(name, parent)
        if existing:
            return existing
        r = self.http.post(
            API,
            params={"supportsAllDrives": "true", "fields": "id"},
            json={"name": name, "mimeType": FOLDER_MIME, "parents": [parent]},
        )
        r.raise_for_status()
        return r.json()["id"]

    def provision_project(self, project_id: str, project_name: str) -> ProvisionResult:
        folder_name = project_folder_name(project_id, project_name)
        base_id = self._ensure_folder(folder_name, self.root_id)
        for sub in SUBFOLDERS:
            self._ensure_folder(sub, base_id)
        return ProvisionResult(self.name, base_id, folder_name, list(SUBFOLDERS))
