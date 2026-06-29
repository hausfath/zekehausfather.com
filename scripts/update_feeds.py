#!/usr/bin/env python3
"""Refresh the website's dynamic feeds:

  * The Climate Brink   (Substack RSS, filtered to posts by Zeke Hausfather)
  * Carbon Brief        (author RSS)
  * Media coverage      (Google News RSS search)

Writes site/data/{climate_brink,carbon_brief,media}.json. Standard library only —
no pip install required, so it runs cleanly on GitHub Actions.

ERA5 data is refreshed separately by process_era5.py (it needs the source CSV).
Run:  python3 scripts/update_feeds.py
"""

import html
import json
import os
import re
import sys
import urllib.request
import urllib.parse
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from xml.etree import ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "site", "data")

NS = {
    "dc": "http://purl.org/dc/elements/1.1/",
    "content": "http://purl.org/rss/1.0/modules/content/",
    "atom": "http://www.w3.org/2005/Atom",
}

UA = "Mozilla/5.0 (compatible; zekehausfather.com feed updater)"
ZEKE = "zeke hausfather"


def fetch(url, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def clean(text, limit=280):
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", " ", text)          # strip tags
    text = html.unescape(text)
    # strip WordPress/Substack RSS boilerplate
    text = re.sub(r"\s*The post .+? appeared first on .+?\.?\s*$", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > limit:
        cut = text[:limit].rsplit(" ", 1)[0]
        text = cut + "…"
    return text


def iso_date(rfc822):
    try:
        dt = parsedate_to_datetime(rfc822)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).strftime("%Y-%m-%d")
    except Exception:
        return ""


def parse_rss_items(xml_bytes):
    """Yield dicts for each <item> in an RSS 2.0 feed."""
    root = ET.fromstring(xml_bytes)
    for item in root.iter("item"):
        def t(tag, ns=None):
            el = item.find(ns + tag if ns is None else tag, NS) if ns else item.find(tag)
            return el.text if el is not None and el.text else ""
        creator = ""
        c = item.find("dc:creator", NS)
        if c is not None and c.text:
            creator = c.text
        source_el = item.find("source")
        source = source_el.text if source_el is not None and source_el.text else ""
        desc = t("description")
        if not desc:
            ce = item.find("content:encoded", NS)
            desc = ce.text if ce is not None and ce.text else ""
        yield {
            "title": clean(t("title"), 240),
            "url": (t("link") or "").strip(),
            "date": iso_date(t("pubDate")),
            "description": clean(desc),
            "creator": creator.strip(),
            "source": source.strip(),
        }


def write_json(name, payload):
    path = os.path.join(DATA, name)
    with open(path, "w") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    n = len(payload.get("posts", payload.get("items", payload.get("repos", []))))
    print(f"  wrote {name} ({n} items)")


def today():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


# ---------------------------------------------------------------- Climate Brink
def update_climate_brink():
    print("Climate Brink…")
    try:
        items = list(parse_rss_items(fetch("https://www.theclimatebrink.com/feed")))
    except Exception as e:
        print(f"  ! skipped ({e})")
        return
    posts = [
        {"title": i["title"], "url": i["url"], "date": i["date"],
         "description": i["description"], "author": i["creator"] or "Zeke Hausfather"}
        for i in items
        if ZEKE in i["creator"].lower()
    ]
    if not posts:   # if no creator info, keep all (better than empty)
        posts = [{"title": i["title"], "url": i["url"], "date": i["date"],
                  "description": i["description"], "author": i["creator"]} for i in items]
    posts = posts[:8]
    if posts:
        write_json("climate_brink.json", {
            "source": "The Climate Brink",
            "author_url": "https://www.theclimatebrink.com/",
            "updated": today(), "posts": posts,
        })


# ---------------------------------------------------------------- Carbon Brief
def update_carbon_brief():
    print("Carbon Brief…")
    for url in ("https://www.carbonbrief.org/author/zekehausfather/feed/",
                "https://www.carbonbrief.org/feed/"):
        try:
            items = list(parse_rss_items(fetch(url)))
        except Exception as e:
            print(f"  ! {url} failed ({e})")
            continue
        if "author/zekehausfather" in url:
            chosen = items
        else:
            chosen = [i for i in items if ZEKE in i["creator"].lower()]
        posts = [{"title": i["title"], "url": i["url"], "date": i["date"],
                  "description": i["description"], "category": ""} for i in chosen][:8]
        if posts:
            write_json("carbon_brief.json", {
                "source": "Carbon Brief",
                "author_url": "https://www.carbonbrief.org/author/zekehausfather/",
                "updated": today(), "posts": posts,
            })
            return
    print("  ! no Carbon Brief items found; keeping existing file")


# Self-published / non-coverage sources to exclude from "media coverage".
SELF_SOURCES = ("theclimatebrink", "carbon brief", "carbonbrief")

# Allowlist of major outlets. Auto-discovered coverage (GDELT / Google News) is
# kept ONLY if it maps to one of these, which screens out minor aggregators and
# reposters (inkl, MSN, Yahoo, syndication mirrors, etc.). Hand-curated items
# (those with a `note`) bypass this entirely. Keyed by domain substring -> the
# display name shown on the site.
MAJOR_OUTLETS = {
    "nytimes.com": "The New York Times",
    "washingtonpost.com": "The Washington Post",
    "bbc.co.uk": "BBC News", "bbc.com": "BBC News",
    "theguardian.com": "The Guardian",
    "reuters.com": "Reuters",
    "apnews.com": "Associated Press",
    "bloomberg.com": "Bloomberg",
    "axios.com": "Axios",
    "theatlantic.com": "The Atlantic",
    "wsj.com": "The Wall Street Journal",
    "economist.com": "The Economist",
    "ft.com": "Financial Times",
    "npr.org": "NPR",
    "cnn.com": "CNN",
    "nbcnews.com": "NBC News",
    "abcnews.go.com": "ABC News",
    "cbsnews.com": "CBS News",
    "cbc.ca": "CBC News",
    "time.com": "TIME",
    "usatoday.com": "USA Today",
    "latimes.com": "Los Angeles Times",
    "politico.com": "Politico",
    "vox.com": "Vox",
    "wired.com": "WIRED",
    "scientificamerican.com": "Scientific American",
    "nature.com": "Nature",
    "science.org": "Science",
    "newscientist.com": "New Scientist",
    "nationalgeographic.com": "National Geographic",
    "propublica.org": "ProPublica",
    "technologyreview.com": "MIT Technology Review",
    "grist.org": "Grist",
    "insideclimatenews.org": "Inside Climate News",
    "yaleclimateconnections.org": "Yale Climate Connections",
    "e360.yale.edu": "Yale Environment 360",
    "csmonitor.com": "The Christian Science Monitor",
    "forbes.com": "Forbes",
    "theconversation.com": "The Conversation",
    "dw.com": "Deutsche Welle",
    "aljazeera.com": "Al Jazeera",
    "independent.co.uk": "The Independent",
    "telegraph.co.uk": "The Telegraph",
    "pbs.org": "PBS NewsHour",
    "newsweek.com": "Newsweek",
    "theverge.com": "The Verge",
    "huffpost.com": "HuffPost",
    "motherjones.com": "Mother Jones",
    "nzz.ch": "Neue Zürcher Zeitung",
    "spiegel.de": "Der Spiegel",
    "lemonde.fr": "Le Monde",
}

# Lowercased display names + a few aliases, for matching Google News source
# names exactly (Google News gives a source NAME, not a domain). Exact match
# only, so short names like "Science"/"Nature" never false-match a lookalike.
MAJOR_NAMES = {name.lower(): name for name in MAJOR_OUTLETS.values()}
MAJOR_ALIASES = {
    "bbc": "BBC News", "the associated press": "Associated Press",
    "ap": "Associated Press", "nature.com": "Nature",
    "abc news (us)": "ABC News", "pbs": "PBS NewsHour",
    "the wall street journal": "The Wall Street Journal",
    "cbc": "CBC News", "cbc.ca": "CBC News",
}


def outlet_from_domain(domain):
    dl = (domain or "").lower()
    for dom, name in MAJOR_OUTLETS.items():
        if dom in dl:
            return name
    return None


def outlet_from_name(src):
    sl = (src or "").strip().lower()
    return MAJOR_NAMES.get(sl) or MAJOR_ALIASES.get(sl)


def load_existing(name):
    try:
        with open(os.path.join(DATA, name)) as f:
            return json.load(f)
    except Exception:
        return {}


def norm_title(t):
    return re.sub(r"[^a-z0-9]+", " ", (t or "").lower()).strip()


def norm_url(u):
    u = re.sub(r"^https?://(www\.)?", "", (u or "").lower())
    return u.split("?")[0].split("#")[0].rstrip("/")


def fetch_gdelt():
    """Global news search via GDELT's free Doc API. Returns clean article URLs
    and real domains (unlike Google News' redirect links)."""
    q = '"Zeke Hausfather"'
    url = ("https://api.gdeltproject.org/api/v2/doc/doc?query=" +
           urllib.parse.quote(q) +
           "&mode=ArtList&maxrecords=100&sort=datedesc&timespan=18m&format=json")
    data = json.loads(fetch(url))   # raises if GDELT returns a rate-limit notice
    out = []
    for a in data.get("articles", []):
        sd = a.get("seendate", "")
        date = f"{sd[0:4]}-{sd[4:6]}-{sd[6:8]}" if len(sd) >= 8 else ""
        out.append({"title": clean(html.unescape(a.get("title", "")), 200),
                    "domain": a.get("domain", ""),
                    "url": a.get("url", ""), "date": date})
    return out


def update_media():
    print("Media coverage…")
    # Hand-curated entries (those carrying a quote/context note) are preserved.
    existing = load_existing("media.json")
    curated = [i for i in existing.get("items", []) if i.get("note")]
    seen = {norm_title(i["title"]) for i in curated}
    seen_urls = {norm_url(i["url"]) for i in curated if i.get("url")}
    auto = []
    ok = False

    def add(title, outlet, url, date):
        key, nu = norm_title(title), norm_url(url)
        if not key or key in seen or (nu and nu in seen_urls):
            return
        seen.add(key)
        if nu:
            seen_urls.add(nu)
        auto.append({"title": title, "outlet": outlet, "url": url,
                     "date": date, "note": ""})

    # Source 1: GDELT — broad global index, screened to major outlets by domain.
    try:
        for a in fetch_gdelt():
            name = outlet_from_domain(a["domain"])
            if name and not any(s in a["domain"].lower() for s in SELF_SOURCES):
                add(a["title"], name, a["url"], a["date"])
        ok = True
        print(f"    GDELT: {len(auto)} major-outlet hits")
    except Exception as e:
        print(f"  ! GDELT skipped ({e})")

    # Source 2: Google News RSS — screened to major outlets by source name.
    try:
        q = '"Zeke Hausfather"'
        url = ("https://news.google.com/rss/search?q=" + urllib.parse.quote(q) +
               "&hl=en-US&gl=US&ceid=US:en")
        before = len(auto)
        for i in parse_rss_items(fetch(url)):
            title, outlet = i["title"], i["source"]
            if not outlet and " - " in title:
                title, outlet = title.rsplit(" - ", 1)
            elif outlet and title.endswith(" - " + outlet):
                title = title[: -(len(outlet) + 3)]
            if any(s in (outlet + " " + i["url"]).lower() for s in SELF_SOURCES):
                continue
            name = outlet_from_name(outlet)
            if name:
                add(clean(title, 200), name, i["url"], i["date"])
        ok = True
        print(f"    Google News: +{len(auto) - before} major-outlet hits")
    except Exception as e:
        print(f"  ! Google News skipped ({e})")

    if not ok:
        print("  ! all sources failed; keeping existing file")
        return

    # Keep only the past 12 months so the section stays current, not lengthy.
    cutoff = (datetime.now(timezone.utc) - timedelta(days=365)).strftime("%Y-%m-%d")
    out = [m for m in (curated + auto) if not m.get("date") or m["date"] >= cutoff]
    out.sort(key=lambda m: m.get("date", ""), reverse=True)
    out = out[:24]
    write_json("media.json", {
        "source": "Media coverage", "updated": today(),
        "note": "Curated highlights plus major-outlet coverage from GDELT and Google News (past 12 months).",
        "items": out,
    })


# ---------------------------------------------------------------- GitHub repos
# Repos to hide from the "recently updated" card (e.g. this website's own repo,
# which would otherwise sit at the top every time the site is rebuilt).
EXCLUDE_REPOS = {"zekehausfather.com"}


def update_github():
    print("GitHub repos…")
    url = "https://api.github.com/users/hausfath/repos?sort=updated&per_page=30"
    try:
        items = json.loads(fetch(url))
    except Exception as e:
        print(f"  ! skipped ({e}); keeping existing file")
        return
    if not isinstance(items, list):
        print("  ! unexpected response; keeping existing file")
        return
    repos = []
    for r in items:
        if r.get("fork") or r.get("archived") or r.get("private"):
            continue
        if r.get("name") in EXCLUDE_REPOS:
            continue
        repos.append({
            "name": r.get("name", ""),
            "url": r.get("html_url", ""),
            "description": (r.get("description") or "").strip(),
            "language": r.get("language") or "",
            "stars": r.get("stargazers_count", 0),
            "updated": (r.get("pushed_at") or r.get("updated_at") or "")[:10],
        })
        if len(repos) >= 6:
            break
    if repos:
        write_json("github.json", {
            "source": "GitHub",
            "profile_url": "https://github.com/hausfath",
            "updated": today(), "repos": repos,
        })


def main():
    # Optional selectors let the cron run subsets on different cadences:
    #   python3 update_feeds.py blog github   # daily (fast-changing)
    #   python3 update_feeds.py media         # weekly (GDELT + Google News)
    # No args runs everything (handy locally / for manual refreshes).
    os.makedirs(DATA, exist_ok=True)
    targets = [a.lower() for a in sys.argv[1:]] or ["blog", "media", "github"]
    if "blog" in targets:
        update_climate_brink()
        update_carbon_brief()
    if "media" in targets:
        update_media()
    if "github" in targets:
        update_github()
    print("Done.")


if __name__ == "__main__":
    main()
