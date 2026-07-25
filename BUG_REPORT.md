# BUG FIX REPORT — GemmaQuest

---

## ✅ FIXED

| # | Bug | File:Line | Fix |
|---|---|---|---|
| 1 | **HF_TOKEN always `None`** — `os.environ.get()` used the token string as env var name | `app.py:16` | Replaced with raw token string |
| 2 | **Gemma 4 not deployed on HF Inference API** — `google/gemma-4-E2B-it` has no inference server, requests hung forever | `app.py:16-18` | Switched to **Google AI API** (`google-genai`) with `gemma-4-26b-a4b-it` |
| 3 | **Choice button outputs in wrong order** — `make_handler` sent scene data to wrong components (header→button, prose→button, characters→header, etc.) | `app.py:325` | Reordered `outputs=[state, tabs, hdr, prose, ca, cb, cc, ch_p, ch_i, ch_s, ln, ch_f, cd, kw, et]` |
| 4 | **Challenge view hides header & prose** — narrative text vanished when a challenge appeared | `app.py:307-315` | Replaced `H` with `gr.update()` for hdr/prose positions so they stay visible |
| 5 | **Landing page buttons don't switch tabs** — `gr.update(selected=1)` silently failed because tabs had no `id` attribute (Gradio 6 requires it) | `app.py:107,131,159,179,185` | Added `id=0` through `id=4` to all `gr.Tab()` calls |
| 6 | **`story_context` field exists but is never populated or passed to prompts** — each scene generated in isolation with no memory of prior scenes' actual prose (only skeleton metadata + choice log) | `app.py:251-253`, `prompts.py:76-78` | After each scene generation, append prose to `s["story_context"]`; pass it as `story_context` param to `scene_prompt` so Gemma sees the full narrative so far |
| 7 | **`narrative_history` entries lack scene prose** — history only stored `{scene_index, choice_text, type}`, so scene prompts had no concrete details from prior scenes to reference for continuity | `app.py:294-298` | Added `"prose": s.get("current_scene_data", {}).get("prose", "")` to each narrative history entry |
| 8 | **`skel_summary` strips the `scenes` array** — skeleton info passed to Gemma excluded all scenes (`{k: v for k, v in skel.items() if k != "scenes"}`), so the scene generator had no awareness of upcoming beats, challenges, or narrative arc | `app.py:230`, `prompts.py:76-78` | Changed to include full skeleton (no filter) + added explicit `upcoming_scenes_summary` param with remaining scenes for foreshadowing guidance |

---

## ❌ NOT YET FIXED

| # | Bug | Priority | Notes |
|---|---|---|---|
| 6 | **Profile interview doesn't auto-start** — chatbot loads empty, user must click "Send" with blank input to trigger first question | Medium | UX improvement for next round |
| 7 | **No loading indicators during API calls** — user sees no spinner/progress while waiting for Gemma 4 to respond | Low | Nice-to-have for demo polish |
| 8 | **"Generate My Story" button can appear while conversation still ongoing** — JSON detection in replies is fragile | Low | Edge case |
| 9 | **Model is `gemma-4-26b-a4b-it` (26B MoE)** — not the smallest E2B variant, slightly higher latency | Low | E2B not available via Google AI API |
