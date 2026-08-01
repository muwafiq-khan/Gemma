# Fixes Log

Records of fixes applied, what broke, and how it was resolved.

---

## 2026-08-01 — Prints invisible on Render (stdout block-buffering, not a code bug)

**File:** `app.py` (`__main__`, +`import sys`)
**What broke:** `[SID=...]`, `[INTERVIEW]`, `[FETCH STATUS]`, `[FETCHER]` prints never showed in Render Logs (only tracebacks did). Root cause (websearch-verified, Render-specific articles + SO): Python block-buffers stdout (8KB) when it's a pipe/non-TTY — which is what Render's log collector is. stderr is unbuffered, so error tracebacks always appeared — the classic "works locally (TTY=line-buffered), vanishes in container" trap. Proven locally: a print through a pipe arrived 4.2s later (process end) vs 61ms after the fix.
**Fix:** `sys.stdout.reconfigure(line_buffering=True)` at startup (wrapped in try/except). Every print flushes per line — local AND Render. **Also recommended (dashboard-side, user action):** add env var `PYTHONUNBUFFERED=1` on Render for process-wide coverage.

---

## 2026-08-01 — Bug B (UnboundLocalError 'prompt') regressed on Render — fix committed + pushed

**File:** `app.py` (gen_scene), pushed to origin/main
**What broke:** After scene 1, clicking any choice crashed on Render with `UnboundLocalError: cannot access local variable 'prompt'` at `app.py:583`. NOT a code regression — the fix (call moved inside `if reply is None:` block) existed only in the local working tree, never committed. Render auto-deploys from GitHub and was running stale commit `8e7fec6` (verified via `git show HEAD:app.py`: line 583 outside the block). Cache HIT (pregen finished while reading scene 1) → `prompt` never assigned → crash.
**Fix:** Committed + pushed `app.py` + `utils.py` (Bug A `_repair_json`, Bug B prompt fix, pregen guard, story_context guard, server_name local/render split) → Render redeploys. **Lesson: commit + push immediately after every fix, then verify on Render — "works locally" is meaningless until pushed.**

---

## 2026-08-01 — Bug C (TypeError int parse) — UNDER OBSERVATION, no fix yet

**File:** `utils.py` (`parse_json`), `app.py:360-361`
**What broke:** `parse_json` uses `json.loads` directly — a bare-number chat message (`"5"`, `"10"`, `"3.5"`, `"true"`) parses to int/float/bool, then `any(k in dumped ...)` in `chat_fn` crashes with `TypeError: argument of type 'int' is not iterable`. Reproduced locally. Same latent risk at app.py:392-394, :447, :590.
**Status:** User decided to log as UNDER OBSERVATION (not reproducible in normal play). Proposed fix when approved: `parse_json` returns only dict/list results; `isinstance(dumped, dict)` guard in `chat_fn`.

---

## 2026-08-01 — Gemma emits malformed JSON (`"text "<value>` — missing colon), raw JSON shown in scenes

**File:** `utils.py` (`_repair_json` in `parse_json`), `app.py` (pregen guard + story_context guard)
**What broke:** Gemma 4 (temp 0.8) occasionally emits a choice as `"text "\"value\""` — key with trailing space, colon dropped, stray backslash. `parse_json` returned None → `gen_scene` fallback displayed the raw reply as scene text + polluted `story_context`. Captured 3 instances in user's log, all on choice b.
**Fix:** `_repair_json` — regex finds a colon-free string token + optional ws + optional `\` + quote (impossible in valid JSON) and inserts the colon, dropping the backslash; second regex normalizes keys with trailing spaces. Wired into `parse_json` before all parse attempts. Pregen thread now only caches replies that parse (also stops non-empty API-error strings from being cached). JSON-shaped text never appended to `story_context`.
**Dev note:** first regex version false-matched `": "` inside valid `"text": "..."` — fixed by excluding `:` from token content (`[^"\\:]`), since scene keys never contain colons.
**Verified:** all 3 exact failing replies from the log parse correctly; regression checks pass; py_compile + app import OK.

---

## 2026-07-31 — Design fix: rag_patterns wrongly nested inside user_profile

**File:** `state.py`, `rag/analyzer.py`, `app.py`, `BUILD_SPEC.md`, `AGENTS.md`
**What was wrong:** `analyze_rag_content(profile, ...)` mutated `profile["rag_patterns"]`, so derived pattern learnings lived inside the static interview profile. Consequences: `user_profile` no longer represented "what the user said" (it accumulated machine-derived data each fetch cycle); persona and pattern learnings were coupled in one container even though the spec's Step 4 treats them as separate prompt inputs (`skeleton_prompt(card, topics, persona_json, pattern_learnings_json)`).
**Fix:** Moved `rag_patterns` to session level (`state["rag_patterns"]`, next to `rag_fetch_status`/`rag_fetch_done`); analyzer no longer takes or mutates a profile — it returns the pattern list; `_start_fetch` assigns the return value in the chain closure. Docs updated in BUILD_SPEC (session state, profile structure, analyzer design, design rule) and AGENTS.md.
**Why it matters going forward:** Step 4 feeds `pattern_learnings_json` from `state["rag_patterns"]` into skeleton + scene prompts as a separate input — profile stays pure static interview data.

---

## 2026-07-31 — Pattern analyzer: Gemma returns EMPTY replies with max_tokens=1024

**File:** `rag/analyzer.py` (Step 3)
**What broke:** `analyze_rag_content` called Gemma with `max_tokens=1024`. The model returned 0-char responses for the pattern-extraction prompt (5/6 files failed in the first test). Probes proved it deterministic — same prompt returned valid JSON at `max_tokens=2048`/`4096`. Same class as the older scene-truncation bug where 2048/1024 were too low.
**Fix:** Bumped analyzer to `max_tokens=2048`. Also removed the strict "Output ONLY this JSON — no extra text" phrasing (correlated with empties in probes) in favor of "Output JSON with this shape:".

---

## 2026-07-31 — Fetch progress never reached the UI (live status)

**File:** `app.py` (fetch_status wiring, Step 1)
**What broke:** The daemon fetch thread wrote status to `s["rag_fetch_status"]`, but no event re-rendered the UI afterward — the Markdown only showed the one-shot snapshot from the last event handler. User saw static "[SEARCH]..." and never the per-name progress or [DONE].
**Fix:** Added `gr.Timer(1)` + `poll_fetch_status()` tick reading `rag_fetch_status` from state; `_start_fetch()` wraps the fetcher status_setter to also set `rag_fetch_done` and fire a `threading.Event`.

---

## 2026-07-31 — Fetcher only handled flat string lists

**File:** `rag/fetcher.py`
**What broke:** Rich Step-2 profile stores movies/games as dicts (`{"title": "Inception", ...}`) — old `fetch_from_profile` only read plain strings, so rich profiles would fetch nothing.
**Fix:** New `_extract_names()` accepts strings AND dicts (title/name key). Also: per-category query templates (`CATEGORY_QUERIES`), stale rag/*.txt cleared per session, optional `done_event` param.

---

## 2026-07-31 — prompts.py overwrite dropped 4 prompt functions (self-inflicted)

**File:** `prompts.py`
**What broke:** During the Step 2 rewrite of prompts.py the skeleton/scene/teaching/ending prompt functions were accidentally removed; app.py failed to import.
**Fix:** Restored all four functions verbatim from the previous version; interview section now contains the new 2-phase prompt. py_compile + app build verified after restore.

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

---

## 2026-07-30 — Choice click causes blank screen when model outputs non-standard choice IDs

**File:** `app.py:532-540`
**What broke:** `on_choice` looked up choices by `c["id"] == cid` (string match against "a"/"b"/"c"). When the model output choices with non-standard IDs (e.g., integers "1"/"2"/"3" or different strings), the lookup failed → returned `*([H]*13)` hiding all UI components including tabs → blank screen. No API call, no log entry.
**Fix:** Changed to positional lookup via `CID_IDX = {"a": 0, "b": 1, "c": 2}` — button A maps to `choices[0]`, B to `choices[1]`, C to `choices[2]`. Also added `[BLANK]` debug print if the path is still hit.

---

## 2026-07-30 — GOOGLE_API_KEY env var name mismatch

**File:** `app.py:20`
**What broke:** `os.environ.get("<API_KEY_VALUE>")` was checking for a literal API key value as the env var name instead of `"GOOGLE_API_KEY"`. Setting `$env:GOOGLE_API_KEY` had no effect.
**Fix:** Changed to `os.environ.get("GOOGLE_API_KEY")`.
