# Barndo Agent architecture and data storage

Verified October 15, 2026. Read-only inspection of local source, authenticated Railway project status and filtered storage settings, plus the public status endpoint. No infrastructure, database or application settings were changed. No customer records or secret values were inspected or included.

## Verified production deployment

- Hosting: Railway project **Barndobible Agent**, production environment, service **Barndo-Agent**, workspace **bowlingwithmrwendell's Projects**.
- Public API/widget origin: https://barndo-agent-production.up.railway.app
- Source: `bowlingwithmrwendell/Barndo-Agent`, branch `main`, root directory `/backend`.
- Build: `backend/Dockerfile`; Python 3.12, FastAPI/Uvicorn. Container working directory `/app`.
- Active deployment: `67bf2f72-a16b-4275-8d21-2e8e112e32f2`, SUCCESS, running instance, created October 13, 2026.
- Deployed commit: `e0cd56f6cc0aa3a45c04ffc63a2bcdabd8c46c97`.
- Deployment metadata reports one replica in `iad`; health check `/health`; public domain targets port 8080.
- Railway reports **no volume instances and no deployment volume mounts**, no buckets and only this one service in the project. There is no separate database service shown in this project.
- Repository CI contains an optional Cloud Run deployment job. It is not evidence that production runs on Cloud Run; the verified deployment is Railway.

## Storage map

| Data | Implementation | Production path/configuration | Durability finding |
|---|---|---|---|
| Projects, clients, cost entries, alert events, feedback | SQLAlchemy relational models, SQLite default | `DATABASE_URL` unset in inspected Railway settings; default `sqlite:///./data/barndo.db`, resolving to `/app/data/barndo.db` | No persistent volume attached; do not assume records survive replacement/redeployment |
| Searchable article knowledge | JSON chunks plus in-memory BM25 search | `KB_CACHE_PATH` unset; default `/app/data/kb.json` | Rebuildable cache; local file is not durable storage |
| Project folders | Local, Google Drive or Dropbox provider abstraction | `STORAGE_PROVIDER` and `STORAGE_LOCAL_ROOT` unset; defaults `local`, `/app/data/storage` | Local default has no mounted persistent volume; cloud providers are supported by code but not selected by inspected settings |
| Visitor conversation history | Browser `sessionStorage`, last 30 messages saved by widget | Visitor browser tab; recent messages sent to API/Anthropic for replies | No database chat-history persistence in inspected application code; external-provider retention was not audited |
| Rate-limit counters | In-process memory | API process | Reset with process lifecycle; not shared durable records |
| Builder pilot records | Local JSON and inline public JavaScript data on WordPress page 807 | `prototypes/builder-finder/companies.json`; published finder page | No builder database tables or shared directory API yet |

Production storage paths are derived from inspected settings and Docker working directory, not a remote filesystem inventory. Actual SQLite file existence, size and row counts were not inspected. Do not infer that customer records currently exist.

## Knowledge ingestion and current live status

The backend reads published WordPress posts and pages from `https://barndobible.com/wp-json/wp/v2/`, excludes policy/contact-style slugs, converts HTML to text and splits it into searchable sections. It uses BM25 text retrieval, not a vector database. Article sections are supplied to the Claude-powered answer service with source URLs. The material estimator is application logic rather than a price database.

`KB_SYNC_ON_STARTUP=true` is explicitly configured. Refresh interval defaults to 12 hours. Public `/public/status` returned:

```json
{"assistant_configured":true,"knowledge_base":{"articles":38,"chunks":317,"synced_at":"2026-10-15T20:47:27+00:00"}}
```

This confirms the running service reports a loaded knowledge base; it does not independently verify every cached excerpt.

**Builder integration gap:** the importer skips `script` and `style` elements. Company records currently embedded in the finder page's JavaScript are therefore not ingested as company profiles. The agent can ingest the page's explanatory prose/checklist, but that is not a structured company lookup. A dedicated directory API or server-rendered company profiles is needed.

## Database models and safeguards in source

Existing tables: `projects`, `clients`, `cost_entries`, `alert_events`, `feedback`. Client personal fields use an encrypted string type; decryption depends on the configured encryption key. Presence and recoverability of production keys were not audited. There are no builder/company, service-area or directory-confirmation tables.

Configuration supports SQLAlchemy database URLs, but an external database requires its corresponding driver/deployment configuration; changing the URL alone should not be assumed sufficient. Initialization uses `Base.metadata.create_all`; no schema migration framework was established by this inspection.

## Persistence and backup status

**Verified:** no Railway persistent volume is attached, and inspected storage settings use local defaults. Docker Compose declares a named `api-data` volume for local Compose deployments; that does not attach a volume to Railway.

**Not verified:** any independent backup jobs, snapshots, export schedule, off-platform copies, restore tests or actual production customer data. No backup guarantee should be made from the repository configuration. Avoid storing authoritative builder records or valuable project records in the present container filesystem.

Before extending production storage:
1. Choose a single authoritative directory store: structured WordPress records or a durable relational database exposed by the agent API.
2. Establish persistent storage, backup retention and a tested restore procedure before importing authoritative records. Inspect and preserve any existing database before a storage migration or redeployment that could replace it.
3. Keep public company fields separate from private outreach notes and correspondence. Expose an explicit public-field API.
4. Add service-area/scope modeling, evidence URLs, reviewed dates, company-confirmation dates and separately dated availability. Company statements are not independent vetting.
5. Connect both the website finder and agent to that source; retain clear unknown/unconfirmed labels.

Recommendation: do not add builder records to the current ephemeral SQLite deployment. WordPress remains a practical editing home if it can supply structured public records to both consumers; alternatively, use durable backend storage with an admin interface. Select after confirming the desired editing workflow and backup arrangement.

## Evidence and maintenance

Source files (relative to Barndo-Agent):
- `backend/app/config.py`: database, provider and KB defaults.
- `backend/app/db.py`, `backend/app/models.py`: database initialization and tables.
- `backend/app/agent/kb.py`: WordPress ingestion, script exclusion, JSON persistence and BM25 retrieval.
- `backend/app/routers/public.py`: public chat/status and admin KB refresh.
- `backend/app/static/barndo-agent.js`: browser session history.
- `backend/app/storage/`: folder provider implementations.
- `backend/Dockerfile`, `compose.yaml`, `.github/workflows/backend-ci.yml`: deployment assumptions.
- Earlier release evidence: `../shared/outputs/barndo-agent-release-2026-10-13.md` relative to the repository parent (workspace `shared/outputs`).

Verification commands: `railway status --json`; `railway variables --json` filtered in-process to storage configuration only (no secret output); GET `/public/status`. Recheck production settings before implementation: this document is a dated snapshot. Never copy raw environment dumps, tokens, encryption keys or customer records into documentation.

## October 15 directory implementation update

Supabase project `frylsynpbyprunbqxxro` now holds five directory company records in `public.builder_companies`; private research schema/table created separately with no anonymous access. Anonymous role visibility/write restrictions tested. Railway connection configured with restricted publishable key. This supersedes the earlier no-builder-table finding for the new directory only; original project/client SQLite persistence remains unchanged. See [rollout status](supabase-directory-rollout.md) for deployment, public export restore test and remaining private-backup limitations.
