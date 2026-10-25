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

## Before you start

- Edit `USER_AGENT` in `scrape.py` and put your own email in it.
- The scraper checks `robots.txt` and fetches only 2 pages per run. Also read each venue's terms before adding it.

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

## Adding a venue

1. Add it to `VENUES` in `scrape.py`.
2. Write `scrape_<venue>()` returning a list of dicts with
   `type` (exhibition / event / workshop), `title`, `start`, `end` (YYYY-MM-DD),
   `venue` (key from `VENUES`), `url`, and optionally `time`.
3. Add it to `SOURCES`. The page picks up new venues and colours automatically.

For sites with messy markup, a good pattern is: fetch the page, strip it to
text, and ask an LLM API for JSON in the format above (keep a parser test
for it too).
