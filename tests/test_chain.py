"""Tests for multi-agent chain roles and configuration."""
from chain import AGENT_ROLES


def test_all_roles_exist():
    expected = {"researcher", "critic", "synthesizer", "creative", "simplifier"}
    assert set(AGENT_ROLES.keys()) == expected


def test_roles_have_prompts():
    for name, prompt in AGENT_ROLES.items():
        assert isinstance(prompt, str)
        assert len(prompt) > 20, f"Role {name} prompt is too short"


def test_roles_are_distinct():
    prompts = list(AGENT_ROLES.values())
    assert len(set(prompts)) == len(prompts), "Duplicate role prompts found"
