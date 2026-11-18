# Tests the Fortune statistics SQL (source/supabase-fortune-stats.sql).
# Needs the local database from source/local_test_db.sh (fresh supabase-setup.sql, which includes it).
# Usage: python3 source/test_fortune_sql.py
# Part 1 goes through PostgREST like the game does. Part 2 checks the path for the EXISTING
# Supabase database: a database made with the old setup gets the file run on top of it (twice),
# then supabase-security.sql again, and Fortune rows must still be accepted.
import json, subprocess, urllib.request, urllib.error
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = "http://127.0.0.1:3001"

def psql(sql, db="postgres", file=None):
    args = ["psql", "-h", "/tmp/pg", "-p", "5433", "-U", "postgres", "-d", db, "-At", "-v", "ON_ERROR_STOP=1"]
    args += ["-f", file] if file else ["-c", sql]
    r = subprocess.run(args, capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else "ERR " + r.stderr.strip()

def post(body):
    req = urllib.request.Request(f"{BASE}/events", data=json.dumps(body).encode(), method="POST",
        headers={"Content-Type": "application/json", "Prefer": "return=minimal", "apikey": "x"})
    try:
        with urllib.request.urlopen(req) as r: return r.status, ""
    except urllib.error.HTTPError as e:
        try: msg = json.loads(e.read().decode()).get("message", "")
        except Exception: msg = ""
        return e.code, msg

def get(view):
    with urllib.request.urlopen(urllib.request.Request(f"{BASE}/{view}?select=*", headers={"apikey": "x"})) as r:
        return json.loads(r.read().decode())

fails = 0
def check(label, got, want):
    global fails
    ok = got == want
    if not ok: fails += 1
    print(f"{'PASS' if ok else 'FAIL'}  {label:64} got={got}  {'' if ok else 'want=' + str(want)}")

def ev(kind="start", **kw):
    b = {"kind": kind, "realm": "holland", "difficulty": "normal", "version": "2026-11-18.3"}; b.update(kw); return b
def fin(**kw):
    b = ev("finish", result="victory", years=30, provinces=16, battles_won=12, battles_lost=3); b.update(kw); return b

psql("truncate public.events, public.scores, public.feedback restart identity")
print("== Inserts through the API")
check("campaign start, no mode (as the game sends it)", post(ev()), (201, ""))
check("campaign finish, no mode", post(fin()), (201, ""))
check("fortune start", post(ev(mode="fortune")), (201, ""))
check("fortune finish with level and cards", post(fin(mode="fortune", level=8, cards="weavers,weavers,hanse,march")), (201, ""))
check("fortune finish with level, no cards", post(fin(mode="fortune", result="defeat", provinces=3, level=2, cards=None)), (201, ""))
check("fortune finish, gelre, lost", post(fin(mode="fortune", realm="gelre", result="defeat", provinces=5, level=4, cards="march,goedendag")), (201, ""))
check("campaign row with cards refused", post(fin(cards="hanse")), (400, "event_invalid"))
check("campaign row with level refused", post(fin(level=3)), (400, "event_invalid"))
check("fortune start with cards refused", post(ev(mode="fortune", cards="hanse")), (400, "event_invalid"))
check("fortune finish without level refused", post(fin(mode="fortune")), (400, "event_invalid"))
check("more cards than levels refused", post(fin(mode="fortune", level=1, cards="hanse,march")), (400, "event_invalid"))
check("cards with capitals refused (check constraint)", post(fin(mode="fortune", level=3, cards="Hanse"))[0], 400)
check("cards with other characters refused (check constraint)", post(fin(mode="fortune", level=3, cards="hanse;drop table"))[0], 400)
check("empty cards text refused (check constraint)", post(fin(mode="fortune", level=3, cards=""))[0], 400)
check("unknown mode refused (check constraint)", post(ev(mode="arcade"))[0], 400)
check("level out of range refused (check constraint)", post(fin(mode="fortune", level=999))[0], 400)
check("normal game rules still checked in Fortune", post(fin(mode="fortune", level=3, provinces=40)), (400, "event_invalid"))

print("== Views")
o = get("stats_overview")[0]
check("campaign overview counts only campaign starts", o["games_started"], 1)
check("campaign overview counts only campaign finishes", o["games_finished"], 1)
r = get("stats_realms")
check("campaign realms only campaign", [(x["realm"], x["started"], x["finished"]) for x in r], [("holland", 1, 1)])
d = get("stats_daily")[0]
check("daily: campaign started and fortune started", (d["started"], d["fortune_started"]), (1, 1))
f = get("stats_fortune_overview")[0]
check("fortune overview started / finished / victories", (f["games_started"], f["games_finished"], f["victories"]), (1, 3, 1))
check("fortune overview avg level and avg cards", (float(f["avg_level"]), float(f["avg_cards"])), (4.7, 2.0))
fr = get("stats_fortune_realms")
check("fortune realms", sorted((x["realm"], x["finished"], x["won"]) for x in fr), [("gelre", 1, 0), ("holland", 2, 1)])
fc = {x["card"]: (x["games"], x["copies"], x["wins"]) for x in get("stats_fortune_cards")}
check("cards: weavers taken in 1 game, 2 copies, 1 win", fc.get("weavers"), (1, 2, 1))
check("cards: march taken in 2 games, 1 win", fc.get("march"), (2, 2, 1))
check("cards: goedendag 1 game, no win", fc.get("goedendag"), (1, 1, 0))
check("the public key still can't read raw events", psql("set role anon; select count(*) from public.events").startswith("ERR"), True)

print("== Existing database: old setup, then this file twice, then security.sql again")
root = HERE.parent
old_setup = subprocess.run(["git", "-C", str(root), "show", "cb59990:source/supabase-setup.sql"], capture_output=True, text=True).stdout
Path("/tmp/old_setup.sql").write_text(old_setup)
psql("drop database if exists olddb")
psql("create database olddb")
check("old setup loads", psql(None, "olddb", "/tmp/old_setup.sql").startswith("ERR"), False)
psql("insert into public.events (kind, realm, difficulty) values ('start', 'brabant', 'easy')", "olddb")
check("fortune file runs on the old database", psql(None, "olddb", str(HERE / "supabase-fortune-stats.sql")).startswith("ERR"), False)
check("and runs a second time", psql(None, "olddb", str(HERE / "supabase-fortune-stats.sql")).startswith("ERR"), False)
check("old rows became campaign rows", psql("select mode from public.events", "olddb"), "campaign")
check("security file runs again afterwards", psql(None, "olddb", str(HERE / "supabase-security.sql")).startswith("ERR"), False)
ins = "set role anon; insert into public.events (kind, realm, difficulty, result, years, provinces, battles_won, battles_lost, mode, level, cards) values ('finish', 'utrecht', 'hard', 'defeat', 50, 4, 3, 9, 'fortune', 5, 'tithes,pact'); select 'ok'"
check("Fortune row still accepted for the public key", psql(ins, "olddb").splitlines()[-1], "ok")
check("campaign row still accepted for the public key",
      psql("set role anon; insert into public.events (kind, realm, difficulty) values ('start', 'gelre', 'normal'); select 'ok'", "olddb").splitlines()[-1], "ok")
check("public key reads the fortune card view",
      psql("set role anon; select card || ':' || games from public.stats_fortune_cards order by card", "olddb").splitlines()[1:], ["pact:1", "tithes:1"])
check("security file runs again on the fresh database too",
      psql(None, "postgres", str(HERE / "supabase-security.sql")).startswith("ERR"), False)
psql("drop database if exists olddb")
print(f"\nFAILURES: {fails}")
