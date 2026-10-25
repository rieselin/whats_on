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

| Source | Covers | How |
|---|---|---|
| kmw.ch | Kunst Museum Winterthur exhibitions and events | `scrape_kmw` |
| theaterwinterthur.ch (home page) | Theater Winterthur: the next few productions, with categories | `parse_tw_home` |
| applaus-winterthur.ch | ~90 upcoming performances at Zimmer-Theater Ariane, Kellertheater, Theater am Gleis, Casinotheater, Theater Kanton Zürich (Winterthur only), Theater Winterthur, Figurentheater | `parse_applaus` |

**Known gaps in the applaus! list.** It only lists performances that get the 50%
member discount. Per the page itself that excludes premieres at several theaters,
and at Theater Winterthur and the Casinotheater only selected shows get 50%
(the rest get 10% and aren't listed). So the calendar is good but not complete
for those two. Theater Winterthur's own home page fills part of the gap; for
the rest, add a parser for the venue's own program page.

If the same show appears in two sources (same venue and date, same time or one
time missing), the earlier source in `SOURCES` wins.

How `parse_applaus` works: each entry is a link whose text runs together date,
venue, a kicker line, the title and a description. The title can't be separated
by looking at the text alone, but the link's URL slug *is* the title, so the
parser finds the slug inside the text and splits around it. If it ever can't
find it, the title falls back to the slug itself.

## Before you start

- Edit `USER_AGENT` in `scrape.py` and put your own email in it.
- The scraper checks `robots.txt` and fetches only 4 pages per run. Also read each venue's terms before adding it.

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
   `category` (`theater`, `dance`, `music`, `comedy`, `kids`), `subtitle`, `description`.
3. Add it to `SOURCES`. The page picks up new venues, colours and filter chips automatically.
4. Save a snippet of the real page into `tests/fixtures/` and add a test for it.
