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
VENUE_BY_NAME = {v["match"]: k for k, v in VENUES.items()}
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


# Add more venues here: SOURCES = [scrape_kmw, scrape_kunsthaus, ...]
SOURCES = [scrape_kmw]


def main():
    events, failures = [], 0
    for source in SOURCES:
        try:
            events += source()
        except Exception as e:  # one broken venue shouldn't wipe the others
            failures += 1
            print(f"ERROR in {source.__name__}: {e}", file=sys.stderr)
    if failures and not events:
        sys.exit("All sources failed; keeping the previous events.json")
    events.sort(key=lambda e: (e["start"], e["title"]))
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
