-- Run once in Supabase SQL Editor to upgrade an existing Telegram-era project.
alter table public.people add column if not exists whatsapp_phone text;
alter table public.people add column if not exists whatsapp_last_inbound_at timestamptz;

create unique index if not exists people_whatsapp_phone_unique_idx
  on public.people(whatsapp_phone) where whatsapp_phone is not null;

create table if not exists public.processed_whatsapp_messages (
  message_id text primary key,
  received_at timestamptz not null default now()
);
alter table public.processed_whatsapp_messages enable row level security;
grant all on public.processed_whatsapp_messages to service_role;
