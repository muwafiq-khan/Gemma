import glob
import json
import os

from utils import parse_json, slog

RAG_DIR = os.path.join(os.path.dirname(__file__), "..", "rag")
SUB_TYPES = {"movies": "movie", "gaming": "game", "stories": "writer"}
MAX_FILES = 6
PATTERNS_FILE = os.path.join(RAG_DIR, "patterns", "patterns.json")


def save_patterns_to_disk(patterns, path=None):
    """Write the extracted pattern notes to disk (pretty JSON).
    Does not raise — on failure prints and the chain continues."""
    target = path or PATTERNS_FILE
    try:
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "w", encoding="utf-8") as f:
            json.dump(patterns, f, indent=2)
        print(f"[ANALYZER] Patterns saved to {target} ({len(patterns)} notes)")
        return target
    except OSError as e:
        print(f"[ANALYZER] Could not save patterns to {target}: {e}")
        return None


def _base_dir(session_dir):
    return session_dir or RAG_DIR


def _list_files(session_dir=None):
    base = _base_dir(session_dir)
    files = []
    for sub in SUB_TYPES:
        files += sorted(glob.glob(os.path.join(base, sub, "*.txt")))
    return files


def _title_from_file(fp):
    try:
        with open(fp, encoding="utf-8") as f:
            first = f.readline().strip()
        if first.lower().startswith("title:"):
            title = first[len("title:"):].strip()
            for sep in (" - ", " | ", " – ", " — "):
                if sep in title:
                    title = title.split(sep)[0].strip()
            return title[:60]
    except OSError:
        pass
    return os.path.splitext(os.path.basename(fp))[0]


def _type_from_dir(fp, session_dir=None):
    rel = os.path.relpath(fp, _base_dir(session_dir))
    sub = rel.split(os.sep)[0] if os.sep in rel else os.path.dirname(rel)
    return SUB_TYPES.get(sub, "unknown")


def _read_content(fp):
    try:
        with open(fp, encoding="utf-8") as f:
            text = f.read()
        parts = text.split("\n\n", 1)
        return parts[1].strip() if len(parts) > 1 else text
    except OSError as e:
        print(f"[ANALYZER] Cannot read {fp}: {e}")
        return ""


def analyze_rag_content(session_dir=None, status_setter=None, call_gemma=None,
                        pattern_prompt=None, sid=None):
    """Analyze the session's rag/*.txt and RETURN the extracted pattern notes
    (list of dicts). Does not touch any state — the caller decides where to
    store the result."""
    files = _list_files(session_dir)
    usable = [f for f in files if _read_content(f)]
    if not usable:
        msg = "[ANALYZE] No rag content to analyze."
        if status_setter:
            status_setter(msg)
        slog(sid, msg)
        return []

    patterns = []
    total = min(len(usable), MAX_FILES)
    for i, fp in enumerate(usable[:MAX_FILES]):
        title = _title_from_file(fp)
        stype = _type_from_dir(fp, session_dir)
        status_msg = f"[ANALYZE] Extracting patterns from {title} ({i+1}/{total})..."
        if status_setter:
            status_setter(status_msg)
        slog(sid, status_msg)
        try:
            prompt = pattern_prompt(title, stype, _read_content(fp))
            reply = call_gemma(prompt, max_tokens=2048)
        except Exception as e:
            slog(sid, f"[ANALYZER] Failed on {fp}: {e}")
            continue
        p = parse_json(reply)
        if p and isinstance(p, dict) and p.get("patterns"):
            p["source"] = p.get("source") or title
            p["type"] = p.get("type") or stype
            patterns.append(p)
        else:
            slog(sid, f"[ANALYZER] Skipped {fp} — unparseable reply ({len(reply)} chars)")

    slog(sid, f"[ANALYZER] Extracted {len(patterns)} pattern notes (returned, not stored).")
    if status_setter:
        status_setter(f"[ANALYZE] Done — {len(patterns)} pattern notes extracted.")
    return patterns
