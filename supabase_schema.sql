create table if not exists public.site_state (
  key text primary key,
  value jsonb not null,
  updated_at timestamptz not null default now()
);

alter table public.site_state enable row level security;

drop policy if exists "server service role full access" on public.site_state;

create policy "server service role full access"
on public.site_state
for all
using (auth.role() = 'service_role')
with check (auth.role() = 'service_role');
