-- ReelGrants — signup capture table for the NEW (separate) Supabase project.
-- Run this once in the new project's SQL editor. Safe, minimal, anon-insert-only.

create table if not exists public.signups (
  id          uuid primary key default gen_random_uuid(),
  email       text not null,
  discipline  text,
  source      text,                         -- which community/post sent them
  created_at  timestamptz not null default now()
);

-- Lock it down: anonymous visitors may INSERT a signup, but cannot read anyone's data.
alter table public.signups enable row level security;

drop policy if exists "anon can insert signups" on public.signups;
create policy "anon can insert signups"
  on public.signups for insert
  to anon
  with check (true);

-- (No SELECT policy for anon = the public anon key cannot read the list. You read it
--  in the Supabase dashboard, or with the service_role key, never from the website.)

-- Optional: prevent the same email piling up duplicates.
create unique index if not exists signups_email_uniq on public.signups (lower(email));
