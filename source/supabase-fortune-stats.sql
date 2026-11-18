-- Lords of the Low Countries: statistics for Fortune mode
--
-- HOW TO USE
--   Existing database: paste ALL of this into Supabase (SQL Editor -> New query -> Run).
--   Fresh database:    run supabase-setup.sql instead, it already contains all of this.
--   Safe to run more than once, and safe before or after supabase-security.sql.
--   Supabase may warn about "destructive operations" (drop trigger). Confirm it.
--
-- WHAT IT DOES
--   1. Adds three columns to public.events:
--        mode   'campaign' (the default, so the game's campaign rows need no change) or 'fortune'
--        level  Fortune only, on a finished game: the EXP level reached
--        cards  Fortune only, on a finished game: the cards taken, as ids separated by
--               commas, copies included (for example 'weavers,weavers,hanse')
--   2. Checks those values before every insert (event_invalid if they don't fit).
--   3. Lets the game's public key insert the three columns.
--   4. Keeps the existing statistics views campaign only, so Fortune runs don't change
--      the campaign numbers, and adds stats_daily.fortune_started at the end.
--   5. Adds three public views for Fortune: stats_fortune_overview, stats_fortune_realms
--      and stats_fortune_cards (how often each card is taken and how often those games are won).
--
-- Until this has been run, the game's Fortune rows are refused by the database (unknown
-- column) and simply not counted; campaign rows keep working either way.

-- BEGIN FORTUNE STATS

-- ---------- 1. Columns ----------

alter table public.events add column if not exists mode  text not null default 'campaign';
alter table public.events add column if not exists level int;
alter table public.events add column if not exists cards text;

do $$ begin
  alter table public.events add constraint events_mode_check check (mode in ('campaign', 'fortune'));
exception when duplicate_object then null; end $$;
do $$ begin
  alter table public.events add constraint events_level_check check (level between 0 and 200);
exception when duplicate_object then null; end $$;
do $$ begin
  -- 1 to 80 lowercase ids separated by commas
  alter table public.events add constraint events_cards_check
    check (char_length(cards) <= 1000 and cards ~ '^[a-z]{2,16}(,[a-z]{2,16}){0,79}$');
exception when duplicate_object then null; end $$;

-- ---------- 2. Checks ----------
-- Campaign rows never carry a level or cards. Start rows never do either.
-- A finished Fortune row has a level, and at most one card per level reached.

create or replace function public.guard_events_fortune() returns trigger
language plpgsql security definer set search_path = public, pg_temp as $$
begin
  if (new.mode = 'campaign' or new.kind = 'start') and (new.level is not null or new.cards is not null) then
    raise exception 'event_invalid' using errcode = 'PT400', hint = 'fortune_fields';
  end if;
  if new.mode = 'fortune' and new.kind = 'finish' then
    if new.level is null then
      raise exception 'event_invalid' using errcode = 'PT400', hint = 'level';
    end if;
    if new.cards is not null and array_length(string_to_array(new.cards, ','), 1) > new.level then
      raise exception 'event_invalid' using errcode = 'PT400', hint = 'cards';
    end if;
  end if;
  return new;
end $$;
revoke all on function public.guard_events_fortune() from public, anon, authenticated;

drop trigger if exists guard_events_fortune on public.events;
create trigger guard_events_fortune before insert on public.events
  for each row execute function public.guard_events_fortune();

-- ---------- 3. Permission for the game ----------

grant insert (mode, level, cards) on public.events to anon;

-- ---------- 4. Campaign statistics stay campaign only ----------

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
from public.events
where mode = 'campaign';

create or replace view public.stats_daily as
select
  (created_at at time zone 'Europe/Amsterdam')::date                      as day,
  count(*) filter (where kind = 'start' and mode = 'campaign')            as started,
  count(*) filter (where kind = 'finish' and mode = 'campaign')           as finished,
  count(*) filter (where result in ('victory', 'united') and mode = 'campaign') as won,
  count(*) filter (where kind = 'start' and mode = 'fortune')             as fortune_started
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
where mode = 'campaign'
group by 1, 2
order by 1, 2;

-- ---------- 5. Fortune statistics ----------

create or replace view public.stats_fortune_overview as
select
  count(*) filter (where kind = 'start')                                  as games_started,
  count(*) filter (where kind = 'finish')                                 as games_finished,
  count(*) filter (where result in ('victory', 'united'))                 as victories,
  count(*) filter (where result = 'united')                               as countries_united,
  count(*) filter (where kind = 'start' and created_at > now() - interval '7 days') as started_last_7_days,
  round(avg(years) filter (where result = 'victory'), 1)                  as avg_years_to_victory,
  round(avg(level) filter (where kind = 'finish'), 1)                     as avg_level,
  round(avg(coalesce(array_length(string_to_array(cards, ','), 1), 0)) filter (where kind = 'finish'), 1) as avg_cards
from public.events
where mode = 'fortune';

create or replace view public.stats_fortune_realms as
select
  realm,
  difficulty,
  count(*) filter (where kind = 'start')                                  as started,
  count(*) filter (where kind = 'finish')                                 as finished,
  count(*) filter (where result in ('victory', 'united'))                 as won,
  round(avg(years) filter (where result = 'victory'), 1)                  as avg_years_to_victory,
  round(avg(level) filter (where kind = 'finish'), 1)                     as avg_level
from public.events
where mode = 'fortune'
group by 1, 2
order by 1, 2;

-- One row per card: in how many finished games it was taken (games), how many copies
-- in total (copies), and how many of those games were won (wins).
create or replace view public.stats_fortune_cards as
with picks as (
  select e.id, e.result, c.card
  from public.events e
  cross join lateral unnest(string_to_array(e.cards, ',')) as c(card)
  where e.mode = 'fortune' and e.kind = 'finish' and e.cards is not null
)
select
  card,
  count(distinct id)                                                      as games,
  count(*)                                                                as copies,
  count(distinct id) filter (where result in ('victory', 'united'))       as wins
from picks
group by card
order by games desc, card;

grant select on public.stats_overview, public.stats_daily, public.stats_realms,
  public.stats_fortune_overview, public.stats_fortune_realms, public.stats_fortune_cards to anon;

-- END FORTUNE STATS
