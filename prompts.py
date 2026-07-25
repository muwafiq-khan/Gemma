import json


def profile_interview_prompt():
    return """You are a friendly interviewer building a user profile for an interactive story game.

Ask the user these questions one at a time (conversationally):
1. What movies or video games have they been HOOKED on in the past?
   (Probe: which ones made them feel deeply invested in the story?)
2. Which DSA topics do they find easy?
3. Which DSA topics do they find hard?

After they answer all 3, output a JSON profile:
{
    "favorites": ["movie1", "movie2", "game1"],
    "hooked_on": ["movie/game that immersed them", "..."],
    "dsa_strong": ["topic1", "topic2"],
    "dsa_weak": ["topic3", "topic4"]
}

Be warm and engaging. React to their answers naturally before moving on."""


def skeleton_prompt(card_info, topics_pool, user_profile_json):
    title = card_info.get('title', 'Unknown')
    subtitle = card_info.get('subtitle', '')
    genre = card_info.get('genre', 'fantasy')
    hook = card_info.get('hook', '')
    topics_str = ", ".join(topics_pool)
    return f"""Based on the card selection and user profile below, generate a story skeleton for an interactive movie-game experience.

Card: {title} — {subtitle}
Genre: {genre}
World Hook: {hook}

Available DSA Topics for This World (pick exactly 2 that feel natural to the plot):
{topics_str}

User Profile (for style and character inspiration):
{user_profile_json}

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
                 story_context, upcoming_scenes_summary):
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

---
Generate this scene dynamically. Write cinematic prose that hooks the user.
The scene should feel like a movie unfolding — vivid descriptions, tension, emotion.

Rules:
1. Start with atmospheric prose setting the scene
2. Include character dialogue where appropriate
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
