import json, subprocess, urllib.request, urllib.error, threading, time, sys
BASE = "http://127.0.0.1:3001"
def psql(sql):
    r = subprocess.run(["psql","-h","/tmp/pg","-p","5433","-U","postgres","-At","-v","ON_ERROR_STOP=1","-c",sql],capture_output=True,text=True)
    return r.stdout.strip() if r.returncode == 0 else "ERR " + r.stderr.strip()
def post(table, body, headers=None):
    req = urllib.request.Request(f"{BASE}/{table}", data=json.dumps(body).encode(), method="POST",
        headers={"Content-Type":"application/json","Prefer":"return=minimal","apikey":"anything", **(headers or {})})
    try:
        with urllib.request.urlopen(req) as r: return r.status, ""
    except urllib.error.HTTPError as e:
        try: msg = json.loads(e.read().decode()).get("message","")
        except Exception: msg = ""
        return e.code, msg
def reset():
    psql("truncate public.events, public.scores, public.feedback restart identity")
    psql("update public.rate_limits set max_rows = case when table_name='scores' and window_seconds=3600 then 30 when table_name='scores' then 200 when table_name='feedback' and window_seconds=3600 then 20 when table_name='feedback' then 50 when window_seconds=600 then 400 else 8000 end")
fails = 0
def check(label, got, want):
    global fails
    ok = got == want
    if not ok: fails += 1
    print(f"{'PASS' if ok else 'FAIL'}  {label:62} got={got}  {'' if ok else 'want=' + str(want)}")
def score(name="Jan", realm="holland", diff="normal", cat="victory", years=22, prov=16):
    return {"name":name,"realm":realm,"difficulty":diff,"category":cat,"years":years,"provinces":prov}
def ev(kind="start", **kw):
    b = {"kind":kind,"realm":"holland","difficulty":"normal","version":"2026-11-16.7"}; b.update(kw); return b

reset()
print("== Normal traffic")
check("good score", post("scores", score()), (201, ""))
check("good feedback", post("feedback", {"message":"Nice game","contact":None,"realm":"gelre","year":1360,"difficulty":"hard","version":"x"}), (201, ""))
check("feedback without game (realm null)", post("feedback", {"message":"Hi","contact":"a@b.nl","realm":None,"year":None,"difficulty":None,"version":"x"}), (201, ""))
check("start event", post("events", ev("start")), (201, ""))
check("finish victory", post("events", ev("finish", result="victory", years=22, provinces=16, battles_won=10, battles_lost=4)), (201, ""))
check("finish victory at year 50 with 9 provinces", post("events", ev("finish", result="victory", years=50, provinces=9, battles_won=10, battles_lost=4)), (201, ""))
check("finish defeat 15 provinces", post("events", ev("finish", result="defeat", years=30, provinces=15, battles_won=1, battles_lost=9)), (201, ""))
check("finish united", post("events", ev("finish", result="united", years=88, provinces=31, battles_won=60, battles_lost=9)), (201, ""))
check("finish destroyed after keep playing", post("events", ev("finish", result="destroyed", years=120, provinces=0, battles_won=6, battles_lost=19)), (201, ""))
check("score united 31 provinces 90 years", post("scores", score("Kees", cat="united", years=90, prov=31)), (201, ""))
check("score victory year 50, 7 provinces", post("scores", score("Anna", years=50, prov=7)), (201, ""))
print(" stored name spacing:", psql("select name from scores order by id limit 1"))

print("== Names")
for name, want in [("f u c k","name_blocked"),("KANKERLIJER","name_blocked"),("Hitler","name_blocked"),("","name_empty"),("   ","name_empty"),("!!!","name_empty"),("​​","name_empty"),
                   ("me@mail.com","name_email"),("http://x.y","name_url"),("evil.com","name_url"),("www.x","name_url")]:
    check(f"name {name!r}", post("scores", score(name)), (400, want))
for name in ["Assen","Harshit","Scunthorpe","Dick Bruna","Zoë van Dijk","李雷","@jonathan"]:
    check(f"name {name!r} accepted", post("scores", score(name))[0], 201)
check("20 chars with double spaces is collapsed (fits)", post("scores", score("Jan  de   Wit  van  Os"))[0], 201)

print("== Impossible scores")
for label, kw in [("victory 51 years", dict(years=51)),("victory 2 years (too fast)", dict(years=2, prov=20)),("victory 0 years", dict(years=0)),
                  ("victory year 30 with 10 provinces", dict(years=30, prov=10)),("victory 31 provinces", dict(prov=31)),("provinces 40", dict(prov=40)),("provinces 0", dict(prov=0)),
                  ("united with 30 provinces", dict(cat="united", years=50, prov=30)),("united in 3 years", dict(cat="united", years=3, prov=31)),("united 250 years", dict(cat="united", years=250, prov=31)),
                  ("unknown category", dict(cat="best")),("unknown realm", dict(realm="france")),("negative years", dict(years=-5))]:
    st, msg = post("scores", score(**kw))
    check(label, st, 400)
print("== Impossible events")
for label, body in [("start with a result", ev("start", result="victory")),("finish without result", ev("finish", years=5, provinces=5, battles_won=1, battles_lost=1)),
                    ("victory 40 provinces", ev("finish", result="victory", years=22, provinces=40, battles_won=1, battles_lost=1)),
                    ("victory year 20 with 9 provinces", ev("finish", result="victory", years=20, provinces=9, battles_won=1, battles_lost=1)),
                    ("defeat with 16 provinces", ev("finish", result="defeat", years=20, provinces=16, battles_won=1, battles_lost=1)),
                    ("united with 20 provinces", ev("finish", result="united", years=60, provinces=20, battles_won=1, battles_lost=1)),
                    ("destroyed with 3 provinces", ev("finish", result="destroyed", years=60, provinces=3, battles_won=1, battles_lost=1)),
                    ("kind 'bogus'", ev("bogus")), ("victory 90 years", ev("finish", result="victory", years=90, provinces=20, battles_won=1, battles_lost=1))]:
    st, msg = post("events", body)
    check(label, st, 400)

print("== Feedback")
for label, body in [("empty message", {"message":"   "}),("fake realm", {"message":"x","realm":"mars"}),("year 3000", {"message":"x","year":3000}),("difficulty nightmare", {"message":"x","difficulty":"nightmare"}),("message 2001 chars", {"message":"a"*2001})]:
    check(label, post("feedback", body)[0], 400)

print("== Forging columns and reading")
st = post("scores", {**score("Forger"), "created_at":"2020-01-01T00:00:00Z"})[0]; check("custom created_at is refused (permission)", st in (401, 403), True)
check("custom id is refused", post("scores", {**score("Forger2"), "id": 9999})[0] in (400, 401, 403), True)
for t in ["events","feedback","rate_limits","blocked_words"]:
    try: urllib.request.urlopen(f"{BASE}/{t}?select=*"); r = "readable"
    except urllib.error.HTTPError as e: r = e.code
    check(f"anon cannot read {t}", r, 401 if r == 401 else 403)
for fn in ["check_rate_limit","name_problem","delete_old_feedback"]:
    req = urllib.request.Request(f"{BASE}/rpc/{fn}", data=b"{}", method="POST", headers={"Content-Type":"application/json"})
    try: urllib.request.urlopen(req); r = "callable"
    except urllib.error.HTTPError as e: r = "refused"
    check(f"anon cannot call {fn}()", r, "refused")
try: r = json.loads(urllib.request.urlopen(f"{BASE}/stats_overview").read())[0]; ok = "games_started" in r
except Exception as e: ok = False
check("anon can read stats_overview", ok, True)
try: r = json.loads(urllib.request.urlopen(f"{BASE}/scores?select=name,years&order=years.asc&limit=3").read()); ok = len(r) > 0
except Exception as e: ok = False
check("anon can read the leaderboard", ok, True)
for method in ["PATCH", "DELETE"]:
    req = urllib.request.Request(f"{BASE}/scores?id=gte.0", data=b'{"years":1}' if method=="PATCH" else None, method=method, headers={"Content-Type":"application/json"})
    try: urllib.request.urlopen(req); r = "allowed"
    except urllib.error.HTTPError as e: r = "refused"
    check(f"anon cannot {method} scores", r, "refused")

print("== Rate limits")
reset()
codes = [post("scores", score(f"P{i}", years=10 + i % 30, prov=16))[0] for i in range(33)]
check("scores: 30 accepted, then 429", (codes.count(201), codes[30:]), (30, [429, 429, 429]))
print(" 31st response body:", post("scores", score("Late")))
codes = [post("feedback", {"message": f"m{i}"})[0] for i in range(23)]
check("feedback: 20 accepted, then 429", (codes.count(201), codes[20:]), (20, [429, 429, 429]))
t0 = time.time(); codes = [post("events", ev("start"))[0] for i in range(403)]
check("events: 400 accepted, then 429", (codes.count(201), codes[400:]), (400, [429, 429, 429]))
print(f" (403 requests in {time.time()-t0:.1f}s)")
print(" game is not affected by 429: statuses are plain HTTP 429 with message 'rate_limit'")
reset()
psql("update rate_limits set max_rows = 5 where table_name='scores' and window_seconds=86400")
codes = [post("scores", score(f"D{i}", years=10 + i, prov=16))[0] for i in range(7)]
check("daily cap (set to 5): 5 accepted, then 429", (codes.count(201), codes[5:]), (5, [429, 429]))
reset()
psql("insert into scores (name,realm,difficulty,category,years,provinces,created_at) select 'Old'||g,'holland','normal','victory',20,16, now() - interval '2 hours' from generate_series(1,40) g")
check("old rows (older than the window) do not count: hourly cap passes", post("scores", score("Fresh"))[0], 201)

print("== Bulk insert (one request, 1000 rows) cannot jump the limit")
reset()
st, msg = post("events", [ev("start") for _ in range(1000)])
check("1000 events in one request", (st, psql("select count(*) from events")), (429, "0"))
reset()
st, msg = post("events", [ev("start") for _ in range(300)])
check("300 events in one request are fine", (st, psql("select count(*) from events")), (201, "300"))
st, msg = post("events", [ev("start") for _ in range(300)])
check("another 300 in one request would pass 400: refused, nothing stored", (st, psql("select count(*) from events")), (429, "300"))

print("== Concurrency: 60 simultaneous requests, limit set to 20")
reset()
psql("update rate_limits set max_rows = 20 where table_name='events' and window_seconds=600")
res = []
def w(): res.append(post("events", ev("start"))[0])
th = [threading.Thread(target=w) for _ in range(60)]
[t.start() for t in th]; [t.join() for t in th]
check("exactly 20 stored", (res.count(201), psql("select count(*) from events")), (20, "20"))
reset()
print("\nFAILURES:", fails)
sys.exit(1 if fails else 0)
