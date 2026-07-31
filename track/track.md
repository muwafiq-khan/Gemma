# Track Log

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
