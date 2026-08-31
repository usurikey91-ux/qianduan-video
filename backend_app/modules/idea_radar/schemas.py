def string_array(min_items=1, max_items=6):
    return {"type": "array", "items": {"type": "string"}, "minItems": min_items, "maxItems": max_items}


def transcript_radar_schema():
    return {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "viral_theme", "audience_anxieties", "contrarian_viewpoint", "evidence_types",
            "migration_angles", "recommended_titles", "opening_script", "personalized_script",
            "adaptation_variants", "complete_script",
            "formula", "content_breakdown",
        ],
        "properties": {
            "viral_theme": {"type": "string"},
            "audience_anxieties": string_array(),
            "contrarian_viewpoint": {"type": "string"},
            "evidence_types": string_array(),
            "migration_angles": string_array(),
            "recommended_titles": string_array(),
            "opening_script": {"type": "string"},
            "personalized_script": {"type": "string"},
            "complete_script": {"type": "string"},
            "adaptation_variants": {
                "type": "array",
                "minItems": 3,
                "maxItems": 3,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["level", "title", "what_to_keep", "what_to_change", "script_outline"],
                    "properties": {
                        "level": {"type": "string"},
                        "title": {"type": "string"},
                        "what_to_keep": {"type": "string"},
                        "what_to_change": {"type": "string"},
                        "script_outline": {"type": "string"},
                    },
                },
            },
            "formula": {"type": "string"},
            "content_breakdown": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "summary", "target_audience", "hook", "structure", "core_viewpoint",
                    "evidence", "emotional_turn", "spread_promise", "reusable_mechanisms",
                    "non_reusable_parts", "opportunity_chain", "gaps", "confidence",
                ],
                "properties": {
                    "summary": {"type": "string"},
                    "target_audience": {"type": "string"},
                    "hook": {"type": "string"},
                    "structure": string_array(),
                    "core_viewpoint": {"type": "string"},
                    "evidence": string_array(),
                    "emotional_turn": {"type": "string"},
                    "spread_promise": {"type": "string"},
                    "reusable_mechanisms": string_array(),
                    "non_reusable_parts": string_array(),
                    "opportunity_chain": string_array(),
                    "gaps": string_array(),
                    "confidence": {"type": "string"},
                },
            },
        },
    }
