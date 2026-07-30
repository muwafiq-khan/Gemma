# Track Log — 5-Liner Summaries

Each entry logs what the agent did, result, and key context.

---

## 2026-07-29 — Created track/ folder system + investigated old bugs

**What happened:** User asked to set up a tracking folder with files for critical updates, fixes, track logs, and bug reports. I also needed to copy existing content from the root into the new folder and investigate whether old bugs are actually fixed.

**Result:** All 4 files created. Existing content copied over from `crucial_updates.md` → `critical.md` and `BUG_REPORT.md` → `bug_report.md`. Investigated all NOT YET FIXED bugs by reading the current code.

**Key findings:** 3 of 4 NOT YET FIXED bugs are still unfixed. Bug #6 (profile interview auto-start) is implemented in code but depends on card selection JS bridge — needs user testing to confirm. Fixed an `app.py` syntax error (try/except indentation) along the way.

**Internal flow:** Read existing files → grepped codebase for each bug's relevant patterns → compared against BUG_REPORT.md claims → created folder structure → wrote files with copied content → noted findings with evidence links.

**Jargon explainer:** "JS bridge" = the JavaScript code in the HTML cards that talks to Gradio's Python backend. When you click a story card, JS sets a hidden textbox value and fires an event — if that event doesn't reach Python, the interview never auto-starts.

---

## 2026-07-29 — Wrote track protocol into AGENTS.md

**What happened:** User pointed out the track folder rules need to be in AGENTS.md so every agent session picks them up. I added the full Track Folder Protocol section to AGENTS.md.

**Result:** AGENTS.md now has a clear Track Folder Protocol section with rules for track.md, critical.md, fixes.md, and bug_report.md — plus writing style rules.

**Key context:** Without AGENTS.md instructions, a new agent session wouldn't know about the track folder system. Now any agent loading AGENTS.md will see the protocol in the instructions.

**Internal flow:** Read current AGENTS.md → found the right spot (before Winning Formula) → appended the protocol section in the same style as existing content → kept it concise and actionable.

**Jargon explainer:** "Agent session" = every time a new AI coding agent is spawned to work on this project. They read AGENTS.md as their instructions. If the protocol isn't there, they won't follow it.

---

## 2026-07-29 — Added git diff rule + terminal logging guide to AGENTS.md

**What happened:** User asked to add the `git diff` investigation method to AGENTS.md writing rules, AND wanted a way to give me direct terminal access without copy-pasting errors.

**Result:** AGENTS.md updated with two new sections: (1) git diff rule added to Writing Style Rules — always use git to confirm fixes, not just code reading. (2) Terminal Output Access section added — user can run `python app.py 2>&1 | tee app.log` and I can read the file directly.

**Key context:** Removed a duplicate "Critical Rule" section that was accidentally doubled in the file.

**Internal flow:** Read AGENTS.md → noticed duplicate section → removed it → appended git diff rule to Writing Style Rules → added Terminal Output Access section explaining the `tee` redirect approach → wrote track update.

**Plain language:** "tee is a way to copy terminal output into a file while still showing it on screen. Agent can then read the file to see errors without you needing to copy-paste anything."

---

## 2026-07-30 — Interview prompt refactor + token truncation fix

**What happened:** User added a 4th custom interview question but Gemma never asked it. Traced root cause: continuation prompt in `chat_fn()` hardcoded "3 topics" and didn't reference the actual question list. Also, scenes rendered as raw JSON — found via `app.log` that `max_tokens=2048` was truncating output mid-JSON, causing `parse_json` to fail.

**Result:** Refactored `prompts.py` to use shared `INTERVIEW_QUESTIONS` list + `INTERVIEW_JSON_FIELDS` dict. Both the full prompt and continuation prompt now build from the same source. Added `print()` statements for interview/skeleton debug logging. Bumped `max_tokens` from 2048/1024 → 4096.

**Key context:** The root cause chain was: low token limit → truncated JSON → parse_json fails → fallback shows raw reply as prose. The 4th question fix was structural — extracted hardcoded strings into a shared constant so adding questions only requires editing `prompts.py`.

**Internal flow:** Read app.log → found truncated JSON → traced to max_tokens=2048 in call_gemma → bumped to 4096 in both main and pregen calls. For interview: read both prompts.py (has Q4) and app.py (hardcodes "3 topics") → realized disconnect → refactored to shared INTERVIEW_QUESTIONS constant.

**Jargon explainer:** "max_tokens" limits how many tokens (roughly words + punctuation) the AI generates per response. If set too low, the AI stops mid-sentence and the JSON is incomplete. "parse_json" then can't find a valid JSON object and falls back to showing the raw, cut-off text. "Continuation prompt" = the prompt sent on every follow-up message during the interview — it was listing 3 questions while the initial prompt had 4. "Pregen cache" = background thread generates the next scene while user reads the current one, stores it in a dict so next scene loads instantly — but it was caching empty API errors too.

---

## 2026-07-30 — Pregen cache stores empty API failure, blocks retry

**What happened:** After Scene 1 rendered fine, clicking a choice showed "[Empty response from API. Using fallback scene.]". Pregen thread for Scene 2 had hit an API connection reset, cached the empty result, and the main thread trusted the cache over making a fresh call.

**Result:** Added `if reply:` guard in `_pregen_next()` so empty API responses are discarded instead of cached. The main `gen_scene()` now falls through to a fresh synchronous call when cache is empty.

**Key context:** The WinError 10053 (connection reset) is intermittent. The pregen thread ran into it, stored `""` in cache, and Scene 2 never got a chance to retry. The cache was poisoning the retry path.

**Internal flow:** User reports Scene 2 empty → read gen_scene code → trace `_check_pregen` → see it returns cached `""` → trace `_pregen_next` → see it stores unconditionally → guard with `if reply:`.

**Jargon explainer:** "Pregen" = short for pre-generation. A background thread that generates the next scene while you're still reading the current one, so when you click a choice it loads instantly. The bug was it cached API failures as valid results.
