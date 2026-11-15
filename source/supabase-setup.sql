-- Lords of the Low Countries: online database setup
-- Paste all of this into Supabase: SQL Editor -> New query -> Run.
-- It creates three tables and three statistics views:
--   events    anonymous game starts and endings (no names, no player IDs)
--   scores    the leaderboard (only what players type in themselves)
--   feedback  messages sent from the game
-- The public "anon" key used by the game can only ADD rows to these tables
-- and READ the leaderboard and the statistics views. Raw events and
-- feedback are only visible to you, in the Supabase dashboard.

-- ---------- Tables ----------

create table if not exists public.events (
  id bigint generated always as identity primary key,
  created_at timestamptz not null default now(),
  kind text not null check (kind in ('start', 'finish')),
  realm text not null check (realm in ('holland', 'utrecht', 'gelre', 'brabant')),
  difficulty text not null check (difficulty in ('easy', 'normal', 'hard')),
  result text check (result in ('victory', 'defeat', 'united', 'destroyed')),
  years int check (years between 0 and 200),
  provinces int check (provinces between 0 and 100),
  battles_won int check (battles_won between 0 and 10000),
  battles_lost int check (battles_lost between 0 and 10000),
  version text check (char_length(version) <= 20)
);

create table if not exists public.scores (
  id bigint generated always as identity primary key,
  created_at timestamptz not null default now(),
  name text not null check (char_length(name) between 1 and 20),
  realm text not null check (realm in ('holland', 'utrecht', 'gelre', 'brabant')),
  difficulty text not null check (difficulty in ('easy', 'normal', 'hard')),
  category text not null check (category in ('victory', 'united')),
  years int not null check (years between 1 and 200),
  provinces int not null check (provinces between 1 and 100)
);

create table if not exists public.feedback (
  id bigint generated always as identity primary key,
  created_at timestamptz not null default now(),
  message text not null check (char_length(message) between 1 and 2000),
  contact text check (char_length(contact) <= 100),
  realm text,
  year int,
  difficulty text,
  version text check (char_length(version) <= 20)
);

-- ---------- Rules (row level security) ----------

alter table public.events enable row level security;
alter table public.scores enable row level security;
alter table public.feedback enable row level security;

drop policy if exists "game adds events" on public.events;
create policy "game adds events" on public.events for insert to anon with check (true);

drop policy if exists "game adds scores" on public.scores;
create policy "game adds scores" on public.scores for insert to anon with check (true);
drop policy if exists "everyone reads scores" on public.scores;
create policy "everyone reads scores" on public.scores for select to anon using (true);

drop policy if exists "game adds feedback" on public.feedback;
create policy "game adds feedback" on public.feedback for insert to anon with check (true);

-- ---------- Statistics (totals only, safe to show publicly) ----------

create or replace view public.stats_overview as
select
  count(*) filter (where kind = 'start')                                  as games_started,
  count(*) filter (where kind = 'finish')                                 as games_finished,
  count(*) filter (where result in ('victory', 'united'))                 as victories,
  count(*) filter (where result = 'united')                               as countries_united,
  count(*) filter (where kind = 'start' and created_at > now() - interval '7 days') as started_last_7_days,
  round(avg(years) filter (where result = 'victory'), 1)                  as avg_years_to_victory,
  (select count(*) from public.scores)                                    as leaderboard_entries,
  (select count(*) from public.feedback)                                  as feedback_messages
from public.events;

create or replace view public.stats_daily as
select
  (created_at at time zone 'Europe/Amsterdam')::date                      as day,
  count(*) filter (where kind = 'start')                                  as started,
  count(*) filter (where kind = 'finish')                                 as finished,
  count(*) filter (where result in ('victory', 'united'))                 as won
from public.events
group by 1
order by 1 desc
limit 60;

create or replace view public.stats_realms as
select
  realm,
  difficulty,
  count(*) filter (where kind = 'start')                                  as started,
  count(*) filter (where kind = 'finish')                                 as finished,
  count(*) filter (where result in ('victory', 'united'))                 as won,
  round(avg(years) filter (where result = 'victory'), 1)                  as avg_years_to_victory
from public.events
group by 1, 2
order by 1, 2;

grant select on public.stats_overview, public.stats_daily, public.stats_realms to anon;
