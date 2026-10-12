# Barndo Build Agent — Killette Innovations

Construction project management for barndominiums and conventional homes.

| Part | Status |
|---|---|
| 1. Python backend (`backend/`) | **MVP built**: projects, budget & alert engine, encrypted client info, cloud folders, feedback log |
| 4. Website agent for barndobible.com | **Built**: Claude chat grounded in the site's guides, material estimator, embeddable widget |
| 2. Android app (`android/`) | Next |
| 3. Cloud storage (Drive / Dropbox) | Folder provisioning built; file upload/sync next |

---

## Running the backend on Windows

You need Python 3.12+ (python.org). In PowerShell:

```powershell
cd "C:\Users\wkill\Barndo Agent\backend"
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt

copy .env.example .env
python -m app.crypto genkey        # paste the output into PII_ENCRYPTION_KEY in .env
# edit API_KEYS in .env with your own long random keys

pytest -q                          # all tests should pass
uvicorn app.main:app --reload
```

Open **http://127.0.0.1:8000/docs** to see every endpoint and try them. Click **Authorize** and enter one of your API keys.

With Docker Desktop installed you can run `docker compose up --build` from the top-level folder instead.

> Keep `.env` safe. If you lose `PII_ENCRYPTION_KEY`, the stored client details can't be decrypted.

---

## Website agent (barndobible.com)

A chat assistant and material estimator that sit on barndobible.com as a floating **Ask BarndoBible** button.

**How it answers.** At startup, and every 12 hours after that, the backend pulls every published post and page from barndobible.com's public WordPress API. Privacy, contact and similar pages are skipped. It splits the content into sections and keeps a searchable copy in `data/kb.json`. For each question it finds the most relevant sections, and Claude answers from them with links back to the guides. Claude can also search the guides again, or run the material estimator, when it needs to. A new blog post is picked up on the next refresh. You can also force a refresh with `POST /admin/kb/refresh` (admin key).

**Material estimator.** `app/estimator.py` gives quantities, not prices, for a rectangular gable-roof building: concrete and rebar, metal panels and trim, spray foam, interior framing and drywall. Every rule of thumb it uses is listed under "How these were calculated". Door and window openings are not deducted, so the numbers run slightly high on purpose.

### Try it on your computer

1. In `backend\.env`, set `ANTHROPIC_API_KEY=` to a key from the Claude Console (platform.claude.com → API keys, in "Wendell's Individual Org").
2. Run `python -m app.agent.kb sync`. It should report about 40 articles.
3. Start the server: `uvicorn app.main:app --reload`.
4. Open **http://127.0.0.1:8000/widget/**, a preview page with the widget on it.

### Put it on barndobible.com

1. Deploy the backend to a public HTTPS address, for example `https://api.barndobible.com` (Cloud Run with a custom domain). Set `ANTHROPIC_API_KEY` as a secret there, and set `FORWARDED_ALLOW_IPS=*` so rate limits see visitors' real IPs.
2. In WordPress, go to **Code Snippets → + Add Snippet** (WPCode), add an HTML snippet, set it to **Site Wide Footer**, and paste:
   ```html
   <script src="https://api.barndobible.com/widget/barndo-agent.js" defer></script>
   ```
3. In **LiteSpeed Cache → Page Optimization**, add `barndo-agent.js` to the JS excludes, so the cache's script optimization can't break the widget.
4. Optional: put the estimator inside a page, such as your Tools pages. Add a Custom HTML block with `<div id="barndo-estimator"></div>`, and use `data-inline="#barndo-estimator" data-tab="estimate"` on the script tag on that page.
5. Add a line to the privacy policy: questions typed into the assistant are sent to Anthropic to generate answers and are not stored by BarndoBible.

### Cost and abuse guards

- The API key stays on the server. The widget only talks to your backend.
- Each visitor IP gets at most 15 questions per 10 minutes, and the whole site at most 500 per day (`PUBLIC_RATE_LIMIT`, `AGENT_DAILY_LIMIT`). Check today's count with `GET /admin/agent/usage`.
- Rough cost on `claude-sonnet-5-5` ($2 input / $10 output per million tokens): about 1 to 3 cents per question, so a full 500-question day is about $5 to $15. Set `AGENT_MODEL=claude-haiku-5-5` for a much cheaper model.
- The text of chats is not logged or stored on the server. The visitor's browser keeps the conversation only for that tab session.

| Method | Path | Purpose |
|---|---|---|
| POST | `/public/chat` | Ask the assistant (no key, rate-limited) |
| POST | `/public/estimate` | Material quantities (no key) |
| GET | `/public/status` | Is the assistant configured; knowledge base size and last sync |
| GET | `/widget/barndo-agent.js` | The embeddable widget |
| POST | `/admin/kb/refresh` | Re-pull the guides now (admin) |
| GET | `/admin/agent/usage` | Chats today vs the daily cap (admin) |

---

## Budget engine (spec section 5)

Each cost entry has a `cost_type`, and the type decides which formula term it counts toward:

| cost_type | Counts toward |
|---|---|
| `invoice`, `labor`, `material` | E_actual (actual spend) |
| `purchase_order`, `unbilled_subcontract` | C_committed |
| `remaining_estimate` | Remaining estimated costs |

- P_total = E_actual + C_committed + remaining estimates
- CV = B_total − P_total
- BR% = (E_actual + C_committed) ÷ B_total × 100
- **Warning** when BR% ≥ 85. **Critical** when BR% ≥ 100 or CV < 0.

Thresholds are checked against the exact ratio, so 84.999% does not trip the 85% warning. They can be changed with `BUDGET_WARNING_PCT` and `BUDGET_CRITICAL_PCT`. Each time a project's alert level changes, an alert event is logged (`GET /projects/{id}/alerts`). The engine is in `app/budget.py` and has no database code, so it can be ported line for line to Kotlin for offline use in the app.

## Roles (send the key in the `X-API-Key` header)

| Role | Can do |
|---|---|
| viewer | Read projects, budgets and the dashboard. Client details are masked. |
| field | Viewer + log invoices, labor and materials + submit feedback |
| manager | Field + create/edit projects, budgets, POs, estimates and client info. Sees full client details. |
| admin | Everything + delete projects, read the feedback log, create cloud folders |

## Main endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/dashboard` | All projects with burn rate, CV, alert level, recent alerts |
| GET/POST | `/projects` | List (`?status=`, `?updated_since=` for offline sync) / create |
| GET/PATCH/DELETE | `/projects/{id}` | Read / update / delete |
| PUT/DELETE | `/projects/{id}/client` | Optional client metadata (encrypted at rest) |
| GET/POST | `/projects/{id}/costs` | List / add cost entries |
| PATCH/DELETE | `/projects/{id}/costs/{cost_id}` | Edit / remove an entry |
| GET | `/projects/{id}/budget` | Full budget summary, including a by-phase rollup |
| GET | `/projects/{id}/alerts` | Alert history |
| POST | `/projects/{id}/storage/provision` | Create the project's cloud folder tree |
| POST/GET | `/feedback`, `/feedback/stats` | Field feedback & bug log |

**Offline sync:** the app can generate its own UUID for each cost entry and send it as `id`. If a queued request is replayed, the backend returns the existing entry instead of creating a duplicate.

## Security

- **Client details at rest:** name, company, phone, email and site address are each encrypted with AES-256-GCM before they reach the database (`app/crypto.py`). The tests confirm the raw database holds no plaintext.
- **In transit:** run behind HTTPS. Cloud Run and App Runner provide TLS automatically.
- **Access:** role-based, as in the table above. Cloud folders use a service account that can only see the folder shared with it.

## Cloud storage

Set `STORAGE_PROVIDER` to `local` (for development), `gdrive` or `dropbox`. Provisioning creates this folder tree:

```
[Project_ID] - [Project_Name]/
  Blueprints/  Site_Photos/  Invoices_Receipts/  Client_Docs/
```

- **Google Drive:** create a service account and a root folder, share the folder with the service account's email, then set `GDRIVE_SERVICE_ACCOUNT_FILE` and `GDRIVE_ROOT_FOLDER_ID`.
- **Dropbox:** create an app-folder-scoped app and set `DROPBOX_ACCESS_TOKEN`.

The Drive and Dropbox code is tested against mocked APIs only. It still needs a run against real accounts.

## CI/CD

`.github/workflows/backend-ci.yml` runs lint and tests on every push or PR, then builds the Docker image. On `main` it pushes the image to GitHub Container Registry. A Cloud Run deploy job is included but switched off until you set the repo variable `DEPLOY_ENABLED=true` and add the GCP secrets.
