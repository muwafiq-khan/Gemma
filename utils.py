import datetime
import glob
import json
import os
import re
import shutil
import threading
import time

LOGS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
SESSIONS_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rag", "sessions")

INACTIVITY_GRACE = 3600          # 1h without any activity = session ended
ORPHAN_TTL = 24 * 3600           # safety net for folders/logs never registered
SWEEP_INTERVAL = 600             # sweeper runs every 10 min
ACTIVE_WINDOW = 900              # sessions with activity in the last 15 min are "active"

_activity = {}
_activity_lock = threading.Lock()


def _ts():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _clip(text, n=600):
    text = str(text or "")
    if len(text) <= n:
        return text
    return text[:n] + f"... [{len(text)} chars total]"


def slog(sid, msg):
    """Per-session log line: printed to stdout (Render Logs) tagged with the
    session id, and appended to logs/<sid>.log. Also marks the session as
    active so the sweeper knows it is still in use."""
    if not sid:
        print(msg)
        return
    with _activity_lock:
        _activity[sid] = time.time()
    line = f"[{_ts()}] {msg}"
    try:
        os.makedirs(LOGS_DIR, exist_ok=True)
        with open(os.path.join(LOGS_DIR, f"{sid}.log"), "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass
    print(f"[SID={sid}] {msg}")


def session_dir(sid):
    return os.path.join(SESSIONS_ROOT, sid)


def wipe_old_sessions():
    """Called whenever a NEW session starts: instantly delete every other
    session's rag files + logs. Sessions with activity in the last
    ACTIVE_WINDOW (15 min) are protected so a concurrently-playing user's
    fetch/story is never broken."""
    now = time.time()
    with _activity_lock:
        active = {sid for sid, t in list(_activity.items()) if now - t <= ACTIVE_WINDOW}
        for sid in list(_activity):
            if _activity[sid] <= now - ACTIVE_WINDOW:
                del _activity[sid]
    deleted = 0
    for d in glob.glob(os.path.join(SESSIONS_ROOT, "*")):
        if not os.path.isdir(d):
            continue
        sid = os.path.basename(d)
        if sid not in active:
            shutil.rmtree(d, ignore_errors=True)
            deleted += 1
    for f in glob.glob(os.path.join(LOGS_DIR, "*.log")):
        sid = os.path.splitext(os.path.basename(f))[0]
        if sid not in active:
            try:
                os.remove(f)
                deleted += 1
            except OSError:
                pass
    if deleted:
        print(f"[SESSIONS] New session start - wiped {deleted} stale file(s)/folder(s)")


def cleanup_session(sid):
    """Delete a user's rag files + log file the moment their session ends."""
    if not sid:
        return
    with _activity_lock:
        _activity.pop(sid, None)
    shutil.rmtree(session_dir(sid), ignore_errors=True)
    try:
        os.remove(os.path.join(LOGS_DIR, f"{sid}.log"))
    except OSError:
        pass
    print(f"[SESSIONS] Cleaned up session {sid} (rag files + log deleted)")


def sweep_once():
    """Delete files of ended sessions (no activity for INACTIVITY_GRACE) and
    any orphaned folder/log older than ORPHAN_TTL."""
    now = time.time()
    with _activity_lock:
        stale = [sid for sid, t in list(_activity.items()) if now - t > INACTIVITY_GRACE]
    for sid in stale:
        cleanup_session(sid)
    for d in glob.glob(os.path.join(SESSIONS_ROOT, "*")):
        if not os.path.isdir(d):
            continue
        sid = os.path.basename(d)
        if sid not in _activity and now - os.path.getmtime(d) > ORPHAN_TTL:
            shutil.rmtree(d, ignore_errors=True)
            print(f"[SESSIONS] Removed orphan rag folder {sid}")
    for f in glob.glob(os.path.join(LOGS_DIR, "*.log")):
        sid = os.path.splitext(os.path.basename(f))[0]
        if sid not in _activity and now - os.path.getmtime(f) > ORPHAN_TTL:
            try:
                os.remove(f)
            except OSError:
                pass
            print(f"[SESSIONS] Removed orphan log {sid}")


def start_sweeper():
    """One daemon thread (local + Render) that sweeps ended sessions."""
    if getattr(start_sweeper, "_started", False):
        return
    start_sweeper._started = True
    try:
        sweep_once()
    except Exception as e:
        print(f"[SESSIONS] Startup sweep error: {e}")

    def _loop():
        while True:
            time.sleep(SWEEP_INTERVAL)
            try:
                sweep_once()
            except Exception as e:
                print(f"[SESSIONS] Sweep error: {e}")

    threading.Thread(target=_loop, daemon=True).start()
    print("[SESSIONS] Sweeper started (every 10 min; 1h inactivity = session end)")


def _repair_json(text):
    """Repair Gemma 4's known JSON quirk: a choice key is sometimes emitted as
    `"text "<value>` — key with a trailing space, the colon dropped, and a
    stray backslash before the value. Two quoted strings sitting next to each
    other are impossible in valid JSON, so every match here is unambiguous."""
    text = re.sub(r'("(?:\\.|[^"\\:])*")(\s*)\\?(?=")', r"\1:\2", text)
    text = re.sub(r'"([^"\\]+?)\s+"(?=:)', r'"\1"', text)
    return text


def parse_json(text):
    if text is None:
        return None
    text = text.strip()
    m = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if m:
        text = m.group(1).strip()
    text = _repair_json(text)
    text = re.sub(r",\s*}", "}", text)
    text = re.sub(r",\s*\]", "]", text)
    for attempt in [json.loads, lambda t: json.JSONDecoder().raw_decode(t)[0]]:
        try:
            return attempt(text)
        except (json.JSONDecodeError, ValueError, TypeError):
            pass
    start = text.find("{")
    if start == -1:
        start = text.find("[")
    if start == -1:
        return None
    depth = 0
    in_str = False
    esc = False
    end = -1
    for i in range(start, len(text)):
        ch = text[i]
        if esc: esc = False; continue
        if ch == "\\": esc = True; continue
        if ch == '"': in_str = not in_str; continue
        if in_str: continue
        if ch in "{[": depth += 1
        elif ch in "}]":
            depth -= 1
            if depth == 0: end = i + 1; break
    if end == -1:
        return None
    try:
        s = text[start:end]
        s = re.sub(r",\s*}", "}", s)
        s = re.sub(r",\s*\]", "]", s)
        return json.loads(s)
    except json.JSONDecodeError:
        return None
