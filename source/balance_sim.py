# Runs N AI-only games in the built index.html and prints win share per realm, game length, comebacks,
# and how many developments each realm finished.
# Usage: python3 source/balance_sim.py $PWD/index.html 2000 '{"abilities":{"gelre":{"attack":0.25}}}'
# The optional 3rd argument is a JSON config (all keys optional):
#   "abilities": {"gelre": {"attack": 0.25}}   overrides realm ability modifiers
#   "mods":      {"market": {"farmGold": 0.5}} overrides development modifiers
#   "dev":       {"sizeSurcharge": 0.03}       overrides DEV numbers (costs, years, aiReserve ...)
#   "nodev":     true                          nobody develops (to compare with a build without developments)
#   "zero":      true                          developments are researched but have no effect (tests the cost of saving)
#   "force":     {"holland": ["market"]}       gives a realm developments from turn 1 (ablation test)
# Prints one summary line; add "json": true to also print the raw result.
import sys, json
from playwright.sync_api import sync_playwright
JS = r"""
([N, cfg]) => {
  for (const id in (cfg.abilities || {})) Object.assign(ABILITIES[id].mods, cfg.abilities[id]);
  if (typeof DEVELOPMENTS !== "undefined") {
    for (const id in (cfg.mods || {})) Object.assign(DEV_BY_ID[id].mods, cfg.mods[id]);
    Object.assign(DEV, cfg.dev || {});
    if (cfg.zero) for (const o of DEVELOPMENTS) o.mods = {};
  }
  for (const f of ["render","startNewYear","checkGameOver","logEvent","playSound","saveGame","focusOnRealm","startGuide","renderGuide","showCard","showBattle","showYearOverview"])
    try { window[f] = () => {}; } catch (e) {}
  if (cfg.nodev) window.aiDevelop = () => {};
  const wins = {}, lengths = [], realmStats = {}, devCount = {}, picks = {};
  let comebacks = 0, setbacks = 0, ran1400 = 0, broke = 0;
  for (let g = 0; g < N; g++) {
    newGame("holland", "normal");
    game.player = "nobody";
    if (cfg.nodev) for (const id of REALM_IDS) game.dev[id].free = false;
    for (const id in (cfg.force || {})) { game.dev[id].done.push(...cfg.force[id]); }
    if (typeof resetMods !== "undefined") resetMods();
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
        if (game.realms[id].gold < 0) broke++;
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
      if (game.dev) {
        devCount[id] = (devCount[id] || 0) + game.dev[id].done.length;
        for (const o of game.dev[id].done) picks[o] = (picks[o] || 0) + 1;
      }
    }
  }
  lengths.sort((a, b) => a - b);
  return { wins, avgLen: lengths.reduce((a, b) => a + b, 0) / N, medLen: lengths[N >> 1], ran1400, setbacks, comebacks, realmStats, devCount, picks, broke };
}
"""

def run(page, path, n, cfg):
    """Runs n games on a freshly loaded page (the page keeps stubs and overrides, so it is reloaded every time)."""
    page.goto("file://" + path)
    page.wait_for_timeout(300)
    return page.evaluate(JS, [n, cfg])

def summary(res, n, cfg):
    w = res["wins"]
    return (" ".join(f"{k[:3]} {100*w.get(k,0)/n:4.1f}" for k in ["holland","utrecht","gelre","brabant"]) +
            f" | len {res['avgLen']:.1f} to1400 {100*res['ran1400']/n:.0f}% comeback {res['comebacks']}/{res['setbacks']}" +
            " dead " + str({k: v["dead"] for k, v in res["realmStats"].items()}) +
            " devs/game " + str({k: round(v / n, 1) for k, v in res["devCount"].items()}) + f" broke {res['broke']} " +
            json.dumps({k: v for k, v in cfg.items() if k != "json"}))

if __name__ == "__main__":
    path, n = sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 200
    cfg = json.loads(sys.argv[3]) if len(sys.argv) > 3 else {}
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path="/usr/bin/google-chrome")
        pg = b.new_page()
        pg.route("https://ktvkqdxxpfmferhdjapz.supabase.co/**", lambda r: r.fulfill(status=200, body="[]"))
        pg.on("pageerror", lambda e: print("PAGEERROR", e))
        res = run(pg, path, n, cfg)
        print(summary(res, n, cfg))
        if cfg.get("json"): print(json.dumps(res))
        b.close()
