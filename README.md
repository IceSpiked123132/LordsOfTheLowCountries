# Lords of the Low Countries

A small turn-based medieval strategy game set in the Low Countries, 1350.
Play it at https://icespiked123132.github.io/LordsOfTheLowCountries/

## What's where

| File | What it is |
|---|---|
| `index.html` | The finished game. This is what GitHub Pages serves. **Don't edit it by hand**: it's generated. |
| `manifest.webmanifest`, `sw.js`, `icon-*.png` | Make it installable ("Add to Home Screen") and work offline. |
| `source/template.html` | The real source: all game code, rules and styling. Edit this. |
| `source/build.py` | Builds the map (coastline, rivers, territories, borders) from real map data and writes it into the template to make `index.html`. |
| `source/fetch_map_data.sh` | Downloads the Natural Earth map data that `build.py` needs (not stored in the repo, ~70 MB). |
| `source/make_icons.py` | Draws the app icons. |
| `fonts/` | Cinzel and EB Garamond, stored with the game (offline, and no requests to Google). SIL Open Font License. |
| `og-image.png` | The preview image shown when the link is shared on social media or in chat apps. |
| `stats.html` | Your statistics page (games started, finished, won, per realm and per day). Not linked from the game. |
| `source/supabase-setup.sql` | Creates the online database for the leaderboard, statistics and feedback. |

## Changing the game

Most balance changes are a single number in the `RULES` block near the top of `source/template.html`.
Province income, manpower and positions are in `PROVINCES` just below it.

After editing, rebuild `index.html`:

```sh
pip install shapely pillow
sh source/fetch_map_data.sh map-data        # once
python3 source/build.py map-data source/template.html index.html
```

`build.py` also recalculates which provinces border each other (and which borders are rivers)
from the province positions, so moving a city on the map changes the borders.

Push to `main` and GitHub Pages publishes it within a minute or two. Installed copies pick up the
new version the next time they're opened online.

## Saves

Games are saved in the browser (`localStorage`, key `lords-of-the-low-countries-save-v1`).
If a change makes old saves incompatible (for example new provinces), bump the `v1` in `SAVE_KEY`.

## Online features (leaderboard, statistics, feedback)

These use a free [Supabase](https://supabase.com) database and stay hidden until it's configured:

1. Create a Supabase project, open SQL Editor, paste `source/supabase-setup.sql` and run it.
2. Copy the Project URL and the `anon` public key (Project Settings, API) into `ONLINE` in
   `source/template.html` and in `stats.html`, then rebuild.

The game only sends anonymous game starts and endings (no player ID, no cookies), names typed into
the leaderboard, and feedback messages. Raw data and feedback are visible in the Supabase dashboard.
