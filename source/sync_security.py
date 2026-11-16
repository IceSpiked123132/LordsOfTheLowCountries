#!/usr/bin/env python3
"""Keeps the offensive-name rules in ONE place (source/blocklist.txt).

Usage:  python3 source/sync_security.py

Copies the blocklist and the accent rules into:
  source/supabase-security.sql   between "-- BEGIN GENERATED" and "-- END GENERATED"
  source/template.html           between "// BEGIN GENERATED NAME RULES" and "// END GENERATED NAME RULES"
and rebuilds the security part of source/supabase-setup.sql from supabase-security.sql,
so a fresh database gets exactly the same rules as the script for the existing one.
Run it after editing blocklist.txt or supabase-security.sql, then rebuild the game.
"""
import re, sys, unicodedata
from pathlib import Path

HERE = Path(__file__).resolve().parent


def read_blocklist():
    words = {}
    for n, line in enumerate((HERE / "blocklist.txt").read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        whole = line.startswith("=")
        word = line[1:] if whole else line
        if not re.fullmatch(r"[a-z]+", word):
            sys.exit(f"blocklist.txt line {n}: '{line}' must be lowercase letters a to z only")
        if word in words and words[word] != whole:
            sys.exit(f"blocklist.txt line {n}: '{word}' is listed both as plain and as whole word")
        words[word] = whole
    return words


def accent_map():
    """lowercase accented letter -> plain ascii letter, built from Unicode decomposition"""
    pairs = {}
    for cp in list(range(0xC0, 0x250)) + list(range(0x1E00, 0x1F00)):
        ch = chr(cp)
        if ch != ch.lower() or ch in "ßæœ":
            continue
        d = unicodedata.normalize("NFD", ch)
        if d[0].isascii() and d[0].isalpha() and all(unicodedata.combining(c) for c in d[1:]) and len(d) > 1:
            pairs[ch] = d[0]
    pairs.update({"ø": "o", "đ": "d", "ł": "l", "ħ": "h", "ı": "i"})
    keys = "".join(pairs)
    return keys, "".join(pairs[k] for k in pairs)


def sql_chunk(words, frm, to):
    values = ",\n".join(f"  ('{w}', {'true' if whole else 'false'})" for w, whole in sorted(words.items()))
    listing = ", ".join(f"'{w}'" for w in sorted(words))
    return f"""-- Lowercase, remove accents. Mirrors normalizeName() in the game.
create or replace function public.normalize_name(t text) returns text
language sql immutable set search_path = public, pg_temp as $$
  select translate(
    replace(replace(replace(lower(t), 'ß', 'ss'), 'æ', 'ae'), 'œ', 'oe'),
    '{frm}',
    '{to}')
$$;

-- The blocklist (plain words match anywhere, whole_word ones only as a whole word).
-- This table is kept in step with source/blocklist.txt: words you add by hand
-- in the Table Editor are removed again the next time this script runs.
insert into public.blocked_words (word, whole_word) values
{values}
on conflict (word) do update set whole_word = excluded.whole_word;

delete from public.blocked_words where word <> all (array[{listing}]);"""


def js_chunk(words, frm, to):
    plain = ",".join(sorted(w for w, whole in words.items() if not whole))
    whole = ",".join(sorted(w for w, whole in words.items() if whole))
    return (f'const NAME_RULES = {{\n  accentFrom: "{frm}",\n  accentTo: "{to}",\n'
            f'  anywhere: "{plain}".split(","),\n  wholeWord: "{whole}".split(",")\n}};')


def replace_between(path, begin, end, body):
    text = path.read_text(encoding="utf-8")
    pat = re.compile(re.escape(begin) + r".*?" + re.escape(end), re.S)
    if not pat.search(text):
        sys.exit(f"{path.name}: markers '{begin}' ... '{end}' not found")
    path.write_text(pat.sub(lambda m: f"{begin}\n{body}\n{end}", text, count=1), encoding="utf-8")


def main():
    words = read_blocklist()
    frm, to = accent_map()
    assert len(frm) == len(to)

    sec = HERE / "supabase-security.sql"
    replace_between(sec, "-- BEGIN GENERATED", "-- END GENERATED", sql_chunk(words, frm, to))
    replace_between(HERE / "template.html", "// BEGIN GENERATED NAME RULES", "// END GENERATED NAME RULES", js_chunk(words, frm, to))

    # supabase-setup.sql = base tables + the same security rules
    security = sec.read_text(encoding="utf-8")
    start = security.index("-- ---------- 1. Settings tables")
    replace_between(HERE / "supabase-setup.sql", "-- BEGIN SECURITY", "-- END SECURITY",
                    "-- (copied from supabase-security.sql by source/sync_security.py, do not edit here)\n\n" + security[start:].rstrip())
    print(f"{len(words)} words ({sum(1 for v in words.values() if v)} whole word), {len(frm)} accent letters. Synced.")


if __name__ == "__main__":
    main()
