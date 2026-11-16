# UI test of the online parts at 390x844 with a mocked Supabase that can answer with errors.
# Usage: python3 ui_test.py /path/to/lords [screenshot_dir]
import sys, json, re
from playwright.sync_api import sync_playwright
ROOT = sys.argv[1]; SHOTS = sys.argv[2] if len(sys.argv) > 2 else "/home/claude/shots"
SUPA = "https://ktvkqdxxpfmferhdjapz.supabase.co/**"
fails = 0
def check(label, ok, extra=""):
    global fails
    if not ok: fails += 1
    print(("PASS  " if ok else "FAIL  ") + label + (("  " + str(extra)) if extra and not ok else ""))

class Mock:
    """mode per table: ok | blocked | url | invalid | busy | server | offline | feedback_invalid"""
    def __init__(self): self.mode = {"scores": "ok", "feedback": "ok", "events": "ok"}; self.posts = []
    def handle(self, route):
        req = route.request; url = req.url
        table = re.search(r"/rest/v1/([a-z_]+)", url).group(1)
        if req.method == "GET":
            rows = [{"name": "Willem", "realm": "holland", "years": 18, "created_at": "2026-11-10T10:00:00Z"},
                    {"name": "Margriet", "realm": "gelre", "years": 21, "created_at": "2026-11-11T10:00:00Z"}] if table == "scores" else []
            return route.fulfill(status=200, content_type="application/json", body=json.dumps(rows))
        self.posts.append((table, req.post_data))
        m = self.mode[table]
        err = {"blocked": (400, "name_blocked"), "url": (400, "name_url"), "invalid": (400, "score_invalid"), "busy": (429, "rate_limit"),
               "server": (500, "boom"), "feedback_invalid": (400, "feedback_invalid"), "weird401": (401, "")}
        if m == "offline": return route.abort("failed")
        if m in err:
            st, msg = err[m]
            return route.fulfill(status=st, content_type="application/json", body=json.dumps({"code": "PT400", "message": msg}))
        return route.fulfill(status=201, body="")

def new_page(browser, mock, lang):
    ctx = browser.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, locale="nl-NL" if lang == "nl" else "en-GB")
    ctx.add_init_script(f"try{{localStorage.setItem('lords-lang','{lang}')}}catch(e){{}}")
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("console", lambda m: errors.append("console: " + m.text) if m.type == "error" and "Failed to load resource" not in m.text else None)
    page.route(SUPA, mock.handle)
    page.goto(f"file://{ROOT}/index.html"); page.wait_for_timeout(500)
    return ctx, page, errors

def win_game(page):
    """start a game as Holland, give the player 16 provinces, let the real checkGameOver end it as a victory"""
    page.evaluate("""() => {
      hide("start"); newGame("holland", "normal"); closeDevelopments && closeDevelopments();
      let n = 0; for (const id in game.provinces) { if (n < 16) game.provinces[id].owner = "holland"; n++; }
      game.year = 1350 + 21; checkGameOver(); }""")
    page.wait_for_timeout(300)

def shot(page, name): page.screenshot(path=f"{SHOTS}/{name}.png")

with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/usr/bin/google-chrome", args=["--no-sandbox"])
    for lang in ["en", "nl"]:
        print(f"\n===== {lang.upper()} =====")
        mock = Mock(); ctx, page, errors = new_page(b, mock, lang)
        T = lambda en, nl: nl if lang == "nl" else en

        # Start screen link
        link = page.locator("#start .start-version a")
        check("start screen has a privacy link next to the version", link.count() == 1 and "v2026" in page.inner_text("#start-version"))
        check("link opens privacy.html", link.get_attribute("href") == "privacy.html")
        box = link.bounding_box(); check("privacy link is on screen at 390x844", box and box["y"] + box["height"] <= 844 and box["y"] > 0, box)
        shot(page, f"01-start-{lang}")

        # Feedback form
        page.evaluate("openFeedback()"); page.wait_for_timeout(200)
        note = page.inner_text("#feedback .privacy-note")
        check("feedback form shows the optional/reply-only note and a privacy link", ("optional" in note or "hoeft niet" in note) and page.locator("#feedback .privacy-note a").count() == 1, note)
        shot(page, f"02-feedback-{lang}")
        def send(msg):
            page.fill("#fb-text", msg); page.click("#fb-send"); page.wait_for_timeout(400); return page.inner_text("#fb-status")
        expect = {"ok": T("Thank you! Your message has been sent.", "Dank je! Je bericht is verstuurd."),
                  "busy": T("The server is very busy right now. Please try again in a little while.", "De server is nu erg druk. Probeer het over een poosje opnieuw."),
                  "feedback_invalid": T("Your message couldn't be sent. Check it and try again.", "Je bericht kon niet worden verstuurd. Controleer het en probeer het opnieuw."),
                  "server": T("Something went wrong on the server. Please try again later.", "Er ging iets mis op de server. Probeer het later opnieuw."),
                  "offline": T("Couldn't send it. Check your internet and try again.", "Versturen lukte niet. Controleer je internet en probeer het opnieuw.")}
        for mode in ["busy", "feedback_invalid", "server", "offline", "weird401", "ok"]:
            mock.mode["feedback"] = mode
            want = expect.get(mode, expect["server"])
            got = send("hello there")
            check(f"feedback with server answer '{mode}' shows: {want[:38]}", got == want, got)
            if mode != "ok": check("  send button is enabled again", page.is_enabled("#fb-send"))
            if mode == "busy": shot(page, f"03-feedback-error-{lang}")
        page.evaluate("hide('feedback')")

        # Leaderboard form after a win
        mock.mode.update(scores="ok", events="ok")
        win_game(page)
        check("the game ended in a victory (real checkGameOver)", page.evaluate("game.endInfo && game.endInfo.won && !game.endInfo.final"))
        page.evaluate("openBoard(true)"); page.wait_for_timeout(300)
        check("leaderboard form has the public-name note and privacy link", page.locator("#board-form .privacy-note a").count() == 1, page.inner_text("#board-form"))
        shot(page, f"04-board-form-{lang}")
        posts_before = len(mock.posts)
        def board(name):
            page.fill("#board-name", name); page.click("#board-submit"); page.wait_for_timeout(400); return page.inner_text("#board-form-error")
        bad_blocked = T("That name isn't allowed on the leaderboard. Please pick another one.", "Die naam mag niet op de ranglijst. Kies een andere naam.")
        bad_format = T("A name can't be empty or look like a link or an email address.", "Een naam mag niet leeg zijn en niet op een link of e-mailadres lijken.")
        for name, want in [("f u c k", bad_blocked), ("KANKERLIJER", bad_blocked), ("Hitler", bad_blocked), ("jan@mail.com", bad_format), ("www.spam.nl", bad_format), ("!!!", bad_format)]:
            got = board(name); check(f"name {name!r}: friendly message, no request sent", got == want and len(mock.posts) == posts_before, got)
        shot(page, f"05-board-name-refused-{lang}")
        got = board("   "); check("empty name: nothing happens, no crash", got == "" and len(mock.posts) == posts_before)
        for mode, want in [("blocked", bad_blocked), ("url", bad_format), ("invalid", T("This result can't be put on the leaderboard.", "Dit resultaat kan niet op de ranglijst.")),
                           ("busy", expect["busy"]), ("server", expect["server"]), ("offline", T("Couldn't reach the leaderboard. Check your internet and try again.", "De ranglijst is niet bereikbaar. Controleer je internet en probeer het opnieuw."))]:
            mock.mode["scores"] = mode
            got = board("Zorro"); check(f"database says '{mode}' (name passes the game's own check): message shown, button usable", got == want and page.is_enabled("#board-submit"), got)
            check("  game state intact", page.evaluate("game.over === true && game.year === 1371 && !(game.submitted||{}).victory"))
        mock.mode["scores"] = "ok"
        got = board("Zorro"); check("good name is accepted: form closes and board lists", got == "" or page.locator("#board-form").is_hidden(), got)
        check("  result marked as submitted", page.evaluate("Boolean(game.submitted && game.submitted.victory)"))
        check("  request body has only the expected fields", set(json.loads([x for x in mock.posts if x[0] == "scores"][-1][1])) == {"name","realm","difficulty","category","years","provinces"})
        shot(page, f"06-board-after-{lang}")
        page.evaluate("hide('board')")

        # Share form
        page.evaluate("game.submitted = {}; render()"); page.wait_for_timeout(100)
        page.evaluate("openShareForm()"); page.wait_for_timeout(200)
        check("share form has the public-name note", page.is_visible("#share-board-note"))
        shot(page, f"07-share-form-{lang}")
        page.fill("#share-name", "n i g g e r"); page.click("#share-go"); page.wait_for_timeout(300)
        check("share form: blocked name stays on the form with a message", page.inner_text("#share-status") == bad_blocked and page.is_visible("#shareform"))
        mock.mode["scores"] = "blocked"; page.fill("#share-name", "Zorro"); page.click("#share-go"); page.wait_for_timeout(400)
        check("share form: database refuses name, stay and show message", page.inner_text("#share-status") == bad_blocked and page.is_visible("#shareform") and page.is_enabled("#share-go"))
        mock.mode["scores"] = "busy"; page.click("#share-go"); page.wait_for_timeout(1500)
        check("share form: busy server, the picture is still shared and the player is told", page.is_hidden("#shareform") and page.is_visible("#sharebox"))
        msg = page.inner_text("#panel .msg") if page.locator("#panel .msg").count() else ""
        check("  and the end panel explains the leaderboard did not work", ("busy" in msg or "druk" in msg), msg)
        shot(page, f"08-share-busy-{lang}")
        page.evaluate("hide('sharebox')")

        # Events failing must never break the game
        for mode in ["busy", "invalid", "offline", "server"]:
            mock.mode["events"] = mode
            page.evaluate("hide('start'); newGame('utrecht','hard'); closeDevelopments && closeDevelopments(); endTurn();"); page.wait_for_timeout(200)
        check("games keep running while statistics requests fail", page.evaluate("game.year === 1351 && game.player === 'utrecht'"))
        check("no page errors or unhandled rejections", not errors, errors)

        # Fully offline browser
        ctx.set_offline(True); mock.mode.update(feedback="offline", events="offline", scores="offline")
        page.evaluate("hide('start'); newGame('gelre','normal'); closeDevelopments && closeDevelopments(); endTurn(); endTurn();"); page.wait_for_timeout(300)
        check("fully offline: the game still plays", page.evaluate("game.year === 1352"))
        page.evaluate("for (const id of ['eventcard','yearview','cardview','battle']) { const el = document.getElementById(id); if (el) el.style.display = 'none'; } openFeedback()"); page.fill("#fb-text", "offline test"); page.click("#fb-send"); page.wait_for_timeout(500)
        check("fully offline: feedback says so", page.inner_text("#fb-status") == expect["offline"])
        check("fully offline: no page errors", not errors, errors)
        ctx.close()

    # Privacy page
    for lang in ["en", "nl"]:
        ctx = b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, locale="nl-NL" if lang == "nl" else "en-GB")
        ctx.add_init_script(f"try{{localStorage.setItem('lords-lang','{lang}')}}catch(e){{}}")
        page = ctx.new_page(); errs = []; page.on("pageerror", lambda e: errs.append(str(e)))
        page.goto(f"file://{ROOT}/privacy.html"); page.wait_for_timeout(400)
        check(f"privacy {lang}: opens in the saved language", page.evaluate("document.documentElement.lang") == lang)
        visible = page.evaluate("document.body.innerText")
        check(f"privacy {lang}: only one language visible", ("Who is behind this" in visible) == (lang == "en") and ("Wie zit hierachter" in visible) == (lang == "nl"))
        check(f"privacy {lang}: no horizontal scrolling", page.evaluate("document.documentElement.scrollWidth <= 390"))
        for need in (["Supabase", "GitHub", "12 months", "Autoriteit Persoonsgegevens", "last updated"] if lang == "en" else ["Supabase", "GitHub", "12 maanden", "Autoriteit Persoonsgegevens", "laatst bijgewerkt"]):
            check(f"privacy {lang}: mentions {need}", need in visible)
        page.screenshot(path=f"{SHOTS}/09-privacy-{lang}-top.png"); page.screenshot(path=f"{SHOTS}/10-privacy-{lang}-full.png", full_page=True)
        # switch language on the page
        other = "nl" if lang == "en" else "en"; page.click(f'[data-set="{other}"]'); page.wait_for_timeout(100)
        check(f"privacy {lang}: language switch works", page.evaluate("document.documentElement.lang") == other)
        check(f"privacy {lang}: no page errors", not errs, errs)
        ctx.close()
    b.close()
print("\nFAILURES:", fails)
sys.exit(1 if fails else 0)
