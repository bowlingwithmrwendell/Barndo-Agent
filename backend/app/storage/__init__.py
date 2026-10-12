"""Cloud storage providers for per-project folders (spec section 4).

Root/
  [Project_ID] - [Project_Name]/
    Blueprints/
    Site_Photos/
    Invoices_Receipts/
    Client_Docs/
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass

SUBFOLDERS = ["Blueprints", "Site_Photos", "Invoices_Receipts", "Client_Docs"]


def project_folder_name(project_id: str, project_name: str) -> str:
    # Strip characters that Windows, Drive or Dropbox reject or treat specially.
    safe = re.sub(r'[\\/:*?"<>|]+', "-", project_name).strip().strip(".")
    safe = re.sub(r"\s+", " ", safe)[:120] or "Untitled"
    return f"{project_id} - {safe}"


@dataclass
class ProvisionResult:
    provider: str
    folder_ref: str  # provider-specific id or path of the project folder
    folder_name: str
    subfolders: list[str]


class StorageProvider(ABC):
    name: str

    @abstractmethod
    def provision_project(self, project_id: str, project_name: str) -> ProvisionResult:
        """Create (idempotently) the project folder and its standard subfolders."""


def get_provider() -> StorageProvider:
    from app.config import get_settings

    s = get_settings()
    if s.storage_provider == "local":
        from app.storage.local import LocalStorage

        return LocalStorage(s.storage_local_root)
    if s.storage_provider == "dropbox":
        from app.storage.dropbox import DropboxStorage

        return DropboxStorage(s.dropbox_access_token, s.dropbox_root_path)
    if s.storage_provider == "gdrive":
        from app.storage.gdrive import GoogleDriveStorage

        return GoogleDriveStorage(s.gdrive_service_account_file, s.gdrive_root_folder_id)
    raise ValueError(f"Unknown STORAGE_PROVIDER: {s.storage_provider}")
