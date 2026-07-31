# BUILD_SPEC.md — GemmaQuest: RAG-Powered Personal Narrative Engine

## Overview
Interactive movie-game-education hybrid. User picks a story card → deep profile interview (movies, games, character identity) → async web search fetches content about the user's favorite movies/games/writers → Gemma 4 analyzer extracts structural patterns → skeleton generator uses persona + pattern learnings to craft a story that structurally mirrors the user's actual taste.

---

## Tech Stack
| Component | Choice | Reason |
|---|---|---|
| Frontend + Backend | Gradio (Python) | Single file, no separate frontend needed |
| LLM | Gemma 4 via Google AI API (`google-genai`) | Only LLM allowed, core of solution |
| State | In-memory Python dict | Per-session, simple for demo |
| Web Search | `ddgs` (DuckDuckGo) + `requests` + `BeautifulSoup` | Free, no API key, runtime self-contained |
| HTML Strip | `lxml` via BeautifulSoup | Removes script/style/nav noise |

---

## File Structure
```
Gemma/
├── AGENTS.md              # Philosophy, rules, build-test steps
├── BUILD_SPEC.md           # THIS FILE — full architecture & plan
├── app.py                  # Main Gradio application
├── prompts.py              # All Gemma 4 prompts
├── state.py                # Session state structure
├── utils.py                # Shared parse_json (app.py + rag/analyzer.py)
├── rag/
│   ├── __init__.py
│   ├── fetcher.py          # DuckDuckGo search + content fetch + file storage
│   ├── analyzer.py         # Gemma 4 pattern extraction + patterns.json persistence
│   └── patterns/           # patterns.json — extracted learnings written to disk
├── requirements.txt        # gradio, google-genai, ddgs, requests, beautifulsoup4, lxml
└── track/                  # Track folder protocol
```

---

## Session State (`state.py`)
```python
{
    "step": "profile",            # profile | skeleton | playing | teaching | ending
    "user_profile": {},           # rich profile (below)
    "skeleton": {},
    "current_scene_index": 0,
    "total_scenes": 0,
    "story_context": "",
    "current_scene_data": {},
    "narrative_history": [],
    "knowledge_stats": {},
    "character_relationships": {},
    "story_flags": [],
    "current_challenge": None,
    "teaching_mode": False,
    "teaching_context": "",
    "pending_challenge": None,
    "ending_generated": False,
    "rag_fetch_status": "",       # shown in UI during fetch
    "rag_fetch_done": False,
    "fetch_started": False,
    "rag_patterns": [],           # DERIVED data — analyzer output, separate from user_profile
}
```
**Design rule:** `user_profile` is STATIC (only the interview/dump writes it). Everything derived lives at session level — `rag_patterns` (analyzer output), `story_context`, `narrative_history`, `knowledge_stats`, etc. Consumer prompts receive persona and pattern learnings as SEPARATE inputs (`skeleton_prompt(card, topics, persona_json, pattern_learnings_json)`).

---

## Target User Profile Structure (Step 2 goal — ✅ implemented in state.py + prompts.py)
```python
"user_profile": {
    # ─── MOVIE SEGMENT ───
    "movies": {
        "genres": ["sci-fi", "noir"],                    # genres that pull them in
        "favorites": [                                    # 2-3 movies, each with WHY
            {"title": "Inception",
             "what_liked": "mind-bending plot layers, emotional core",
             "unique": "dream-within-dream structure",
             "characters_loved": "Cobb — guilt-driven protagonist"}
        ],
        "character_types": ["anti-hero", "mentor with secrets"],  # character archetypes they love
        "writers_directors": ["Christopher Nolan", "Denis Villeneuve"]
    },
    # ─── GAME SEGMENT ───
    "games": {
        "genres": ["RPG", "immersive sim"],
        "favorites": [
            {"title": "Disco Elysium",
             "hooked_by": "dialogue system, no combat",
             "unique": "inner-voice mechanics",
             "characters_loved": "Harry — broken detective"}
        ],
        "hooked_elements": ["branching narrative", "meaningful choices", "atmosphere"]
    },
    # ─── CHARACTER SEGMENT (who the USER wants to BE) ───
    "character": {
        "wants_to_be": "strategist who outsmarts enemies",
        "resonated_with": ["Geralt of Rivia", "Cassandra Pentaghast"],
        "personality_traits": ["analytical", "morally flexible"],
        "decision_style": "calculated / gut / empathetic"
    }
}
```
**Note:** Implemented in Step 2 — the interview and fetcher use this rich structure. `rag_patterns` is NOT part of user_profile — it lives at session level (`state["rag_patterns"]`) because it is derived data, not a user statement. Example shape of one entry:
```python
{
    "source": "inception",
    "type": "movie",
    "patterns": {
        "structure": "layered non-linear timeline",
        "tension_building": "cross-cutting with rising stakes",
        "character_intro": "show expertise through action",
        "dialogue": "exposition disguised as conflict",
        "devices": ["time pressure as pacing tool"]
    }
}
```

---

## Interview Design (2-Phase)

### Phase 1 — Movie + Game Segment (TRIGGERS web fetch)
Questions are asked conversationally by Gemma, one at a time. User answers naturally.

**Movie segment:**
1. What movie genres pull you in?
2. Name 2-3 movies you love. What did you like most about each?
3. What made those movies unique or exceptional in your eyes?
4. What type of characters do you love in movies? (anti-hero? mentor? villain?)
5. Which writers/directors do you admire — whose work would you binge?

**Game segment:**
6. What game genres do you play?
7. Which games have gripped you the most? What was it about them?
8. What elements in a game attract you? (story, world-building, choices, loot, atmosphere)
9. Which game characters made you feel invested? Why?

**After Phase 1 → fire async web fetch thread** (user's movie/game/writer names are used for searching)

### Phase 2 — Character Segment (runs WHILE fetch happens in background)
10. What type of character do you want to BE in this story? (strategist? warrior? diplomat? detective?)
11. What fictional characters have you resonated with before? What about them hooked you?
12. What personalities do you get drawn to? (charisma? intellect? moral ambiguity?)
13. How do you make decisions under pressure — gut, logic, or emotion?

**After Phase 2 → wait for fetch if not complete → run analyzer → "Generate Story" button appears**
- **⚠️ DEVIATION (Step 2/3):** the button appears immediately after Phase 2/full dump (no wait). Fetch + analyzer run in a background chain; the bounded wait (≤180s) happens on the **"Dive Into Story" click**, and the button's loading state covers it.

---

## RAG Fetch Design (`rag/fetcher.py`)

### Flow
```
User answers Phase 1 → profile JSON extracted (movies/games/writers with names)
  → fetch_from_profile() reads profile keys:
      profile["movies"]   → save to rag/movies/
      profile["games"]    → save to rag/gaming/
      profile["writers"]  → save to rag/stories/
  → for each name → search DuckDuckGo with MULTIPLE query angles
  → fetch top 2 unique URLs per name → strip HTML → save as {sanitized_name}_N.txt
```

### Per-Category Query Templates (target for Step 2)
For **movies** (user's specific titles):
```
"{name} plot analysis"
"{name} story breakdown"
"{name} what makes it unique"
"{name} why is it exceptional"
"{name} character development analysis"
"{name} in-depth review"
```
For **games**:
```
"{name} plot analysis"
"{name} story breakdown"
"{name} what makes it unique"
"{name} game design analysis"
"{name} character development"
"{name} in-depth review"
```
For **writers** (their works / style):
```
"{name} writing style analysis"
"{name} story structure breakdown"
"{name} best works"
"{name} what makes their writing unique"
"{name} how they build characters"
```

### Current Implementation (Step 2 — what exists NOW)
- `rag/fetcher.py` — `_extract_names()` accepts **strings AND dicts** (`title` key); per-category query templates (`CATEGORY_QUERIES`); stale `rag/*.txt` + `rag/patterns/patterns.json` cleared per session; optional `done_event` (threading.Event) fired on completion
- Folder routing IS working: `profile["movies"]`→`rag/movies/`, `["games"]`→`rag/gaming/`, `["writers"]`→`rag/stories/`
- 3 retry attempts with 2s backoff, 3s delay between names, skips junk domains (discord/youtube/social/shopping), min 200 chars content
- Runs in daemon thread, progress reported via `status_setter` callback → UI Markdown, made **live** by `gr.Timer(1)` polling in `app.py`
- **Interview:** 2-phase (`prompts.py`) — Phase 1 movie+game questions, Phase 2 character questions; partial JSON after Phase 1, full JSON after Phase 2. If the user dumps complete profile info (incl. JSON) in one message, Gemma is instructed NOT to ask more and output the full profile immediately
- **JSON dump shortcut:** `chat_fn` first checks the raw user message with `parse_json` — if it parses to a profile dict, Gemma is bypassed entirely, profile merged, fetch fired (only once per session via `fetch_started` flag)
- **Wait logic:** `on_generate` waits bounded (60s) on the session fetch event before skeleton generation (`_fetch_events` module dict keyed by `id(s)`, kept OUTSIDE gr.State)
  - **⚠️ DEVIATION (Step 3):** the actual bounded wait is **180s**, not 60s — the event now fires only after the fetch **and** analyzer chain complete (`[DONE] RAG + pattern analysis complete.`).
- **Rich profile:** `user_profile` = `{movies: {genres, favorites: [{title, what_liked, unique, characters_loved}], character_types, writers_directors}, games: {genres, favorites: [{title, hooked_by, unique, characters_loved}], hooked_elements}, writers: [...], character: {wants_to_be, resonated_with, personality_traits, decision_style}}`
- Scene/ending personalization now reads the rich profile via `profile_refs()` (titles extracted from dicts) instead of the old flat `hooked_on`/`favorites` keys

---

## Analyzer Design (`rag/analyzer.py` — Step 3, ✅ BUILT)
```
Reads all files in rag/{movies,gaming,stories}/
For each file (cap 6, skips unreadable) → call Gemma 4 with pattern_extraction_prompt:
    "Analyze this content about {title}. Extract:
     1. Story structure & pacing
     2. How tension builds
     3. Character introduction style
     4. Dialogue patterns
     5. Narrative devices used
    Output structured JSON pattern notes."
Store results in state["rag_patterns"] (session level — derived data, NOT user_profile)
```
- Chained in the SAME background thread as the fetcher: fetcher `[DONE]` → analyzer runs → then `rag_fetch_done=True` + event + `[DONE] RAG + pattern analysis complete.`
- `parse_json` moved to `utils.py` to avoid circular imports
- Important: `max_tokens=1024` yields EMPTY replies for this prompt — analyzer uses 2048
- Patterns ALSO persisted to disk: `save_patterns_to_disk()` → `rag/patterns/patterns.json` (pretty JSON, graceful on failure; stale file cleared per session by the fetcher)

---

## Skeleton Generation (Step 4 — ✅ DONE 2026-07-31)
Before: `skeleton_prompt(card_info, topics, user_profile_json)`
After: `skeleton_prompt(card_info, topics, user_persona_json, pattern_learnings_json)`

Prompt adds critical section:
```
PATTERN LEARNINGS from user's favorite writers/movies/games:
{pattern_learnings_json}

Apply these structural techniques to the story. Example:
- If user's favorite writer uses non-linear timelines, mirror that
- If user's favorite game uses environmental storytelling, use sparse dialogue
- Match the pacing, tension curve, character introduction style
```

### Step 4 scope (✅ completed 2026-07-31)
1. **Profile schema completion — DONE (2026-07-31, pre-Step-4):** `INTERVIEW_JSON_FIELDS` extended to the full target structure — `movies.{genres, favorites, character_types, writers_directors}`, `games.{genres, favorites, hooked_elements}`. Fetcher `_extract_names()` and `profile_refs()` handle dict segments (writers_directors → rag/stories/) AND legacy list shapes for back-compat. Step 4 uses the completed persona.
2. **Pattern learnings reach SCENE generation too (not just skeleton):** `scene_prompt()` + `gen_scene()` + `_pregen_next()`/`_snapshot_state()` carry `pattern_learnings_json` — patterns influence pacing, tension curve, character intros, and dialogue style per scene, matching the user's stated intent. **Decision (user):** full pattern notes passed as-is, no trimming/top-N; skeleton max_tokens bumped 3072 → 4096.
3. **Test — DONE:** skeleton before/after patterns compared (WITH = 80s aesthetic, layered-dream structure, inner-voice character; WITHOUT = generic) + scene prose adopts the techniques.

---

## Testing Shortcut (Step 2)
Hidden textbox where tester pastes all answers as JSON → skips chat interview → straight to fetch → analyze → skeleton → play.

- **⚠️ DEVIATION (Step 2):** the hidden textbox was **never built** — replaced by pasting the full profile JSON **directly into the interview chat**. `chat_fn` parses the raw message via `parse_json`; if it's a profile dict, Gemma is bypassed entirely (no API call), profile is merged, fetch fires. Same result, different mechanism.

---

## Build-Test Steps (Build Small → Test → Proceed)

**Step 1: Web Search Ability — ✅ DONE**
- `rag/` folder structure + `rag/fetcher.py`
- ddgs search + requests + BeautifulSoup, file storage
- Folder routing by profile JSON key (movies/games/writers)
- Wired into `app.py` after profile capture, UI status Markdown
- Tested manually — files appear in correct subfolders

**Step 2: Redesigned Interview + Rich Profile + Full RAG Fetch — ✅ DONE**
- Rewrite `prompts.py` — 2-phase interview questions (as designed above)
- Rewrite `state.py` — rich nested user_profile structure (movies/games/character with details)
- Update `app.py` — Phase 1 → async fetch → Phase 2 → wait → proceed
- Per-category query templates in fetcher (movies/games/writers distinct)
- JSON-dump shortcut: paste full profile JSON directly in the chat → parsed client-side, Gemma bypassed, fetch fired
- Live fetch progress via gr.Timer polling
- **Tested:** Full dump → rag/ files in correct subfolders with category-appropriate queries; event + rag_fetch_done verified

**Step 3: Pattern Analyzer — ✅ DONE**
- Create `rag/analyzer.py` — reads rag/ content, calls Gemma 4 with pattern_extraction_prompt
- Structured patterns stored in `state["rag_patterns"]` (session-level derived data)
- Chained in the fetch background thread; wait bumped to 180s; utils.py holds shared parse_json
- **Tested:** 6/6 existing rag/ files analyzed with quality pattern JSON; full dump→fetch→analyze→state flow verified

**Step 4: Enhanced Skeleton + Pattern-Aware Scenes — ✅ DONE**
- `skeleton_prompt()` receives pattern_learnings_json (4th param) + PATTERN LEARNINGS apply-rules section
- Scene generation (scene_prompt/gen_scene/pregen) receives full pattern learnings (no trimming — user decision)
- `_snapshot_state` carries rag_patterns so the pregen thread sees them; skeleton max_tokens 3072 → 4096
- **Tested:** real fetch→analyze→generate run; skeleton WITH vs WITHOUT patterns compared — WITH mirrors Stranger Things 80s aesthetic, Inception layered-dream structure, Disco Elysium inner-voice character; scene prompt smoke test passed

---

## What Has Been Done So Far (log for new agents)

1. **Project setup complete** — Gradio app with 5 tabs (Landing, Profile Interview, Movie-Game, DSA Tutor, Ending), Netflix-style story cards, Gemma 4 via Google AI API, scene generation loop, challenge embedding, teaching window, ending generator.

2. **Step 1 complete — Web Search Ability:**
   - Created `rag/__init__.py`, `rag/fetcher.py`
   - `rag/fetcher.py`: ddgs search, requests+BeautifulSoup fetch, HTML stripping, junk domain skip list, 3 retries + 2s backoff, 3s delay between names, min 200 chars filter, files saved as `{sanitized_name}_N.txt`
   - Folder routing by profile key: `movies`→`rag/movies/`, `games`→`rag/gaming/`, `writers`→`rag/stories/`
   - Wired into `app.py`: after interview profile captured → `fetch_from_profile(p, status_setter=...)` fires in daemon thread
   - UI: `fetch_status` Markdown in Profile Interview tab shows `[SEARCH] Fetching {name} (i/total)...` → `[DONE] RAG content saved`
   - `requirements.txt`: added `ddgs`, `requests`, `beautifulsoup4`, `lxml`

3. **Step 2 complete — Redesigned Interview + Rich Profile + Full RAG Fetch:**
   - `prompts.py`: 2-phase interview (Phase 1 = 9 movie/game questions → partial JSON, Phase 2 = 4 character questions → full JSON), with the "don't ask if user provides complete profile info in one message" rule
   - `state.py`: rich nested `user_profile` (movies/games as dicts with why-details, character segment) + `fetch_started` flag
   - `rag/fetcher.py`: strings AND dicts extraction, per-category query templates, per-session rag/ clearing, `done_event` support
   - `app.py`: JSON-dump detection in chat (Gemma bypassed), phase-aware flow (Phase 1 → fetch, Phase 2 → gen button), bounded wait in `on_generate`, `gr.Timer(1)` live fetch status, `profile_refs()` for rich profile personalization
   - Verified: real fetch end-to-end (event set, rag_done=True, category-specific queries in saved files)

4. **Step 3 complete — Pattern Analyzer:**
   - `rag/analyzer.py`: reads rag/*.txt (cap 6 files), per-file Gemma analysis via `pattern_extraction_prompt`, RETURNS the pattern list (no mutation), skips failures gracefully
   - `utils.py`: `parse_json` moved here verbatim (shared by app.py + analyzer, no circular import)
   - `prompts.py`: `pattern_extraction_prompt` — 5 structural aspects → JSON per rag_patterns schema
   - `app.py`: analyzer chained in fetch thread on `[DONE]` (status `[ANALYZE] Extracting narrative patterns...` → `[DONE] RAG + pattern analysis complete.`); wait 60s → 180s; result assigned to `state["rag_patterns"]` (session level — profile stays static interview data)
   - Verified: standalone 6-file analysis (quality JSON), full dump→fetch→analyze flow

5. **Profile schema completed (2026-07-31, pre-Step-4):**
   - `prompts.py` `INTERVIEW_JSON_FIELDS` now matches the full Target Profile Structure: `movies.{genres, favorites, character_types, writers_directors}`, `games.{genres, favorites, hooked_elements}` (+ existing `writers`, `character`)
   - `state.py` default profile updated to the nested segment shape
   - `rag/fetcher.py` `_extract_names()` + `app.py` `profile_refs()` support dict segments AND legacy lists (back-compat); `writers_directors` maps to rag/stories/
   - Verified: schema renders as valid JSON; extraction tests pass for new + old shapes; app builds
   - Previously asked-but-lost answers (genres, character types, writer/director names, game elements) are now stored and fetchable

6. **Step 4 complete (2026-07-31) — Enhanced Skeleton + Pattern-Aware Scenes:**
   - `skeleton_prompt(card_info, topics, persona, pattern_learnings_json)` — PATTERN LEARNINGS section with apply-rules (non-linear timelines, tension curve, character intros, dialogue style); conditional on empty `[]`
   - `scene_prompt(..., pattern_learnings_json)` — same section for per-scene pacing/tension/dialogue mirroring
   - `app.py`: `on_generate` passes `s["rag_patterns"]` raw + max_tokens 4096; `_snapshot_state` gains `rag_patterns`; `_pregen_next`/`gen_scene` pass full notes into every scene call
   - Verified: 8 files fetched, 6 pattern notes, WITH-patterns skeleton adopted Stranger Things 80s aesthetic + Inception dream-layers + Disco Elysium inner-voice; py_compile + app build pass

7. **Pattern persistence to disk (2026-07-31, post-Step-4):**
   - `rag/analyzer.py`: `save_patterns_to_disk(patterns)` → `rag/patterns/patterns.json` (pretty JSON, same data as `s["rag_patterns"]`, graceful on failure)
   - `app.py`: called in the fetch→analyze background chain right after analysis
   - `rag/fetcher.py`: `_clear_subdirs()` also removes the stale patterns file per session (disk mirrors current session)
   - Verified: 5 notes written to disk; stale-file removal works; compile + app build pass

8. **Known limitations (next steps):**
   - Live browser demo needed: full interview → fetch → analyze → skeleton → scenes, eyeball prose quality
   - `max_tokens=1024` returns empty Gemma replies for pattern extraction — analyzer pinned to 2048 (also documented in fixes.md)
   - Spec deviations flagged in bold: wait is 180s (not 60s), testing shortcut is chat-dump (no hidden textbox), gen button appears before fetch/analyze completes
