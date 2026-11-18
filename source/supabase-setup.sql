-- Lords of the Low Countries: online database setup
-- Paste all of this into Supabase: SQL Editor -> New query -> Run.
-- It creates three tables and three statistics views:
--   events    anonymous game starts and endings (no names, no player IDs)
--   scores    the leaderboard (only what players type in themselves)
--   feedback  messages sent from the game
-- The public "anon" key used by the game can only ADD rows to these tables
-- and READ the leaderboard and the statistics views. Raw events and
-- feedback are only visible to you, in the Supabase dashboard.
--
-- The last part of this file (BEGIN SECURITY ... END SECURITY) holds the spam and
-- flooding protection: rate limits, value checks, name blocklist, optional cleanup.
-- The same part exists on its own as supabase-security.sql, for databases that
-- were set up before it existed. Both files are kept in step by
-- python3 source/sync_security.py (edit supabase-security.sql, not the copy below).

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

-- ---------- Spam and flooding protection ----------

-- BEGIN SECURITY
-- (copied from supabase-security.sql by source/sync_security.py, do not edit here)

-- ---------- 1. Settings tables (only you can read or change these) ----------

create table if not exists public.rate_limits (
  table_name     text not null check (table_name in ('events', 'scores', 'feedback')),
  window_seconds int  not null check (window_seconds > 0),
  max_rows       int  not null check (max_rows > 0),
  primary key (table_name, window_seconds)
);
alter table public.rate_limits enable row level security;

-- Defaults. Re-running this file does NOT overwrite numbers you changed.
--   scores:   30 per hour,       200 per day
--   feedback: 20 per hour,        50 per day
--   events:  400 per 10 minutes, 8000 per day   (2 rows per game: start and finish)
insert into public.rate_limits (table_name, window_seconds, max_rows) values
  ('scores',   3600,    30),
  ('scores',   86400,   200),
  ('feedback', 3600,    20),
  ('feedback', 86400,   50),
  ('events',   600,     400),
  ('events',   86400,   8000)
on conflict (table_name, window_seconds) do nothing;

create table if not exists public.blocked_words (
  word       text primary key check (word ~ '^[a-z]+$'),
  whole_word boolean not null default false
);
alter table public.blocked_words enable row level security;

-- ---------- 2. Name cleaning and the blocklist (GENERATED, do not edit here) ----------
-- Edit source/blocklist.txt and run: python3 source/sync_security.py

-- BEGIN GENERATED
-- Lowercase, remove accents. Mirrors normalizeName() in the game.
create or replace function public.normalize_name(t text) returns text
language sql immutable set search_path = public, pg_temp as $$
  select translate(
    replace(replace(replace(lower(t), 'ß', 'ss'), 'æ', 'ae'), 'œ', 'oe'),
    'àáâãäåçèéêëìíîïñòóôõöùúûüýÿāăąćĉċčďēĕėęěĝğġģĥĩīĭįĵķĺļľńņňōŏőŕŗřśŝşšţťũūŭůűųŵŷźżžơưǎǐǒǔǖǘǚǜǟǡǧǩǫǭǰǵǹǻȁȃȅȇȉȋȍȏȑȓȕȗșțȟȧȩȫȭȯȱȳḁḃḅḇḉḋḍḏḑḓḕḗḙḛḝḟḡḣḥḧḩḫḭḯḱḳḵḷḹḻḽḿṁṃṅṇṉṋṍṏṑṓṕṗṙṛṝṟṡṣṥṧṩṫṭṯṱṳṵṷṹṻṽṿẁẃẅẇẉẋẍẏẑẓẕẖẗẘẙạảấầẩẫậắằẳẵặẹẻẽếềểễệỉịọỏốồổỗộớờởỡợụủứừửữựỳỵỷỹøđłħı',
    'aaaaaaceeeeiiiinooooouuuuyyaaaccccdeeeeegggghiiiijklllnnnooorrrssssttuuuuuuwyzzzouaiouuuuuaagkoojgnaaaeeiioorruusthaeooooyabbbcdddddeeeeefghhhhhiikkkllllmmmnnnnoooopprrrrsssssttttuuuuuvvwwwwwxxyzzzhtwyaaaaaaaaaaaaeeeeeeeeiioooooooooooouuuuuuuyyyyodlhi')
$$;

-- The blocklist (plain words match anywhere, whole_word ones only as a whole word).
-- This table is kept in step with source/blocklist.txt: words you add by hand
-- in the Table Editor are removed again the next time this script runs.
insert into public.blocked_words (word, whole_word) values
  ('anal', true),
  ('arse', true),
  ('arsehole', false),
  ('ass', true),
  ('asshole', false),
  ('bitch', false),
  ('blowjob', false),
  ('bollocks', false),
  ('boobs', true),
  ('bullshit', true),
  ('chink', true),
  ('cock', true),
  ('cocks', true),
  ('coon', true),
  ('cum', true),
  ('cumshot', false),
  ('cunt', true),
  ('cunts', true),
  ('dickhead', false),
  ('dildo', true),
  ('fag', true),
  ('faggot', false),
  ('fags', true),
  ('flikker', true),
  ('flikkers', true),
  ('fuck', false),
  ('gaschamber', false),
  ('godverdom', false),
  ('gook', true),
  ('handjob', false),
  ('heilhitler', false),
  ('hitler', false),
  ('hoer', true),
  ('hoeren', true),
  ('hoerenzoon', false),
  ('jizz', false),
  ('kanker', false),
  ('kike', true),
  ('killyourself', false),
  ('kkk', false),
  ('klootzak', false),
  ('klote', true),
  ('kut', true),
  ('kutten', true),
  ('kutwijf', false),
  ('kys', true),
  ('lul', true),
  ('lullen', true),
  ('masturbat', false),
  ('molest', false),
  ('molester', true),
  ('mongolen', true),
  ('mongool', true),
  ('motherfucker', false),
  ('nazi', true),
  ('nazis', true),
  ('neger', true),
  ('negers', true),
  ('negro', true),
  ('neuk', true),
  ('neuken', true),
  ('neukt', true),
  ('neukte', true),
  ('nigga', true),
  ('niggas', true),
  ('nigger', false),
  ('nikker', true),
  ('nikkers', true),
  ('orgasm', false),
  ('paedo', true),
  ('paedophile', false),
  ('pedo', true),
  ('pedophile', false),
  ('penis', true),
  ('pik', true),
  ('porn', true),
  ('pornhub', false),
  ('porno', true),
  ('pussy', true),
  ('rape', true),
  ('raped', true),
  ('rapist', true),
  ('retard', true),
  ('retarded', true),
  ('retards', true),
  ('schijt', true),
  ('sex', true),
  ('sexy', true),
  ('shit', true),
  ('shithead', true),
  ('shits', true),
  ('shitty', true),
  ('siegheil', false),
  ('slet', true),
  ('sletje', true),
  ('sletjes', true),
  ('sletten', true),
  ('slut', true),
  ('sluts', true),
  ('snol', true),
  ('spic', true),
  ('tering', true),
  ('teringlijer', false),
  ('tits', true),
  ('tranny', true),
  ('twat', true),
  ('tyfus', false),
  ('vagina', true),
  ('wanker', true),
  ('whitepower', false),
  ('whitepride', false),
  ('whore', true),
  ('whores', true),
  ('xvideos', false)
on conflict (word) do update set whole_word = excluded.whole_word;

delete from public.blocked_words where word <> all (array['anal', 'arse', 'arsehole', 'ass', 'asshole', 'bitch', 'blowjob', 'bollocks', 'boobs', 'bullshit', 'chink', 'cock', 'cocks', 'coon', 'cum', 'cumshot', 'cunt', 'cunts', 'dickhead', 'dildo', 'fag', 'faggot', 'fags', 'flikker', 'flikkers', 'fuck', 'gaschamber', 'godverdom', 'gook', 'handjob', 'heilhitler', 'hitler', 'hoer', 'hoeren', 'hoerenzoon', 'jizz', 'kanker', 'kike', 'killyourself', 'kkk', 'klootzak', 'klote', 'kut', 'kutten', 'kutwijf', 'kys', 'lul', 'lullen', 'masturbat', 'molest', 'molester', 'mongolen', 'mongool', 'motherfucker', 'nazi', 'nazis', 'neger', 'negers', 'negro', 'neuk', 'neuken', 'neukt', 'neukte', 'nigga', 'niggas', 'nigger', 'nikker', 'nikkers', 'orgasm', 'paedo', 'paedophile', 'pedo', 'pedophile', 'penis', 'pik', 'porn', 'pornhub', 'porno', 'pussy', 'rape', 'raped', 'rapist', 'retard', 'retarded', 'retards', 'schijt', 'sex', 'sexy', 'shit', 'shithead', 'shits', 'shitty', 'siegheil', 'slet', 'sletje', 'sletjes', 'sletten', 'slut', 'sluts', 'snol', 'spic', 'tering', 'teringlijer', 'tits', 'tranny', 'twat', 'tyfus', 'vagina', 'wanker', 'whitepower', 'whitepride', 'whore', 'whores', 'xvideos']);
-- END GENERATED

-- ---------- 3. Checks ----------

-- Splits a name into lowercase words of plain letters. "Sh!t" becomes {shit}.
create or replace function public.name_tokens(t text) returns text[]
language sql immutable set search_path = public, pg_temp as $$
  select string_to_array(btrim(regexp_replace(
    translate(public.normalize_name(t), '013457@$!+', 'oieastasit'),
    '[^a-z]+', ' ', 'g')), ' ')
$$;

-- Returns null when the name is fine, otherwise a short code.
create or replace function public.name_problem(raw text) returns text
language plpgsql stable security definer set search_path = public, pg_temp as $$
declare
  n    text := btrim(regexp_replace(coalesce(raw, ''), '\s+', ' ', 'g'));
  toks text[];
  squashed text;
begin
  if n = '' then return 'empty'; end if;
  -- Control and invisible characters, written as \u escapes on purpose: the literal characters
  -- (U+2028 in particular) get lost when this file is pasted into the Supabase SQL editor.
  if n ~ '[\u0001-\u001f\u007f-\u009f\u200b-\u200f\u2028-\u202f\u2060-\u206f\ufeff]' then return 'empty'; end if;
  if n !~ '[[:alnum:]]' then return 'empty'; end if;
  if n ~ '[^ @]+@[^ @]+' then return 'email'; end if;
  if lower(n) ~ '(https?:|www\.|[a-z0-9-]\.(com|net|org|nl|be|io|co|uk|eu|ru|tk|ly|gg|xyz|app|dev|info|biz|link|click|shop|site|online|top|store|live|me)([^a-z0-9]|$))' then
    return 'url';
  end if;
  toks := public.name_tokens(n);
  squashed := array_to_string(toks, '');
  if exists (
    select 1 from public.blocked_words b
    where (not b.whole_word and position(b.word in squashed) > 0)
       or (b.whole_word and b.word = any (toks))
  ) then
    return 'blocked';
  end if;
  return null;
end $$;

-- Game rules the checks below follow (keep in step with RULES in the game):
--   31 provinces, 16 needed to win, the game ends in year 1400 = 50 years after 1350.
--   After that you can keep playing, up to a hard cap of 200 years.
--   "victory" before year 50 means you held at least 16 provinces.
--   "victory" in year 50 can be fewer (you simply held the most provinces).
--   "united" means all 31 provinces. "defeat" means at most 15 provinces.
--   "destroyed" means 0 provinces.
-- The minimum years are cautious guesses of the fastest possible human play.

create or replace function public.score_problem(p_category text, p_years int, p_provinces int) returns text
language plpgsql immutable set search_path = public, pg_temp as $$
declare
  total       constant int := 31;
  to_win      constant int := 16;
  last_year   constant int := 50;
  max_years   constant int := 200;
  min_victory constant int := 3;
  min_united  constant int := 6;
begin
  if p_category = 'victory' then
    if p_years is null or p_years < min_victory or p_years > last_year then return 'years'; end if;
    if p_provinces is null or p_provinces < 1 or p_provinces > total - 1 then return 'provinces'; end if;
    if p_years < last_year and p_provinces < to_win then return 'provinces'; end if;
  elsif p_category = 'united' then
    if p_years is null or p_years < min_united or p_years > max_years then return 'years'; end if;
    if p_provinces is distinct from total then return 'provinces'; end if;
  else
    return 'category';
  end if;
  return null;
end $$;

create or replace function public.event_problem(p_kind text, p_result text, p_years int, p_provinces int, p_won int, p_lost int) returns text
language plpgsql immutable set search_path = public, pg_temp as $$
declare
  total       constant int := 31;
  to_win      constant int := 16;
  last_year   constant int := 50;
  max_years   constant int := 200;
  min_victory constant int := 3;
  min_united  constant int := 6;
begin
  if p_kind = 'start' then
    if p_result is not null or p_years is not null or p_provinces is not null
       or p_won is not null or p_lost is not null then return 'start_has_result'; end if;
    return null;
  end if;
  -- finish
  if p_result is null or p_years is null or p_provinces is null or p_won is null or p_lost is null then
    return 'finish_incomplete';
  end if;
  if p_result = 'victory' then
    if p_years < min_victory or p_years > last_year then return 'years'; end if;
    if p_provinces < 1 or p_provinces > total - 1 then return 'provinces'; end if;
    if p_years < last_year and p_provinces < to_win then return 'provinces'; end if;
  elsif p_result = 'defeat' then
    if p_years < 1 or p_years > last_year then return 'years'; end if;
    if p_provinces < 1 or p_provinces >= to_win then return 'provinces'; end if;
  elsif p_result = 'united' then
    if p_years < min_united or p_years > max_years then return 'years'; end if;
    if p_provinces <> total then return 'provinces'; end if;
  elsif p_result = 'destroyed' then
    if p_years < 1 or p_years > max_years then return 'years'; end if;
    if p_provinces <> 0 then return 'provinces'; end if;
  else
    return 'result';
  end if;
  return null;
end $$;

-- Refuses the insert when the table already got too many rows in a time window.
-- Takes a lock per table, so two inserts at the same moment can't both slip through.
create or replace function public.check_rate_limit(tbl text) returns void
language plpgsql security definer set search_path = public, pg_temp as $$
declare
  r record;
  n bigint;
begin
  perform pg_advisory_xact_lock(hashtext('lords_rate_limit_' || tbl));
  for r in select window_seconds, max_rows from public.rate_limits where table_name = tbl loop
    execute format('select count(*) from public.%I where created_at > now() - make_interval(secs => $1)', tbl)
      into n using r.window_seconds;
    if n >= r.max_rows then
      raise exception 'rate_limit' using errcode = 'PT429';
    end if;
  end loop;
end $$;

-- ---------- 4. Triggers (run before every insert, so they can't be bypassed) ----------
-- errcode 'PT400' / 'PT429' makes the Supabase API answer with HTTP 400 / 429.

create or replace function public.guard_scores() returns trigger
language plpgsql security definer set search_path = public, pg_temp as $$
declare p text;
begin
  new.created_at := now();
  new.name := btrim(regexp_replace(new.name, '\s+', ' ', 'g'));
  p := public.name_problem(new.name);
  if p is not null then raise exception 'name_%', p using errcode = 'PT400'; end if;
  p := public.score_problem(new.category, new.years, new.provinces);
  if p is not null then raise exception 'score_invalid' using errcode = 'PT400', hint = p; end if;
  perform public.check_rate_limit('scores');
  return new;
end $$;

create or replace function public.guard_feedback() returns trigger
language plpgsql security definer set search_path = public, pg_temp as $$
begin
  new.created_at := now();
  new.message := btrim(new.message);
  new.contact := nullif(btrim(new.contact), '');
  if new.message = ''
     or (new.realm is not null and new.realm not in ('holland', 'utrecht', 'gelre', 'brabant'))
     or (new.difficulty is not null and new.difficulty not in ('easy', 'normal', 'hard'))
     or (new.year is not null and new.year not between 1350 and 1550) then
    raise exception 'feedback_invalid' using errcode = 'PT400';
  end if;
  perform public.check_rate_limit('feedback');
  return new;
end $$;

create or replace function public.guard_events() returns trigger
language plpgsql security definer set search_path = public, pg_temp as $$
declare p text;
begin
  new.created_at := now();
  p := public.event_problem(new.kind, new.result, new.years, new.provinces, new.battles_won, new.battles_lost);
  if p is not null then raise exception 'event_invalid' using errcode = 'PT400', hint = p; end if;
  perform public.check_rate_limit('events');
  return new;
end $$;

drop trigger if exists guard_scores_insert on public.scores;
create trigger guard_scores_insert before insert on public.scores
  for each row execute function public.guard_scores();

drop trigger if exists guard_feedback_insert on public.feedback;
create trigger guard_feedback_insert before insert on public.feedback
  for each row execute function public.guard_feedback();

drop trigger if exists guard_events_insert on public.events;
create trigger guard_events_insert before insert on public.events
  for each row execute function public.guard_events();

-- Indexes so the rate limit counts stay fast, and the leaderboard too
create index if not exists events_created_at_idx   on public.events (created_at);
create index if not exists scores_created_at_idx   on public.scores (created_at);
create index if not exists feedback_created_at_idx on public.feedback (created_at);
create index if not exists scores_board_idx        on public.scores (difficulty, category, years, created_at);

-- ---------- 5. What the public key may do ----------
-- Only insert the columns the game really sends (so no custom id or created_at),
-- and only read the leaderboard. The settings tables and the helper functions
-- are closed to everyone except you.

revoke all on public.events, public.scores, public.feedback from anon, authenticated;
grant insert (kind, realm, difficulty, result, years, provinces, battles_won, battles_lost, version) on public.events to anon;
-- Fortune statistics columns (added by supabase-fortune-stats.sql). Granted again here when they
-- exist, so running this file again later doesn't switch the Fortune statistics off.
do $$ begin
  if exists (select 1 from information_schema.columns where table_schema = 'public' and table_name = 'events' and column_name = 'cards') then
    grant insert (mode, level, cards) on public.events to anon;
  end if;
end $$;
grant insert (name, realm, difficulty, category, years, provinces) on public.scores to anon;
-- The Fortune leaderboard column (added by supabase-fortune-stats.sql), granted again when it exists.
do $$ begin
  if exists (select 1 from information_schema.columns where table_schema = 'public' and table_name = 'scores' and column_name = 'mode') then
    grant insert (mode) on public.scores to anon;
  end if;
end $$;
grant select on public.scores to anon;
grant insert (message, contact, realm, year, difficulty, version) on public.feedback to anon;

revoke all on public.rate_limits, public.blocked_words from anon, authenticated;

revoke all on function public.normalize_name(text) from public, anon, authenticated;
revoke all on function public.name_tokens(text) from public, anon, authenticated;
revoke all on function public.name_problem(text) from public, anon, authenticated;
revoke all on function public.score_problem(text, int, int) from public, anon, authenticated;
revoke all on function public.event_problem(text, text, int, int, int, int) from public, anon, authenticated;
revoke all on function public.check_rate_limit(text) from public, anon, authenticated;
revoke all on function public.guard_scores() from public, anon, authenticated;
revoke all on function public.guard_feedback() from public, anon, authenticated;
revoke all on function public.guard_events() from public, anon, authenticated;

-- ---------- 6. Optional: delete feedback older than 12 months ----------
-- Matches the privacy statement. Needs pg_cron (Database -> Extensions on Supabase).
-- If pg_cron can't be switched on, this part only prints a notice and everything
-- above still works. Then run this once a year by hand:
--     select public.delete_old_feedback();

create or replace function public.delete_old_feedback() returns bigint
language plpgsql security definer set search_path = public, pg_temp as $$
declare n bigint;
begin
  delete from public.feedback where created_at < now() - interval '12 months';
  get diagnostics n = row_count;
  return n;
end $$;
revoke all on function public.delete_old_feedback() from public, anon, authenticated;

do $$
begin
  create extension if not exists pg_cron;
  perform cron.schedule('delete-old-feedback', '17 3 * * *', 'select public.delete_old_feedback()');
  raise notice 'Nightly feedback cleanup is scheduled (03:17 UTC).';
exception when others then
  raise notice 'pg_cron is not available here (%). Run: select public.delete_old_feedback(); by hand once a year.', sqlerrm;
end $$;
-- END SECURITY

-- ---------- Fortune statistics ----------

-- BEGIN FORTUNE STATS
-- (copied from supabase-fortune-stats.sql by source/sync_security.py, do not edit here)


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

-- ---------- 6. Fortune leaderboard ----------
-- Same categories (victory, united), same checks and the same rate limit as the campaign;
-- the mode keeps the two boards apart.

alter table public.scores add column if not exists mode text not null default 'campaign';
do $$ begin
  alter table public.scores add constraint scores_mode_check check (mode in ('campaign', 'fortune'));
exception when duplicate_object then null; end $$;

grant insert (mode) on public.scores to anon;

create index if not exists scores_mode_board_idx on public.scores (mode, difficulty, category, years, created_at);
-- END FORTUNE STATS
