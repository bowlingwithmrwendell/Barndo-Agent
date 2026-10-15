"""Export published public records only; private research requires a separate privileged backup."""
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

url = os.environ["SUPABASE_URL"].rstrip("/")
key = os.environ["SUPABASE_PUBLISHABLE_KEY"]
headers = {"apikey": key}
if key.startswith("eyJ"):
    headers["Authorization"] = "Bearer " + key
records = []
for offset in range(0, 100000, 500):
    request = Request(url + f"/rest/v1/builder_companies?select=*&order=id.asc&limit=500&offset={offset}", headers=headers)
    with urlopen(request, timeout=30) as response:
        batch = json.load(response)
    records.extend(batch)
    if len(batch) < 500:
        break
else:
    raise RuntimeError("Export limit reached; no backup saved")
path = Path("backups") / ("builders-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + ".json")
path.parent.mkdir(exist_ok=True)
path.write_text(json.dumps(records, indent=2) + "\n")
print(f"Exported {len(records)} published records to {path}")
