# Runs N headless Fortune games in a built index.html. The player's realm is played by the
# same AI as the other realms and drafts cards at random (sometimes the cursed one, sometimes
# a reroll). Prints crashes, broken numbers, win share, and how each card does.
# Usage: python3 source/fortune_sim.py $PWD/index.html 300 [campaign]
#   with "campaign" as 3rd argument the same AI player plays without cards (to compare)
import sys, json
from playwright.sync_api import sync_playwright

JS = r"""
([N, mode]) => {
  for (const f of ["render","startNewYear","checkGameOver","logEvent","playSound","saveGame","focusOnRealm","startGuide","renderGuide","showCard","showBattle","showYearOverview"])
    try { window[f] = () => {}; } catch (e) {}
  const out = { games: 0, errors: [], bad: [], wins: {}, played: {}, cards: {}, cardWins: {}, lengths: [],
                maxGold: 0, maxArmy: 0, maxCards: 0, best: [], drafts: 0, rerolls: 0, cursed: 0, sets: {} };
  const realms = ["holland", "utrecht", "gelre", "brabant"];
  const check = (g) => {
    for (const id in game.realms) {
      const r = game.realms[id];
      if (!Number.isFinite(r.gold) || r.gold < 0) out.bad.push(`game ${g} ${game.year} ${id} gold ${r.gold}`);
      if (!Number.isFinite(r.manpower) || r.manpower < 0) out.bad.push(`game ${g} ${game.year} ${id} manpower ${r.manpower}`);
    }
    for (const p of allProvinces()) {
      if (!Number.isInteger(p.army) || p.army < 0) out.bad.push(`game ${g} ${game.year} ${p.id} army ${p.army}`);
      if (!Number.isFinite(provinceIncome(p))) out.bad.push(`game ${g} ${p.id} income NaN`);
    }
    if (out.bad.length > 30) out.bad.length = 30;
  };
  const draft = () => {
    let guard = 0;
    while (draftsWaiting() && guard++ < 50) {
      const f = game.fortune;
      if (!f.offer) f.offer = makeOffer();
      if (Math.random() < 0.15 && game.realms[game.player].gold >= rerollCost()) { rerollOffer(); out.rerolls++; }
      let id = f.offer.cards[Math.floor(Math.random() * f.offer.cards.length)];
      if (f.offer.cursed && Math.random() < 0.2) { id = f.offer.cursed; out.cursed++; }
      takeCard(id);
      out.drafts++;
    }
  };
  for (let g = 0; g < N; g++) {
    const me = realms[g % 4];
    try {
      newGame(me, "normal", mode);
      for (const id of REALM_IDS) aiDevelop(id);   // the free first pick
      let result = null, peak = 0, peakYear = 0;
      while (!result) {
        const notes = [];
        aiDiplomacy(me, notes);
        aiTurn(me);
        if (mode === "fortune") draft();
        endTurn();
        for (const b of game.offers) if (rel(me, b).state === "war" && Math.random() < 0.5) makePeace(me, b, notes);
        if (mode === "fortune") draft();
        check(g);
        const mine = provincesOf(me).length;
        if (mine > peak) { peak = mine; peakYear = game.year; }
        out.maxGold = Math.max(out.maxGold, game.realms[me].gold);
        out.maxArmy = Math.max(out.maxArmy, armyOf(me));
        const leader = leaderBesides(me);
        if (mine >= RULES.provincesToWin) result = "win";
        else if (mine === 0 || provincesOf(leader).length >= RULES.provincesToWin) result = "loss";
        else if (game.year >= RULES.endYear) result = provincesOf(leader).length <= mine ? "win" : "loss";
      }
      out.games++;
      out.played[me] = (out.played[me] || 0) + 1;
      if (result === "win") out.wins[me] = (out.wins[me] || 0) + 1;
      out.lengths.push(game.year - RULES.startYear);
      if (mode === "fortune") {
        const cards = game.fortune.cards;
        out.maxCards = Math.max(out.maxCards, cards.length);
        for (const id of new Set(cards)) {
          out.cards[id] = (out.cards[id] || 0) + 1;
          if (result === "win") out.cardWins[id] = (out.cardWins[id] || 0) + 1;
        }
        for (const t of TAGS) { const l = setLevel(t); if (l) out.sets[t + l] = (out.sets[t + l] || 0) + 1; }
        out.best.push({ realm: me, years: game.year - RULES.startYear, result, cards: cards.slice(), provinces: provincesOf(me).length, gold: game.realms[me].gold, army: armyOf(me) });
      }
    } catch (e) {
      out.errors.push(`game ${g} (${me}, ${game.year}): ${e.message}\n${(e.stack || "").split("\n").slice(0, 4).join("\n")}`);
      if (out.errors.length > 10) break;
    }
  }
  out.best.sort((a, b) => (a.result === b.result ? a.years - b.years : a.result === "win" ? -1 : 1));
  out.best = out.best.slice(0, 6);
  return out;
}
"""

path, n = sys.argv[1], int(sys.argv[2])
mode = sys.argv[3] if len(sys.argv) > 3 else "fortune"
with sync_playwright() as p:
    browser = p.chromium.launch(executable_path="/usr/bin/google-chrome", args=["--no-sandbox"])
    page = browser.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto("file://" + path)
    page.wait_for_timeout(300)
    res = page.evaluate(JS, [n, mode])
    browser.close()
g = res["games"]
print(f"{mode}: {g} games, page errors {len(errors)}, crashes {len(res['errors'])}, broken numbers {len(res['bad'])}")
for e in res["errors"][:5]: print("  CRASH", e)
for b in res["bad"][:10]: print("  BAD", b)
print("player win % per realm:", {k: round(100 * res["wins"].get(k, 0) / v, 1) for k, v in res["played"].items()},
      "overall", round(100 * sum(res["wins"].values()) / max(1, g), 1))
L = sorted(res["lengths"]); print("years: median", L[len(L) // 2] if L else None, "max gold", res["maxGold"], "max army", res["maxArmy"])
if mode == "fortune":
    print(f"drafts/game {res['drafts'] / g:.1f}  rerolls {res['rerolls']}  cursed taken {res['cursed']}  most cards {res['maxCards']}")
    print("set bonuses reached (games):", res["sets"])
    base = sum(res["wins"].values()) / g
    rows = sorted(((100 * res["cardWins"].get(k, 0) / v, k, v) for k, v in res["cards"].items()), reverse=True)
    print("win % of games that drafted the card (overall", round(100 * base, 1), "):")
    print("  " + "  ".join(f"{k} {w:.0f}% ({v})" for w, k, v in rows))
    print("fastest runs:")
    for b in res["best"]: print("  ", json.dumps(b))
