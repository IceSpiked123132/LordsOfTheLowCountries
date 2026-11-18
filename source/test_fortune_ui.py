# Screenshots of the Fortune screens at phone size (390x844) in English and Dutch, plus
# save checks: an old campaign save still loads, and Fortune and campaign saves don't clash.
# Usage: python3 source/test_fortune_ui.py $PWD /tmp/shots
import sys, os, json
from playwright.sync_api import sync_playwright

root, out = sys.argv[1], sys.argv[2]
os.makedirs(out, exist_ok=True)
problems = []
SCAN = r"""() => {
  const rx = /[\u2190-\u21FF\u2300-\u23FF\u2600-\u27BF\u2B50\u2B06\u{1F000}-\u{1FAFF}]/u, found = [];
  const w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  while (w.nextNode()) {
    const n = w.currentNode, tag = n.parentNode.nodeName;
    if (/^(SCRIPT|STYLE|TEXTAREA|TITLE)$/i.test(tag) || n.parentNode.namespaceURI !== "http://www.w3.org/1999/xhtml") continue;
    if (n.parentNode.offsetParent === null && getComputedStyle(n.parentNode).position !== "fixed") continue;
    const m = n.nodeValue.match(rx); if (m) found.push(m[0] + " in: " + n.nodeValue.trim().slice(0, 40));
  }
  return found;
}"""

OLD_SAVE = None  # filled from a real campaign game below

with sync_playwright() as p:
    browser = p.chromium.launch(executable_path="/usr/bin/google-chrome", args=["--no-sandbox"])
    ctx = browser.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2)
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    sent = []    # bodies the game posts to the statistics (events)
    scores = []  # (method, url, body) of leaderboard requests
    def handle(r):
        url = r.request.url
        if "/events" in url:
            sent.append(json.loads(r.request.post_data or "{}")); return r.fulfill(status=500, body="{}")
        if "/scores" in url:
            scores.append((r.request.method, url, json.loads(r.request.post_data or "{}")))
            if r.request.method == "POST": return r.fulfill(status=201, body="")
            return r.fulfill(status=200, content_type="application/json",
                             body=json.dumps([{"name": "Willem", "realm": "holland", "years": 14, "created_at": "2026-11-18T10:00:00Z"}]))
        problems.append("other online request: " + url); return r.fulfill(status=500, body="{}")
    page.route("https://ktvkqdxxpfmferhdjapz.supabase.co/**", handle)
    page.goto(f"file://{root}/index.html")
    page.wait_for_timeout(500)

    # A campaign save made the old way (no mode field), written before Fortune exists in storage
    page.evaluate("""() => { localStorage.clear(); newGame('gelre', 'normal'); game.year = 1361; saveGame(); }""")
    OLD_SAVE = page.evaluate("() => localStorage.getItem('lords-of-the-low-countries-save-v2')")
    if '"mode"' in OLD_SAVE or '"fortune"' in OLD_SAVE: problems.append("campaign save contains Fortune fields")

    for lang in ["en", "nl"]:
        page.evaluate(f"() => {{ setLanguage('{lang}'); localStorage.setItem('lords-mode', 'fortune'); chosenMode = 'fortune'; showStart(); renderMode(); }}")
        page.wait_for_timeout(200)
        problems.extend(f"{lang} emoji {x}" for x in page.evaluate(SCAN))
        page.screenshot(path=f"{out}/{lang}-1-start-fortune.png")

        # Start a Fortune game with Holland, skip the development screen and the tips
        page.evaluate("""() => { hide('start'); newGame('holland', 'normal', 'fortune'); hide('devs');
                                 const g = document.getElementById('guide'); if (g) g.style.display = 'none';
                                 game.selected = null; render(); }""")
        page.wait_for_timeout(200)
        problems.extend(f"{lang} emoji {x}" for x in page.evaluate(SCAN))
        page.screenshot(path=f"{out}/{lang}-2-panel.png")

        # A draft with one card of each rarity and the cursed fourth
        page.evaluate("""() => { game.fortune.level = 1; game.fortune.cards = ['weavers', 'herring', 'tithes'];
                                 resetMods(); game.realms[game.player].gold = 30;
                                 openDraft(() => {});
                                 game.fortune.offer = { rarity: "epic", cards: ["siege", "treasury", "feud"], cursed: "pact" }; renderFortune(); }""")
        page.wait_for_timeout(300)
        problems.extend(f"{lang} emoji {x}" for x in page.evaluate(SCAN))
        page.screenshot(path=f"{out}/{lang}-3-draft.png")
        page.click("[data-card=treasury]")
        page.wait_for_timeout(150)
        problems.extend(f"{lang} emoji {x}" for x in page.evaluate(SCAN))
        page.screenshot(path=f"{out}/{lang}-4-draft-selected.png")
        page.click("[data-fo=take]")
        page.wait_for_timeout(300)
        state = page.evaluate("() => ({ cards: game.fortune.cards, drafts: game.fortune.drafts, open: document.getElementById('fortune').style.display, msg: game.message })")
        if "treasury" not in state["cards"] or state["open"] != "none": problems.append(f"{lang}: taking a card failed {state}")

        # Reroll costs gold and deals new cards
        page.evaluate("() => { game.fortune.level = 2; game.realms[game.player].gold = 12; openDraft(() => {}); }")
        before = page.evaluate("() => game.realms[game.player].gold")
        page.click("[data-fo=reroll]")
        after = page.evaluate("() => ({ gold: game.realms[game.player].gold, rerolls: game.fortune.rerolls })")
        if before - after["gold"] != 5 or after["rerolls"] != 1: problems.append(f"{lang}: reroll {before} -> {after}")
        same = page.evaluate("""() => { const bad = []; const keep = game.fortune.offer.rarity;
            for (let i = 0; i < 300; i++) { const o = makeOffer(); const r = new Set(o.cards.map(id => CARD_BY_ID[id].rarity));
              if (r.size !== 1 || !r.has(o.rarity) || o.cards.length !== 3) bad.push(JSON.stringify(o)); }
            const o2 = makeOffer('legendary'); if (o2.rarity !== 'legendary') bad.push('reroll lost its rarity');
            return { bad: bad.slice(0, 3), keep, after: game.fortune.offer.rarity }; }""")
        if same["bad"]: problems.append(f"{lang}: mixed draft {same['bad']}")
        page.evaluate("() => { const f = game.fortune; takeCard(f.offer.cards[0]); hide('fortune'); }")

        # Your cards: a big collection with set bonuses
        page.evaluate("""() => { game.fortune.cards = ['weavers','weavers','herring','rhine','hanse','goedendag','march','veterans','veterans','tithes','granary','devotion','servatius']; game.fortune.level = 13; game.fortune.drafts = 13;
                                 resetMods(); openCards(); }""")
        page.wait_for_timeout(200)
        problems.extend(f"{lang} emoji {x}" for x in page.evaluate(SCAN))
        page.screenshot(path=f"{out}/{lang}-5-cards.png", full_page=False)
        page.evaluate("() => { document.querySelector('#fortune .box').scrollTop = 9999; }")
        problems.extend(f"{lang} emoji {x}" for x in page.evaluate(SCAN))
        page.screenshot(path=f"{out}/{lang}-6-cards-scrolled.png")
        page.evaluate("() => closeFortune()")

        # An own province selected (4 buttons in the bottom row) and the end screen
        page.evaluate("() => { game.selected = 'haarlem'; render(); }")
        problems.extend(f"{lang} emoji {x}" for x in page.evaluate(SCAN))
        page.screenshot(path=f"{out}/{lang}-7-province.png")
        page.evaluate("() => { game.selected = null; endGame(T`Victory!`, 'Test', true, false); }")
        page.wait_for_timeout(300)
        problems.extend(f"{lang} emoji {x}" for x in page.evaluate(SCAN))
        page.screenshot(path=f"{out}/{lang}-8-end.png")
        page.evaluate("() => { hide('install'); }")
        # Help: the Fortune section
        page.evaluate("() => { showHelp(); document.querySelectorAll('#help details').forEach(d => d.open = d.querySelector('summary').textContent.includes('Fortu')); }")
        page.evaluate("() => { const d = [...document.querySelectorAll('#help details')].find(d => d.open && d.offsetParent); if (d) d.scrollIntoView(); }")
        problems.extend(f"{lang} emoji {x}" for x in page.evaluate(SCAN))
        page.screenshot(path=f"{out}/{lang}-9-help.png")
        page.evaluate("() => closeHelp()")

    # Saves: Fortune and campaign live side by side
    page.evaluate("""() => { localStorage.setItem('lords-of-the-low-countries-save-v2', arguments[0]); }""".replace("arguments[0]", json.dumps(OLD_SAVE)))
    page.evaluate("() => { newGame('brabant', 'hard', 'fortune'); game.fortune.cards = ['ransom']; game.year = 1370; saveGame(); }")
    saves = page.evaluate("""() => ({ camp: loadSave('campaign'), fort: loadSave('fortune') })""")
    if not saves["camp"] or saves["camp"]["player"] != "gelre" or saves["camp"]["year"] != 1361: problems.append("campaign save was touched by Fortune")
    if not saves["fort"] or saves["fort"]["player"] != "brabant" or saves["fort"]["fortune"]["cards"] != ["ransom"]: problems.append("Fortune save missing")
    # Continue each one
    page.evaluate("() => { chosenMode = 'campaign'; showStart(); document.getElementById('continue').click(); }")
    st = page.evaluate("() => ({ mode: game.mode, player: game.player, fortune: game.fortune, year: game.year })")
    if st["mode"] != "campaign" or st["player"] != "gelre" or st["fortune"] is not None: problems.append(f"continue campaign: {st}")
    page.evaluate("() => { saveGame(); chosenMode = 'fortune'; showStart(); }")
    page.screenshot(path=f"{out}/en-0-start-continue-fortune.png")
    page.evaluate("() => document.getElementById('continue').click()")
    st = page.evaluate("() => ({ mode: game.mode, player: game.player, cards: game.fortune && game.fortune.cards, ransom: mod(game.player, 'ransomGold') })")
    if st["mode"] != "fortune" or st["cards"] != ["ransom"] or st["ransom"] != 2: problems.append(f"continue Fortune: {st}")
    # Fortune has its own leaderboard: scores are sent with mode "fortune", the board reads mode=eq.fortune
    if not page.evaluate("() => { game.endInfo = { won: true, final: false }; game.year = 1372; return canSubmitScore(); }"): problems.append("Fortune score can't be submitted")
    page.evaluate("() => postScore('Jonathan')"); page.wait_for_timeout(400)
    posted = [b for (m, u, b) in scores if m == "POST"]
    if not posted or posted[-1].get("mode") != "fortune": problems.append(f"Fortune score sent without mode fortune: {posted}")
    gets = [u for (m, u, b) in scores if m == "GET"]
    if not gets or "mode=eq.fortune" not in gets[-1]: problems.append(f"Fortune rank query not filtered on mode: {gets}")
    page.evaluate("() => { hide('start'); openBoard(false); }"); page.wait_for_timeout(400)
    if page.evaluate("() => board.mode") != "fortune": problems.append("leaderboard opened in a Fortune game is not on the Fortune tab")
    gets = [u for (m, u, b) in scores if m == "GET"]
    if "mode=eq.fortune" not in gets[-1]: problems.append(f"Fortune board not filtered on mode: {gets[-1]}")
    page.screenshot(path=f"{out}/en-10-board-fortune.png")
    page.click("[data-board-mode=campaign]"); page.wait_for_timeout(300)
    gets = [u for (m, u, b) in scores if m == "GET"]
    if "mode=eq.campaign" not in gets[-1]: problems.append(f"campaign tab not filtered on mode: {gets[-1]}")
    page.evaluate("() => hide('board')")
    page.evaluate("() => { game.mode = 'campaign'; game.fortune = null; resetMods(); }")
    if page.evaluate("() => mod('gelre', 'ransomGold')") != 0: problems.append("campaign has card modifiers")
    browser.close()

# Statistics: campaign rows exactly as before, Fortune rows marked, finished Fortune games with level and cards
camp = [b for b in sent if "mode" not in b]
fort = [b for b in sent if b.get("mode") == "fortune"]
if not camp or any(k in b for b in camp for k in ("level", "cards")): problems.append(f"campaign events wrong: {camp}")
starts = [b for b in fort if b["kind"] == "start"]
ends = [b for b in fort if b["kind"] == "finish"]
if not starts or any(k in b for b in starts for k in ("level", "cards")): problems.append(f"Fortune start events wrong: {starts}")
if not ends or any(not isinstance(b.get("level"), int) or (b.get("cards") and len(b["cards"].split(",")) > b["level"]) for b in ends):
    problems.append(f"Fortune finish events wrong: {ends}")
print("statistics rows sent:", len(camp), "campaign,", len(starts), "Fortune starts,", len(ends), "Fortune finishes, e.g.", ends[:1])
print("page errors:", errors)
print("problems:", problems)
