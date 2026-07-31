# GemmaQuest

🎮 **Where code becomes story** — an interactive movie-game-education hybrid powered by Gemma 4. Your favorite movies/games/writers are researched in real time, their structural patterns are extracted by Gemma, and your story is built to mirror your taste.

## 🎮 Play the demo

Live at **Render free tier** (URL pending — see track log). Pick a story card → answer a few questions (or paste a profile JSON) → the engine researches your taste → you play your personalized story.

## Setup on a new machine

```powershell
# 1. Clone
git clone https://github.com/muwafiq-khan/Gemma.git
cd Gemma

# 2. Set API key (get one at https://aistudio.google.com/apikey)
$env:GOOGLE_API_KEY = "your_key_here"

# 3. Install deps
pip install -r requirements.txt

# 4. Run
python app.py
# Opens at http://127.0.0.1:7860
```

## To see logs while running

```powershell
Start-Transcript -Path .\app.log; python app.py; Stop-Transcript
# Then read: Get-Content .\app.log -Tail 50
```

## Checkpoints

See `checkpoints.md` or `git tag -n`.

| Tag | What |
|---|---|
| `v0-success-base` | Working 8-scene flow: interview refactor, max_tokens, pregen fix, track system |
| `v1-blank-screen-fixed` | Full end-to-end: positional choice lookup fixes random blank screens |

To return: `git checkout tags/<tag-name>`
