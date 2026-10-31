# What's on

A static "what's on around me" calendar. A GitHub Action scrapes venue
websites every morning, writes `site/events.json`, and deploys `site/` to
GitHub Pages. Free hosting, no server.

```
scrape.py                     one function per venue -> site/events.json
site/index.html               the calendar page (reads events.json)
site/events.json              generated data (seeded with Kunst Museum Winterthur)
tests/                        parser tests run against saved HTML snippets
.github/workflows/update.yml  daily schedule + deploy
```

## Setup (about 10 minutes)

1. Create a new GitHub repo (public is simplest for free Pages) and push this folder:
   ```
   git init && git add . && git commit -m "Initial commit"
   git branch -M main
   git remote add origin https://github.com/YOU/whats-on.git
   git push -u origin main
   ```
2. In the repo: **Settings → Pages → Build and deployment → Source: GitHub Actions**.
3. **Settings → Actions → General → Workflow permissions → Read and write permissions** (needed to commit `events.json`).
4. Open the **Actions** tab, pick *Update events and deploy*, click **Run workflow**.
5. When it finishes, your site is at `https://YOU.github.io/whats-on/`.

From then on it runs daily at 05:00 UTC. Edit the cron line in the workflow to change that.

## Sources

Each theater's own program page is the primary source. Aggregators fill in everything else, and
applaus! is used as a **filter** that flags which performances get 50% off for members.
Earlier sources win when two list the same event (same venue and date, and the same title or time).

| Source | Covers | Status |
|---|---|---|
| kmw.ch | Kunst Museum Winterthur exhibitions + agenda | own parser |
| theaterwinterthur.ch (home) | Theater Winterthur, next few productions only (the full Spielplan is JavaScript) | own parser |
| keller.theater/events | Kellertheater (weekly Milonga skipped: no fixed dates) | own parser |
| theater-am-gleis.ch/spielplan | Theater am Gleis | own parser |
| casinotheater.ch/spielplan | Casinotheater (cancelled and "ausser Haus" dates skipped) | own parser |
| theaterkantonzuerich.ch (home) | Winterthur performances only; school shows skipped | own parser |
| figurentheater-winterthur.ch | next date per production (more dates are on detail pages) | own parser |
| **coucoumagazin.ch/de/kalender.html** | the broadest calendar: theater, concerts, film, clubs, talks, museums and exhibitions. Covers **Technorama, Fotomuseum, Gewerbemuseum, Römerholz, Naturmuseum, Museum Schaffen, Uhrenmuseum, Oxyd, Galerie Weiertal, Mörsburg, Schloss Kyburg, Münzkabinett, Zimmer-Theater Ariane** and many more | own parser; only the days the page shows without JavaScript (about a week) |
| stadt.winterthur.ch/veranstaltungen | the city's event calendar, all pages | own parser |
| altekaserne.ch (Veranstaltungen im Haus) | Alte Kaserne | own parser (same format as the city site) |
| lok.al/winterthur | Lok.al; **private-hire dates ("Geschlossene Gesellschaft") are left out** | own parser |
| dampfzentrum.ch | open every 2nd and 4th Saturday, 13:00–16:00 (stated on its home page) | rule, no scraping; special events live in a server include that isn't parsed |
| applaus-winterthur.ch | the 50% list | own parser |
| 20 more pages (Münzkabinett, Neuthal, Museum Schaffen, Kyburg, Naturmuseum, Oxyd, Technorama, Mörsburg, Hegi, Römerholz, Uhrenmuseum, Fotostiftung, Gewerbemuseum, Galerie Weiertal, Kunsthalle, Fotomuseum, NGW, waslauft.in, kulturzüri, House of Winterthur) | whatever they publish as schema.org Event data | **best effort, not inspected.** Pages without such data yield nothing; the log prints how many came up empty. waslauft.in and kulturzüri cover all of Zurich, so only events whose location says Winterthur are kept. House of Winterthur's calendar is filled in by JavaScript and will most likely stay empty |

**Exhibitions from Coucou** don't carry real date ranges. They appear as "On view · listed through <last
day Coucou showed>" and are refreshed on every run. Kunst Museum Winterthur keeps its exact ranges from kmw.ch.

**How the 50% flag works** (`mark_discounts`): a performance on the applaus! list is
matched to an event from a theater's own page by venue + date + time (or when
either time is missing). Matches get `"applaus": true` and a "50% off" badge.
Anything on the applaus! list that no own-page event matches is **added** as an
event (also flagged), so 50% shows never disappear, for example for Ariane or
when a theater's page breaks.

**Know the limits:** applaus! only lists discounted performances, and excludes premieres
at several theaters; at Theater Winterthur and the Casinotheater only selected
shows are 50%. A missing flag therefore means "not on the list", not "definitely
full price".

How `parse_applaus` and `parse_figurentheater` work: each entry is a link whose
text runs date, kicker, title and description together. The URL slug *is* the
title, so the parser finds the slug inside the text and splits around it.

The other parsers read one "card" at a time: find the title element, climb to the
largest ancestor that still contains only that one title, then read its text
strings in order. If a site changes its markup, the card finder usually still
works but the string positions don't, and the run reports "found 0 dates".

## Before you start

- Edit `USER_AGENT` in `scrape.py` and put your own email in it.
- The scraper checks `robots.txt` and fetches roughly 50 pages per run (the city calendar is paginated). Also read each venue's terms before adding it.

## Run locally

```
pip install -r requirements.txt
python -m unittest discover tests     # parser tests
python scrape.py                      # writes site/events.json
cd site && python -m http.server      # open http://localhost:8000
```

## If the scraper breaks

Venue sites change their HTML. When that happens the run fails (GitHub emails
you), the site keeps showing the last good data, and the log says which
venue broke. Fix: save the new page HTML into `tests/fixtures/`, adjust the
parser until the tests pass, push.

## Adding a venue or source

1. Add the venue to `VENUES` in `scrape.py` (if it's new).
2. Write `scrape_<name>()` returning a list of dicts with `type`
   (`exhibition`, `show` or `event`), `title`, `start`, `end` (YYYY-MM-DD),
   `venue` (key from `VENUES`), `url`, and optionally `time` (HH:MM),
   `category` (`theater`, `dance`, `music`, `comedy`, `kids`), `subtitle`, `description`, `status` (e.g. "Ausverkauft").
3. Add it to `SOURCES`. The page picks up new venues, colours and filter chips automatically.
4. Save a snippet of the real page into `tests/fixtures/` and add a test for it.
