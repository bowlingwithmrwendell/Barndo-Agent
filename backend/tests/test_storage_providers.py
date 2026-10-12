"""Cloud providers tested against mocked HTTP (no real credentials needed)."""

import json

import httpx

from app.storage.dropbox import DropboxStorage
from app.storage.gdrive import GoogleDriveStorage


def test_dropbox_creates_tree_and_tolerates_existing():
    calls = []

    def handler(req: httpx.Request):
        path = json.loads(req.content)["path"]
        calls.append(path)
        if path.endswith("Blueprints"):
            return httpx.Response(409, json={"error_summary": "path/conflict/folder/"})
        return httpx.Response(200, json={"metadata": {"path_display": path}})

    store = DropboxStorage("tok", "Killette Projects", client=httpx.Client(transport=httpx.MockTransport(handler)))
    res = store.provision_project("abc", "Barn")
    assert res.folder_ref == "/Killette Projects/abc - Barn"
    assert calls == [
        "/Killette Projects/abc - Barn",
        "/Killette Projects/abc - Barn/Blueprints",
        "/Killette Projects/abc - Barn/Site_Photos",
        "/Killette Projects/abc - Barn/Invoices_Receipts",
        "/Killette Projects/abc - Barn/Client_Docs",
    ]


def test_gdrive_reuses_existing_and_creates_missing():
    created = []

    def handler(req: httpx.Request):
        assert req.headers["Authorization"] == "Bearer t0k"
        if req.method == "GET":
            q = req.url.params["q"]
            if "name = 'Blueprints'" in q:
                return httpx.Response(200, json={"files": [{"id": "bp-existing", "name": "Blueprints"}]})
            return httpx.Response(200, json={"files": []})
        body = json.loads(req.content)
        created.append((body["name"], body["parents"][0]))
        return httpx.Response(200, json={"id": f"id-{body['name']}"})

    store = GoogleDriveStorage("", "ROOT", client=httpx.Client(transport=httpx.MockTransport(handler)), token="t0k")
    res = store.provision_project("abc", "Barn")
    assert res.folder_ref == "id-abc - Barn"
    assert created == [
        ("abc - Barn", "ROOT"),
        ("Site_Photos", "id-abc - Barn"),
        ("Invoices_Receipts", "id-abc - Barn"),
        ("Client_Docs", "id-abc - Barn"),
    ]
