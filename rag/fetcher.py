import os
import shutil
import threading
import re
import time
import glob
import requests
from bs4 import BeautifulSoup
from ddgs import DDGS

from utils import slog

RAG_DIR = os.path.join(os.path.dirname(__file__), "..", "rag")
# category -> subfolder name inside the session's rag directory
CATEGORY_DIRS = {
    "movies": "movies",
    "games": "gaming",
    "writers": "stories",
}

# Category-specific query templates (Step 2: no more category-blind queries)
CATEGORY_QUERIES = {
    "movies": [
        "{name} plot analysis",
        "{name} story breakdown",
        "{name} what makes it unique",
        "{name} why is it exceptional",
        "{name} character development analysis",
        "{name} in-depth review",
    ],
    "games": [
        "{name} plot analysis",
        "{name} story breakdown",
        "{name} what makes it unique",
        "{name} game design analysis",
        "{name} character development",
        "{name} in-depth review",
    ],
    "writers": [
        "{name} writing style analysis",
        "{name} story structure breakdown",
        "{name} best works",
        "{name} what makes their writing unique",
        "{name} how they build characters",
    ],
}

SKIP_DOMAINS = [
    "discord.com", "youtube.com", "youtu.be", "reddit.com", "facebook.com",
    "twitter.com", "x.com", "instagram.com", "tiktok.com", "pinterest.com",
    "amazon.com", "ebay.com", "walmart.com",
]


def _safe_filename(name):
    name = re.sub(r'[^\w\s-]', '', name).strip().replace(' ', '_').lower()
    return name[:60] or "unknown"


def _fetch_text(url, timeout=8):
    try:
        resp = requests.get(url, timeout=timeout, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()
        body = soup.find("body") or soup
        return body.get_text(separator="\n", strip=True)[:8000]
    except Exception as e:
        return f"[fetch error: {e}]"


def _first_line(filepath):
    try:
        with open(filepath, encoding="utf-8") as f:
            return f.readline().strip()[:120]
    except OSError:
        return ""


def search_and_save(name, subdir, category, sid=None):
    os.makedirs(subdir, exist_ok=True)
    base = _safe_filename(name)
    queries = [q.format(name=name) for q in CATEGORY_QUERIES.get(category, CATEGORY_QUERIES["movies"])]

    fetched = 0
    for query in queries:
        if fetched >= 2:
            break
        for attempt in range(3):
            try:
                results = []
                with DDGS() as ddgs:
                    for r in ddgs.text(query, max_results=4):
                        results.append(r)
                if results:
                    break
            except Exception as e:
                slog(sid, f"[FETCHER] attempt {attempt+1}/3 failed: {e}")
                time.sleep(2)
        else:
            continue

        for r in results:
            if fetched >= 2:
                break
            url = r["href"]
            if any(d in url.lower() for d in SKIP_DOMAINS):
                continue
            content = _fetch_text(url)
            if not content or len(content) < 200:
                continue
            filename = f"{base}_{fetched + 1}.txt"
            filepath = os.path.join(subdir, filename)
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(f"Title: {r.get('title', '')}\nURL: {url}\nQuery: {query}\n\n{content}")
            slog(sid, f"[FETCHER] Saved: {filepath} ({len(content)} B) — first line: {_first_line(filepath)}")
            fetched += 1

    if fetched == 0:
        slog(sid, f"[FETCHER] No results for '{name}'")


def _extract_names(profile):
    """Extract (name, category) from profile. Segments may be:
    - dict segments: movies {genres, favorites, character_types, writers_directors},
      games {genres, favorites, hooked_elements}
    - legacy list segments (plain strings or dicts with 'title') — still supported
    writers_directors and the top-level writers list both map to the 'writers' category."""
    names = []
    seen = set()

    def add(items, category):
        for item in items or []:
            if isinstance(item, dict):
                name = item.get("title") or item.get("name") or ""
            elif isinstance(item, str):
                name = item
            else:
                continue
            name = name.strip()
            if len(name) < 2:
                continue
            key = (name.lower(), category)
            if key in seen:
                continue
            seen.add(key)
            names.append((name, category))

    movies = profile.get("movies")
    if isinstance(movies, dict):
        add(movies.get("favorites", []), "movies")
        add(movies.get("writers_directors", []), "writers")
    elif isinstance(movies, list):
        add(movies, "movies")

    games = profile.get("games")
    if isinstance(games, dict):
        add(games.get("favorites", []), "games")
    elif isinstance(games, list):
        add(games, "games")

    add(profile.get("writers", []), "writers")
    return names


def fetch_from_profile(profile, session_dir=None, status_setter=None, done_event=None, sid=None):
    all_names = _extract_names(profile)

    if not all_names:
        if status_setter:
            status_setter("[SKIP] No movies/games/writers found in profile.")
        if done_event:
            done_event.set()
        return

    total = len(all_names)
    if status_setter:
        labels = [n for n, _ in all_names[:3]]
        status_setter(f"[SEARCH] Looking up: {', '.join(labels)}")

    def _run():
        # Fresh per-session storage: wipe the session's own folder (if it
        # somehow exists) so we never mix with previous runs of this user.
        if session_dir:
            shutil.rmtree(session_dir, ignore_errors=True)
        for i, (name, category) in enumerate(all_names):
            if i > 0:
                time.sleep(3)
            subdir = os.path.join(session_dir, CATEGORY_DIRS[category]) if session_dir else RAG_DIR
            if status_setter:
                status_setter(f"[SEARCH] Fetching {name} ({i+1}/{total})...")
            search_and_save(name, subdir, category, sid=sid)
        if status_setter:
            status_setter(f"[DONE] RAG content saved to rag/ folders.")
        if done_event:
            done_event.set()

    threading.Thread(target=_run, daemon=True).start()
