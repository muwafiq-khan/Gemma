# BUG FIX REPORT — GemmaQuest

---

## ✅ FIXED

| # | Bug | File:Line | Fix |
|---|---|---|---|
| 1 | **HF_TOKEN always `None`** — `os.environ.get()` used the token string as env var name | `app.py:16` | Replaced with raw token string |
| 2 | **Gemma 4 not deployed on HF Inference API** — `google/gemma-4-E2B-it` has no inference server, requests hung forever | `app.py:16-18` | Switched to **Google AI API** (`google-genai`) with `gemma-4-26b-a4b-it` |
| 3 | **Choice button outputs in wrong order** — `make_handler` sent scene data to wrong components | `app.py:325` | Reordered outputs list |
| 4 | **Challenge view hides header & prose** — narrative text vanished when a challenge appeared | `app.py:307-315` | Replaced `H` with `gr.update()` for hdr/prose |
| 5 | **Landing page buttons don't switch tabs** — `gr.update(selected=1)` silently failed because tabs had no `id` | `app.py` tabs | Added `id=0` through `id=4` to all `gr.Tab()` calls |
| 6 | **`story_context` never populated** — each scene generated in isolation with no memory of prior scenes | `app.py` | Append prose to `story_context` after each scene; pass to `scene_prompt` |
| 7 | **`narrative_history` entries lack scene prose** — prompts had no concrete details for continuity | `app.py:294-298` | Added `"prose"` field to each narrative history entry |
| 8 | **Scene generator had no awareness of upcoming beats** — skeleton info excluded scenes array | `app.py:230` | Added `upcoming_scenes_summary` param with remaining scenes |
| 9 | **Interview continuation prompt hardcodes question count** — adding Q4 to prompts.py not reflected in chat_fn | `app.py:309-316` | Refactored to shared INTERVIEW_QUESTIONS constant in prompts.py |
| 10 | **Scene JSON truncated** — 2048/1024 tokens too low, rich prose cut off mid-JSON, parse_json fails | `app.py:487,151` | Bumped both to 4096 |
| 11 | **Pregen cache stores empty API failure** — background thread caches `""`, main thread trusts cache, never retries | `app.py:153-154` | Added `if reply:` guard before `_store_pregen` |
| 12 | **Choice click causes blank screen** — `call_gemma` uses `temperature=0.8`, so the model sometimes outputs choice IDs as integers (`"id": 1`) or non-standard strings instead of `"id": "a"`/`"b"`/`"c"`. The old `on_choice` did string match `c["id"] == cid`, found no match, returned `*([H]*13)` hiding all components including tabs. | `app.py:532-540` | Changed to positional lookup: button A → `choices[0]`, B → `choices[1]`, C → `choices[2]` via `CID_IDX` dict. Model's ID value no longer matters — position is always consistent. |
| 13 | **`UnboundLocalError: cannot access local variable 'prompt'` at scene ~6** — pregen cache hit path crashed. `prompt` is assigned only inside `if reply is None:` (cache MISS branch), but `reply = call_gemma(prompt)` sat OUTSIDE that block. When the background pregen thread finished in time (cache HIT), `prompt` was never assigned → crash. Introduced in Step 4 commit `1f1d9d4` (reformatted the `scene_prompt` call when `pattern_learnings_json` was added and accidentally dedented the call line out of the block). Hit at scene 6 only because of timing: earlier scenes clicked before pregen finished (cache miss), scene 6 was the first where reading time exceeded background generation time. | `app.py:583` (pre-fix), now inside the block + `else: print("[PREGEN] ... cache hit")` | Moved `call_gemma(prompt, ...)` back inside `if reply is None:`; cache-hit path now skips the API call and logs `[PREGEN] scene N cache hit`. |
| 14 | **Terminal shows `http://0.0.0.0:7860` instead of the old `127.0.0.1`** — server actually fine (127.0.0.1 still worked), but 0.0.0.0 is not browser-navigable, so the printed URL appeared dead. Introduced by Render deploy commit `8137fd4` (`server_name="0.0.0.0"` unconditional). | `app.py:760` | `server_name="0.0.0.0" if on_render else "127.0.0.1"` — Render keeps 0.0.0.0 bind; local runs print the clickable 127.0.0.1 URL again. Verified both paths. |

ignore for now:
| 7 | **No loading indicators during API calls** — no spinner while waiting | **PARTIALLY FIXED** — Added `show_loading()` for the "Dive Into Story" button (`app.py:391`). Still missing for: choice clicks → next scene, challenge submission, teaching responses, ending generation. |
| 9 | **Model is `gemma-4-26b-a4b-it` (26B MoE)** — not the smallest E2B variant, higher latency | **NOT FIXED** — Still at `app.py:18`. E2B variant not available via Google AI API. |

---

# DETAILED BUG REPORTS

## BUG A — Raw JSON shown in some scenes (the "story broke" bug)

### 1. Symptom

- During play, **some scenes** (observed: scenes 3, 5, 6 of one run) displayed the **raw JSON output** instead of story prose — the full machine text with `{`, `"prose":`, `"choices":`, `"challenge":` visible to the user.
- Instead of 2-3 meaningful choice buttons, the broken scene often showed only a single "Continue" button.
- Other scenes worked fine — the story seemed fine until a scene suddenly "broke", and the broken scene's raw text polluted later scenes.

### 2. Findings

**How a scene becomes raw JSON (the code path):**

1. `gen_scene()` (`app.py:556-595`) asks Gemma 4 for the scene and gets back a raw text reply that is *supposed* to be JSON (prose + choices + optional challenge).
2. `parse_json()` (`utils.py:1-46`) tries to turn that text into a Python dict. It handles markdown fences, trailing commas, and even grabs a balanced `{...}` block out of surrounding text.
3. **If parsing fails**, the code does NOT show an error — it silently falls back: `sd = {"prose": reply, "choices": [{"id": "a", "text": "Continue", ...}]}` (`app.py:593-595`). The **raw reply becomes the scene text**. That is exactly the raw JSON the user saw. The "Continue" button is the fallback's single choice.

**Why parsing failed — the smoking gun (from user's `app.log`):**

All 3 logged failures (`[DEBUG] parse_json FAILED. Full reply:`) have the **identical, tiny defect** — always on choice **b**:

```json
"text "\"There has to be a way to break the cycle. I need to find the base case.\"",
```

The key is `"text "` — **with a trailing space and the colon missing** — so the key and value are two strings sitting next to each other with no `:`, which is not valid JSON. Compare the correct siblings (choices a, c) in the same replies:

```json
"text": "\"I'll just run faster! I can break through the loop!\"",
```

Every other part of the three failed replies (prose, other choices, challenge object, `show_learn_button`) is **complete and well-formed** — the JSON is NOT truncated, NOT wrapped weirdly. It dies on this one missing colon.

**Root cause:** a **Gemma 4 output quirk** (temperature 0.8) — the model occasionally emits a choice object as `"text "<value>` instead of `"text": <value>`. In the captured run it happened on the challenge scenes and the dark-moment scene, always on the second choice. `parse_json` has no repair for a missing colon → returns `None` → fallback → raw JSON displayed.

**My earlier hypothesis was WRONG:** I initially suspected token truncation (4096-token cap cutting long scenes mid-JSON — same bug class as table entry #10). The log proved otherwise: the failed replies are complete, closed JSON with one malformed key.

**Cascade damage:** the raw JSON is also appended to `story_context` (`app.py:604`), so every later scene's prompt gets the garbage injected — one bad scene degrades the rest of the run.

**Bonus — unifies a previous bug:** this same root cause explains the earlier "📖 Learn this concept button missing + no text input" report. When parse fails, the fallback scene contains `"challenge": None` and no challenge UI is ever shown. **One model defect, two symptoms.**

### 3. Suggested plan (root-cause fix — no quality compromise)

1. **`utils.py parse_json` — add a JSON repair pass** before the existing parse attempts: find any quoted string immediately followed by whitespace + another quoted string (`"<key>" <ws> "`) and insert the missing colon → `"<key>": <ws> "`. Two adjacent strings are *impossible* in valid JSON, so the repair can only ever fire on this exact model defect. Surgical, targeted, preserves all quality.
2. **Pregen guard:** in `_pregen_next` (`app.py:169-204`), only cache a background-generated reply if `parse_json(reply)` succeeds. This also fixes a **latent bug**: non-empty API-error strings (e.g. `"[Need a valid Google AI API key...]"`) are currently cached and could be delivered as a "scene".
3. **`story_context` guard:** only append `p` to `story_context` if it isn't JSON-shaped (doesn't start with `{`) — belt-and-braces so one bad reply can never poison later scenes.
4. **Verify:** `py_compile` + a standalone test that runs `parse_json` against the **exact 3 failing replies from the log** — all must now parse into scene dicts with choices/challenges intact.

### 4. Worked?

**YES — FIXED and verified (2026-08-01).**

- **`utils.py` — `_repair_json()`** added and wired into `parse_json` (after fence-strip, before all parse attempts). It finds any string token (no colons inside, since keys never contain them) followed by optional whitespace + optional stray backslash + a quote — impossible in valid JSON — and inserts the missing colon, dropping the stray backslash. A second pass normalizes keys with a trailing space (`"text ":` → `"text":`).
- **`app.py` — pregen guard:** `_pregen_next` now only caches a background reply if `parse_json(reply)` succeeds (`if reply and parse_json(reply):`) — also fixes the latent bug where non-empty API-error strings got cached and delivered as scenes.
- **`app.py` — story_context guard:** JSON-shaped prose (starts with `{`) is no longer appended to `story_context`, so a bad reply can't poison later scene prompts.
- **Verified:** standalone test ran the **exact 3 failing replies from the user's log** through `parse_json` — all 3 now parse: prose 1312/1459/1831 chars, 3 choices each, choice-b text extracted cleanly, challenge objects intact (recursion/backtracking/null). Regression checks pass: valid JSON, escaped quotes inside values, and trailing-space keys all handled without touching valid content. `py_compile` + app import pass.
- **The false-match bug during development:** the first repair regex initially matched `": "` (quote-colon-space) inside valid `"text": "..."` spots — fixed by excluding colons from token content (`[^"\\:]`), since scene JSON keys never contain colons.

---

## BUG B — "cannot access local variable 'prompt'" during scene generation (scene ~6) — ✅ FIXED

### 1. Symptom

- During play, around **scene 6**, the scene area showed an error instead of the story: `## ⚠️ Error in Scene` with the message `cannot access local variable 'prompt' where it is not associated with a value`.
- Scenes 1-5 worked; the crash appeared only later in the story.

### 2. Findings

**The code path (the race):**

1. When scene N is displayed, `gen_scene()` spawns a background thread (`_pregen_next`) that pre-generates scene N+1 and stores the raw reply in an in-memory cache (`_pregen_cache`, keyed by session id + scene index).
2. When the user clicks a choice, `gen_scene()` for scene N+1 first checks the cache: `reply = _check_pregen(s, idx)` (`app.py:556`).
   - **Cache MISS** (background thread not done yet) → `if reply is None:` → builds the prompt → `prompt = scene_prompt(...)` → calls the API. Works.
   - **Cache HIT** (thread finished in time) → the `if` block is skipped → `prompt` was **never assigned**.
3. But the API call line — `reply = call_gemma(prompt, max_tokens=4096)` — sat **OUTSIDE** the `if reply is None:` block (at the same indent level as the `if`, `app.py:583`). On a cache HIT it tried to read `prompt`, which didn't exist in this scope → Python raises `UnboundLocalError` (Python 3.11+ wording: "cannot access local variable..."). `gen_scene`'s outer try/except catches it and shows the raw error in the UI.

**Why scene 6 (and not earlier):** pure **timing race**, not scene-specific. The pregen thread takes ~15-60s (API call). At scenes 1-5 the user clicked before the thread finished → cache MISS → `prompt` built → fine. At scene 6 the user's reading time exceeded the background generation time → first cache HIT → first crash. Any scene could hit it.

**When was it introduced:** the **Step 4 commit `1f1d9d4`** ("pattern-aware skeleton + scenes"). When `pattern_learnings_json` was added to `scene_prompt`, the call was reformatted and the `call_gemma` line was accidentally dedented out of the `if` block. Proven via git: `git show 1f1d9d4^:app.py` has the line **inside** the block (24 spaces); after the commit it's at 20 spaces, outside.

### 3. Suggested plan

1. Move `reply = call_gemma(prompt, max_tokens=4096)` back **inside** the `if reply is None:` block — cache HIT → use the cached reply and skip the API call entirely; cache MISS → build prompt → call.
2. Add an `else:` branch printing `[PREGEN] scene N cache hit (background thread)` for visibility.
3. Verify: `py_compile`, trace both paths (hit and miss), confirm all other `call_gemma(prompt)` sites (pregen thread, ending, tutor) assign `prompt` before use.

### 4. Worked?

**YES — FIXED and verified (2026-08-01).**

- `app.py:583-585` — the call is now inside the block, with the cache-hit log line.
- `python -m py_compile app.py` → OK.
- Traced both paths: cache HIT → uses cached reply, no API call, logs `[PREGEN] scene N cache hit`; cache MISS → builds prompt → calls API.
- All 4 `call_gemma(prompt, ...)` call sites audited (lines 199, 542, 583, 724) — every one assigns `prompt` before reading it.
- User's later test run (`app.log`) shows `[PREGEN] scene 2 cache hit` and `[PREGEN] scene 4 cache hit` — the cache-hit path now works instead of crashing.
- Logged in `track/track.md` (2026-08-01 entry). **Note:** fix is in the working tree only — commit + push still pending.

### 5. ⚠️ REGRESSED ON RENDER — Bug B "came back" (2026-08-01)

**Symptom:** On Render, after Gemma generates scene 1, clicking any choice crashes:
```
File "/opt/render/project/src/app.py", line 583, in gen_scene
    reply = call_gemma(prompt, max_tokens=4096)
UnboundLocalError: cannot access local variable 'prompt' where it is not associated with a value
```
Locally the same click works (`[PREGEN] scene N cache hit` logs). **Not a new bug — a stale deployment.** Render auto-deploys from GitHub commits; the last commit is `8e7fec6` (Jul 31), which still contains the pre-fix code. **Verified with `git show HEAD:app.py`:** lines 557-583 — `prompt = scene_prompt(...)` is inside `if reply is None:` but `reply = call_gemma(prompt, ...)` sits OUTSIDE at line 583 (same indent as the `if`). Cache HIT → `prompt` never assigned → crash. The local working tree has the fix (call moved inside the block + `else: print("[PREGEN] ... cache hit")`) but it was **never committed/pushed** (bug_report.md itself warned: "fix is in the working tree only — commit + push still pending").

**Status:** ❌ NOT YET FIXED ON RENDER — fix exists locally, requires commit + push → Render redeploy.

**Common pattern discovered (both Render-only bugs):** every bug seen on Render but not locally = a fix sitting uncommitted in the working tree while Render runs the stale last commit (`8e7fec6`). Same for Bug A (JSON repair in `utils.py` `_repair_json`) and the pregen/story_context guards. **Lesson: after any fix, commit + push immediately, then verify on Render.**

---

## BUG C — `TypeError: argument of type 'int' is not iterable` in `chat_fn` — 🟡 UNDER OBSERVATION

### 1. Symptom

- During the interview, after sending a message, the app crashes with:
```
File "/opt/render/project/src/app.py", line 360, in chat_fn
    is_dump = dumped is not None and any(
File "/opt/render/project/src/app.py", line 361, in <genexpr>
    k in dumped for k in ("movies", "games", "writers", "character")
TypeError: argument of type 'int' is not a container or iterable
```
- User first believed it happened during story generation; evidence shows it can only fire from the interview **Send** button (`send.click`, line 406 — the only wiring for `chat_fn`; no `.submit()` handlers exist; story generation never calls `chat_fn`).

### 2. Findings

**Root cause:** `parse_json(msg)` uses `json.loads` directly. A bare-number message is valid JSON: `parse_json("5")` → `5` (int), `"10"` → `10`, `"3.5"` → `3.5` (float), `"true"` → `True` (bool). Then `any(k in dumped ...)` does `"movies" in 5` → TypeError. Reproduced locally (Python 3.13): identical crash.

**Why it feels like story-generation time:** the green signal ("✅ Profile locked in") comes from the SAME `is_dump` code — that send succeeds first. A later send with a numeric message (leftover number in the box, or answering a follow-up question with e.g. "5") crashes. On crash, Gradio does NOT clear the textbox → the number stays → every Send press re-crashes identically → 6 identical tracebacks in the log.

**Latent instances of the same class:** anywhere `parse_json` output is consumed as a dict without a type check — `app.py:392-394` (`p.get` on Gemma reply), `:447` (skeleton), `:590` (scene). If the model ever replies with a bare number, each would crash too.

### 3. Status / Decision

**🟡 UNDER OBSERVATION (user decision, 2026-08-01).** Not reproducible in normal play (needs a bare-number chat message). No fix applied yet — do not close. Proposed fix when approved: `parse_json` returns only dict/list results (everything else → `None`), plus `isinstance(dumped, dict)` guard at `chat_fn`.

---

