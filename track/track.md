# Track Log

## 2026-08-01 — FIXED: prints invisible on Render (stdout buffering)

**What happened:** User got no `[SID]`/`[FETCH STATUS]` logs in Render Logs after the logging feature deploy — only tracebacks. Websearch confirmed the known Render/Python issue: stdout is block-buffered (8KB) when piped (non-TTY); stderr is unbuffered, which is why only tracebacks appeared. Locally it "worked" because the terminal is a TTY (line-buffered). Local proof: piped print arrived after 4.2s (process exit) — with `line_buffering=True` it arrives in ~60ms.

**Result:** FIXED — `app.py` `__main__` adds `sys.stdout.reconfigure(line_buffering=True)` (try/except-wrapped). Pushed with commit. User additionally asked to add `PYTHONUNBUFFERED=1` in Render dashboard env vars for process-wide coverage.

**Files:** app.py (`import sys` + reconfigure in `__main__`), track/fixes.md (entry)

## 2026-08-01 — Edit: new session start wipes old session files instantly

**What happened:** User's rule simplified to "whenever a new session starts, old files get wiped out" (replaces waiting for the 1h sweeper grace).

**Result:** `utils.py` gained `wipe_old_sessions()` — called from `new_session()` in state.py (Gradio invokes the state factory per session lazily on first state access — verified in gradio's state_holder source), so every new session start instantly deletes all other sessions' `rag/sessions/<sid>/` folders + `logs/<sid>.log`. Sessions with activity in the last 15 min (`ACTIVE_WINDOW`) are protected so a concurrently-playing user's fetch/story is never broken. `on_play_again` triggers it too (it calls `new_session()`). The 10-min sweeper (1h grace) and 24h orphan sweep remain as backups. Verified: wipe test — active session's files survive, dead sessions' folders+logs deleted; py_compile + Gradio build pass.

**Files:** utils.py (`wipe_old_sessions`, ACTIVE_WINDOW), state.py (`new_session` calls wipe)

## 2026-08-01 — Feature: per-user session logs + session-end file cleanup (local + Render)

**What happened:** User wanted (1) every user's interview Q&A + fetch/analyze activity visible in Render Logs like the local terminal, (2) to verify downloaded websearch files (where they are + first line preview), (3) files deleted when a user's session ends, on local AND Render.

**Result:** Built. (1) `state.py` adds `sid` (uuid) to every session; `utils.py` gains `slog()` — prints `[SID=xxxx]` lines to stdout (Render Logs, filterable per user) AND appends to `logs/<sid>.log` with timestamps. All app print sites routed through it with CONTENT: interview user msgs + Gemma replies, skeleton, scene replies (600-char clip), pregen hits, tutor Q&A, ending, fetch/analyze statuses. (2) `rag/fetcher.py` saves per session into `rag/sessions/<sid>/{movies,gaming,stories}/` and after every save logs `[FETCHER] Saved: <full path> (<bytes> B) — first line: <Title line>` (first line only, per user request — no 600-char dumps). (3) Session-end cleanup: `rag/analyzer.py` + fetcher read/write only the session's own folder; sweeper daemon (`start_sweeper()` in `__main__`, runs every 10 min on local AND Render) deletes a session's folder + log after 1h of no activity (= user closed tab), 24h orphan safety net, plus `on_play_again` deletes instantly. Free Render has no file browser, so Render Logs is the only window into fetched files — verified content is real via the first-line preview.

**Files:** state.py (sid), utils.py (slog/session_dir/cleanup_session/sweep_once/start_sweeper), rag/fetcher.py (session dirs, saved-file line w/ first-line preview, no more global _clear_subdirs), rag/analyzer.py (session-scoped _list_files/_type_from_dir, sid logs), app.py (all prints → slog, _start_fetch session_dir, play-again cleanup, start_sweeper), .gitignore (logs/, rag/sessions/).

**Verified:** py_compile all; smoke test passed — slog writes + clips to logs/<sid>.log, fetcher first-line preview, analyzer extracts from session dir only, cleanup_session deletes folder+log, orphan sweep removes 25h-old folder; app import + Gradio build OK. **Note:** local old rag/{movies,gaming,stories} files from prior tests are now legacy — the old global dirs are no longer read/written.

## 2026-08-01 — Bug B regressed on Render → committed + pushed all pending fixes

**What happened:** User hit `UnboundLocalError: 'prompt'` at app.py:583 on Render right after scene 1 + first choice click. NOT a new bug — Bug B's fix lived only in the local working tree (bug_report.md even warned "commit + push still pending"). Render deploys from GitHub; last commit `8e7fec6` still had `call_gemma(prompt)` OUTSIDE the `if reply is None:` block (verified via `git show HEAD:app.py` lines 557-583). Also investigated user's earlier "crash at story generation" report — that TypeError is Bug C (parse_json returns int for bare-number messages; can only fire from the interview Send button; logged as UNDER OBSERVATION per user).

**Result:** Bug report updated (Bug B → REGRESSED ON RENDER + common-pattern finding; Bug C → UNDER OBSERVATION with full analysis). Committed + pushed `app.py`, `utils.py`, track files → Render auto-redeploys. Next: user re-tests choice click + scene 2+ on Render, then verify pregen logs.

**Files:** track/bug_report.md (Bug B regression note, Bug C entry), track/fixes.md (2 entries), app.py + utils.py (committed + pushed)

## 2026-08-01 — FIXED: raw JSON shown in some scenes (Gemma's missing-colon quirk)

**What happened:** User saw raw JSON as scene text in some scenes. User's log captured 3 `parse_json FAILED` dumps — all with the SAME defect on choice b: `"text "\"value\""` (key with trailing space, colon dropped, stray backslash) instead of `"text": "value"`. Complete JSON otherwise (NOT truncation — my earlier hypothesis was wrong). parse failure → fallback (`sd = {"prose": reply}`) → raw JSON displayed + story_context polluted. Also unified with the earlier "Learn button missing" report (fallback scene has challenge=None). Similar incidents existed: July 30 truncation bug (fix: token bump, fixes.md:65) and pregen empty-cache bug (fixes.md:73) — same fragile point (parse fail → raw display), different causes.

**Result:** FIXED. (1) `utils.py` `_repair_json()` wired into `parse_json`: token + optional ws + optional stray `\` + quote (impossible in valid JSON) → insert colon, drop stray backslash; second pass normalizes trailing-space keys. First attempt false-matched `": "` in valid JSON → fixed by excluding colons from token content (`[^"\\:]`). (2) pregen cache guard: only cache parseable replies (also kills latent API-error-string caching). (3) story_context guard: no JSON-shaped text appended. Verified with the exact 3 failing replies from the log — all parse (prose/choices/challenges intact); regression checks pass; py_compile + import OK.

**Files:** utils.py (`_repair_json`), app.py (pregen guard, story_context guard), AGENTS.md (huha command added), track/bug_report.md (BUG A → Worked: YES), track/fixes.md

## 2026-08-01 — FIXED: local URL shows 0.0.0.0 (Render bind leak into local runs)

**What happened:** User reported that after the Render deploy commit (`8137fd4`), `python app.py` prints `http://0.0.0.0:7860` and nothing loads at that address (app still reachable at old 127.0.0.1). Root cause: the deploy commit made `server_name="0.0.0.0"` unconditional. `0.0.0.0` is a bind-all placeholder, not a navigable address — browsers refuse it (Chrome/Edge block it), so the printed URL was never clickable, while 127.0.0.1 still worked because a 0.0.0.0 bind serves all local interfaces. Server was never down — purely a display regression.

**Result:** FIXED — `server_name="0.0.0.0" if on_render else "127.0.0.1"` (`app.py:760`). Locally the terminal prints `http://127.0.0.1:7860` again (verified with unbuffered launch: "Running on local URL: http://127.0.0.1:7860"); Render path verified with `RENDER=1` — binds `('0.0.0.0', 7860)` exactly as before (error shown in test was only a port-in-use conflict from the previous test instance). py_compile passes.

**Files:** app.py (760), track/track.md (this entry)

## 2026-08-01 — FIXED: UnboundLocalError 'prompt' at scene ~6 (pregen cache hit race)

**What happened:** User hit `cannot access local variable 'prompt' where it is not associated with a value` around scene 6. Root cause found in `gen_scene`: `prompt` is assigned only inside `if reply is None:` (the cache-MISS branch), but `reply = call_gemma(prompt, ...)` sat OUTSIDE that block (`app.py:583`). When the background pregen thread finished in time, `_check_pregen` returned the cached scene → `prompt` never assigned → UnboundLocalError, caught by the outer except and shown in the UI. Bug introduced in Step 4 commit `1f1d9d4` (scene_prompt reformat when adding pattern_learnings_json dedented the call line out of the block — verified against `1f1d9d4^` where it was correctly inside).

**Result:** FIXED — moved the call back inside the block (cache hit → use cached reply, no API call) + added `else: print(f"[PREGEN] scene {idx} cache hit")` for future diagnosis. py_compile passes; traced both paths (hit/miss); all 4 `call_gemma(prompt)` sites verified assigned-before-use. Why scene 6: timing — earlier scenes clicked before pregen finished (miss), scene 6 was the first cache hit.

**Files:** app.py (583-585), track/bug_report.md (#13), track/track.md (this entry)

## 2026-07-31 — README rewrite + push

**What happened:** Studied the full codebase (app.py, prompts.py, state.py, utils.py, rag/ fetcher+analyzer, BUILD_SPEC, AGENTS.md, track logs) and rewrote README.md — now covers what the project is, the full user flow (landing → interview → skeleton → play → challenge → teaching → ending), a behind-the-scenes pipeline diagram (async fetch → pattern analysis → skeleton → pregen scene loop), and a key design decisions table (beats-not-branches, no-retry darker turns, DSA-as-gameplay, RAG personalization, static-vs-derived state).

**Result:** README rewritten (115 insertions, 11 deletions), committed `8e7fec6`, pushed to origin/main (`931a8ab..8e7fec6`). Working tree clean after push.

**Files:** README.md (rewrite), track/track.md (this entry)

## 2026-07-31 — Deployment: Render free tier (HF Spaces blocked)

**What happened:** Attempted HF Spaces deployment — BLOCKED: `402 Payment Required` — Gradio/Docker Spaces on free cpu-basic now require PRO subscription (credit card), violating the no-card constraint. Researched alternatives (websearch, 2026 sources): Render free tier confirmed — no credit card (GitHub signup), 750 hrs/month (enough for 24/7), 512MB RAM, env vars free, git-push deploy, sleeps after 15 min idle (~30-60s cold start). User approved the pivot (HF → Render). Code change: `app.py` launch now reads `PORT` env + binds `0.0.0.0`, `debug=not on_render` (avoids reloader subprocess on Render). Pushed (`8137fd4`).

**Status:** User created Render web service from repo (build+start commands set), paused before Deploy — waiting for my code push (done). Next: user adds `GOOGLE_API_KEY` env var in Render dashboard (key NEVER in repo — gitignored `local_config.py` + verified clean), hits Deploy, then live URL test end-to-end (fetch → analyze → skeleton → scenes).

**Decisions:** No render.yaml blueprint (keeps secrets out of repo — env vars only via dashboard). HF token `gemmadeploy` unused → recommend revoke. AGENTS.md constraint line updated: "Hugging Face Inference API or Kaggle" → Render free tier + Google AI API.

**Known next:** live test on Render URL; keep-alive protocol for judging week (visit 5 min before demo; cold start 30-60s).

## 2026-07-31 — BUILD_SPEC doc sync (3 stale spots fixed)

**What happened:** Audit of BUILD_SPEC.md vs actual code found 3 stale spots: file-structure tree missing `rag/patterns/` folder, Analyzer Design section missing the disk-persistence note, and the "stale files cleared per session" line missing patterns.json. All 3 fixed with one-line edits. No code changes.

**Result:** BUILD_SPEC now fully matches the current code (Steps 1-4 + pattern persistence documented).

**Files:** BUILD_SPEC.md

## 2026-07-31 — Post-Step-4 add: patterns written to disk

**What happened:** User wanted extracted patterns persisted to disk, not just in-memory. Added `save_patterns_to_disk(patterns)` to `rag/analyzer.py` (writes pretty JSON to `rag/patterns/patterns.json`, graceful on failure — never crashes the chain). `app.py` `_start_fetch` chain calls it right after `analyze_rag_content` assigns `s["rag_patterns"]`. `rag/fetcher.py` `_clear_subdirs()` now also deletes the stale patterns file per session, so disk mirrors the current session (no leftovers from previous users).

**Result:** Verified — analyzer ran on 8 fetched files → 5 notes saved to `rag/patterns/patterns.json` (full structure/tension_building/character_intro/dialogue/devices per note); `_clear_subdirs` removes the file correctly; py_compile + app build pass. Note: one file's API reply was empty (0 chars, known transient class — skipped gracefully, logged as unparseable).

**Decisions:** Patterns file cleared per session together with rag/*.txt (fresh-state consistency). Analyzer stays pure (returns list); disk write is a separate explicit step.

**Files:** rag/analyzer.py (+save_patterns_to_disk, PATTERNS_FILE), app.py (import + call), rag/fetcher.py (stale file removal)

**Known next:** live browser demo — full interview → fetch → analyze (patterns.json appears on disk) → skeleton → scenes.

## 2026-07-31 — Step 4: Enhanced Skeleton + Pattern-Aware Scenes — DONE

**What happened:** `skeleton_prompt()` and `scene_prompt()` now take a `pattern_learnings_json` param; both prompts gained a "Pattern Learnings" section instructing Gemma to mirror the user's favorite structural techniques (non-linear timelines, tension curve, character intro style, dialogue) — conditional wording so empty `[]` (skip/failed fetch path) still works. `app.py`: `on_generate` passes `json.dumps(s["rag_patterns"])` into skeleton (max_tokens 3072 → 4096); `_snapshot_state` added `rag_patterns` so the pregen background thread sees them; `_pregen_next` + `gen_scene` pass raw patterns into every scene call. NO trimming — user decided full pattern notes go in as-is.

**Result:** Verified end-to-end with a real fetch→analyze→generate run: 8 rag files fetched, 6 pattern notes extracted (Inception/Stranger Things/Disco Elysium/Nolan), skeleton WITHOUT patterns vs WITH patterns compared — WITH patterns adopted Stranger Things' 80s aesthetic, Inception's layered-dream/temporal-kick structure, and Disco Elysium's inner-voice character ("The Analyst", "fractured psyche" protagonist). Scene prompt smoke test: patterns section present, param accepted. py_compile + Gradio app build pass.

**Decisions:** No compaction/trimming (user chose full notes); skeleton max_tokens bumped to 4096 (user approved); patterns passed raw via `json.dumps` — empty list keeps `[SKIP]` path working.

**Files:** prompts.py (2 prompt signatures + sections), app.py (on_generate, _snapshot_state, _pregen_next, gen_scene)

**Known next:** live demo run in browser — full interview → fetch → analyze → skeleton → scenes, eyeball prose quality.

## 2026-07-31 — Pre-Step-4: Profile schema completed to full target structure

**What happened:** BUILD_SPEC review found the rich profile was a SUBSET of the target — the interview ASKED about genres/character types/writers/game elements but the JSON schema never stored those answers (they were lost after the conversation). Extended `INTERVIEW_JSON_FIELDS` in prompts.py to the full target: `movies.{genres, favorites, character_types, writers_directors}`, `games.{genres, favorites, hooked_elements}` (+ existing writers/character). Schema builders render nested objects and produce valid JSON. `state.py` default profile matches. `_extract_names()` (fetcher) and `profile_refs()` (app.py) now handle dict segments AND legacy lists (back-compat); `writers_directors` maps to rag/stories/.

**Result:** Verified — schema valid JSON, extraction tests pass on new + old shapes, app builds. User's genre/character-type/writer answers now survive into skeleton + scene personalization.

**Decisions:** Kept legacy list handling so old dumps/sessions don't break. writers_directors fetched as "writers" category per spec. Step 4 scope expanded in BUILD_SPEC: scene generation also receives compact pattern learnings.

**Files:** prompts.py, state.py, rag/fetcher.py, app.py, BUILD_SPEC.md

**Known next:** Step 4 — pattern-aware skeleton + scenes.

## 2026-07-31 — Step 3 fix: rag_patterns moved OUT of user_profile (static vs derived separation)

**Current status (before the fix):** `rag_patterns` lived INSIDE `user_profile` — the analyzer function `analyze_rag_content(profile, ...)` mutated `profile["rag_patterns"]` directly in the background thread. This followed the original BUILD_SPEC target structure ("RAG OUTPUTS (filled by analyzer)" nested under user_profile), but the user correctly flagged it as wrong.

**What the mixing actually looked like (state level):**
```python
s["user_profile"] = {
    "movies": [...], "games": [...], "writers": [...],
    "character": {...},
    "rag_patterns": [...]   # ← derived data living inside static interview answers
}
```
Meaning: `user_profile` was no longer "what the user told us" — it silently accumulated Gemma's learned output on every fetch+analyze cycle. Two different kinds of data (user statements vs machine-derived learnings) shared one container, even though the spec's own Step 4 language treats them as SEPARATE inputs: `skeleton_prompt(card_info, topics, user_persona_json, pattern_learnings_json)`.

**The fix applied:** kept `user_profile` purely static (only the interview/dump ever writes it) and moved derived data to session level:
```python
s["rag_patterns"] = [...]   # session-level derived data, next to rag_fetch_status/rag_fetch_done
s["user_profile"] = {"movies": [...], "games": [...], "writers": [...], "character": {...}}  # untouched by analysis
```
Changes: `state.py` (key moved from `default_user_profile()` → `new_session()`), `rag/analyzer.py` (signature is now `analyze_rag_content(status_setter=None, call_gemma=None, pattern_prompt=None)` — no profile param, no mutation, RETURNS the list), `app.py` (`_start_fetch` assigns `s["rag_patterns"] = analyze_rag_content(...)` in the chain closure), `BUILD_SPEC.md` + `AGENTS.md` (docs updated: session state listing, profile structure, analyzer design, design rule section).

**Result:** Verified end-to-end — real fetch→analyze chain ran; 1 pattern note landed in `s["rag_patterns"]`; `rag_fetch_done=True`, event fired, `[DONE] RAG + pattern analysis complete.`; `user_profile` confirmed free of the `rag_patterns` key. Step 4 will now naturally feed `pattern_learnings_json` from `s["rag_patterns"]` into skeleton + scene prompts.

## 2026-07-31 — Step 3: Pattern Analyzer — DONE

**What happened:** Built `rag/analyzer.py` exactly per the plan above. `parse_json` moved verbatim into new `utils.py` (app.py + analyzer both import it — no circular import). Added `pattern_extraction_prompt(title, type, content)` to prompts.py (5 structural aspects → JSON per the rag_patterns schema). Wired analyzer into `_start_fetch`'s status_setter: when fetcher sends `[DONE]`, the same background thread immediately runs analysis, then sets `rag_fetch_done=True`, fires the event, status `[DONE] RAG + pattern analysis complete`. `on_generate` wait bumped 60s → 180s. `rag_patterns: []` added to default profile.

**Result:** Verified end-to-end. Standalone test on 6 existing rag/ files → 6 high-quality pattern notes (structure, tension_building, character_intro, dialogue, devices). Full-flow test (Stranger Things fetch → analyze → event → patterns in state) passed: 2 pattern notes, done flag set, final status correct.

**Key bug found & fixed:** `max_tokens=1024` makes Gemma return EMPTY responses for this prompt — same class as the old scene-truncation bug (fixes.md). Analyzer now uses 2048. Also "Output ONLY this JSON — no extra text" phrasing was linked to empties; softened to "Output JSON with this shape:".

**Files:** utils.py (new), rag/analyzer.py (new), prompts.py (+pattern_extraction_prompt), app.py (imports, analyzer chain, 180s wait), state.py (rag_patterns default)

**Known next:** Step 4 — enhanced skeleton_prompt receiving pattern_learnings_json; compare skeleton before/after patterns.

## PLAN — Step 3: Pattern Analyzer (verbatim plan, awaiting execution)

Here's the Step 3 plan (Pattern Analyzer):

### 1. New file `rag/analyzer.py`
- `analyze_rag_content(profile, status_setter=None)`:
  - Reads all `*.txt` in `rag/{movies, gaming, stories}/` (the files fetched in Step 2)
  - **Cap at ~6 files** (2 per name) to bound API calls/latency; skips `[fetch error` files
  - For each file → `call_gemma(pattern_extraction_prompt(...))` → parse JSON → append to a list
  - Mutates `profile["rag_patterns"]` (shared state dict, so it flows back to the session)
  - Graceful: a failed file is skipped, analysis continues
- **Circular import problem:** `parse_json` lives in `app.py`, and `app.py` will import `analyzer.py`. Fix: move `parse_json` (verbatim) into a small `utils.py`; `app.py` imports it from there (one-line import change — verified with py_compile + app build after). Or duplicate a parser inside analyzer — I recommend the `utils.py` refactor (single source of truth).

### 2. `prompts.py` — add `pattern_extraction_prompt(title, type, content)`
- Extracts 5 things per BUILD_SPEC: story structure & pacing, tension building, character intro style, dialogue patterns, narrative devices
- Outputs structured JSON matching the `rag_patterns` schema: `{"source", "type", "patterns": {"structure", "tension_building", "character_intro", "dialogue", "devices": [...]}}`

### 3. `app.py` — wire analysis into the fetch chain (background)
- In `_start_fetch`'s `status_setter`: when fetcher sends `[DONE]`, **don't** set `rag_fetch_done` yet — set status `[ANALYZE] Extracting narrative patterns...`, run analyzer (chained in the same daemon thread), then set `rag_fetch_done=True`, fire the event, status `[DONE] Analysis complete`
- Bump `on_generate`'s wait from 60s → **180s** (fetch + analysis both happen in background; if it times out, story still generates with empty patterns — graceful)
- `rag_patterns` flows into `s["user_profile"]` automatically via the shared dict; empty list when skipped/failed (safe for Step 4's skeleton)

### 4. Verify
- Standalone analyzer test against the **existing `rag/` files** (Inception etc. from Step 2's test) → inspect pattern JSON quality
- Full flow: JSON dump → wait → check `rag_patterns` populated in state
- py_compile + app build; log to `track/`

**Timing note:** analysis adds ~3-6s per file behind the scenes — the UI already shows live `[ANALYZE]...` status via the timer, so no dead screen.

One open question: **background chain** (recommended above, seamless) vs **synchronous on "Dive Into Story" click** (simpler, but blocks the button ~30s)?

### Confirmed decision — background chain (async)
Yes — exactly that. Same background chain, zero extra user involvement:

```
JSON dump in chat → background thread: fetch web content → [DONE]
    → immediately chained: analyze patterns (same thread, no new trigger)
    → set rag_fetch_done + fire event + "[DONE] Analysis complete"
```

The only thing the UI ever shows is live status via the timer: `[SEARCH] Fetching...` → `[ANALYZE] Extracting narrative patterns...` → `[DONE]`. By the time you click "Dive Into Story", `user_profile["rag_patterns"]` is already filled (the 180s wait is just a safety net). If analysis fails or times out, story still generates — patterns just stay empty.

---

## 2026-07-31 — Step 2: Redesigned Interview + Rich Profile + Full RAG Fetch

**What happened:** Rewrote the interview into 2 phases (Phase 1 = movie+game segments, Phase 2 = character segment). Rich nested user_profile (movies/games/writers as dicts with why-details + character segment). Fetcher now handles dict titles and uses per-category query templates. App detects direct JSON dumps in chat (no Gemma round-trip), fires fetch at phase-1 completion, waits bounded on "Dive Into Story", and shows LIVE fetch progress via gr.Timer polling.

**Result:** Verified end-to-end with a real fetch — profile merged, event fired, rag_done flag set, files saved to rag/movies/ with category-specific queries ("Inception plot analysis").

**Key decisions:** JSON-dump detection bypasses Gemma (guaranteed correctness + no wasted API call); threading.Event kept OUTSIDE gr.State in a module dict (id(s) pattern, avoids Gradio serialization risk); fresh rag/ per session (old .txt files cleared before fetch).

**Files:** prompts.py (rewrite), state.py (rewrite), rag/fetcher.py (rewrite), app.py (chat_fn, helpers, timer, wait logic, profile_refs)

**Known next:** rag/analyzer.py + pattern-aware skeleton_prompt (Steps 3-4). The gr.Timer ticks forever while app runs (cheap no-op when status unchanged).

## 2026-07-31 — Step 1: Web Search Ability

**What happened:** Created `rag/` folder structure, `rag/fetcher.py` with DuckDuckGo search + content fetch + file storage. Wired into `app.py`. Added UI feedback in Profile Interview tab.

**Result:** ✅ Works. Files appear in `rag/{stories,movies,gaming}/`. Fetch status shown in UI.

**Changes made in Step 1:**
- Created: `rag/__init__.py`, `rag/fetcher.py`
- Modified: `app.py` (import + fetch trigger + fetch_status UI), `state.py` (rag_fetch_status + rag_fetch_done fields), `AGENTS.md` (RAG section + build steps + no-exec rule), `BUILD_SPEC.md` (full rewrite), `requirements.txt` (added ddgs, requests, bs4, lxml), `track/track.md`

**Key decisions:** ddgs for free search, known-entity classification, category-specific queries, retry+delay for rate limits, daemon threads, BeautifulSoup for HTML stripping, URL skip list.

## 2026-07-31 — Step 1 fix: UI feedback

**What happened:** Added `fetch_status` Markdown component to Profile Interview tab. Shows "🔍 Searching..." immediately after profile capture. Status updated via state. Shows "Skipped" if user skips interview.

**Files:** `app.py`, `state.py`, `rag/fetcher.py`

## 2026-07-31 — Step 1 fix: Removed classifier logic

**What happened:** Removed KNOWN_MOVIES/GAMES/WRITERS lists, `_classify()` function, and subfolder routing. Now fetcher is direct: extract names from profile JSON → search DuckDuckGo → save ALL to `rag/` folder. Simpler, no hardcoded assumptions.

**Files:** `rag/fetcher.py` (full rewrite)
