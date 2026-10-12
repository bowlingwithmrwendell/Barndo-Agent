"""Dropbox provider (Dropbox API v2, plain HTTPS via httpx).

Auth: a scoped access token with files.content.write (set DROPBOX_ACCESS_TOKEN).
For production, use an app-folder-scoped app so the token can only touch
its own folder (least privilege), and swap to refresh-token OAuth.
"""

from __future__ import annotations

import httpx

from app.storage import SUBFOLDERS, ProvisionResult, StorageProvider, project_folder_name

API = "https://api.dropboxapi.com/2"


class DropboxStorage(StorageProvider):
    name = "dropbox"

    def __init__(self, access_token: str, root_path: str, client: httpx.Client | None = None):
        if not access_token:
            raise ValueError("DROPBOX_ACCESS_TOKEN is not set")
        self.root = "/" + root_path.strip("/")
        self.http = client or httpx.Client(timeout=30, headers={"Authorization": f"Bearer {access_token}"})

    def provision_project(self, project_id: str, project_name: str) -> ProvisionResult:
        folder_name = project_folder_name(project_id, project_name)
        base = f"{self.root}/{folder_name}"
        paths = [base] + [f"{base}/{sub}" for sub in SUBFOLDERS]
        for path in paths:
            r = self.http.post(f"{API}/files/create_folder_v2", json={"path": path, "autorename": False})
            # 409 path/conflict/folder means it already exists: fine, provisioning is idempotent.
            if r.status_code == 409 and "conflict" in r.text:
                continue
            r.raise_for_status()
        return ProvisionResult(self.name, base, folder_name, list(SUBFOLDERS))
