# Checks that two builds play the campaign exactly the same: both run the same AI-only games
# with the same seeded random numbers, and every year's map, gold and armies are compared.
# Usage: python3 source/same_campaign.py old_index.html new_index.html 300
import sys, hashlib
from playwright.sync_api import sync_playwright

SEED = """
(() => { let a = 12345; Math.random = function () {
  a |= 0; a = a + 0x6D2B79F5 | 0; let t = Math.imul(a ^ a >>> 15, 1 | a);
  t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; }; })();
"""
JS = r"""
(N) => {
  for (const f of ["render","startNewYear","checkGameOver","logEvent","playSound","saveGame","focusOnRealm","startGuide","renderGuide","showCard","showBattle","showYearOverview"])
    try { window[f] = () => {}; } catch (e) {}
  const lines = [];
  for (let g = 0; g < N; g++) {
    newGame(["holland","utrecht","gelre","brabant"][g % 4], ["easy","normal","hard"][g % 3]);
    game.player = "nobody";
    resetMods();
    while (game.year < RULES.endYear) {
      endTurn();
      lines.push(game.year + "|" + allProvinces().map(p => p.owner[0] + p.army + (p.building || "")[0] + p.unrest).join(",") + "|" +
        REALM_IDS.map(id => game.realms[id].gold + ":" + game.realms[id].manpower + ":" + game.dev[id].done.join(".")).join(","));
    }
  }
  return lines;
}
"""
def run(path, n):
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path="/usr/bin/google-chrome", args=["--no-sandbox"])
        page = b.new_page()
        page.add_init_script(SEED)
        page.goto("file://" + path)
        page.wait_for_timeout(300)
        lines = page.evaluate(JS, n)
        b.close()
        return lines

old, new = run(sys.argv[1], int(sys.argv[3])), run(sys.argv[2], int(sys.argv[3]))
same = sum(1 for a, b in zip(old, new) if a == b)
print(f"years compared: {len(old)} vs {len(new)}, identical: {same}")
print("old", hashlib.sha256("\n".join(old).encode()).hexdigest()[:16], "new", hashlib.sha256("\n".join(new).encode()).hexdigest()[:16])
for a, b in zip(old, new):
    if a != b:
        print("FIRST DIFFERENCE\n old:", a[:300], "\n new:", b[:300]); break
