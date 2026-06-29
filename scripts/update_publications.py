#!/usr/bin/env python3
"""Refresh the full publication list from OpenAlex.

Pulls Zeke Hausfather's works (OpenAlex author A5085329398), keeps peer-reviewed
items, de-dupes preprint/published pairs, and writes site/data/publications.json.
main.js renders the expandable "full publication list" from this file (falling
back to its built-in list if the fetch ever fails).

The hand-picked "Selected publications" featured cards in index.html are NOT
touched by this script: those stay curated, with Google Scholar citation badges.

Standard library only, so it runs on GitHub Actions with no pip install.
Run:  python3 scripts/update_publications.py
"""

import json
import os
import re
import urllib.request
import urllib.parse
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "site", "data")

AUTHOR_ID = "A5085329398"
MAILTO = "zeke@berkeleyearth.org"   # OpenAlex "polite pool" courtesy header
UA = "Mozilla/5.0 (compatible; zekehausfather.com publication updater)"

# Work types worth listing as publications (skip preprints, errata, editorials,
# datasets, paratext, etc.).
KEEP_TYPES = {"article", "review", "book-chapter", "report", "book"}

# OpenAlex sometimes tags peer-reviewed Comments/Perspectives as these; keep them
# only when they have a real venue + DOI (filtered below).
SOFT_TYPES = {"paratext", "letter", "editorial"}

# Preprint servers / repositories that masquerade as venues. Matched as a
# case-insensitive substring of the venue name.
PREPRINT_VENUES = (
    "arxiv", "figshare", "cdrxiv", "zenodo", "ssrn", "biorxiv", "medrxiv",
    "research square", "preprint", "discussions", "egusphere", "essoar",
    "authorea", "osf",
    # conference abstracts (AGU / EGU fall meetings, etc.)
    "fall meeting", "general assembly", "conference abstract", "agufm",
    "eguga", "aguga",
)

# Popular-press / non-peer-reviewed outlets to leave out of the academic list.
NONACADEMIC_VENUES = (
    "scientific american", "carbon brief", "the conversation",
    "yale climate", "the guardian", "washington post",
)

# Title prefixes that signal non-papers (corrections, supplements, replies).
SKIP_TITLE_PREFIXES = (
    "supplementary material", "supplement to", "supporting information",
    "correction", "corrigendum", "erratum", "author correction",
    "reply to", "comment on", "response to",
)

# Curated entries OpenAlex misses or formats poorly. Always merged into the
# output; any OpenAlex work whose DOI matches SUPPRESS_DOIS is dropped so the
# clean pinned version wins instead of producing a duplicate.
PINNED = [
    {"year": 2021,
     "title": "Climate Change 2021: The Physical Science Basis, Ch. 1: Framing, Context and Methods (IPCC AR6 WGI, contributing author)",
     "venue": "Cambridge University Press",
     "url": "https://www.ipcc.ch/report/ar6/wg1/chapter/chapter-1/",
     "cites": 0},
    {"year": 2023,
     "title": "Ch. 2: Climate Trends, Fifth U.S. National Climate Assessment",
     "venue": "U.S. Global Change Research Program",
     "url": "https://nca2023.globalchange.gov/chapter/2/",
     "cites": 78},
]
SUPPRESS_DOIS = ("10.7930/nca5.2023.ch2",)

# Keep an untitled-venue work only if it has cleared this many citations
# (catches a high-profile paper OpenAlex hasn't linked to a venue yet, while
# dropping the long tail of un-indexed preprints).
VENUELESS_MIN_CITES = 25


def fetch(url, timeout=45):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def norm_title(t):
    return re.sub(r"[^a-z0-9]+", " ", (t or "").lower()).strip()


def today():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def fetch_works():
    base = "https://api.openalex.org/works"
    params = {
        "filter": f"author.id:{AUTHOR_ID}",
        "sort": "publication_year:desc,cited_by_count:desc",
        "per-page": "200",
        "mailto": MAILTO,
    }
    url = base + "?" + urllib.parse.urlencode(params)
    data = fetch(url)
    return data.get("results", [])


def venue_of(w):
    loc = w.get("primary_location") or {}
    src = loc.get("source") or {}
    name = (src.get("display_name") or "").strip().rstrip(".")
    stype = (src.get("type") or "").strip()
    return name, stype


def to_entry(w):
    title = (w.get("display_name") or "").strip()
    year = w.get("publication_year")
    venue, stype = venue_of(w)
    doi = w.get("doi") or ""          # already a full https://doi.org/... URL
    cites = w.get("cited_by_count", 0)
    wtype = w.get("type", "")
    return {
        "year": year,
        "title": title,
        "venue": venue,
        "url": doi,
        "cites": cites,
        "_type": wtype,
        "_source_type": stype,
        "_has_doi": bool(doi),
    }


def keep(e):
    if not e["title"] or not e["year"]:
        return False
    low_title = e["title"].lower()
    if any(low_title.startswith(p) for p in SKIP_TITLE_PREFIXES):
        return False
    # Drop preprint servers / repositories and conference proceedings.
    if e["_source_type"] in ("repository", "conference"):
        return False
    low_venue = e["venue"].lower()
    if low_venue and any(p in low_venue for p in PREPRINT_VENUES):
        return False
    if low_venue and any(p in low_venue for p in NONACADEMIC_VENUES):
        return False
    # Untitled-venue works are usually un-indexed preprints; keep only if the
    # citation count proves it's a real, established paper.
    if not e["venue"] and e["cites"] < VENUELESS_MIN_CITES:
        return False
    if e["_type"] in KEEP_TYPES:
        return True
    # Borderline types only count if they look like a real paper.
    if e["_type"] in SOFT_TYPES:
        return e["_has_doi"] and bool(e["venue"])
    return False


def dedupe(entries):
    """Collapse preprint/published duplicates by title; keep the strongest."""
    best = {}
    for e in entries:
        k = norm_title(e["title"])
        if not k:
            continue
        cur = best.get(k)
        # Prefer the one with a DOI, then more citations, then a named venue.
        score = (e["_has_doi"], e["cites"], bool(e["venue"]))
        if cur is None or score > cur[0]:
            best[k] = (score, e)
    out = [v[1] for v in best.values()]
    out.sort(key=lambda e: (e["year"], e["cites"]), reverse=True)
    return out


def main():
    os.makedirs(DATA, exist_ok=True)
    print("Publications (OpenAlex)…")
    try:
        works = fetch_works()
    except Exception as e:
        print(f"  ! skipped ({e}); keeping existing file")
        return
    entries = [to_entry(w) for w in works]
    entries = [e for e in entries if keep(e)]
    # Drop OpenAlex versions of works we pin a cleaner copy of.
    entries = [e for e in entries
               if not any(d in (e["url"] or "").lower() for d in SUPPRESS_DOIS)]
    entries = dedupe(entries)

    # Strip internal helper fields, then merge in the curated pinned entries.
    pubs = [{"year": e["year"], "title": e["title"], "venue": e["venue"],
             "url": e["url"], "cites": e["cites"]} for e in entries]
    pubs.extend(dict(p) for p in PINNED)
    pubs.sort(key=lambda e: (e["year"] or 0, e["cites"]), reverse=True)

    payload = {
        "source": "OpenAlex",
        "author_url": f"https://openalex.org/{AUTHOR_ID}",
        "updated": today(),
        "count": len(pubs),
        "publications": pubs,
    }
    path = os.path.join(DATA, "publications.json")
    with open(path, "w") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    print(f"  wrote publications.json ({len(pubs)} items)")


if __name__ == "__main__":
    main()
