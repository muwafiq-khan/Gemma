import json
import os
import threading
from google import genai

import gradio as gr
from state import new_session, default_user_profile
from utils import parse_json
from rag.fetcher import fetch_from_profile
from rag.analyzer import analyze_rag_content, save_patterns_to_disk
from prompts import (
    profile_interview_prompt,
    skeleton_prompt,
    scene_prompt,
    teaching_prompt,
    ending_prompt,
    pattern_extraction_prompt,
)

GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", "")
if not GOOGLE_API_KEY:
    try:
        from local_config import GOOGLE_API_KEY as _local_key
        GOOGLE_API_KEY = _local_key
    except ImportError:
        pass
if not GOOGLE_API_KEY:
    raise RuntimeError("GOOGLE_API_KEY not set. Set the environment variable or create local_config.py (see README). Get a key at https://aistudio.google.com/apikey")
MODEL = "gemma-4-26b-a4b-it"
client = genai.Client(api_key=GOOGLE_API_KEY)

_pregen_cache = {}
_pregen_lock = threading.Lock()
_profile_first_q = None
_fetch_events = {}


def profile_refs(prof):
    """Extract display names from rich profile. Handles dict segments
    (movies {favorites, writers_directors}, games {favorites}) AND legacy lists."""
    refs = []

    def add(items):
        for item in items or []:
            if isinstance(item, dict):
                title = (item.get("title") or "").strip()
                if title:
                    refs.append(title)
            elif isinstance(item, str) and item.strip():
                refs.append(item.strip())

    movies = prof.get("movies")
    if isinstance(movies, dict):
        add(movies.get("favorites", []))
        add(movies.get("writers_directors", []))
    elif isinstance(movies, list):
        add(movies)

    games = prof.get("games")
    if isinstance(games, dict):
        add(games.get("favorites", []))
    elif isinstance(games, list):
        add(games)

    add(prof.get("writers", []))
    return refs


def _merge_profile(s, p):
    prof = s.get("user_profile") or {}
    for k in ("movies", "games", "writers", "character"):
        if k in p:
            prof[k] = p[k]
    s["user_profile"] = prof


def _start_fetch(s):
    if s.get("fetch_started"):
        return
    s["fetch_started"] = True
    ev = threading.Event()
    _fetch_events[id(s)] = ev
    s["rag_fetch_status"] = "[SEARCH] Looking up your movies/games/writers..."

    def analyze_status(msg):
        s["rag_fetch_status"] = msg
        print(f"[ANALYZE] {msg}")

    def status_setter(msg):
        s["rag_fetch_status"] = msg
        print(f"[FETCH STATUS] {msg}")
        if msg.startswith("[DONE]") and not s.get("rag_fetch_done"):
            s["rag_fetch_status"] = "[ANALYZE] Extracting narrative patterns from fetched content..."
            print("[ANALYZE] Extracting narrative patterns from fetched content...")
            try:
                s["rag_patterns"] = analyze_rag_content(
                    status_setter=analyze_status,
                    call_gemma=call_gemma,
                    pattern_prompt=pattern_extraction_prompt,
                )
                save_patterns_to_disk(s["rag_patterns"])
                print(f"[ANALYZER] s['rag_patterns'] now holds {len(s['rag_patterns'])} notes")
            except Exception as e:
                print(f"[ANALYZER] Analysis failed (continuing): {e}")
            finally:
                s["rag_fetch_done"] = True
                s["rag_fetch_status"] = "[DONE] RAG + pattern analysis complete."
                ev.set()
        elif msg.startswith("[SKIP]"):
            s["rag_fetch_done"] = True
            ev.set()

    fetch_from_profile(s["user_profile"], status_setter=status_setter, done_event=ev)


def call_gemma(prompt, max_tokens=2048):
    try:
        response = client.models.generate_content(
            model=MODEL,
            contents=prompt,
            config={
                "max_output_tokens": max_tokens,
                "temperature": 0.8,
                "top_p": 0.95,
            },
        )
        return response.text or ""
    except Exception as e:
        msg = str(e)
        if "API_KEY" in msg or "key" in msg.lower() and "invalid" in msg.lower():
            return "[Need a valid Google AI API key from https://aistudio.google.com/apikey]"
        return f"[API Error: {msg[:200]}]"


def _check_pregen(s, idx):
    key = id(s)
    with _pregen_lock:
        if key in _pregen_cache and idx in _pregen_cache[key]:
            reply = _pregen_cache[key].pop(idx)
            if not _pregen_cache[key]:
                del _pregen_cache[key]
            return reply
    return None

def _store_pregen(key, idx, reply):
    with _pregen_lock:
        if key not in _pregen_cache:
            _pregen_cache[key] = {}
        _pregen_cache[key][idx] = reply

def _snapshot_state(s, next_idx):
    scenes = s.get("skeleton", {}).get("scenes", [])
    upcoming = scenes[next_idx:] if next_idx < len(scenes) else []
    return {
        "scenes": scenes,
        "current_scene_index": next_idx,
        "total_scenes": len(scenes),
        "story_context": s.get("story_context", ""),
        "narrative_history": list(s.get("narrative_history", [])),
        "knowledge_stats": dict(s.get("knowledge_stats", {})),
        "character_relationships": dict(s.get("character_relationships", {})),
        "story_flags": list(s.get("story_flags", [])),
        "user_profile": dict(s.get("user_profile", {})),
        "rag_patterns": list(s.get("rag_patterns", [])),
        "next_upcoming": upcoming[:2],
    }

def _pregen_next(s, next_idx):
    snap = _snapshot_state(s, next_idx)
    key = id(s)
    def _gen():
        try:
            info = snap["scenes"][snap["current_scene_index"]]
            skel = {"title": s.get("skeleton", {}).get("title", ""), "genre": s.get("skeleton", {}).get("genre", "")}
            skel_summary = json.dumps(skel)
            refs = json.dumps(profile_refs(snap["user_profile"]))
            ctx = snap["story_context"]
            if len(ctx) > 1000:
                ctx = "..." + ctx[-1000:]
            nh = snap["narrative_history"]
            if len(nh) > 2:
                nh = nh[-2:]
            prompt = scene_prompt(
                skeleton_summary=skel_summary,
                scene_id=info["scene_id"], beat=info.get("beat", ""),
                summary=info.get("summary", ""),
                has_challenge=info.get("has_challenge", False),
                dsa_concept=info.get("dsa_concept", None),
                narrative_history=json.dumps(nh),
                knowledge_stats_json=json.dumps(snap["knowledge_stats"]),
                character_relationships_json=json.dumps(snap["character_relationships"]),
                story_flags=json.dumps(snap["story_flags"]),
                hooked_on_references=refs,
                story_context=ctx,
                upcoming_scenes_summary=json.dumps(snap["next_upcoming"]),
                pattern_learnings_json=json.dumps(snap.get("rag_patterns", [])),
            )
            reply = call_gemma(prompt, max_tokens=4096)
            if reply:
                _store_pregen(key, next_idx, reply)
        except Exception:
            pass
    threading.Thread(target=_gen, daemon=True).start()

STORY_CARDS = [
    {"id": "dark_protocol", "title": "Dark Protocol", "subtitle": "A city's AI went rogue. Your code is the last firewall.", "genre": "Cyberpunk Thriller",
     "hook": "In a city where data is the new opium, one hacker holds the key to salvation — and it's written in code.",
     "gradient": "#0f0c29, #302b63, #24243e", "badge": "CYBERPUNK",
     "topics": ["sorting", "binary_search", "hash_maps", "string_matching", "arrays", "two_pointers", "sliding_window", "prefix_sum", "bit_manipulation", "greedy"]},
    {"id": "the_lost_algorithm", "title": "The Lost Algorithm", "subtitle": "Ancient ruins hide the Algorithm of Creation.", "genre": "Adventure / Mystery",
     "hook": "Every chamber is a riddle. Every riddle is a test of logic. The Algorithm of Creation awaits.",
     "gradient": "#1a0a00, #4a2500, #1a0a00", "badge": "ADVENTURE",
     "topics": ["recursion", "backtracking", "dfs", "bfs", "divide_conquer", "memoization", "tree_traversal", "graph_cycles", "topological_sort", "union_find"]},
    {"id": "loop_zero", "title": "Loop Zero", "subtitle": "A quantum heist trapped in a recursive time loop.", "genre": "Sci-Fi Heist",
     "hook": "The perfect crime doesn't exist. Not unless you can break the loop.",
     "gradient": "#0a0015, #2a0050, #001530", "badge": "SCI-FI",
     "topics": ["recursion", "dp", "graphs", "dijkstra", "lcs", "knapsack", "segment_tree", "fenwick", "shortest_path", "mst"]},
]


def render_knowledge(state):
    ks = state.get("knowledge_stats", {})
    lines = []
    for t, s in ks.items():
        if s["attempts"] > 0:
            pct = int(s["correct"] / max(s["attempts"], 1) * 100)
            bar = "█" * (pct // 10) + "░" * (10 - pct // 10)
            lines.append(f"**{t}:** {bar} {pct}%")
    return "\n".join(lines) if lines else "No challenges attempted yet."


def render_characters(state):
    rels = state.get("character_relationships", {})
    if not rels:
        return "Meet characters as the story unfolds."
    parts = []
    for name, val in rels.items():
        hearts = "♥" * val + "♡" * (5 - val)
        parts.append(f"**{name}** {hearts}")
    return "\n".join(parts)


H = gr.update(visible=False)


CSS = """
:root, .gradio-container, body { background: #0a0a0f !important; color: #e0e0e0 !important; }
.tabs { background: transparent !important; border: none !important; }
.tab-nav { background: #141420 !important; border-bottom: 1px solid #2a2a4a !important; }
.tab-nav button { color: #888 !important; background: transparent !important; border: none !important; font-weight: 600 !important; letter-spacing: 0.5px !important; }
.tab-nav button.selected { color: #6bcbff !important; border-bottom: 2px solid #6bcbff !important; }
.gr-box { border-color: #2a2a4a !important; background: #141420 !important; }
textarea, input { background: #1a1a2e !important; border-color: #2a2a4a !important; color: #e0e0e0 !important; border-radius: 8px !important; }
.markdown-text { color: #e0e0e0 !important; line-height: 1.7 !important; }
h1, h2, h3, h4, h5 { color: #fff !important; }
h1 { letter-spacing: 1px !important; }
.chatbot { background: #141420 !important; border-color: #2a2a4a !important; }
.netflix-row { display:flex !important; gap:20px; padding:10px 0; }
.story-card { position:relative; flex:1; border-radius:10px; overflow:hidden; cursor:pointer; transition:transform 0.35s cubic-bezier(.25,.46,.45,.94), box-shadow 0.35s ease, border-color 0.35s ease; background:#141420; border:2px solid #2a2a4a; }
.story-card:hover { transform:scale(1.06); box-shadow:0 12px 40px rgba(107,203,255,0.18); border-color:#6bcbff; z-index:10; }
.card-poster { height:200px; display:flex; align-items:flex-start; justify-content:flex-end; padding:14px; position:relative; }
.card-poster::after { content:''; position:absolute; inset:0; background:linear-gradient(transparent 55%, rgba(10,10,15,0.95)); pointer-events:none; }
.card-badge { position:relative; z-index:2; background:rgba(0,0,0,0.75); backdrop-filter:blur(4px); color:#6bcbff; font-size:10px; font-weight:800; letter-spacing:2px; padding:4px 12px; border-radius:4px; border:1px solid rgba(107,203,255,0.25); }
.card-body { padding:16px 18px 22px; position:relative; }
.card-body h3 { margin:0 0 6px 0 !important; font-size:20px; font-weight:800; color:#fff !important; letter-spacing:0.5px; }
.card-body p { margin:0 0 10px 0; font-size:13px; color:#999; line-height:1.5; }
.card-tags { display:flex; flex-wrap:wrap; gap:6px; }
.card-tags span { font-size:10px; font-weight:600; color:#6bcbff; background:rgba(107,203,255,0.08); border:1px solid rgba(107,203,255,0.15); padding:2px 8px; border-radius:10px; text-transform:uppercase; letter-spacing:0.5px; }
#card-picker { position:fixed !important; left:-9999px !important; opacity:0 !important; height:0 !important; overflow:hidden !important; padding:0 !important; margin:0 !important; border:none !important; pointer-events:none !important; }
button { border-radius:8px !important; transition:all 0.2s ease !important; }
button:hover { filter:brightness(1.15) !important; transform:translateY(-1px) !important; }
"""


def build_app():
    with gr.Blocks(title="GemmaQuest") as app:
        state = gr.State(new_session())

        with gr.Tabs() as tabs:
            # ─── TAB 0: LANDING ───
            with gr.Tab("Landing", id=0):
                gr.HTML(
                    '<div style="text-align:center;padding:20px 0;">'
                    '<h1 style="font-size:44px;font-weight:900;letter-spacing:8px;margin:0;'
                    'background:linear-gradient(135deg,#ff6b6b 0%,#ffd93d 50%,#6bcbff 100%);'
                    '-webkit-background-clip:text;-webkit-text-fill-color:transparent;">GEMMAQUEST</h1>'
                    '<p style="color:#666;font-size:16px;margin-top:-6px;letter-spacing:2px;">WHERE CODE BECOMES STORY</p>'
                    "</div>"
                )
                gr.HTML('<div style="font-size:20px;font-weight:700;margin:30px 0 16px 10px;color:#fff;">🔥 TRENDING NOW</div>')
                cards_html = '<div class="netflix-row">'
                for card in STORY_CARDS:
                    tags = "".join(f'<span>{t.replace("_"," ")}</span>' for t in card["topics"][:4])
                    cards_html += f"""<div class="story-card" onclick="var c=document.getElementById('card-picker');var t=c.querySelector('textarea')||c.querySelector('input');if(t){{t.value='{card['id']}';t.dispatchEvent(new Event('input',{{bubbles:true}}));}}">
                        <div class="card-poster" style="background:linear-gradient(135deg,{card['gradient']})">
                            <span class="card-badge">{card['badge']}</span>
                        </div>
                        <div class="card-body">
                            <h3>{card['title']}</h3>
                            <p>{card['subtitle']}</p>
                            <div class="card-tags">{tags}</div>
                        </div>
                    </div>"""
                cards_html += '</div>'
                gr.HTML(cards_html)
                card_picker = gr.Textbox(elem_id="card-picker", visible=True)

                def on_card_pick(cid, s):
                    c = next((x for x in STORY_CARDS if x["id"] == cid), None)
                    if not c:
                        # If card_id is invalid or state hasn't updated, do nothing
                        return s, gr.update()
                    s["card_info"] = c
                    s["selected_story"] = c["id"]
                    s["knowledge_stats"] = {t: {"attempts": 0, "correct": 0, "wrong": 0, "fluency": None} for t in c.get("topics", [])}
                    s["step"] = "profile"
                    return s, gr.update(selected=1) # Switch to profile tab

                def generate_first_question(s):
                    if s.get("step") != "profile" or s.get("card_info") is None or s.get("chat_history_started", False):
                        return gr.update(), "", gr.update(visible=False)
                    global _profile_first_q
                    if _profile_first_q is None:
                        print("[INTERVIEW] Calling Gemma for first question (profile_interview_prompt)")
                        _profile_first_q = call_gemma(profile_interview_prompt())
                        print(f"[INTERVIEW] First question received ({len(_profile_first_q)} chars)")
                    else:
                        print("[INTERVIEW] Using cached first question")
                    s["chat_history_started"] = True
                    return [{"role": "assistant", "content": _profile_first_q}], "", gr.update(visible=False)



            # ─── TAB 1: PROFILE ───
            with gr.Tab("Profile Interview", id=1):
                gr.Markdown("## Before your story begins...")
                gr.Markdown("*Answer a few questions or just say **\"I'm ready\"** to jump straight into the story.*")
                chat = gr.Chatbot(label="Interview", height=400, value=[])
                inp = gr.Textbox(label="Your response", placeholder="Type your answer...", scale=4)
                with gr.Row():
                    send = gr.Button("Send", variant="primary", scale=1)
                    skip_btn = gr.Button("Skip to story →", variant="secondary", scale=1)
                gen_btn = gr.Button("✨ Dive Into Story", variant="primary", visible=False, size="lg")
                fetch_status = gr.Markdown("", visible=True)

                def chat_fn(msg, history, s):
                    if not history or len(history) == 0:
                        global _profile_first_q
                        if _profile_first_q is None:
                            print("[INTERVIEW] First question call (chat_fn fallback)")
                            _profile_first_q = call_gemma(profile_interview_prompt())
                        history = [{"role": "assistant", "content": _profile_first_q}]
                        return history, "", H, gr.update()
                    if not msg.strip():
                        return history, "", H, gr.update()
                    history.append({"role": "user", "content": msg})

                    dumped = parse_json(msg)
                    is_dump = dumped is not None and any(
                        k in dumped for k in ("movies", "games", "writers", "character")
                    )

                    if is_dump:
                        _merge_profile(s, dumped)
                        has_character = bool(dumped.get("character"))
                        has_names = any(k in dumped for k in ("movies", "games", "writers"))
                        if has_names:
                            _start_fetch(s)
                        if has_character:
                            reply = ("✅ Profile locked in! The story engine knows your taste and is "
                                     "researching your favorite movies/games/writers. "
                                     "Click **✨ Dive Into Story** when ready.")
                            gen_visible = gr.update(visible=True)
                        else:
                            reply = ("Got your movie and game tastes! One last piece: **what kind of "
                                     "character do you want to be** in this story (strategist? warrior? "
                                     "diplomat? detective?), or paste the full profile JSON including "
                                     "the character section.")
                            gen_visible = H
                        print(f"[INTERVIEW] JSON dump captured — character={has_character}")
                        status_ui = gr.update(value=s.get("rag_fetch_status", ""))
                    else:
                        ctx = "\n".join(f"{m['role']}: {m['content']}" for m in history)
                        print(f"[INTERVIEW] User sent: {msg[:60]} — calling Gemma for continuation")
                        reply = call_gemma(
                            profile_interview_prompt()
                            + "\n\nConversation so far:\n"
                            + ctx
                            + "\n\nContinue the interview naturally. Follow the phase and JSON output rules above."
                        )
                        p = parse_json(reply)
                        has_character = bool(p and p.get("character"))
                        has_partial = bool(p and any(k in p for k in ("movies", "games", "writers")))
                        if p:
                            _merge_profile(s, p)
                            print(f"[INTERVIEW] Gemma profile: character={has_character} partial={has_partial}")
                        if has_partial and not s.get("fetch_started"):
                            _start_fetch(s)
                        gen_visible = gr.update(visible=has_character)
                        status_ui = gr.update(value=s.get("rag_fetch_status", ""))

                    history.append({"role": "assistant", "content": reply})
                    return history, "", gen_visible, status_ui

                send.click(fn=chat_fn, inputs=[inp, chat, state], outputs=[chat, inp, gen_btn, fetch_status])

                def on_skip(s):
                    if not s.get("user_profile"):
                        s["user_profile"] = default_user_profile()
                    s["rag_fetch_status"] = "[SKIP] No web search (skipped interview)."
                    return gr.update(visible=True), gr.update(value=s["rag_fetch_status"])

                skip_btn.click(fn=on_skip, inputs=[state], outputs=[gen_btn, fetch_status])

                last_fetch_status = {"v": ""}

                def poll_fetch_status(s):
                    v = s.get("rag_fetch_status", "")
                    if v and v != last_fetch_status["v"]:
                        last_fetch_status["v"] = v
                        return gr.update(value=v)
                    return gr.update()

                fetch_timer = gr.Timer(1, active=True)
                fetch_timer.tick(fn=poll_fetch_status, inputs=[state], outputs=[fetch_status])

                def on_generate(s):
                    try:
                        ev = _fetch_events.get(id(s))
                        if ev and not s.get("rag_fetch_done"):
                            s["rag_fetch_status"] = "[WAIT] Finishing web search before story generation..."
                            ev.wait(timeout=180)
                        s["step"] = "skeleton"
                        ci = s.get("card_info", {})
                        if not ci:
                            return (s, gr.update(), gr.update(value="## Error: No story selected. Go back and pick one."),
                                    H, H, H, H, H, H, H, H, H, H, H, gr.update())
                        topics = ci.get("topics", [])
                        pj = json.dumps(s.get("user_profile", {}))
                        pl = json.dumps(s.get("rag_patterns", []))
                        reply = call_gemma(skeleton_prompt(ci, topics, pj, pl), max_tokens=4096)
                        if reply.startswith("[Need a valid") or reply.startswith("[API Error"):
                            return (s, gr.update(selected=2), gr.update(value="## ⚠️ API Error"),
                                    gr.update(value=reply), H, H, H, H, H, H, H, H,
                                    gr.update(), gr.update(), gr.update())
                        sk = parse_json(reply)
                        if sk:
                            s["skeleton"] = sk
                            s["total_scenes"] = len(sk.get("scenes", []))
                            s["current_scene_index"] = 0
                            s["step"] = "playing"
                            print(f"[SKELETON] Generated: {json.dumps(sk, indent=2)}")
                        if not sk:
                            s["total_scenes"] = 0
                            return (s, gr.update(selected=2), gr.update(value="## ⚠️ Could not parse story skeleton"),
                                    gr.update(value=f"The story engine returned unexpected output. Please try again.\n\nRaw output:\n```\n{reply[:1000]}\n```"),
                                    H, H, H, H, H, H, H, H, gr.update(), gr.update(), gr.update())
                        return gen_scene(s)
                    except Exception as e:
                        return (s, gr.update(selected=2), gr.update(value="## ⚠️ Error"),
                                gr.update(value=f"An error occurred:\n```\n{str(e)}\n```"),
                                H, H, H, H, H, H, H, H, gr.update(), gr.update(), gr.update())

            # ─── TAB 2: GAME ───
            with gr.Tab("Movie-Game", id=2):
                with gr.Row():
                    with gr.Column(scale=3):
                        hdr = gr.Markdown("### Your adventure awaits...")
                        prose = gr.Markdown("Pick a story card from the Landing page, then return here to begin.")
                        ca = gr.Button(visible=False, variant="secondary", size="lg")
                        cb = gr.Button(visible=False, variant="secondary", size="lg")
                        cc = gr.Button(visible=False, variant="secondary", size="lg")
                        ch_p = gr.Markdown(visible=False)
                        ch_i = gr.Textbox(label="Your answer", placeholder="Type your solution...", visible=False)
                        ch_s = gr.Button("Submit Answer", variant="primary", visible=False)
                        ln = gr.Button("📖 Learn this concept", variant="secondary", visible=False)
                        ch_f = gr.Markdown(visible=False)
                    with gr.Column(scale=1):
                        gr.HTML('<div style="font-weight:700;font-size:16px;margin-bottom:8px;color:#fff;">🎭 Characters</div>')
                        cd = gr.Markdown("Meet characters as the story unfolds.")
                        gr.HTML('<div style="font-weight:700;font-size:16px;margin:16px 0 8px;color:#fff;">🧠 Knowledge</div>')
                        kw = gr.Markdown("No challenges attempted yet.")

            # ─── TAB 3: TEACHING ───
            with gr.Tab("DSA Tutor", id=3):
                gr.Markdown("## 📚 Learn at Your Own Pace")
                tc = gr.Chatbot(label="Tutor", height=400, value=[])
                ti = gr.Textbox(label="Ask something...", placeholder="Type your question...", scale=4)
                with gr.Row():
                    ts = gr.Button("Send", variant="primary", scale=1)
                    ret = gr.Button("↩ Return to Story", scale=1)

            # ─── TAB 4: ENDING ───
            with gr.Tab("Ending", id=4):
                et = gr.Markdown("## Your legend will be written here...")
                pa = gr.Button("🔄 Play Again", variant="primary", size="lg")

            def show_loading(s):
                return (s, gr.update(selected=2),
                        gr.update(value="### ⏳ Crafting your story..."),
                        gr.update(value="The narrative engine is weaving your adventure...\n\n*Building characters...*\n\n*Forging the plot...*"),
                        H, H, H, H, H, H, H, H,
                        gr.update(), gr.update(), gr.update())

            gen_btn.click(fn=show_loading, inputs=[state],
                          outputs=[state, tabs, hdr, prose, ca, cb, cc,
                                   ch_p, ch_i, ch_s, ln, ch_f, cd, kw, et]) \
                .then(fn=on_generate, inputs=[state],
                      outputs=[state, tabs, hdr, prose, ca, cb, cc,
                               ch_p, ch_i, ch_s, ln, ch_f, cd, kw, et])

            card_picker.change(fn=on_card_pick, inputs=[card_picker, state], outputs=[state, tabs]) \
                .then(fn=generate_first_question, inputs=[state], outputs=[chat, inp, gen_btn])

            # ═══════════════════════════════════════════════
            # EVENT HANDLERS
            # ═══════════════════════════════════════════════

            def gen_scene(s):
                try:
                    idx = s["current_scene_index"]
                    scenes = s.get("skeleton", {}).get("scenes", [])
                    total = s.get("total_scenes", 0)

                    if idx >= total:
                        if not s.get("ending_generated"):
                            s["step"] = "ending"
                            prof = s.get("user_profile", {})
                            skel = s.get("skeleton", {})
                            hist = s.get("narrative_history", [])
                            choices_made = [h["choice"] for h in hist]
                            prompt = ending_prompt(
                                user_profile_json=json.dumps(prof),
                                skeleton_title=skel.get("title", "Unknown"),
                                narrative_history_summary=json.dumps(hist),
                                key_choices=json.dumps(choices_made),
                                knowledge_stats_json=json.dumps(s.get("knowledge_stats", {})),
                                character_relationships_json=json.dumps(s.get("character_relationships", {})),
                                story_flags=json.dumps(s.get("story_flags", [])),
                            )
                            ending_text = call_gemma(prompt, max_tokens=2048)
                            s["ending_generated"] = True
                            ks = render_knowledge(s)
                            full = f"{ending_text}\n\n---\n## Your Journey\n\n{ks}"
                            s["_ending_full"] = full
                        return (s, gr.update(selected=4), H, H, H, H, H,
                                H, H, H, H, H, H, H,
                                gr.update(value=s.get("_ending_full", "The end.")))

                    info = scenes[idx]
                    prof = s.get("user_profile", {})
                    skel = s.get("skeleton", {})
                    refs = json.dumps(profile_refs(prof))

                    reply = _check_pregen(s, idx)
                    if reply is None:
                        ctx = s.get("story_context", "")
                        if len(ctx) > 1000:
                            ctx = "..." + ctx[-1000:]
                        nh = s.get("narrative_history", [])
                        if len(nh) > 2:
                            nh = nh[-2:]
                        upcoming = scenes[idx + 1:] if idx + 1 < total else []
                        if len(upcoming) > 2:
                            upcoming = upcoming[:2]
                        skel_summary = json.dumps({"title": skel.get("title", ""), "genre": skel.get("genre", "")})
                        prompt = scene_prompt(
                            skeleton_summary=skel_summary,
                            scene_id=info["scene_id"], beat=info.get("beat", ""),
                            summary=info.get("summary", ""),
                            has_challenge=info.get("has_challenge", False),
                            dsa_concept=info.get("dsa_concept", None),
                            narrative_history=json.dumps(nh),
                            knowledge_stats_json=json.dumps(s.get("knowledge_stats", {})),
                            character_relationships_json=json.dumps(s.get("character_relationships", {})),
                            story_flags=json.dumps(s.get("story_flags", [])),
                        hooked_on_references=refs,
                        story_context=ctx,
                        upcoming_scenes_summary=json.dumps(upcoming),
                        pattern_learnings_json=json.dumps(s.get("rag_patterns", [])),
                    )
                    reply = call_gemma(prompt, max_tokens=4096)

                    if not reply:
                        reply = f"[Empty response from API. Using fallback scene.]"
                    print(f"[DEBUG] scene reply chars={len(reply)} parse_json...")
                    sd = parse_json(reply)
                    if not sd:
                        print(f"[DEBUG] parse_json FAILED. Full reply:\n{reply}")
                    if not sd:
                        sd = {"prose": reply, "choices": [{"id": "a", "text": "Continue", "type": "narrative"}],
                              "challenge": None, "show_learn_button": False, "atmosphere": "mysterious"}

                    s["current_scene_data"] = sd
                    s["current_scene_index"] = idx + 1
                    s["current_challenge"] = sd.get("challenge")
                    p = sd.get("prose") or sd.get("Prose") or sd.get("narrative") or reply
                    ctx = s.get("story_context", "")
                    if len(ctx) > 1000:
                        ctx = "..." + ctx[-1000:]
                    s["story_context"] = (ctx + "\n\n---\n\n" + p).strip()

                    choices = sd.get("choices", [{"id": "a", "text": "Continue", "type": "narrative"}])
                    header = f"### Scene {idx + 1} of {total}  |  {info.get('beat', '').replace('_', ' ').title()}"

                    a = gr.update(value=choices[0]["text"], visible=True) if len(choices) > 0 else H
                    b = gr.update(value=choices[1]["text"], visible=True) if len(choices) > 1 else H
                    c = gr.update(value=choices[2]["text"], visible=True) if len(choices) > 2 else H

                    if idx + 1 < total:
                        _pregen_next(s, idx + 1)

                    return (s, gr.update(selected=2), gr.update(value=header), gr.update(value=p),
                            a, b, c, H, H, H, H, H,
                            gr.update(value=render_characters(s)),
                            gr.update(value=render_knowledge(s)),
                            gr.update())
                except Exception as e:
                    import traceback
                    traceback.print_exc()
                    return (s, gr.update(selected=2), gr.update(value="## ⚠️ Error in Scene"),
                            gr.update(value=f"An error occurred generating this scene:\n```\n{str(e)}\n```"),
                            H, H, H, H, H, H, H, H, gr.update(), gr.update(), gr.update())

            # ── Choice buttons ──
            CID_IDX = {"a": 0, "b": 1, "c": 2}
            def on_choice(cid, s):
                sd = s.get("current_scene_data", {})
                choices = sd.get("choices", [])
                idx = CID_IDX.get(cid)
                chosen = choices[idx] if idx is not None and idx < len(choices) else None
                if not chosen:
                    print(f"[BLANK] on_choice(cid={cid}) — scene_data keys={list(sd.keys())}, choices={choices}")
                    return s, *([H]*13), gr.update()

                s["narrative_history"].append({
                    "scene": s["current_scene_index"] - 1,
                    "choice": chosen["text"],
                    "type": chosen.get("type", "narrative"),
                    "prose": s.get("current_scene_data", {}).get("prose", ""),
                })

                if chosen.get("type") == "challenge":
                    ch = sd.get("challenge")
                    if ch:
                        s["current_challenge"] = ch
                        opts = ch.get("options", [])
                        txt = ch.get("narrative_prompt", "Solve.")
                        display = f"**{txt}**" + ("\n\n" + "\n".join(opts) if opts else "")
                        return (s, gr.update(), gr.update(), gr.update(),
                                H, H, H,
                                gr.update(visible=True, value=display),
                                gr.update(visible=True, value=""),
                                gr.update(visible=True),
                                gr.update(visible=ch.get("show_learn_button", True)),
                                gr.update(value=""),
                                gr.update(value=render_characters(s)),
                                gr.update(value=render_knowledge(s)),
                                gr.update())

                return tuple(gen_scene(s))

            def make_handler(cid):
                def handler(s):
                    return on_choice(cid, s)
                return handler
            for cid, btn in [("a", ca), ("b", cb), ("c", cc)]:
                btn.click(fn=make_handler(cid), inputs=[state],
                          outputs=[state, tabs, hdr, prose, ca, cb, cc, ch_p, ch_i, ch_s, ln, ch_f, cd, kw, et])

            # ── Challenge submit ──
            def on_challenge_submit(answer, s):
                ch = s.get("current_challenge")
                if not ch:
                    return s, gr.update(value="No challenge."), H, H, gr.update(), gr.update()

                correct = ch.get("correct_answer", "")
                ok = answer.strip().lower() == correct.strip().lower()
                concept = ch.get("concept", "unknown")
                ks = s["knowledge_stats"]
                if concept not in ks:
                    ks[concept] = {"attempts": 0, "correct": 0, "wrong": 0, "fluency": None}
                ks[concept]["attempts"] += 1
                if ok:
                    ks[concept]["correct"] += 1
                    fb = "✅ Correct! Your character pushes forward."
                else:
                    ks[concept]["wrong"] += 1
                    fb = "❌ Not quite. The story takes a darker turn..."
                    s["story_flags"].append(f"{concept}_failed")
                s["current_challenge"] = None
                return s, gr.update(value=fb), H, H, gr.update(value=render_knowledge(s)), gr.update(value=render_characters(s))

            ch_s.click(fn=on_challenge_submit, inputs=[ch_i, state],
                       outputs=[state, ch_f, ch_s, ln, kw, cd]
                       ).then(fn=gen_scene, inputs=[state],
                              outputs=[state, tabs, hdr, prose, ca, cb, cc,
                                       ch_p, ch_i, ch_s, ln, ch_f, cd, kw, et])

            # ── Learn button ──
            def on_learn(s):
                ch = s.get("current_challenge") or {}
                s["teaching_mode"] = True
                s["teaching_context"] = ch.get("concept", "unknown")
                s["pending_challenge"] = ch
                return s, gr.update(selected=3)

            ln.click(fn=on_learn, inputs=[state], outputs=[state, tabs])

            # ── Tutor chat ──
            def on_tutor(msg, history, s):
                concept = s.get("teaching_context", "the concept")
                if not history or len(history) == 0:
                    ch = s.get("pending_challenge") or {}
                    prompt = teaching_prompt(
                        concept=concept,
                        challenge_context=ch.get("narrative_prompt", ""),
                        challenge_prompt=json.dumps(ch),
                        concept_stats=json.dumps(s["knowledge_stats"].get(concept, {})),
                    )
                    reply = call_gemma(prompt)
                    return [{"role": "assistant", "content": reply}], ""
                if not msg.strip():
                    return history, ""
                history.append({"role": "user", "content": msg})
                ctx = "\n".join(f"{m['role']}: {m['content']}" for m in history)
                reply = call_gemma(f"You are a DSA tutor. Continue teaching {concept}.\n{ctx}\n\nRespond helpfully.")
                history.append({"role": "assistant", "content": reply})
                return history, ""

            ts.click(fn=on_tutor, inputs=[ti, tc, state], outputs=[tc, ti])

            # ── Return to story ──
            def on_return(s):
                s["teaching_mode"] = False
                return s, gr.update(selected=2)

            ret.click(fn=on_return, inputs=[state], outputs=[state, tabs])

            # ── Play again ──
            def on_play_again(s):
                return new_session(), gr.update(selected=0)

            pa.click(fn=on_play_again, inputs=[state], outputs=[state, tabs])

    return app


if __name__ == "__main__":
    app = build_app()

    print(f"[+] Using {MODEL} with Google AI API")

    on_render = bool(os.environ.get("RENDER"))
    port = int(os.environ.get("PORT", "7860"))
    app.launch(
        server_name="0.0.0.0",
        server_port=port,
        debug=not on_render,
        share=False,
        theme=gr.themes.Soft(primary_hue="blue"),
        css=CSS,
    )
