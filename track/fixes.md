# Fixes Log

Records of fixes applied, what broke, and how it was resolved.

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
