-- Public directory contains public business facts only. Private correspondence stays separate.
create schema if not exists directory_private;
revoke all on schema directory_private from public, anon, authenticated;
create table public.builder_companies (
 id text primary key,
 name text not null,
 scope text not null,
 areas text[] not null default '{}',
 coverage_note text not null default '',
 phone text not null default '',
 source text not null check (source like 'https://%'),
 last_web_checked date not null,
 work_types text[] not null check (work_types <@ array['complete','shell','trade']::text[]),
 company_confirmed_at date,
 availability text not null default 'unknown',
 availability_confirmed_at date,
 published boolean not null default false,
 updated_at timestamptz not null default now(),
 check (availability = 'unknown' or availability_confirmed_at is not null)
);
alter table public.builder_companies enable row level security;
revoke all on public.builder_companies from anon, authenticated;
grant select on public.builder_companies to anon, authenticated;
create policy public_published_builders on public.builder_companies for select
 to anon, authenticated using (published = true);
create table directory_private.builder_research (
 company_id text primary key references public.builder_companies(id),
 outreach_status text not null default 'not_contacted',
 contacted_at date,
 notes text not null default '',
 updated_at timestamptz not null default now()
);
alter table directory_private.builder_research enable row level security;
revoke all on directory_private.builder_research from public, anon, authenticated;
-- No public writes or private-table policies. Admin changes through trusted database tooling only.
