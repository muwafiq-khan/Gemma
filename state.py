def default_knowledge_stats():
    return {}


def default_user_profile():
    return {
        "movies": {
            "genres": [],
            "favorites": [],
            "character_types": [],
            "writers_directors": [],
        },
        "games": {
            "genres": [],
            "favorites": [],
            "hooked_elements": [],
        },
        "writers": [],
        "character": {},
    }


def new_session():
    return {
        "step": "profile",
        "user_profile": default_user_profile(),
        "skeleton": {},
        "current_scene_index": 0,
        "total_scenes": 0,
        "story_context": "",
        "current_scene_data": {},
        "narrative_history": [],
        "knowledge_stats": default_knowledge_stats(),
        "character_relationships": {},
        "story_flags": [],
        "current_challenge": None,
        "teaching_mode": False,
        "teaching_context": "",
        "pending_challenge": None,
        "ending_generated": False,
        "rag_fetch_status": "",
        "rag_fetch_done": False,
        "fetch_started": False,
        "rag_patterns": [],
    }
