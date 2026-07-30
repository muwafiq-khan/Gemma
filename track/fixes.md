# Fixes Log

Records of fixes applied, what broke, and how it was resolved.

---

## 2026-07-29 — Syntax fix: try/except indentation in gen_scene

**File:** `app.py`
**What broke:** `gen_scene()` had a `try:` block but the `except` was on the wrong indent level — code between `try:` and `except` was actually OUTSIDE the try block (at `def` level indentation). Python raised `SyntaxError: expected 'except' or 'finally' block`.

**Fix:** Re-indented the entire function body to be properly inside the `try:` block, with `except` at the matching level.

---

## 2026-07-30 — Interview continuation prompt hardcoded "3 topics" when user had 4 questions

**File:** `app.py:309-316`
**What broke:** User added a 4th question to `profile_interview_prompt()` in prompts.py, but the continuation prompt in `chat_fn()` still hardcoded `"all 3 topics (1=favorite movies/games, 2=easy DSA, 3=hard DSA)"`. Gemma never saw Q4 after the first turn.
**Fix:** Refactored prompts.py to export `INTERVIEW_QUESTIONS` list + `INTERVIEW_JSON_FIELDS` dict + `interview_json_schema()` function. `app.py` now builds the continuation prompt dynamically from these shared constants. Also updated `on_skip()` default profile to include `"crush":""`.

---

## 2026-07-30 — Scene prose truncated mid-JSON, rendered as raw text

**File:** `app.py:487, 151`
**What broke:** `max_tokens=2048` (main) and `1024` (pregen) were too low. Gemini's rich scene output got cut off before the JSON closed. `parse_json` failed → fallback displayed the raw half-finished JSON as "story prose".
**Fix:** Bumped both to `max_tokens=4096`. Also cleaned up the DEBUG print to show char count instead of first 300 chars.

---

## 2026-07-30 — Pregen cache stores empty API failure, blocks retry

**File:** `app.py:153-154`
**What broke:** When the pregen background thread hit an API error (WinError 10053), `call_gemma` returned `""`. The thread stored this empty string in the pregen cache unconditionally. When the user clicked a choice, `gen_scene` hit the cache, got `""`, and showed "[Empty response from API]" — never attempting a fresh synchronous call.
**Fix:** Added `if reply:` guard before `_store_pregen`. Empty API responses are now discarded instead of cached, allowing `gen_scene` to retry synchronously.

---

## 2026-07-30 — No debug logging in interview phase

**File:** `app.py:275, 277, 279, 300, 308, 319, 322`
**What broke:** Interview LLM calls had no `print()` statements, so `app.log` showed nothing during the interview phase.
**Fix:** Added 7 `print()` lines prefixed with `[INTERVIEW]` covering: first question generation (cache hit/miss), user message receipt, Gemma reply length, and profile capture. Also added `[SKELETON]` print for skeleton output.
