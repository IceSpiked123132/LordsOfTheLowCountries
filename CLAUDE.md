# Notes for Claude

Read README.md first. Edit `source/template.html`, never `index.html` directly; rebuild `index.html` with `source/build.py` (see README) and test before pushing.
The design doc for the game lives in a Claude Doc called "Lords of the Low Countries: Game Design".
The owner prefers no dashes used as punctuation in text written for him.
The game is in English and Dutch. Every sentence a player sees goes through T`...` (or tr("...") for plain strings, data-t / data-tp for fixed page text); add the Dutch version to the NL table at the top of the script, using {0}, {1}, ... for the values in order. The How to play page has a separate English and Dutch block.
