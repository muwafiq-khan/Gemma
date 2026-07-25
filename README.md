# GemmaQuest — Where Code Becomes Story

An interactive narrative experience where **learning DSA is the gameplay**. Built with **Gemma 4** as the core narrative engine for the *Build with Gemma 4: ML, AI, Deep Learning & NLP Community Hackathon*.

> **Movie** × **Game** × **Education** = A new kind of learning experience

---

## The Vision

Most educational tools feel like school — detached problems, artificial exercises, zero stakes. Most games waste their potential by keeping learning separate from play.

**GemmaQuest fuses all three:**

- **Movie** — Cinematic story with plot, characters, atmosphere, and emotional arcs
- **Game** — Player agency, branching choices, consequences, and hidden stats
- **Education** — DSA challenges embedded naturally into the story's fabric

**The key insight:** Learning is not a separate activity or a reward — it *is* the gameplay. The user must solve DSA problems to progress the story, giving every learning moment immediate purpose and emotional stakes.

---

## Core Philosophy

### No Retry — Story Flows Forward

- Get a DSA challenge wrong? The story continues on a *different* branch, not a harder one
- Wrong ≠ Game Over. Wrong = a darker turn. The character fails and the movie adapts
- Permanent consequences, no save-scumming — just like a real movie

### Purposeful Learning

- DSA concepts are never force-embedded. Gemma 4 decides: "Does this concept fit naturally in this scene?"
- Learning feels like something the user *needs* to survive the moment
- Not every scene has a challenge — learning happens infrequently but meaningfully

### The User is the Dictator

- The user shapes major plot shifts through their choices
- Non-educational choices are abundant (talk to Jax or Nyx? Go left or right?)
- The system scaffolds, the user determines the path

### Personalization via Implicit Stats

Every session tracks:
- **Knowledge profile** — per-concept: correct/wrong ratio, fluency, mistake patterns
- **Character relationships** — who the user sided with (visible as hearts in the sidebar)
- **Story flags** — important events and choices that echo in later scenes
- **Engagement signals** — did they pause to learn? How many hints needed?

These stats feed back into Gemma 4's prompts to personalize every subsequent scene — the story literally adapts to how the user plays and learns.

---

## How It Works

```
User picks a story → Profile interview → Skeleton generation → Scene-by-scene gameplay → Ending
                          ↓                                                     ↑
                     Skip button                                        Teaching window
                                                                        (learn concepts)
```

### Step-by-Step Flow

1. **Landing Page** — User picks a story card (Cyberpunk Thriller, Sci-Fi Heist, or Adventure Mystery)

2. **Profile Interview** — Gemma 4 interviews the user conversationally about:
   - Favorite movies and games (to mirror their storytelling style)
   - DSA topics they find easy
   - DSA topics they find hard
   
   (Or click "Skip to story →" to jump straight in)

3. **Skeleton Generation** — Gemma 4 generates a 7-10 scene story skeleton with:
   - 2 DSA challenges that feel natural to the plot
   - 3 different endings based on user choices
   - Character archetypes fitting the genre

4. **Scene-by-Scene Gameplay** — For each scene:
   - Gemma 4 generates cinematic prose, atmosphere, dialogue
   - 2-3 meaningful choices appear
   - Some choices lead to DSA challenges (if the skeleton scheduled them)
   - Wrong answers = darker narrative branches, not dead ends
   - The next scene is pre-generated in the background for zero wait time

5. **Teaching Window** — When facing a DSA challenge:
   - Click "Learn this concept" to open the DSA Tutor tab
   - Gemma 4 teaches interactively, connecting back to the story
   - Return to the story when ready — the challenge is still there

6. **Ending** — After all scenes, Gemma 4 generates a cinematic conclusion that:
   - References specific choices the user made
   - Reflects their DSA journey (growth or struggle)
   - Leaves the user feeling like their choices mattered

---

## Gemma 4 — The Engine (Not a Chatbot)

Gemma 4 is **not** bolted on as a chatbot. It IS the entire engine, playing **7 distinct roles**:

| Role | Function |
|---|---|
| **Profile Analyzer** | Interviews user, builds preferences + knowledge profile |
| **Skeleton Generator** | Creates story structure from genre + profile + beat guidance |
| **Scene Generator** | Generates prose, choices, and challenge content for every scene |
| **Challenge Designer** | Embeds DSA problems naturally into the narrative |
| **Answer Evaluator** | Judges user solutions, provides contextual feedback |
| **Adaptive Tutor** | Teaches concepts in the learning window with story context |
| **Ending Generator** | Crafts conclusion based on accumulated stats + choices |

All 7 roles are the **same Gemma 4 model** steered by different prompts — making Gemma 4 indispensable to the solution.

---

## Architecture Decisions

### Beats, Not a Tree

- NOT a fixed branching tree (too rigid)
- NOT pure dynamic generation (too risky)
- **Hybrid approach:** 7-9 narrative beats as constraint anchors
- Hard points: certain character archetypes, destined events, overall arc
- Soft points: character development, paths taken, exact dialogue
- Everything between beats is dynamically generated by Gemma 4

### Background Pre-generation

- After a scene is served, a daemon thread immediately starts generating the next scene
- Result is cached per session
- When user clicks a choice, the next scene is served instantly from cache
- If pre-generation hasn't finished, falls back to synchronous generation

### Prompt Efficiency

- `story_context` truncated to last 1000 chars
- `narrative_history` limited to last 2 entries
- `upcoming_scenes` limited to next 2 scenes
- This reduces input tokens ~5x per API call

---

## Tech Stack

| Component | Choice | Reason |
|---|---|---|
| Frontend + Backend | **Gradio 6** | Single Python file, no separate frontend |
| LLM | **Gemma 4** (26B) via Google AI API | Free inference, no GPU required |
| State | **In-memory Python dict** | Per-session, simple for demo |
| Background tasks | **threading** | Pre-generation of next scenes |

### File Structure

```
Gemma/
├── app.py              # Main Gradio application (UI + logic + event handlers)
├── prompts.py          # All Gemma 4 prompt templates
├── state.py            # Session state factory
├── requirements.txt    # Dependencies
└── README.md           # This file
```

---

## Setup & Running

### Prerequisites

- Python 3.10+
- A Google AI API key (free from [aistudio.google.com/apikey](https://aistudio.google.com/apikey))

### Install

```bash
pip install -r requirements.txt
```

### Run

```bash
$env:GOOGLE_API_KEY = "your-api-key-here"
python app.py
```

The app launches at `http://localhost:7860`.

---

## DSA Challenge System

- Each story card has a pool of ~10 DSA topics
- Gemma 4 picks 2 per story during skeleton generation
- Challenges are framed as something the **character** needs to figure out — never as a meta "solve this problem"
- **Correct** → character pushes forward, knowledge stat improves
- **Wrong** → the story takes a darker turn, story flag recorded
- **Wrong results** are tracked and influence the ending — never punitively
- The teaching window opens with story context pre-loaded

---

## What Makes This Stand Out

| Criteria | How GemmaQuest Delivers |
|---|---|
| **Gemma Integration (30%)** | Gemma 4 is the entire engine — 7 distinct roles, no other LLM involved |
| **Innovation & Impact (30%)** | First narrative experience where learning DSA *is* the gameplay loop |
| **Functionality (20%)** | Working prototype with 3 storylines, full scene generation, teaching window |
| **Presentation (20%)** | Netflix-style UI, cinematic tone, polished dark theme |

---

## Built For

The *Build with Gemma 4: ML, AI, Deep Learning & NLP Community Hackathon* on Kaggle.

**Constraints respected:**
- ✅ Gemma 4 is the ONLY LLM
- ✅ No GPU, no credit card required (Google AI API free tier)
- ✅ Public GitHub repo + live demo
- ✅ Working prototype in 3 hours
- ✅ Writeup-ready architecture
