# zekehausfather.com

A personal site for Zeke Hausfather — climate scientist (Berkeley Earth · Stripe / Frontier ·
Carbon Brief). Static HTML/CSS/JS with auto-refreshing feeds and a live ERA5 temperature
visualization. No build step, no framework.

```
Personal Website/
├── site/                     ← the deployable static site (this is what GitHub Pages serves)
│   ├── index.html
│   ├── css/style.css
│   ├── js/viz.js             ← fills the hero "live climate data" card from ERA5
│   ├── js/main.js            ← feeds, nav, reveal + scroll-viz backdrop, pub list
│   ├── data/                 ← JSON the page reads (auto-refreshed)
│   │   ├── era5_daily.json    · daily temperature series + headline stats
│   │   ├── climate_brink.json · latest Climate Brink posts (Zeke only)
│   │   ├── carbon_brief.json  · latest Carbon Brief articles
│   │   └── media.json         · recent media coverage
│   ├── images/               ← portrait + bg/ (spiral, heatmap, ridgeline, rings)
│   └── CNAME                 ← custom domain (zekehausfather.com)
├── scripts/
│   ├── process_era5.py       ← builds era5_daily.json from the Climate Dashboard CSV
│   ├── update_feeds.py       ← refreshes the blog + media JSON (stdlib only)
│   └── update_all.sh         ← runs both; handy for a local cron
└── .github/workflows/deploy.yml  ← scheduled refresh + Pages deploy
```

## Run it locally

The page fetches JSON, so open it through a web server (not `file://`):

```bash
cd site
python3 -m http.server 8000
# → http://localhost:8000
```

## The data feeds

| Feed | Source | Updated by |
|------|--------|-----------|
| Temperature chart | ERA5 daily series (Copernicus / C3S) | `scripts/process_era5.py` |
| The Climate Brink | `theclimatebrink.com/feed` (filtered to Zeke) | `scripts/update_feeds.py` |
| Carbon Brief | `carbonbrief.org/author/zekehausfather/feed/` | `scripts/update_feeds.py` |
| Media coverage | Google News RSS search for "Zeke Hausfather" | `scripts/update_feeds.py` |

`update_feeds.py` uses **only the Python standard library** — no `pip install` needed.

**Media coverage** merges two things: any hand-curated entries that have a `note`
(quote/context) are *preserved* across refreshes, and fresh Google News hits from real
outlets are merged in (Zeke's own Climate Brink / Carbon Brief posts are filtered out).
To pin a high-quality item, add it to `site/data/media.json` with a `note` field.

### ERA5 chart data

`process_era5.py` reads the Climate Dashboard daily CSV (default path is hard-coded; override
with the `ERA5_CSV` env var) and writes `site/data/era5_daily.json` — per-year daily anomalies
vs. the 1850–1900 baseline plus headline stats. Re-run it whenever the underlying ERA5 series
updates:

```bash
python3 scripts/process_era5.py
```

## Deploy on GitHub Pages

1. Create a repo and push this folder.
2. **Settings → Pages → Build and deployment → Source: GitHub Actions.**
3. **Settings → Pages → Custom domain:** `zekehausfather.com` (the `site/CNAME` is already set).
   Point DNS at GitHub (A records to GitHub's IPs, or a CNAME to `<user>.github.io`).
4. The workflow `.github/workflows/deploy.yml` then:
   - refreshes the blog + media feeds daily (11:00 UTC) and on every push,
   - commits any changed JSON back to the repo,
   - publishes `site/` to Pages.

You can trigger it any time from the **Actions** tab → *Update feeds & deploy* → *Run workflow*.

### Auto-updating the temperature chart in CI (optional)

The ERA5 source CSV lives on Zeke's machine, so by default the committed `era5_daily.json`
is what ships. To refresh it automatically in CI, host the daily CSV somewhere public and set
a repository **variable** `ERA5_CSV_URL` (Settings → Secrets and variables → Actions →
Variables). The workflow will download and reprocess it on each run.

Otherwise, refresh it locally and let the daily local cron push it:

```bash
crontab -e
# daily at 7am:
0 7 * * *  /full/path/to/Personal\ Website/scripts/update_all.sh >> /tmp/zh-site.log 2>&1
```

## Notes

- **Climate data:** rather than a heavy in-page chart, the hero links to the live
  [Climate Dashboard](https://dashboard.theclimatebrink.com/#global) and shows a few headline
  numbers from `era5_daily.json`. The GMST visualizations (spiral, heatmap, ridgeline, tree
  rings) drift subtly through the background as you scroll — swap the files in `site/images/bg/`
  to change them.
- **Social:** X, Bluesky, and LinkedIn appear in the nav, the writing sidebar, and the footer.
  The sidebar also embeds X's official timeline widget (it simply shows the link text if X
  blocks the widget). No free, reliable way exists to mirror posts into JSON without API access.
- **Design:** deep-navy data-viz aesthetic carried from The Climate Brink visualizations.
  Fraunces (display serif) · Hanken Grotesk (body) · IBM Plex Mono (data labels).
- **Media links** sourced from Google News are redirect URLs — fine for clicking, worth a
  periodic sanity check.
```
