# Runs N AI-only games in the built index.html and prints win share per realm, game length, comebacks.
# Usage: python3 source/balance_sim.py $PWD/index.html 2000 '{"gelre":{"charge":1.25}}'  (optional TRAITS overrides)
import sys, json
from playwright.sync_api import sync_playwright
path, n = sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 200
over = json.loads(sys.argv[3]) if len(sys.argv) > 3 else {}
JS = r"""
([N, over]) => {
  if (typeof TRAITS !== "undefined") for (const id in over) Object.assign(TRAITS[id], over[id]);
  for (const f of ["render","startNewYear","checkGameOver","logEvent","playSound","saveGame","focusOnRealm","startGuide","renderGuide","showCard","showBattle","showYearOverview"])
    try { window[f] = () => {}; } catch (e) {}
  const wins = {}, lengths = [], realmStats = {};
  let comebacks = 0, setbacks = 0, ran1400 = 0;
  for (let g = 0; g < N; g++) {
    newGame("holland", "normal");
    game.player = "nobody";
    const start = {}, low = {}, back = {};
    for (const id of REALM_IDS) { start[id] = provincesOf(id).length; low[id] = start[id]; back[id] = false; }
    let winner = null;
    while (!winner) {
      endTurn();
      for (const id of REALM_IDS) {
        const c = provincesOf(id).length;
        low[id] = Math.min(low[id], c);
        if (low[id] <= start[id] - 2 && c >= start[id]) back[id] = true;
        if (c >= RULES.provincesToWin) winner = id;
      }
      if (!winner && game.year >= RULES.endYear) {
        ran1400++;
        winner = REALM_IDS.slice().sort((a, b) => provincesOf(b).length - provincesOf(a).length)[0];
      }
    }
    wins[winner] = (wins[winner] || 0) + 1;
    lengths.push(game.year - RULES.startYear);
    for (const id of REALM_IDS) {
      if (low[id] <= start[id] - 2) { setbacks++; if (back[id]) comebacks++; }
      const s = realmStats[id] = realmStats[id] || { dead: 0, prov: 0 };
      if (!alive(id)) s.dead++;
      s.prov += provincesOf(id).length;
    }
  }
  lengths.sort((a, b) => a - b);
  return { wins, avgLen: lengths.reduce((a, b) => a + b, 0) / N, medLen: lengths[N >> 1], ran1400, setbacks, comebacks, realmStats };
}
"""
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/usr/bin/google-chrome")
    pg = b.new_page()
    pg.route("https://ktvkqdxxpfmferhdjapz.supabase.co/**", lambda r: r.fulfill(status=200, body="[]"))
    pg.on("pageerror", lambda e: print("PAGEERROR", e))
    pg.goto("file://" + path)
    pg.wait_for_timeout(500)
    res = pg.evaluate(JS, [n, over])
    w=res["wins"]; N=n
    print(" ".join(f"{k[:3]} {100*w.get(k,0)/N:4.1f}" for k in ["holland","utrecht","gelre","brabant"]), f"| len {res['avgLen']:.1f} to1400 {100*res['ran1400']/N:.0f}% comeback {res['comebacks']}/{res['setbacks']} dead", {k:v["dead"] for k,v in res["realmStats"].items()}, json.dumps(over))
    b.close()
