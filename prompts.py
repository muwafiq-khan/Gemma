import json


# ─── PHASE 1: MOVIE + GAME SEGMENTS (triggers web fetch) ───
PHASE1_MOVIE_QUESTIONS = [
    "What movie genres pull you in?",
    "Name 2-3 movies you love. What did you like most about each?",
    "What made those movies unique or exceptional in your eyes?",
    "What type of characters do you love in movies? (anti-hero? mentor? villain?)",
    "Which writers or directors do you admire — whose work would you binge?",
]

PHASE1_GAME_QUESTIONS = [
    "What game genres do you play?",
    "Which games have gripped you the most? What was it about them?",
    "What elements in a game attract you? (story, world-building, choices, loot, atmosphere)",
    "Which game characters made you feel invested? Why?",
]

# ─── PHASE 2: CHARACTER SEGMENT (runs while web fetch is in background) ───
PHASE2_CHARACTER_QUESTIONS = [
    "What type of character do you want to BE in this story? (strategist? warrior? diplomat? detective?)",
    "What fictional characters have you resonated with before? What about them hooked you?",
    "What personalities do you get drawn to? (charisma? intellect? moral ambiguity?)",
    "How do you make decisions under pressure — gut, logic, or emotion?",
]

INTERVIEW_QUESTIONS = PHASE1_MOVIE_QUESTIONS + PHASE1_GAME_QUESTIONS + PHASE2_CHARACTER_QUESTIONS

INTERVIEW_JSON_FIELDS = {
    "movies": {
        "genres": '["sci-fi", "noir"]',
        "favorites": '[{"title": "Inception", "what_liked": "...", "unique": "...", "characters_loved": "..."}]',
        "character_types": '["anti-hero", "mentor with secrets"]',
        "writers_directors": '["Christopher Nolan", "Denis Villeneuve"]',
    },
    "games": {
        "genres": '["RPG", "immersive sim"]',
        "favorites": '[{"title": "Disco Elysium", "hooked_by": "...", "unique": "...", "characters_loved": "..."}]',
        "hooked_elements": '["branching narrative", "meaningful choices", "atmosphere"]',
    },
    "writers": '["writer1", "director1"]',
}


def interview_questions_list():
    return "\n".join(f"{i+1}. {q}" for i, q in enumerate(INTERVIEW_QUESTIONS))


def _render_schema_entry(key, value):
    if isinstance(value, dict):
        inner = ",\n        ".join(f'"{ik}": {iv}' for ik, iv in value.items())
        return f'"{key}": {{\n        {inner}\n    }}'
    return f'"{key}": {value}'


def interview_json_schema_partial():
    items = ",\n    ".join(_render_schema_entry(k, v) for k, v in INTERVIEW_JSON_FIELDS.items())
    return "{\n    " + items + "\n}"


def interview_json_schema_full():
    partial = ",\n    ".join(_render_schema_entry(k, v) for k, v in INTERVIEW_JSON_FIELDS.items())
    return (
        "{\n    "
        + partial
        + ',\n    "character": {\n'
        '        "wants_to_be": "e.g. strategist who outsmarts enemies",\n'
        '        "resonated_with": ["Geralt of Rivia", "Cassandra Pentaghast"],\n'
        '        "personality_traits": ["analytical", "morally flexible"],\n'
        '        "decision_style": "calculated | gut | empathetic"\n'
        "    }\n}"
    )


def interview_json_schema():
    return interview_json_schema_full()


def profile_interview_prompt():
    return f"""You are a friendly interviewer building a rich user profile for an interactive story game. You interview the user in TWO phases.

## PHASE 1 — Movie + Game segment
Ask these questions one at a time, conversationally (react to their answers naturally before moving on):
Movie questions:
{chr(10).join(f"  {i+1}. {q}" for i, q in enumerate(PHASE1_MOVIE_QUESTIONS))}
Game questions:
{chr(10).join(f"  {i+6}. {q}" for i, q in enumerate(PHASE1_GAME_QUESTIONS))}

After the user has answered the movie + game topics, output the PARTIAL profile JSON and then continue to Phase 2. Partial schema:
{interview_json_schema_partial()}

## PHASE 2 — Character segment
Continue asking, one at a time:
{chr(10).join(f"  {i+10}. {q}" for i, q in enumerate(PHASE2_CHARACTER_QUESTIONS))}

After Phase 2 topics are covered, output the FULL profile JSON and wrap up warmly. Full schema:
{interview_json_schema_full()}

## CRITICAL RULES
1. If the user provides COMPLETE profile information in a single message (movies, games, writers AND character details — possibly as a JSON dict), do NOT ask any further questions. Acknowledge briefly and output the FULL profile JSON immediately.
2. If the user says they're ready / wants to skip, output the FULL JSON with whatever information was collected (empty lists for missing fields).
3. Never output JSON mid-conversation until a phase is complete.
4. Be warm and engaging. The user is here to have fun."""


def pattern_extraction_prompt(title, source_type, content):
    return f"""You are a narrative structure analyst. Analyze the content below about {title} ({source_type}).

CONTENT:
{content[:6000]}

Extract these 5 structural patterns:
1. structure — the story structure & pacing (e.g. "layered non-linear timeline", "slow-burn with cold open")
2. tension_building — how tension is built (e.g. "cross-cutting with rising stakes", "information withholding")
3. character_intro — how characters are introduced (e.g. "show expertise through action", "entrance with moral dilemma")
4. dialogue — dialogue patterns (e.g. "exposition disguised as conflict", "sparse, laconic lines")
5. devices — narrative devices used, as a list of short strings (e.g. "time pressure as pacing tool", "unreliable narrator")

Output JSON with this shape:
{{
    "source": "{title}",
    "type": "{source_type}",
    "patterns": {{
        "structure": "...",
        "tension_building": "...",
        "character_intro": "...",
        "dialogue": "...",
        "devices": ["device1", "device2"]
    }}
}}"""


def skeleton_prompt(card_info, topics_pool, user_profile_json, pattern_learnings_json=None):
    title = card_info.get('title', 'Unknown')
    subtitle = card_info.get('subtitle', '')
    genre = card_info.get('genre', 'fantasy')
    hook = card_info.get('hook', '')
    topics_str = ", ".join(topics_pool)
    patterns = pattern_learnings_json or "[]"
    return f"""Based on the card selection and user profile below, generate a story skeleton for an interactive movie-game experience.

Card: {title} — {subtitle}
Genre: {genre}
World Hook: {hook}

Available DSA Topics for This World (pick exactly 2 that feel natural to the plot):
{topics_str}

User Profile (for style and character inspiration):
{user_profile_json}

Pattern Learnings from user's favorite writers/movies/games (structural techniques they love):
{patterns}

Apply these structural techniques to the story. For example:
- If a pattern notes a non-linear timeline, mirror that structure
- If a pattern notes environmental storytelling or information withholding, match it
- Match the pacing, tension curve, character introduction style, and dialogue patterns
- If the list is empty, use your own best judgment
These techniques must blend naturally into the genre — never feel mechanical or copied.

The story MUST:
- Have 7-10 scenes total
- Include 2 DSA algorithm challenges — both chosen from the Available DSA Topics above
- Have 3 different possible endings based on user choices
- Contain character archetypes that fit the genre
- Allow the user to make both narrative choices and solve challenges
- The story must feel like a real movie, not a textbook
- Mirror the storytelling style of the user's favorite movies/games (hooked_on + favorites)

Narrative beats to follow:
1. Inciting Incident (introduces the world and stakes)
2. First Choice Point (user shapes direction)
3. Rising Action (build tension, introduce first DSA challenge naturally)
4. Midpoint Twist (revelation or complication)
5. Second Challenge (harder DSA concept, higher stakes)
6. Dark Moment (things look hopeless)
7. Climax (final confrontation or decision, no DSA)
8. Resolution (based on all prior choices + performance)

Output ONLY a JSON skeleton:
{{
    "title": "string",
    "genre": "{genre}",
    "setting": "string",
    "protagonist": {{"name": "string", "role": "string"}},
    "characters": [{{"name": "string", "role": "string", "archetype": "string"}}],
    "scenes": [
        {{
            "scene_id": 1,
            "beat": "inciting_incident",
            "setting": "string",
            "summary": "what happens in this scene",
            "has_challenge": false,
            "dsa_concept": null,
            "narrative_purpose": "establish stakes"
        }}
    ],
    "endings": [
        {{"ending_id": 1, "condition": "most challenges correct + heroic choices", "summary": "..."}},
        {{"ending_id": 2, "condition": "mixed results", "summary": "..."}},
        {{"ending_id": 3, "condition": "most challenges wrong + dark choices", "summary": "..."}}
    ]
}}"""


def scene_prompt(skeleton_summary, scene_id, beat, summary, has_challenge,
                 dsa_concept, narrative_history, knowledge_stats_json,
                 character_relationships_json, story_flags, hooked_on_references,
                 story_context, upcoming_scenes_summary, pattern_learnings_json=None):
    patterns = pattern_learnings_json or "[]"
    return f"""You are the narrative engine of an interactive movie-game.

Story World:
{skeleton_summary}

Story So Far (previous scenes' narrative prose):
{story_context}

Upcoming Scene: scene_id={scene_id}, beat={beat}, summary={summary}
Has Challenge: {has_challenge}
DSA Concept (if any): {dsa_concept}

Remaining Scenes from Skeleton (for foreshadowing):
{upcoming_scenes_summary}

User's Past Choices: {narrative_history}
User's Knowledge Stats: {knowledge_stats_json}
Character Relationships: {character_relationships_json}
Story Flags: {story_flags}

User's Hooked-On References (movies/games they loved):
{hooked_on_references}
Use these as inspiration: if the user loved Inception, channel that mind-bending
atmosphere. If they loved The Dark Knight, bring moral tension. If they loved
a specific game, borrow its pacing and dramatic beats. This makes the story
feel personally tailored to their taste.

Structural Pattern Learnings (from user's favorite writers/movies/games):
{patterns}
Apply them subtly to THIS scene: match the pacing, tension curve, character
introduction style, and dialogue patterns. If the list is empty, use your own
best judgment. Blend them with the genre — never mechanically or forced.

---
Generate this scene dynamically. Write cinematic prose that hooks the user.
The scene should feel like a movie unfolding — vivid descriptions, tension, emotion.

BUT also keep the prose **easy to read and follow**. Follow these readability rules:
- Use **short paragraphs** (2-4 sentences each). Break long descriptions into smaller chunks.
- Prefer **clean, simple sentence structures** over long winding clauses.
- Use **plenty of dialogue** — characters talking makes the story feel faster and clearer.
- Avoid overly ornate vocabulary. Keep language vivid but accessible.
- Each paragraph should advance the scene — don't pad.

Rules:
1. Start with a short atmospheric hook setting the scene
2. Use character dialogue frequently to move the scene forward
3. End with 2-3 meaningful choices for the user
4. If has_challenge is true, one of the choices leads to a DSA challenge
5. Reference past choices and character relationships naturally
6. Reference events and details from previous scenes (Story So Far) for continuity
7. The tone should match the genre and current dramatic tension level

CRITICAL — Challenge Embedding Rules:
If this scene has a DSA challenge, it MUST NOT feel like a task or question
thrown at the user. Instead:
- Frame the challenge as something the CHARACTER needs to figure out to survive
- Example: NOT "Solve this sorting problem" BUT "The ancient lock requires the
  names arranged in a specific order. You realize if you sort them alphabetically..."
- The user should feel like they're thinking as the character, not answering a quiz
- No meta-language like "here's a challenge" or "solve this problem"
- The challenge is presented through the narrative: the character is in a situation
  where this knowledge is the key to progress

Output JSON:
{{
    "prose": "full narrative text for this scene...",
    "choices": [
        {{"id": "a", "text": "Choice A text", "type": "narrative"}},
        {{"id": "b", "text": "Choice B text", "type": "narrative"}},
        {{"id": "c", "text": "Choice C text", "type": "challenge" | "narrative"}}
    ],
    "challenge": null | {{
        "concept": "quicksort",
        "narrative_prompt": "The challenge as the CHARACTER experiences it...",
        "type": "multiple_choice" | "code" | "conceptual",
        "options": ["A) ...", "B) ...", "C) ...", "D) ..."] | null,
        "correct_answer": "the correct answer string or option letter",
        "difficulty": "easy" | "medium" | "hard"
    }},
    "show_learn_button": true | false,
    "atmosphere": "tense" | "mysterious" | "hopeful" | "dark" | "calm"
}}"""


def teaching_prompt(concept, challenge_context, challenge_prompt, concept_stats):
    return f"""You are an adaptive tutor for DSA concepts inside an interactive story game.

The user encountered a challenge involving: {concept}
Story context: The user was in this scene:
{challenge_context}

The challenge was: {challenge_prompt}
The user's past performance on this concept: {concept_stats}

---
Teach this concept in a way that:
1. Connects back to the story (explain how this concept appears in the story)
2. Start with a simple, intuitive explanation
3. Give a simpler example than the challenge they faced
4. Check their understanding with a practice question
5. Be encouraging and patient — they're in the middle of a story

Tone: Think of yourself as a wise mentor figure from the story world.
Use language that fits the genre when appropriate.

After each user response, either:
- Praise and go deeper if they're getting it
- Simplify and try a different angle if they're struggling
- Offer to let them return to the story when they feel ready

End your response with "[READY]" when you think they understand enough
to attempt the challenge, or ask if they want to return."""


def ending_prompt(user_profile_json, skeleton_title, narrative_history_summary,
                  key_choices, knowledge_stats_json, character_relationships_json,
                  story_flags):
    return f"""Based on the user's full journey through the story, generate the ending.

User Profile: {user_profile_json}
Story Skeleton Used: {skeleton_title}
Scenes Experienced: {narrative_history_summary}
Key Choices Made: {key_choices}
Knowledge Stats: {knowledge_stats_json}
Character Relationships: {character_relationships_json}
Story Flags: {story_flags}

Generate a cinematic ending that:
1. Wraps up the character's arc based on their choices
2. References specific choices they made
3. Incorporates their DSA journey (did they grow? did they struggle?)
4. Matches the tone of the genre
5. Leaves the user feeling like their choices mattered

Output 3-4 paragraphs of prose. No JSON."""
