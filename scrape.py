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
    "kellertheater": {"name": "Kellertheater Winterthur", "address": "Marktgasse 53, 8400 Winterthur"},
    "zimmer-theater-ariane": {"name": "Zimmer-Theater Ariane", "address": "Schaffhauserstrasse 44, 8400 Winterthur"},
    "figurentheater": {"name": "Figurentheater Winterthur", "address": "Marktgasse 25, 8400 Winterthur"},
    "tkz-winterthur": {"name": "Theater Kanton Zürich (Winterthur)", "address": "Scheideggstrasse 37, Winterthur-Grüze"},
})
VENUES.update({
    "dampfzentrum": {"name": "Dampfzentrum", "address": "Lagerplatz 27, 8400 Winterthur"},
    "muenzkabinett": {"name": "Münzkabinett (Villa Bühler)", "address": "Lindstrasse 8, 8400 Winterthur"},
    "uhrenmuseum": {"name": "Uhrenmuseum (Villa Bühler)", "address": "Lindstrasse 8, 8400 Winterthur"},
    "neuthal": {"name": "Museum Neuthal Industriekultur", "address": ""},
    "museumschaffen": {"name": "Museum Schaffen", "address": ""},
    "kyburg": {"name": "Schloss Kyburg", "address": "8314 Kyburg"},
    "naturmuseum": {"name": "Naturmuseum Winterthur", "address": "Museumstrasse 52, 8400 Winterthur"},
    "oxyd": {"name": "Oxyd Kunsträume", "address": ""},
    "technorama": {"name": "Technorama", "address": "Technoramastrasse 1, 8404 Winterthur"},
    "moersburg": {"name": "Schloss Mörsburg", "address": ""},
    "hegi": {"name": "Schloss Hegi", "address": "Hegifeldstrasse 125, 8409 Winterthur"},
    "roemerholz": {"name": "Sammlung Oskar Reinhart «Am Römerholz»", "address": "Haldenstrasse 95, 8400 Winterthur"},
    "fotostiftung": {"name": "Fotostiftung Schweiz", "address": "Grüzenstrasse 45, 8400 Winterthur"},
    "gewerbemuseum": {"name": "Gewerbemuseum Winterthur", "address": "Kirchplatz 14, 8400 Winterthur"},
    "galerie-weiertal": {"name": "Galerie Weiertal", "address": ""},
    "kunsthalle": {"name": "Kunsthalle Winterthur", "address": "Löwenstrasse 18, 8400 Winterthur"},
    "fotomuseum": {"name": "Fotomuseum Winterthur", "address": "Grüzenstrasse 44, 8400 Winterthur"},
    "alte-kaserne": {"name": "Alte Kaserne", "address": "Technikumstrasse 8, 8403 Winterthur"},
    "lokal": {"name": "Lok.al", "address": "Zeughausstrasse 52, 8400 Winterthur"},
    "other": {"name": "Other places", "address": ""},
})
# (substring of the place name, lower-case) -> venue key. First match wins, so order matters
# ("casinotheater" must come before "theater winterthur").
VENUE_ALIASES = [
    ("beim stadthaus", "kmw-stadthaus"), ("reinhart am stadtgarten", "kmw-reinhart"), ("villa flora", "kmw-flora"),
    ("casinotheater", "casinotheater"), ("theater winterthur", "theater-winterthur"),
    ("theater am gleis", "theater-am-gleis"), ("kellertheater", "kellertheater"),
    ("theater ariane", "zimmer-theater-ariane"), ("figurentheater", "figurentheater"),
    ("dampfzentrum", "dampfzentrum"), ("münzkabinett", "muenzkabinett"), ("uhrenmuseum", "uhrenmuseum"),
    ("neuthal", "neuthal"), ("museum schaffen", "museumschaffen"), ("kyburg", "kyburg"),
    ("naturmuseum", "naturmuseum"), ("oxyd", "oxyd"), ("technorama", "technorama"), ("mörsburg", "moersburg"),
    ("schloss hegi", "hegi"), ("römerholz", "roemerholz"), ("fotostiftung", "fotostiftung"),
    ("gewerbemuseum", "gewerbemuseum"), ("galerie weiertal", "galerie-weiertal"), ("kunsthalle", "kunsthalle"),
    ("fotomuseum", "fotomuseum"), ("alte kaserne", "alte-kaserne"), ("lok.al", "lokal"), ("lokal winterthur", "lokal"),
]
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


def _norm_with_map(text, expand=True):
    """Lower-case, transliterate, keep only a-z0-9; return (normalized, index map into text)."""
    import unicodedata
    out, idx = [], []
    for i, ch in enumerate(text):
        t = unicodedata.normalize("NFKD", ch.translate(_UMLAUTS) if expand else ch)
        for c in t:
            if c.isascii() and c.isalnum():
                out.append(c.lower())
                idx.append(i)
    return "".join(out), idx


def split_by_slug(rest, slug):
    """-> (kicker, title, description); title is None if the slug can't be located in the text.
    Tries 'ä'->'ae' (WordPress slugs) and 'ä'->'a' (Django slugs)."""
    for expand in (True, False):
        norm, idx = _norm_with_map(rest, expand)
        for cand in (slug, re.sub(r"-\d+$", "", slug)):
            key = re.sub(r"[^a-z0-9]", "", cand.lower())
            pos = norm.find(key) if key else -1
            if pos >= 0:
                a, b = idx[pos], idx[pos + len(key) - 1] + 1
                while a > 0 and rest[a - 1] in "«“„\"'(":  # opening quote belongs to the title
                    a -= 1
                while b < len(rest) and rest[b] in "?!»“”\"'.…":  # so does closing punctuation
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
    print(f"applaus: {len(ev)} performances (50% list)")
    if not ev:
        raise RuntimeError("applaus: found 0 performances - the page layout probably changed")
    return ev


# ================================================== the theaters' own sites ===
# Each page is parsed "card by card": find the title element, climb to the largest
# ancestor that still contains only that one title, then read the card's strings in order.
DE_MONTHS = {"jan": 1, "feb": 2, "mär": 3, "mar": 3, "apr": 4, "mai": 5, "jun": 6,
             "jul": 7, "aug": 8, "sep": 9, "okt": 10, "nov": 11, "dez": 12}
WD = r"(?:Mo|Di|Mi|Do|Fr|Sa|So)"


def month_num(word):
    return DE_MONTHS.get(word.lower().strip(".")[:3])


def strings(node):
    return [flat(s.replace("\xad", "")) for s in node.stripped_strings if flat(s.replace("\xad", ""))]


def card_for(el, selector):
    node = el
    while (node.parent is not None and node.parent.name not in ("body", "html", "[document]")
           and len(node.parent.select(selector)) <= 1):
        node = node.parent
    return node


def mk(type_, title, d, time, venue, url, **extra):
    e = {"type": type_, "title": title, "start": d.isoformat(), "end": d.isoformat(),
         "time": time, "venue": venue, "url": url}
    e.update({k: v for k, v in extra.items() if v})
    return e


def hhmm(h, m):
    return f"{int(h):02d}:{m}"


class YearTracker:
    """For lists in chronological order whose dates have no year: roll over at New Year."""
    def __init__(self, today):
        self.today, self.year, self.prev = today, None, None

    def date(self, day, month):
        if self.year is None:
            first = infer_year(day, month, self.today)
            if first is None:
                return None
            self.year = first.year
        elif (month, day) < self.prev:
            self.year += 1
        self.prev = (month, day)
        try:
            return dt.date(self.year, month, day)
        except ValueError:
            return None


# ------------------------------------------------------------ Kellertheater ---
def parse_keller(html, base="https://keller.theater/events/", today=None):
    today = today or dt.date.today()
    soup = BeautifulSoup(html, "html.parser")
    years, out = YearTracker(today), []
    for h in soup.find_all("h2"):
        a = h.find("a", href=True)
        if not a or "/events/" not in a["href"]:
            continue
        ss = strings(card_for(h, "h2"))
        title = flat(h.get_text(" "))
        di = next((i for i, s in enumerate(ss) if re.fullmatch(r"\d{1,2}\.\d{1,2}\.", s)), None)
        if di is None or title not in ss:
            continue
        day, mon = (int(x) for x in ss[di].strip(".").split("."))
        d = years.date(day, mon)
        if d is None:
            continue
        labels = " ".join(s.lower() for s in ss[:di])
        after = ss[ss.index(title) + 1:]
        ti = next((i for i, s in enumerate(after) if re.search(r"\d{1,2}:\d{2}\s*Uhr", s)), None)
        t = re.search(r"(\d{1,2}):(\d{2})", after[ti]) if ti is not None else None
        sub = " – ".join(after[:ti]) if ti else None
        if "comedy" in labels:
            typ, cat = "show", "comedy"
        elif "liedermacher" in labels:
            typ, cat = "show", "music"
        elif "tanz" in labels:
            typ, cat = "event", "dance"
        elif "theater" in labels:
            typ, cat = "show", "theater"
        else:
            typ, cat = "event", None
        out.append(mk(typ, title, d, hhmm(*t.groups()) if t else None, "kellertheater",
                      urljoin(base, a["href"]), category=cat, subtitle=sub,
                      status="Ausverkauft" if "sold out" in labels else None))
    return out


def scrape_keller():
    ev = parse_keller(fetch("https://keller.theater/events"))
    print(f"kellertheater: {len(ev)} dates")
    if not ev:
        raise RuntimeError("kellertheater: found 0 dates - layout probably changed")
    return ev


# ------------------------------------------------------------ Theater am Gleis ---
GLEIS_DATE = re.compile(r"^" + WD + r"\s+(\d{1,2})\.(\d{1,2})\.\s+(\d{1,2})[.:](\d{2})\s*Uhr")
PRICE = re.compile(r"^(CHF|Vorverkauf|Abendkasse|Pass|Eintritt)", re.I)


def parse_gleis(html, base="https://theater-am-gleis.ch/spielplan", today=None):
    today = today or dt.date.today()
    soup = BeautifulSoup(html, "html.parser")
    years, out = YearTracker(today), []
    for h in soup.find_all("h2"):
        a = h.find("a", href=True)
        if not a or "/spielplan/" not in a["href"]:
            continue
        ss = strings(card_for(h, "h2"))
        title = flat(h.get_text(" "))
        di = next((i for i, s in enumerate(ss) if GLEIS_DATE.match(s)), None)
        if di is None or title not in ss:
            continue
        m = GLEIS_DATE.match(ss[di])
        d = years.date(int(m.group(1)), int(m.group(2)))
        if d is None:
            continue
        labels = " ".join(s.lower() for s in ss[:di])
        ti = ss.index(title)
        between = ss[di + 1:ti]
        kicker = next((s for s in reversed(between) if not PRICE.match(s) and not GLEIS_DATE.match(s)), None)
        sold_out = any("ausverkauft" in s.lower() for s in between)
        desc = next((s for s in ss[ti + 1:] if len(s) > 30 and s not in ("Tickets kaufen", "Mehr")), None)
        cat = next((v for k, v in (("kinder", "kids"), ("tanz", "dance"), ("musik", "music"), ("theater", "theater"))
                    if k in labels), None)
        out.append(mk("show" if cat else "event", title, d, hhmm(m.group(3), m.group(4)), "theater-am-gleis",
                      urljoin(base, a["href"]), category=cat, subtitle=kicker,
                      description=desc[:220] if desc else None, status="Ausverkauft" if sold_out else None))
    return out


def scrape_gleis():
    ev = parse_gleis(fetch("https://theater-am-gleis.ch/spielplan"))
    print(f"theater-am-gleis: {len(ev)} dates")
    if not ev:
        raise RuntimeError("theater-am-gleis: found 0 dates - layout probably changed")
    return ev


# ------------------------------------------------------------ Casinotheater ---
CASINO_DATE = re.compile(r"^" + WD + r",\s*(\d{1,2})\.\s*([A-Za-zäÄ]+)\.?\s+(\d{1,2}):(\d{2})\s*Uhr$")
CASINO_STATUS = {"Ausverkauft", "Letzte Plätze", "Premiere", "Derniere", "Zusatzvorstellung", "Clubangebot",
                 "Preview", "CH-Premiere", "Abgesagt", "ausser Haus"}
CASINO_SKIP = {"Abgesagt", "ausser Haus"}   # cancelled, or not at the Casinotheater
CASINO_TAGS = [  # first match wins: (keywords, type, category)
    (("familie", "märchen", "kinder"), "show", "kids"),
    (("kulinarik", "dinner"), "event", None),
    (("lesung", "talk", "podcast"), "event", None),
    (("theater", "komödie", "musical", "artistik", "zauber", "magie", "clown", "drag", "hommage"), "show", "theater"),
    (("comedy", "kabarett", "satire", "stand-up", "impro", "slam", "spoken"), "show", "comedy"),
    (("musik", "konzert", "unplugged", "lieder", "cappella"), "show", "music"),
]


def casino_year_for(h, month, today):
    for prev in h.find_all_previous("h2"):
        m = re.fullmatch(r"([A-Za-zäÄ]+)\s+(\d{4})", flat(prev.get_text(" ")))
        if m and month_num(m.group(1)):
            hm, hy = month_num(m.group(1)), int(m.group(2))
            return hy + 1 if month < hm else hy
    return None


def parse_casino(html, base="https://www.casinotheater.ch/spielplan/", today=None):
    today = today or dt.date.today()
    soup = BeautifulSoup(html, "html.parser")
    out = []
    for h in soup.find_all("h1"):
        card = card_for(h, "h1")
        link = card.select_one('a[href*="/spielplan/produktion/"]')
        if link is None:
            continue
        url = urljoin(base, link["href"].split("?")[0])
        title = flat(h.get_text(" "))
        ss = strings(card)
        if title not in ss:
            continue
        rest = ss[ss.index(title) + 1:]
        subtitle = rest[0] if rest and not CASINO_DATE.match(rest[0]) else None
        slots, tags, desc = [], "", None
        for s in rest:
            m = CASINO_DATE.match(s)
            if m:
                slots.append([m, None])
            elif s in CASINO_STATUS and slots:
                slots[-1][1] = s
            elif "#" in s and desc is None:
                tags = " ".join(re.findall(r"#(\S+)", s)).lower()
                desc = re.sub(r"^(?:[A-ZÄÖÜ][A-ZÄÖÜ&/ -]+\s+)?(?:#\S+\s*)+", "", s).strip() or None
        typ, cat = "show", "comedy"
        for words, t, c in CASINO_TAGS:
            if any(w in tags for w in words):
                typ, cat = t, c
                break
        for m, status in slots:
            if status in CASINO_SKIP:
                continue
            day, mon = int(m.group(1)), month_num(m.group(2))
            year = casino_year_for(h, mon, today) if mon else None
            try:
                d = dt.date(year, mon, day) if year else infer_year(day, mon, today)
            except (ValueError, TypeError):
                d = None
            if d is None:
                continue
            out.append(mk(typ, title, d, hhmm(m.group(3), m.group(4)), "casinotheater", url, category=cat,
                          subtitle=subtitle, description=desc[:220] if desc else None, status=status))
    return out


def scrape_casino():
    ev = parse_casino(fetch("https://www.casinotheater.ch/spielplan/"))
    print(f"casinotheater: {len(ev)} dates")
    if not ev:
        raise RuntimeError("casinotheater: found 0 dates - layout probably changed")
    return ev


# ------------------------------------------------------- Theater Kanton Zürich ---
TKZ_DATE = re.compile(r"^[A-Za-zäöü]+,\s*(\d{1,2})\.\s*([A-Za-zä]+)\s+(\d{4}),\s*(\d{1,2})\.(\d{2})\s*(.*)$")


def parse_tkz(html, base="https://theaterkantonzuerich.ch/", today=None):
    """Only performances in Winterthur are kept. School performances of the youth theatre
    (JTZ logo, weekday before 17:00) are skipped because the public can't attend them."""
    soup = BeautifulSoup(html, "html.parser")
    out = []
    for a in soup.select('a[href*="#vorstellung-"]'):
        card = card_for(a, 'a[href*="#vorstellung-"]')
        h = card.find(["h2", "h3"])
        ss = strings(card)
        di = next((i for i, s in enumerate(ss) if TKZ_DATE.match(s)), None)
        if h is None or di is None:
            continue
        m = TKZ_DATE.match(ss[di])
        title = flat(h.get_text(" "))
        rest = ss[ss.index(title) + 1:] if title in ss else []
        location = rest[-1] if rest else ""
        if not location.startswith("Winterthur"):
            continue
        mon = month_num(m.group(2))
        try:
            d = dt.date(int(m.group(3)), mon, int(m.group(1)))
        except (ValueError, TypeError):
            continue
        note = m.group(6)
        jtz = card.find("img", alt=re.compile("Junges Theater"))
        if "Schulhaus" in note or (jtz and d.weekday() < 5 and int(m.group(4)) < 17):
            continue
        out.append(mk("show", title, d, hhmm(m.group(4), m.group(5)),
                      "theater-winterthur" if location == "Winterthur" else "tkz-winterthur",
                      urljoin(base, a["href"].split("#")[0]), category="kids" if jtz else "theater",
                      subtitle=rest[0] if len(rest) > 1 else None,
                      status="Premiere" if "Premiere" in note else None))
    return out


def scrape_tkz():
    ev = parse_tkz(fetch("https://theaterkantonzuerich.ch/"))
    print(f"theater-kanton-zuerich: {len(ev)} dates in Winterthur")
    if not ev:
        raise RuntimeError("theater-kanton-zuerich: found 0 Winterthur dates - layout probably changed")
    return ev


# ---------------------------------------------------- Figurentheater Winterthur ---
FIG_DATE = re.compile(r"^" + WD + r"\s+(\d{1,2})\.\s*([A-Za-zäÄ]+)\.?\s+(\d{1,2}):(\d{2})")
FIG_KINDS = ("NACHMITTAGS-VORSTELLUNG", "ABEND-VORSTELLUNG", "VORMITTAGS-VORSTELLUNG", "WORKSHOP")


SMALL = {"die", "der", "das", "des", "dem", "den", "und", "oder", "de", "la", "le", "am", "im", "in", "auf",
         "zu", "von", "vom", "mit", "ein", "eine", "noch", "nach", "bei", "an"}


def smart_title(t):
    words = t.lower().split()
    return " ".join(w if (i and w in SMALL) else w[:1].upper() + w[1:] for i, w in enumerate(words))


def parse_figurentheater(html, base="https://www.figurentheater-winterthur.ch/de/", today=None):
    """The home page shows each production once, with its *next* date ("Weitere Daten" = more
    dates on the detail page, which we don't follow)."""
    today = today or dt.date.today()
    soup = BeautifulSoup(html, "html.parser")
    out, seen = [], set()
    for a in soup.select('a[href*="/de/spielplan/"]'):
        ss = strings(a)
        di = next((i for i, s in enumerate(ss) if FIG_DATE.match(s)), None)
        if di is None:
            continue
        url = urljoin(base, a["href"])
        m = FIG_DATE.match(ss[di])
        mon = month_num(m.group(2))
        d = infer_year(int(m.group(1)), mon, today) if mon else None
        if d is None or (url, d) in seen:
            continue
        seen.add((url, d))
        age = ss[0] if di > 0 else None
        kind = next((s.upper() for s in ss[di:] if s.upper() in FIG_KINDS), None)
        text = " ".join(s for s in ss[di + 1:] if s not in ("Weitere Daten", "Letzte Vorstellung") and s.upper() != kind)
        slug = re.sub(r"-[0-9a-f]{4}$", "", urlparse(url).path.rstrip("/").split("/")[-1])
        kicker, title, desc = split_by_slug(text, slug)
        if title is None:
            title, desc = slug.replace("-", " ").capitalize(), text
        if title.isupper():
            title = smart_title(title)
        desc = re.sub(r"\s*FIGURENTHEATER WINTERTHUR$", "", desc or "").strip()
        workshop = kind == "WORKSHOP"
        out.append(mk("event" if workshop else "show", title, d, hhmm(m.group(3), m.group(4)), "figurentheater", url,
                      category=None if workshop else ("theater" if kind == "ABEND-VORSTELLUNG" else "kids"),
                      subtitle=(age or kicker or "").strip() or None,
                      description=desc[:220] if desc else None))
    return out


def scrape_figurentheater():
    ev = parse_figurentheater(fetch("https://www.figurentheater-winterthur.ch/de/"))
    print(f"figurentheater: {len(ev)} dates (next date per production)")
    if not ev:
        raise RuntimeError("figurentheater: found 0 dates - layout probably changed")
    return ev


# ================================================== aggregators & small venues ===
def venue_for(name):
    """-> (venue key, place text). Unknown places become the 'other' venue with the name kept."""
    n = (name or "").lower()
    for needle, key in VENUE_ALIASES:
        if needle in n:
            return key, None
    place = re.sub(r",?\s*\d{4}\s+Winterthur$|\s+Winterthur$", "", flat(name or "")).strip() or None
    return "other", place


def guess_category(text):
    t = text.lower()
    for words, cat in ((("film", "kino", "kurzfilm"), "film"), (("konzert", "concert", "musik", "band", "orchest"), "music"),
                       (("tanz", "ballett"), "dance"), (("theater", "bühne"), "theater"),
                       (("lesung", "vortrag", "führung", "gespräch", "talk"), "talk")):
        if any(w in t for w in words):
            return cat
    return None


def day_range(start, end):
    return (end - start).days


# ----------------------------------------- Stadt Winterthur + Alte Kaserne ---
# Both run on the same platform: a list of links "d. Monat yyyy · title · place · hh:mm–hh:mm Uhr".
NUXT_DATE = re.compile(r"^(\d{1,2})\.\s+([A-Za-zäÄ]+)\s+(\d{4})$")
NUXT_TIME = re.compile(r"^(\d{1,2}):(\d{2})(?:\s*[–-]\s*\d{1,2}:\d{2})?\s*Uhr")


def parse_nuxt_events(html, base):
    soup = BeautifulSoup(html, "html.parser")
    out, seen = [], set()
    for a in soup.select('a[href*="/veranstaltung/"]'):
        ss = [s for s in strings(a) if s != "Mehr erfahren"]
        di = next((i for i, s in enumerate(ss) if NUXT_DATE.match(s)), None)
        if di is None or len(ss) < di + 2:
            continue
        m = NUXT_DATE.match(ss[di])
        mon = month_num(m.group(2))
        try:
            d = dt.date(int(m.group(3)), mon, int(m.group(1)))
        except (ValueError, TypeError):
            continue
        ti = next((i for i, s in enumerate(ss) if i > di and NUXT_TIME.match(s)), None)
        t = NUXT_TIME.match(ss[ti]) if ti is not None else None
        title = ss[di + 1]
        loc = " ".join(ss[di + 2:ti if ti is not None else len(ss)]).strip() or None
        url = urljoin(base, a["href"])
        if (url, d) in seen:
            continue
        seen.add((url, d))
        venue, place = venue_for(loc) if loc else ("other", None)
        out.append(mk("event", title, d, hhmm(t.group(1), t.group(2)) if t else None, venue, url,
                      category=guess_category(title), place=(place or loc) if venue == "other" else None))
    return out


def scrape_stadt():
    out = []
    for page in range(1, 11):
        url = "https://stadt.winterthur.ch/veranstaltungen" + (f"?page={page}" if page > 1 else "")
        ev = parse_nuxt_events(fetch(url), "https://stadt.winterthur.ch/")
        if not ev:
            break
        out += ev
    print(f"stadt-winterthur: {len(out)} events")
    if not out:
        raise RuntimeError("stadt-winterthur: found 0 events - layout probably changed")
    return out


def scrape_alte_kaserne():
    ev = parse_nuxt_events(fetch("https://altekaserne.ch/agenda/veranstaltungen-im-haus"), "https://altekaserne.ch/")
    for e in ev:
        e.pop("place", None)          # everything on this page is in the house
        e["venue"] = "alte-kaserne"
    print(f"alte-kaserne: {len(ev)} events")
    if not ev:
        raise RuntimeError("alte-kaserne: found 0 events - layout probably changed")
    return ev


# ------------------------------------------------------------------ Coucou ---
# "Das Winterthurer Kulturmagazin" - the broadest calendar: concerts, theater, film, clubs, museums.
# One section per day (h1 "Sa 31. Okt"); inside, events, then an "Ausstellungen anzeigen" block that
# repeats every running exhibition on every day.
COUCOU_DAY = re.compile(r"^(?:Mo|Di|Mi|Do|Fr|Sa|So)\s+(\d{1,2})\.\s+([A-Za-zäÄ]+)$")
COUCOU_CATS = [  # first match wins: (Coucou category, (type, category))
    ("Kinder", ("show", "kids")), ("Konzert", ("show", "music")), ("Musik", ("show", "music")),
    ("Film", ("show", "film")), ("Tanz", ("show", "dance")), ("Theater", ("show", "theater")),
    ("Party", ("show", "party")), ("Vortrag", ("event", "talk")), ("Literatur", ("event", "talk")),
    ("Führung", ("event", "talk")),
]


def parse_coucou(html, base="https://www.coucoumagazin.ch/", today=None):
    today = today or dt.date.today()
    soup = BeautifulSoup(html, "html.parser")
    out, expos = [], {}
    day, in_expo = None, False
    for el in soup.find_all(["h1", "h2", "a"]):
        if el.name == "h1":
            m = COUCOU_DAY.match(flat(el.get_text(" ")))
            if m:
                mon = month_num(m.group(2))
                day = infer_year(int(m.group(1)), mon, today) if mon else None
                in_expo = False
            continue
        if el.name == "a":
            if flat(el.get_text(" ")).startswith("Ausstellungen anzeigen"):
                in_expo = True
            continue
        link = el.find("a", href=True)
        if day is None or link is None or "/kalender/" not in link["href"]:
            continue
        card = card_for(el, "h2")
        title = flat(el.get_text(" "))
        cats = [flat(h.get_text(" ")) for h in card.find_all("h4")]
        rest = strings(card)
        if title in rest:
            rest.remove(title)                 # only the heading itself - a venue can have the same name as its title
        rest = [s for s in rest if s not in cats]
        ti = next((i for i, s in enumerate(rest) if re.match(r"^\d{2}:\d{2}", s)), None)
        t = re.match(r"^(\d{2}):(\d{2})(?:\s*-\s*(\d{2}):(\d{2}))?", rest[ti]) if ti is not None else None
        place_s = rest[ti + 1] if ti is not None and ti + 1 < len(rest) else (rest[0] if ti is None and rest else None)
        venue, place = venue_for(place_s) if place_s else ("other", None)
        url = urljoin(base, link["href"])
        if in_expo and "Ausstellung" in cats:
            if venue.startswith("kmw-"):               # Kunst Museum Winterthur has its own, exact source
                continue
            if place_s and flat(place_s).lower().startswith(title.lower()[:12]):  # generic "museum" entry
                continue
            e = expos.setdefault(url, mk("exhibition", title, day, None, venue, url, place=place, ongoing=True))
            e["start"] = min(e["start"], day.isoformat())
            e["end"] = max(e["end"], day.isoformat())
            continue
        typ, cat = "event", None
        for key, val in COUCOU_CATS:
            if key in cats:
                typ, cat = val
                break
        all_day = t and t.group(1) == "00" and t.group(3) == "23"
        out.append(mk(typ, title, day, hhmm(t.group(1), t.group(2)) if t and not all_day else None,
                      venue, url, category=cat, place=place))
    return out + list(expos.values())


def scrape_coucou():
    ev = parse_coucou(fetch("https://www.coucoumagazin.ch/de/kalender.html"))
    print(f"coucou: {len(ev)} entries")
    if not ev:
        raise RuntimeError("coucou: found 0 entries - layout probably changed")
    return ev


# ------------------------------------------------------------------ lok.al ---
LOKAL_DATE = re.compile(r"^(\d{1,2})\.\s+([A-Za-zäÄ]+)\s+(\d{4})(?:\s*-\s*(\d{1,2})\.\s+([A-Za-zäÄ]+)\s+(\d{4}))?$")
LOKAL_SKIP_TAGS = {"geschlossene gesellschaft", "raum miete", "raum miete winterthur"}   # private hire = closed to the public


def parse_lokal(html, base="https://lok.al/", today=None):
    today = today or dt.date.today()
    soup = BeautifulSoup(html, "html.parser")
    out = []
    for h in soup.find_all("h3"):
        a = h.find("a", href=True)
        if not a or "/events/" not in a["href"] or "/events/tags/" in a["href"]:
            continue
        prev = next((flat(p.get_text(" ")) for p in h.find_all_previous("h2")), "")
        if "Vergangene" in prev:
            continue
        card = card_for(h, "h3")
        title = flat(h.get_text(" "))
        tags = [flat(t.get_text(" ")).lower() for t in card.select('a[href*="/events/tags/"]')]
        if title.lower() == "geschlossene gesellschaft" or LOKAL_SKIP_TAGS & set(tags):
            continue
        ss = strings(card)
        di = next((i for i, s in enumerate(ss) if LOKAL_DATE.match(s)), None)
        if di is None:
            continue
        m = LOKAL_DATE.match(ss[di])
        try:
            start = dt.date(int(m.group(3)), month_num(m.group(2)), int(m.group(1)))
            end = dt.date(int(m.group(6)), month_num(m.group(5)), int(m.group(4))) if m.group(4) else start
        except (ValueError, TypeError):
            continue
        if end < start or (end - start).days <= 1:    # "Sat–Sun" with a late finish is one evening
            end = start
        if end < today - dt.timedelta(days=1):
            continue
        t = next((re.match(r"(\d{1,2}):(\d{2})", s) for s in ss if re.match(r"^\d{1,2}:\d{2}\s*-", s)), None)
        desc = next((s for s in reversed(ss) if len(s) > 40 and s != title), None)
        text = " ".join(tags)
        cat = ("party" if re.search(r"party|disco|dj", text) else "music" if re.search(r"konzert|musik|jam|band", text)
               else "talk" if re.search(r"vernissage|lesung|slam|vortrag", text) else None)
        e = mk("show" if cat in ("party", "music") else "event", title, start, hhmm(*t.groups()) if t else None,
               "lokal", urljoin(base, a["href"]), category=cat, description=desc[:220] if desc else None)
        e["end"] = end.isoformat()
        out.append(e)
    return out


def scrape_lokal():
    ev = parse_lokal(fetch("https://lok.al/winterthur/"))
    print(f"lok.al: {len(ev)} events (private-hire dates left out)")
    return ev   # may legitimately be empty


# ------------------------------------------------------------- Dampfzentrum ---
def scrape_dampfzentrum(today=None):
    """The home page states: open every 2nd and 4th Saturday of the month, 13:00-16:00.
    Special events are on its agenda page, which is filled in by a server include we don't parse."""
    today = today or dt.date.today()
    out = []
    for i in range(0, 200):
        d = today + dt.timedelta(days=i)
        if d.weekday() == 5 and ((d.day - 1) // 7) in (1, 3):
            out.append(mk("event", "Open day (2nd & 4th Saturday of the month)", d, "13:00", "dampfzentrum",
                          "https://www.dampfzentrum.ch/veranstaltungen/agenda", category=None,
                          subtitle="13:00–16:00 · regular opening hours, special events on the agenda page"))
    print(f"dampfzentrum: {len(out)} open days (rule-based)")
    return out


# ------------------------- other pages: best effort via schema.org Event data ---
# Pages I haven't inspected. If a page embeds schema.org Event data (JSON-LD) we use it; otherwise it
# yields nothing and the log says so. Their events mostly also reach us through Coucou / Stadt Winterthur.
JSONLD_PAGES = [  # (venue key, url, require the word "Winterthur" in the location?)
    ("muenzkabinett", "https://muenzkabinett.winterthur.ch/", False),
    ("neuthal", "https://neuthal-industriekultur.ch/", False),
    ("museumschaffen", "https://www.museumschaffen.ch/", False),
    ("kyburg", "https://schlosskyburg.ch/", False),
    ("naturmuseum", "https://natur.winterthur.ch/", False),
    ("oxyd", "https://www.oxydart.ch/", False),
    ("technorama", "https://www.technorama.ch/en/home", False),
    ("moersburg", "https://www.moersburg-winterthur.ch/site/", False),
    ("hegi", "https://www.schlosshegi.com/", False),
    ("roemerholz", "https://www.roemerholz.ch/en", False),
    ("uhrenmuseum", "https://www.uhrenmuseumwinterthur.ch/", False),
    ("fotostiftung", "https://fotostiftung.ch/en/", False),
    ("gewerbemuseum", "https://gewerbemuseum.ch/de/", False),
    ("galerie-weiertal", "https://www.galerieweiertal.ch/", False),
    ("kunsthalle", "https://kunsthallewinterthur.ch/", False),
    ("fotomuseum", "https://www.fotomuseum.ch/de/", False),
    ("other", "https://www.ngw.ch/aktivitaeten/vortraege", False),
    ("other", "https://waslauft.in/winterthur", True),
    ("other", "https://www.kulturzueri.ch/", True),
    ("other", "https://en.winterthur.com/house-of-winterthur/veranstaltungen/alle-unsere-anlaesse.html", False),
]


def jsonld_events(html, base, default_venue, require_winterthur=False, today=None):
    today = today or dt.date.today()
    soup = BeautifulSoup(html, "html.parser")
    found = []

    def walk(node):
        if isinstance(node, list):
            for n in node:
                walk(n)
        elif isinstance(node, dict):
            t = node.get("@type")
            if any(isinstance(x, str) and x.endswith("Event") and x != "EventSeries" for x in (t if isinstance(t, list) else [t])):
                found.append(node)
            for v in node.values():
                if isinstance(v, (list, dict)):
                    walk(v)

    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            walk(json.loads(tag.string or ""))
        except (ValueError, TypeError):
            continue
    out = []
    for n in found:
        sd = str(n.get("startDate") or "")
        if not re.match(r"\d{4}-\d{2}-\d{2}", sd):
            continue
        loc = n.get("location")
        addr = loc.get("address") if isinstance(loc, dict) else None
        loc_name = loc.get("name") if isinstance(loc, dict) else loc
        blob = f"{loc_name} {addr}"
        if require_winterthur and "winterthur" not in blob.lower():
            continue
        d = dt.date.fromisoformat(sd[:10])
        if d < today:
            continue
        venue, place = (venue_for(loc_name) if isinstance(loc_name, str) and loc_name else (default_venue, None))
        if default_venue != "other":
            venue, place = default_venue, None
        t = re.match(r"\d{4}-\d{2}-\d{2}[T ](\d{2}):(\d{2})", sd)
        url = urljoin(base, n["url"]) if isinstance(n.get("url"), str) else base
        if urlparse(url).scheme not in ("http", "https"):
            url = base
        out.append(mk("event", flat(str(n.get("name") or "")), d, hhmm(*t.groups()) if t and sd[11:16] != "00:00" else None,
                      venue, url, place=place))
    return [e for e in out if e["title"]]


def scrape_jsonld_pages():
    out, empty = [], []
    for venue, url, req in JSONLD_PAGES:
        try:
            ev = jsonld_events(fetch(url), url, venue, req)
        except Exception as e:      # a dead museum site shouldn't fail the whole run
            print(f"  warning: {url}: {e}", file=sys.stderr)
            continue
        if not ev:
            empty.append(urlparse(url).netloc)
        out += ev
    print(f"structured-data pages: {len(out)} events; no schema.org events on {len(empty)} of {len(JSONLD_PAGES)} pages")
    return out


# ============================================================ putting it together ===
# Order matters for dedupe: an earlier source wins over a later one. Own sites first, aggregators last.
SOURCES = [scrape_kmw, scrape_theater_winterthur, scrape_keller, scrape_gleis, scrape_casino,
           scrape_tkz, scrape_figurentheater, scrape_dampfzentrum, scrape_lokal, scrape_alte_kaserne,
           scrape_stadt, scrape_coucou, scrape_jsonld_pages]
# Zimmer-Theater Ariane has no source of its own yet (its Spielplan page isn't parsed), so its
# performances come from Coucou and the applaus! list.


def norm_title(t):
    return re.sub(r"[^a-z0-9]", "", _norm_with_map(t)[0])


def vkey(e):
    return e["venue"] if e["venue"] != "other" else "other:" + norm_title(e.get("place") or "")


def dedupe(events_by_source):
    """The same date and venue from two sources is one event if the titles match, or the times match,
    or either time is unknown. Earlier sources win. Exhibitions are never merged here."""
    kept = {}  # (start, venue) -> [(source, time, normalized title)]
    out = []
    for name, evs in events_by_source:
        for e in evs:
            t, nt = e.get("time") or "", norm_title(e["title"])
            others = [(n, tt, ntt) for n, tt, ntt in kept.get((e["start"], vkey(e)), []) if n != name]
            if e["type"] != "exhibition" and any(ntt == nt or not tt or not t or tt == t for _, tt, ntt in others):
                continue
            kept.setdefault((e["start"], vkey(e)), []).append((name, t, nt))
            out.append(e)
    return out


def mark_discounts(events, applaus):
    """applaus! lists the performances that get 50% off for members. Flag the matching events
    (same venue and date; same time, or one of them has none). Performances on the list that no
    own-site event matches are returned so they still show up - flagged too."""
    unmatched = []
    for a in applaus:
        hit = False
        for e in events:
            if e["type"] == "exhibition" or e["venue"] != a["venue"] or e["start"] != a["start"]:
                continue
            if not e.get("time") or not a.get("time") or e["time"] == a["time"]:
                e["applaus"] = True
                hit = True
        if not hit:
            unmatched.append(dict(a, applaus=True))
    return unmatched


def main():
    by_source, failures = [], 0
    for source in SOURCES:
        try:
            by_source.append((source.__name__, source()))
        except Exception as e:  # one broken source shouldn't wipe the others
            failures += 1
            print(f"ERROR in {source.__name__}: {e}", file=sys.stderr)
    events = dedupe(by_source)
    try:
        applaus = scrape_applaus()
    except Exception as e:
        failures += 1
        applaus = []
        print(f"ERROR in scrape_applaus: {e}", file=sys.stderr)
    extra = mark_discounts(events, applaus)
    print(f"applaus: {sum(1 for e in events if e.get('applaus'))} matched own listings, "
          f"{len(extra)} added from the applaus list itself")
    events = events + extra
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
