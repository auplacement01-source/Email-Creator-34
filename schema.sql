-- Air University internship outreach. Apply in the Supabase SQL Editor.
-- Keep the service-role key only in Streamlit server secrets; do not expose it in a browser.
create extension if not exists pgcrypto;

create table if not exists public.employers (
  id uuid primary key default gen_random_uuid(),
  source text not null default 'manual',
  title text,
  first_name text,
  last_name text,
  position text,
  industry text,
  company_name text not null,
  country text,
  email text unique,
  phone text,
  website text,
  source_url text,
  program_fit text[] not null default '{}',
  fit_notes text,
  status text not null default 'new' check (status in ('new','prospect','drafted','sent','do_not_contact')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.email_drafts (
  id uuid primary key default gen_random_uuid(),
  employer_id uuid not null references public.employers(id) on delete restrict,
  to_email text not null,
  subject text not null,
  body_text text not null,
  program_fit text[] not null default '{}',
  status text not null default 'draft' check (status in ('draft','sent','send_error','discarded')),
  created_by text,
  approved_by text,
  approved_at timestamptz,
  sent_at timestamptz,
  outlook_message_id text,
  error_text text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.activity_logs (
  id uuid primary key default gen_random_uuid(),
  event_type text not null,
  employer_id uuid references public.employers(id) on delete set null,
  draft_id uuid references public.email_drafts(id) on delete set null,
  actor text not null default 'operator',
  details jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create table if not exists public.campaign_settings (
  key text primary key,
  value jsonb not null,
  updated_at timestamptz not null default now()
);

create index if not exists employers_status_updated_idx on public.employers(status, updated_at desc);
create index if not exists employers_company_search_idx on public.employers using gin (to_tsvector('simple', company_name || ' ' || coalesce(industry,'')));
create index if not exists email_drafts_status_created_idx on public.email_drafts(status, created_at desc);
create index if not exists email_drafts_sent_at_idx on public.email_drafts(sent_at desc) where sent_at is not null;
create index if not exists activity_logs_created_idx on public.activity_logs(created_at desc);

-- No public or browser-facing policies are created. Streamlit server-side service-role access
-- bypasses RLS and must remain protected by APP_PASSWORD and server secrets.
alter table public.employers enable row level security;
alter table public.email_drafts enable row level security;
alter table public.activity_logs enable row level security;
alter table public.campaign_settings enable row level security;
