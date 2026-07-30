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

ignore for now:
| 7 | **No loading indicators during API calls** — no spinner while waiting | **PARTIALLY FIXED** — Added `show_loading()` for the "Dive Into Story" button (`app.py:391`). Still missing for: choice clicks → next scene, challenge submission, teaching responses, ending generation. |
| 9 | **Model is `gemma-4-26b-a4b-it` (26B MoE)** — not the smallest E2B variant, higher latency | **NOT FIXED** — Still at `app.py:18`. E2B variant not available via Google AI API. |
