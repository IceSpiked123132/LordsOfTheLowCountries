-- Lords of the Low Countries: protection against spam and flooding
--
-- HOW TO USE
--   Existing database: paste ALL of this into Supabase (SQL Editor -> New query -> Run).
--   Fresh database:    run supabase-setup.sql instead, it already contains all of this.
--   It is safe to run more than once. Supabase may warn about "destructive
--   operations" (drop trigger, delete from blocked_words, revoke). That is expected,
--   confirm it.
--
-- WHAT IT DOES
--   1. Global rate limits per table (no personal data, no IP addresses needed).
--      The numbers live in the table public.rate_limits and can be changed in the
--      Table Editor without running this file again.
--   2. Value checks on scores and anonymous events that match the game rules.
--   3. Leaderboard name checks: empty, hidden characters, links, email addresses,
--      and a blocklist of offensive words (English and Dutch).
--   4. The game's public key can only insert the columns it really sends, and it
--      cannot choose its own created_at.
--   5. Optional: delete feedback older than 12 months every night (pg_cron).
--
-- Errors the game understands (the message text of the database error):
--   rate_limit         too many rows in the window (HTTP 429)
--   name_blocked       name on the blocklist
--   name_empty         empty name, only symbols, or hidden characters
--   name_url           name looks like a link
--   name_email         name looks like an email address
--   score_invalid      score does not fit the game rules
--   feedback_invalid   empty message, or values that don't exist in the game
--   event_invalid      statistics row that does not fit the game rules

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
  if n ~ '[\u0001-\u001f\u007f-\u009f​-‏ - ⁠-⁯﻿]' then return 'empty'; end if;
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
