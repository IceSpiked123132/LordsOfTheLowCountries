# Ablation test for developments: gives ONE realm ONE development from turn 1 (without the tier before it and
# without paying) and compares that realm's win rate with a baseline of the same build.
# Usage: python3 source/dev_ablation.py $PWD/index.html 600 [baseline games] [workers] [JSON config shared by all runs]
# Prints a table of win rate change in percentage points per realm and option; flags |change| over 8.
import sys, json
from multiprocessing import Pool
from playwright.sync_api import sync_playwright
sys.path.insert(0, __import__("os").path.dirname(__file__))
import balance_sim as bs

path, n = sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 600
base_n = int(sys.argv[3]) if len(sys.argv) > 3 else 3000
workers = int(sys.argv[4]) if len(sys.argv) > 4 else 2
shared = json.loads(sys.argv[5]) if len(sys.argv) > 5 else {}
REALMS = ["holland", "utrecht", "gelre", "brabant"]
OPTIONS = ["market","tolls","dikes","guilds","bank","fleet","crossbow","pikes","castles","mercs","captains","plunder",
           "town","marriage","charters","tax","peace","standing"]

def job(task):
    realm, option, games = task
    cfg = dict(shared)
    if realm: cfg["force"] = {realm: [option]}
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path="/usr/bin/google-chrome")
        pg = b.new_page()
        pg.route("https://ktvkqdxxpfmferhdjapz.supabase.co/**", lambda r: r.fulfill(status=200, body="[]"))
        res = bs.run(pg, path, games, cfg)
        b.close()
    return realm, option, games, res

if __name__ == "__main__":
    tasks = [(None, None, base_n)] + [(r, o, n) for r in REALMS for o in OPTIONS]
    out = {}
    with Pool(workers) as pool:
        for realm, option, games, res in pool.imap_unordered(job, tasks):
            out[(realm, option)] = (games, res)
            print("done", realm, option, flush=True)
    bn, bres = out[(None, None)]
    base = {r: 100 * bres["wins"].get(r, 0) / bn for r in REALMS}
    print("\\nBaseline (%d games):" % bn, {r: round(v, 1) for r, v in base.items()})
    rows, flagged = [], []
    print("\\nWin rate change in percentage points (%d games each), realm that received the option:" % n)
    print("%-10s" % "option" + "".join("%10s" % r[:3] for r in REALMS))
    for o in OPTIONS:
        line = "%-10s" % o
        for r in REALMS:
            g, res = out[(r, o)]
            d = 100 * res["wins"].get(r, 0) / g - base[r]
            line += "%+9.1f%s" % (d, "*" if abs(d) > 8 else " ")
            if abs(d) > 8: flagged.append((r, o, d))
        print(line)
    json.dump({"base": base, "n": n, "base_n": bn, "flagged": flagged,
               "table": {o: {r: 100 * out[(r, o)][1]["wins"].get(r, 0) / out[(r, o)][0] - base[r] for r in REALMS} for o in OPTIONS}},
              open("/tmp/ablation.json", "w"))
    print("\\nFlagged (over 8 points):", flagged)
