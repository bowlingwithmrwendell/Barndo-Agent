"""Local-disk provider for development and testing."""

from __future__ import annotations

from pathlib import Path

from app.storage import SUBFOLDERS, ProvisionResult, StorageProvider, project_folder_name


class LocalStorage(StorageProvider):
    name = "local"

    def __init__(self, root: str):
        self.root = Path(root)

    def provision_project(self, project_id: str, project_name: str) -> ProvisionResult:
        folder_name = project_folder_name(project_id, project_name)
        base = self.root / folder_name
        for sub in SUBFOLDERS:
            (base / sub).mkdir(parents=True, exist_ok=True)
        return ProvisionResult(self.name, str(base.resolve()), folder_name, list(SUBFOLDERS))
