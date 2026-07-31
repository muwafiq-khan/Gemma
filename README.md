# GemmaQuest

try live: https://gemma-1.onrender.com/

🎮 **Where code becomes story** — an interactive movie-game-education hybrid where the user is the protagonist and Data Structures & Algorithms are the gameplay. Built for the *Build with Gemma 4* hackathon — Gemma 4 is the narrative engine, not a bolted-on chatbot.

**The core insight:** Learning isn't a separate activity or a reward — it *is* the gameplay. You must solve DSA problems to survive the story, giving learning immediate purpose and emotional stakes. Get an answer wrong? The story doesn't end — it takes a **darker turn** and adapts, exactly like a movie with consequences.

**Personalization engine:** your favorite movies, games, and writers are researched in real time (DuckDuckGo + web fetch), Gemma 4 extracts their *structural patterns* (pacing, tension curve, dialogue style, narrative devices), and your story is generated to mirror your taste.

---

## How It Works — User Flow

### 1. Landing page
Pick one of three story cards — **Dark Protocol** (cyberpunk thriller), **The Lost Algorithm** (adventure/mystery), or **Loop Zero** (sci-fi heist). Each card has a curated pool of ~10 DSA topics that fit its world.

### 2. Profile interview (Tab 2)
A Gemma-driven interviewer asks questions in two phases:
- **Phase 1** — movie & game taste (favorites, why they're unique, admired writers/directors, game hooks)
- **Phase 2** — character identity (who you want to *be*: strategist? warrior? diplomat?)

You can answer conversationally, say *"I'm ready"* to skip, or paste a complete profile JSON to jump straight in. Non-educational choices are everywhere — the interview itself is part of the game feel.

### 3. Story generation
Click **✨ Dive Into Story**. Gemma 4 generates a 7–10 scene story skeleton from: card genre + your persona + structural patterns extracted from your favorite media. The skeleton is a **beat structure, not a fixed script** — hard points (archetypes, destined events, arc) are anchored; everything between is generated dynamically, so your choices genuinely shape the story.

### 4. Playing (Tab 3)
Each scene is cinematic prose with 2–3 meaningful choices. Sidebar tracks:
- 🎭 **Characters** — relationship meters (♥) updated by who you side with
- 🧠 **Knowledge** — fluency bars per DSA concept

Most choices are narrative (talk to Mary or Kathy, go left or right). Occasionally a scene's plot demands a DSA challenge — framed as the **character** needing to figure something out to survive ("The lock requires the names arranged in a specific order..."), never as a quiz.

### 5. Challenge → wrong answer
Wrong answers never block the story. The character fails, a `{concept}_failed` flag is stored, and the story branches into a **darker turn** with permanent consequences.

### 6. Teaching window (Tab 4)
When stuck, click **📖 Learn this concept** — the story pauses (the character finds a safe space) and an **adaptive tutor** takes over, pre-loaded with: the concept, the challenge as the character experienced it, and your past performance on that concept. It teaches through story metaphors, checks understanding, and says `[READY]` when you can return to attempt the challenge (or skip — the story moves on regardless).

### 7. Ending
After the final scene, Gemma 4 writes a cinematic ending that references your specific choices, relationship scores, and DSA journey. Then replay with a fresh story.

---

## Behind the Scenes

```
Pick card ──► Interview Phase 1
                  │ Gemma extracts profile JSON (movies/games/writers)
                  ▼
          ┌─► [Background thread] DuckDuckGo search per name ──► fetch top pages
          │    rag/movies/, rag/gaming/, rag/stories/ (.txt)
          │    (interview Phase 2 continues meanwhile)
          │         ▼
          │    Gemma pattern analyzer: 5 structural aspects per source
          │    (structure, tension_building, character_intro, dialogue, devices)
          │         ▼
          │    rag_patterns ──► saved to rag/patterns/patterns.json
          ▼
      ✨ Dive Into Story
          ▼
      Gemma skeleton generator (card + persona + pattern learnings) → 7-10 beat scenes
          ▼
      Scene loop (pre-generated in background for the next scene)
          ▼
      Challenge → learn → adapt ──► Ending (choices + stats + relationships)
```

**Pipeline details:**
- **Async fetch chain** — web research starts the moment Phase 1 yields names, running in a daemon thread while the interview continues. On **✨ Dive Into Story** click, the UI waits up to 180s for the chain to finish, with live status polling (`gr.Timer`).
- **Scene pregeneration** — while you read a scene, the *next* one is already being written in a background thread against a snapshot of state (pregen cache keyed by session). This hides generation latency.
- **7 Gemma 4 roles** — interviewer, pattern analyst, skeleton generator, scene planner/generator, answer evaluator, adaptive tutor, ending writer. One model, seven functions — Gemma 4 *is* the engine.
- **Implicit stats** — every choice updates knowledge stats, character relationships, and story flags; these feed back into every subsequent scene prompt for personalization.
- **Context trimming** — story context and narrative history are windowed (last 1000 chars / 2 scenes) to keep prompts efficient.

---

## Key Design Decisions

| Decision | Why |
|---|---|
| **Beats, not branches** | Fixed trees are rigid; pure dynamic generation is risky. 7–9 skeleton beats anchor the arc; everything between is generated live. |
| **No retry, story flows forward** | Wrong answers produce a darker branch, never a dead end — feels like a movie with permanent consequences, no save-scumming. |
| **DSA = gameplay, not syllabus** | Challenges appear only when the plot demands them (agentic scene planning), so learning feels like survival, not homework. |
| **Learning is infrequent but meaningful** | Not every scene has a challenge — sparingly placed, story-stakes-loaded challenges make each one matter. |
| **RAG personalization** | User's favorite media researched live → structural patterns extracted by Gemma → mirrored in pacing, dialogue, and narrative devices of the generated story. |
| **Separate teaching window** | Story pauses (narratively justified) for focused tutoring; tutor is pre-loaded with the challenge, concept, and user's past performance. |
| **User profile is static; everything else derived** | Interview output lives in `user_profile`; derived data (`rag_patterns`, stats, history) lives at session level and is fed to prompts separately. |
| **Free-tier friendly** | No GPU, no credit card: Gemma 4 via Google AI API key, Gradio app hosted on Render free tier, DuckDuckGo (keyless) for web search. |

---

## Setup

```powershell
git clone https://github.com/muwafiq-khan/Gemma.git
cd Gemma

# Set your Google AI API key (https://aistudio.google.com/apikey)
$env:GOOGLE_API_KEY = "your_key_here"

pip install -r requirements.txt
python app.py
# Opens at http://127.0.0.1:7860
```

The key is read from `GOOGLE_API_KEY` env var (fallback: `local_config.py`, which is gitignored — never commit keys).

**Logs while running:**
```powershell
Start-Transcript -Path .\app.log; python app.py; Stop-Transcript
Get-Content .\app.log -Tail 50
```

**Render deploy:** the app binds `0.0.0.0`, reads `PORT` env var, and disables debug mode when `RENDER` is set. Set `GOOGLE_API_KEY` in Render's dashboard env vars.

---

## Architecture

```
app.py              # Gradio app — 5 tabs, event handlers, scene loop, pregen cache
prompts.py          # All 7 Gemma 4 role prompts (interview, patterns, skeleton, scene, tutor, ending)
state.py            # Session state schema
utils.py            # Robust parse_json (shared by app + analyzer)
rag/
├── fetcher.py      # ddgs search + HTML fetch → rag/{movies,gaming,stories}/.txt
├── analyzer.py     # Gemma pattern extraction → session + patterns.json
└── patterns/       # patterns.json (derived learnings, persisted per session)
track/              # Session log: track.md, fixes.md, bug_report.md
```

## Checkpoints

See `checkpoints.md` or `git tag -n`.

| Tag | What |
|---|---|
| `v0-success-base` | Working 8-scene flow: interview refactor, max_tokens, pregen fix, track system |
| `v1-blank-screen-fixed` | Full end-to-end: positional choice lookup fixes random blank screens |

To return: `git checkout tags/<tag-name>`

## Constraints honored

- Gemma 4 is the **only** LLM — 7 distinct agentic roles, all core to the experience
- Non-LLM tooling only where free: DuckDuckGo, BeautifulSoup, vector-free (JSON, no DB)
- Public repo, live demo on Render, writeup ≤ 1500 words
