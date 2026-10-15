# Supabase directory rollout — work in progress

October 15, 2026. User approved database, five-company import, finder/agent integration, privacy and backup validation, and eventual publication. Existing project/client database migration is excluded.

## Prepared locally

- `supabase/migrations/202610150001_builder_directory.sql`: public business facts, unpublished-by-default records, SELECT-only published-row RLS for anon/authenticated, no public writes. Private research table in a separate schema with no public grants or policies.
- `supabase/seed.sql`: five website-researched companies, availability unknown, no confirmation dates; repeat import does not overwrite later edits.
- `backend/app/routers/directory.py`: GET `/public/builders`, explicit field whitelist, published-only reads, generic upstream failures. Disabled with HTTP 503 until configured. Uses a publishable/legacy anon key, not a privileged service-role key.
- `SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY`: new backend settings. No actual credentials saved.

## Pending account access and completion

Supabase dashboard opened to sign-in. No Supabase project provisioned, migration executed, records imported, production settings changed or code deployed. Stripe Projects provisioning skill was inspected; required Stripe CLI is unavailable. Direct Supabase dashboard is the fallback.

After sign-in: select the intended organization and existing/new project, review plan and region before any financial commitment. Apply schema and seed in a development project. Verify anonymous readers can read published records only; cannot insert/update/delete; cannot read drafts or private schema; no credential exposure. Test actual SQL policies in Supabase (local API tests alone do not establish RLS correctness).

Still implement agent lookup tool and switch published finder to shared endpoint with honest unavailable/empty states. Test geographic precision, scope and unknown availability; do not infer county coverage from towns. Verify public-only payloads. Establish backup/export and actual restoration test before calling storage production-ready. Publish after checks; retain current live finder until replacement is verified.

Do not migrate project/client data or change the existing SQLite database as part of this rollout.

## Verified Supabase setup — October 15

Project `frylsynpbyprunbqxxro`, organization Killettes Mule LLC, East US/North Virginia. Schema applied transactionally via SQL editor; five published company records imported. Anonymous SQL-role test saw 5 public records and 0 temporary unpublished probe records. INSERT/UPDATE/DELETE privileges and private schema USAGE all false. Probe rolled back. Public REST export succeeded.

User selected Free plan with separate exports. Free plan dashboard explicitly reports no project backups. Initial public export: workspace `shared/outputs/builder-directory-export-2026-10-15.json`. Restored that export to a temporary table in Supabase: 5 records, 0 differences; transaction rolled back. This tests the public record export, not full-project disaster recovery or private research backups. `scripts/export_builder_directory.py` supports repeat public exports; keep copies off the app host after directory updates. No recurring backup automation has been created. Before storing private notes or unpublished research, add a privileged schema/data export and restore procedure; publishable-key exports cannot preserve those records.

Railway connection variables configured using restricted publishable key; no privileged Supabase key used. Agent tool and website switch still require deployment verification.

## Published integration

Backend commit `8609b3a5c95db7e058ddd9a730a8f26128ac0b6e` pushed to main and deployed. Live `/public/builders` returned five profiles with no private research fields. WordPress page 807 now fetches this endpoint instead of embedding company records. Live browser verified Paris complete-build results (3) and Texarkana shell results (1, Crank & Son), with unconfirmed/unknown labels. All 59 backend tests pass; lint and formatting pass. Production screenshot: workspace `shared/outputs/supabase-finder-live-2026-10-15.png`.

Public lookup currently caps its result set at 500 companies; add server-side geographic queries/pagination before exceeding that directory size. Editing currently uses Supabase Table Editor; no custom admin interface was added. Export process is manual, not scheduled, and the tested backup covers published directory records only. Original project/client database migration was not performed.
