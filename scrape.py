#!/usr/bin/env python3
"""Scrape venue websites and write site/events.json.

Each venue gets its own function that returns a list of events. To add a
venue: write one more function, register it in SOURCES, done.
"""
import datetime as dt
import json
import re
import sys
import urllib.robotparser
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

OUT = Path(__file__).parent / "site" / "events.json"
# Identify yourself so site owners can contact you. Put your own email here.
USER_AGENT = "whats-on-calendar/0.1 (personal project; contact: you@example.com)"

# ---------------------------------------------------------------- venues ---
VENUES = {
    "kmw-stadthaus": {"name": "KMW · Beim Stadthaus", "address": "Museumstrasse 52, 8400 Winterthur", "match": "Beim Stadthaus"},
    "kmw-reinhart": {"name": "KMW · Reinhart am Stadtgarten", "address": "Stadthausstrasse 6, 8400 Winterthur", "match": "Reinhart am Stadtgarten"},
    "kmw-flora": {"name": "KMW · Villa Flora", "address": "Tösstalstrasse 44, 8400 Winterthur", "match": "Villa Flora"},
}
VENUES.update({
    "theater-winterthur": {"name": "Theater Winterthur", "address": "Theaterstrasse 6, 8400 Winterthur"},
    "theater-am-gleis": {"name": "Theater am Gleis", "address": "Untere Vogelsangstrasse 3, 8400 Winterthur"},
    "casinotheater": {"name": "Casinotheater Winterthur", "address": "Stadthausstrasse 119, 8400 Winterthur"},
    "kellertheater": {"name": "Kellertheater Winterthur", "address": "Altstadt, 8400 Winterthur"},
    "zimmer-theater-ariane": {"name": "Zimmer-Theater Ariane", "address": "Schaffhauserstrasse 44, 8400 Winterthur"},
    "figurentheater": {"name": "Figurentheater Winterthur", "address": "Marktgasse 25, 8400 Winterthur"},
    "tkz-winterthur": {"name": "Theater Kanton Zürich (Winterthur)", "address": "Scheideggstrasse 37, Winterthur-Grüze"},
})
VENUE_BY_NAME = {v["match"]: k for k, v in VENUES.items() if "match" in v}
VENUE_RE = "|".join(re.escape(n) for n in VENUE_BY_NAME)

# ------------------------------------------------------------- fetching ----
_robots = {}


def allowed(url):
    host = "{0.scheme}://{0.netloc}".format(urlparse(url))
    if host not in _robots:
        rp = urllib.robotparser.RobotFileParser(host + "/robots.txt")
        try:
            rp.read()
        except Exception:
            rp = None
        _robots[host] = rp
    rp = _robots[host]
    return True if rp is None else rp.can_fetch(USER_AGENT, url)


def fetch(url):
    if not allowed(url):
        raise RuntimeError(f"robots.txt disallows {url}")
    r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)
    r.raise_for_status()
    return r.text


# -------------------------------------------------------------- helpers ----
def flat(text):
    return re.sub(r"\s+", " ", text).strip()


def to_iso(y, m, d):
    return dt.date(int(y), int(m), int(d)).isoformat()


# Matches "9.10. – 1.11.2026 | Reinhart am Stadtgarten" (start year optional)
RANGE_RE = re.compile(
    r"(\d{1,2})\.(\d{1,2})\.(?:(\d{4}))?\s*[–-]\s*(\d{1,2})\.(\d{1,2})\.(\d{4})\s*\|\s*(" + VENUE_RE + ")"
)
# Matches "08.11.2026 15:00 - 17:00 Humaniz-Arte Mitmischen!Beim Stadthaus"
EVENT_RE = re.compile(r"(\d{1,2})\.(\d{1,2})\.(\d{4})\s+(\d{1,2}:\d{2})\s*[-–]\s*(\d{1,2}:\d{2})\s*(.*)")


# ----------------------------------------------- Kunst Museum Winterthur ---
def parse_kmw_exhibitions(html, base="https://www.kmw.ch/en/"):
    soup = BeautifulSoup(html, "html.parser")
    found = {}
    for a in soup.select('a[href*="/exhibition/"]'):
        url = urljoin(base, a["href"])
        if url in found:  # the page lists every exhibition twice (menu + body)
            continue
        # climb to the smallest container that holds exactly this one exhibition
        node = a
        for _ in range(6):
            node = node.parent
            if node is None:
                break
            n_links = len({x["href"] for x in node.select('a[href*="/exhibition/"]')})
            if n_links == 1 and RANGE_RE.search(flat(node.get_text(" "))):
                break
        else:
            continue
        if node is None:
            continue
        m = RANGE_RE.search(flat(node.get_text(" ")))
        if not m:
            continue
        sd, sm, sy, ed, em, ey, venue = m.groups()
        end = dt.date(int(ey), int(em), int(ed))
        start = dt.date(int(sy or ey), int(sm), int(sd))
        if start > end:  # "4.7. – 25.10.2026" style, or a range crossing New Year
            start = start.replace(year=start.year - 1)
        # title = text lines before the date line, de-duplicated
        parts = []
        for s in node.stripped_strings:
            if re.match(r"\d{1,2}\.\d{1,2}\.", s):
                break
            if not parts or parts[-1] != s:
                parts.append(s)
        found[url] = {
            "type": "exhibition",
            "title": " – ".join(parts),
            "start": start.isoformat(),
            "end": end.isoformat(),
            "venue": VENUE_BY_NAME[venue],
            "url": url,
        }
    return list(found.values())


def parse_kmw_events(html, base="https://www.kmw.ch/en/agenda/"):
    soup = BeautifulSoup(html, "html.parser")
    events = []
    for h in soup.find_all(["h2", "h3"]):
        m = EVENT_RE.match(flat(h.get_text(" ")))
        if not m:
            continue
        d, mo, y, t1, t2, rest = m.groups()
        venue_key = None
        vm = re.search(r"(" + VENUE_RE + r")\s*$", rest)
        if vm:
            venue_key = VENUE_BY_NAME[vm.group(1)]
            rest = rest[: vm.start()].strip()
        # first bold line of the description is usually the real title
        sub = None
        nxt = h.find_next_sibling()
        if nxt is not None:
            b = nxt.find(["strong", "b"])
            sub = flat(b.get_text(" ")) if b else None
        title = f"{rest}: {sub}" if sub else rest
        iso = to_iso(y, mo, d)
        events.append({
            "type": "event",
            "title": title,
            "start": iso,
            "end": iso,
            "time": f"{t1}–{t2}",
            "venue": venue_key or "kmw-stadthaus",
            "url": base,
        })
    return events


def scrape_kmw():
    ex = parse_kmw_exhibitions(fetch("https://www.kmw.ch/en/exhibitions/"))
    ev = parse_kmw_events(fetch("https://www.kmw.ch/en/agenda/"))
    print(f"kmw: {len(ex)} exhibitions, {len(ev)} events")
    if not ex:
        raise RuntimeError("kmw: found 0 exhibitions - the page layout probably changed")
    return ex + ev



# ------------------------------------------------------- Theater Winterthur ---
TW_CATEGORIES = [("Musiktheater", "music"), ("Tanz", "dance"), ("Ballett", "dance"),
                 ("Junges Publikum", "kids"), ("Schauspiel", "theater"), ("Performance", "theater")]


def infer_year(day, month, today):
    """'25.10.' has no year: pick the first year that puts it no more than 60 days in the past."""
    for y in (today.year - 1, today.year, today.year + 1):
        try:
            c = dt.date(y, month, day)
        except ValueError:
            continue
        if c >= today - dt.timedelta(days=60):
            return c
    return None


def parse_tw_home(html, base="https://www.theaterwinterthur.ch/", today=None):
    """The home page lists the next few productions server-side: an <h2> with the
    title, category <li>s, and a <table> with one row per date/time."""
    today = today or dt.date.today()
    soup = BeautifulSoup(html, "html.parser")
    events = []
    for table in soup.find_all("table"):
        h = table.find_previous("h2")
        if h is None:
            continue
        a = h.find("a")
        url = urljoin(base, a["href"]) if a and a.get("href") else base
        title = flat(h.get_text(" "))
        cats = []
        for el in h.next_elements:
            if el is table:
                break
            if getattr(el, "name", None) == "li":
                cats.append(flat(el.get_text(" ")))
        kind = "event" if "Extra" in cats else "show"
        category = next((v for k, v in TW_CATEGORIES for c in cats if k in c), None) if kind == "show" else None
        for tr in table.find_all("tr"):
            cells = [flat(c.get_text(" ")) for c in tr.find_all(["td", "th"])]
            m = re.match(r"(\d{1,2})\.(\d{1,2})\.", cells[0]) if cells else None
            if not m:
                continue
            d = infer_year(int(m.group(1)), int(m.group(2)), today)
            t = re.search(r"(\d{1,2}):(\d{2})", " ".join(cells[1:]))
            if d is None:
                continue
            events.append({
                "type": kind, "category": category, "title": title,
                "start": d.isoformat(), "end": d.isoformat(),
                "time": f"{int(t.group(1)):02d}:{t.group(2)}" if t else None,
                "venue": "theater-winterthur", "url": url,
            })
    return events


def scrape_theater_winterthur():
    ev = parse_tw_home(fetch("https://www.theaterwinterthur.ch/"))
    print(f"theater-winterthur: {len(ev)} dates")
    if not ev:
        raise RuntimeError("theater-winterthur: found 0 dates - layout probably changed")
    return ev


# ---------------------------------------------- applaus! (7 theaters at once) ---
# https://applaus-winterthur.ch/ lists upcoming performances of all Winterthur theaters
# that give a 50% discount to applaus! members. Each entry is a link whose text reads
#   "So, 25.10.2026,  17:00 Uhr Zimmer-Theater Ariane <kicker> <title> <description>"
# The title can't be told apart from kicker and description by looking at the text alone,
# but the link's URL slug is the title (".../vorstellung/wer-hat-angst-vor-leo-trotzki/"),
# so we find the slug inside the text and split around it.
APPLAUS_URL = "https://applaus-winterthur.ch/"
APPLAUS_VENUES = {
    "Zimmer-Theater Ariane": "zimmer-theater-ariane",
    "Kellertheater Winterthur": "kellertheater",
    "Theater am Gleis": "theater-am-gleis",
    "Casinotheater Winterthur": "casinotheater",
    "Theater Kanton Zürich": "tkz-winterthur",
    "Theater Winterthur": "theater-winterthur",
    "Figurentheater Winterthur": "figurentheater",
}
APPLAUS_RE = re.compile(
    r"^[A-Za-z]{2},\s*(\d{1,2})\.(\d{1,2})\.(\d{4}),\s*(\d{1,2}:\d{2})\s*Uhr\s+("
    + "|".join(re.escape(n) for n in sorted(APPLAUS_VENUES, key=len, reverse=True)) + r")\s*(.*)$"
)
_UMLAUTS = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "Ä": "ae", "Ö": "oe", "Ü": "ue", "ß": "ss"})


def _norm_with_map(text):
    """Lower-case, transliterate, keep only a-z0-9; return (normalized, index map into text)."""
    import unicodedata
    out, idx = [], []
    for i, ch in enumerate(text):
        t = unicodedata.normalize("NFKD", ch.translate(_UMLAUTS))
        for c in t:
            if c.isascii() and c.isalnum():
                out.append(c.lower())
                idx.append(i)
    return "".join(out), idx


def split_by_slug(rest, slug):
    """-> (kicker, title, description); title is None if the slug can't be located in the text."""
    norm, idx = _norm_with_map(rest)
    for cand in (slug, re.sub(r"-\d+$", "", slug)):
        key = re.sub(r"[^a-z0-9]", "", cand.lower())
        pos = norm.find(key) if key else -1
        if pos >= 0:
            a, b = idx[pos], idx[pos + len(key) - 1] + 1
            while a > 0 and rest[a - 1] in "«“„\"'(":  # opening quote belongs to the title
                a -= 1
            # swallow trailing punctuation that belongs to the title ("Trotzki?", "«Dr. Nest»")
            while b < len(rest) and rest[b] in "?!»“”\"'.…":
                b += 1
            return rest[:a].strip(" |–-"), rest[a:b].strip(), rest[b:].strip()
    return None, None, rest


def categorize(kicker, title, description):
    k = f"{kicker} {title}".lower()
    if re.search(r"tanz|ballett", k):
        return "dance"
    if re.search(r"kinder|ab \d+ jahren", k + " " + description.lower()[:60]):
        return "kids"
    if re.search(r"comedy|kabarett|slam|impro|theatersport|satire", k):
        return "comedy"
    if re.search(r"musik|konzert|oper\b|operette|lieder|album|plattentaufe|band", k):
        return "music"
    return "theater"


def parse_applaus(html, base=APPLAUS_URL):
    soup = BeautifulSoup(html, "html.parser")
    events = []
    for a in soup.select('a[href*="/vorstellung/"]'):
        text = flat(a.get_text(" "))
        m = APPLAUS_RE.match(text)
        if not m:
            continue
        d, mo, y, hhmm, venue, rest = m.groups()
        try:
            iso = to_iso(y, mo, d)
        except ValueError:
            continue
        url = urljoin(base, a["href"])
        slug = [p for p in urlparse(url).path.split("/") if p][-1]
        kicker, title, desc = split_by_slug(rest, slug)
        if title is None:  # slug not found in the text: fall back to the slug itself
            title = slug.replace("-", " ").capitalize()
        ev = {
            "type": "show", "category": categorize(kicker or "", title, desc),
            "title": title, "start": iso, "end": iso,
            "time": f"{int(hhmm.split(':')[0]):02d}:{hhmm.split(':')[1]}",
            "venue": APPLAUS_VENUES[venue], "url": url,
        }
        if kicker:
            ev["subtitle"] = kicker
        if desc:
            ev["description"] = desc[:220]
        events.append(ev)
    return events


def scrape_applaus():
    ev = parse_applaus(fetch(APPLAUS_URL))
    print(f"applaus: {len(ev)} performances")
    if not ev:
        raise RuntimeError("applaus: found 0 performances - the page layout probably changed")
    return ev


# Order matters for dedupe: an earlier source wins over a later one.
SOURCES = [scrape_kmw, scrape_theater_winterthur, scrape_applaus]


def dedupe(events_by_source):
    """The same date/venue from two sources (e.g. Theater Winterthur's own site and applaus!)
    is one event if the times match or either time is unknown. Earlier sources win."""
    kept = {}  # (start, venue) -> [(source, time)]
    out = []
    for name, evs in events_by_source:
        for e in evs:
            t = e.get("time") or ""
            others = [(n, tt) for n, tt in kept.get((e["start"], e["venue"]), []) if n != name]
            if e["type"] != "exhibition" and any(not tt or not t or tt == t for _, tt in others):
                continue
            kept.setdefault((e["start"], e["venue"]), []).append((name, t))
            out.append(e)
    return out


def main():
    by_source, failures = [], 0
    for source in SOURCES:
        try:
            by_source.append((source.__name__, source()))
        except Exception as e:  # one broken source shouldn't wipe the others
            failures += 1
            print(f"ERROR in {source.__name__}: {e}", file=sys.stderr)
    events = dedupe(by_source)
    if failures and not events:
        sys.exit("All sources failed; keeping the previous events.json")
    for e in events:
        e.setdefault("time", None)
    events.sort(key=lambda e: (e["start"], e.get("time") or "", e["title"]))
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps({
        "updated": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "venues": {k: {"name": v["name"], "address": v["address"]} for k, v in VENUES.items()},
        "events": events,
    }, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"wrote {len(events)} events to {OUT}")
    if failures:
        sys.exit(1)  # the workflow still deploys partial data, but the run shows as failed (GitHub emails you)


if __name__ == "__main__":
    main()
