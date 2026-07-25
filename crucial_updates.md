# Crucial Updates

## 1. Prompt Truncation
- `story_context` now truncated to **last 1000 chars** (was: full growing history)
- `narrative_history` limited to **last 2 entries** (was: all entries, unbounded)
- `upcoming_scenes` limited to **next 2 scenes** (was: all remaining scenes)
- `skeleton_summary` reduced to **title + genre only** (was: full skeleton JSON)
- **Effect:** ~5x fewer input tokens per API call, drastically reducing latency per scene

## 2. Reduced Output Tokens
- Scene generation: **3072 → 1024** max_tokens
- Skeleton generation: **3072 → 1536** max_tokens
- **Effect:** ~50% faster per generation call

## 3. Background Pre-generation (Next Scene)
- After a scene is served, a **daemon thread** immediately starts generating the next scene in the background
- Result is cached in a thread-safe dict keyed by session + scene index
- When user clicks a choice, the next scene is **served instantly from cache** (zero API wait)
- If pre-generation hasn't finished yet, falls back to synchronous generation (same as before)
- **Effect:** After scene 1, all subsequent scenes feel instant

## 4. Profile Interview Caching
- The first interview question is **static** (always the same prompt)
- Now generated **once** and cached in `_profile_first_q` global
- Reused across all sessions — saves 1 API call per user
- **Effect:** Profile tab opens instantly, no spinner

## 5. Fixed Interview Loop (Critical Bug)
- **Root cause:** `chat_fn` (`app.py:268`) was re-sending the **full** `profile_interview_prompt()` (which says *"Ask the user these questions one at a time"*) with every user message, causing Gemma to restart the interview loop instead of progressing toward JSON completion
- **Fix:** Replaced with a short continuation prompt that only reminds Gemma of the 3 topics without re-asking them from scratch
- **JSON detection:** Changed fragile regex lookup (`"favorites":`) to full JSON parse + key check — catches JSON even if formatted differently
- **Skip button:** Added **"Skip to story →"** button so the user can always proceed if the interview gets stuck — never trapped
- **Helper text:** Added instruction *"Answer a few questions or just say 'I'm ready' to jump straight into the story"* above the chat

## Files Modified
- `app.py` — all changes above
- `prompts.py` — no changes needed (truncation happens at call site)
- `state.py` — no changes needed
