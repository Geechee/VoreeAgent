"""Tests for agent personas."""
from personas import BUILTIN_PERSONAS, get_persona_prompt


def test_all_personas_have_required_fields():
    for p in BUILTIN_PERSONAS:
        assert "name" in p
        assert "display_name" in p
        assert "description" in p
        assert "system_prompt" in p


def test_persona_names_unique():
    names = [p["name"] for p in BUILTIN_PERSONAS]
    assert len(set(names)) == len(names)


def test_persona_count():
    assert len(BUILTIN_PERSONAS) == 6


def test_default_persona_exists():
    names = [p["name"] for p in BUILTIN_PERSONAS]
    assert "voree" in names


def test_get_builtin_persona():
    prompt = get_persona_prompt("architect")
    assert "Architect" in prompt or "architect" in prompt


def test_get_unknown_persona_falls_back():
    prompt = get_persona_prompt("nonexistent")
    assert prompt == BUILTIN_PERSONAS[0]["system_prompt"]


def test_prompts_are_distinct():
    prompts = [p["system_prompt"] for p in BUILTIN_PERSONAS]
    assert len(set(prompts)) == len(prompts)


def test_personas_have_tone_and_expertise():
    for p in BUILTIN_PERSONAS:
        assert "tone" in p, f"Persona {p['name']} missing tone"
        assert "expertise" in p, f"Persona {p['name']} missing expertise"
