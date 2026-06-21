"""Tests for the workflow selection system."""
from workflows import select_workflow, get_workflow_instruction, BUILTIN_WORKFLOWS


def test_research_keywords():
    assert select_workflow("Research the best databases") == "research_v1"
    assert select_workflow("Find me a good tool") == "research_v1"
    assert select_workflow("Investigate this issue") == "research_v1"


def test_compare_keywords():
    assert select_workflow("Compare Python and Go") == "compare_v1"
    assert select_workflow("What's the difference between X and Y") == "compare_v1"
    assert select_workflow("Which is better, React vs Vue") == "compare_v1"


def test_brainstorm_keywords():
    assert select_workflow("Brainstorm ideas for my startup") == "brainstorm_v1"
    assert select_workflow("Come up with creative solutions") == "brainstorm_v1"
    assert select_workflow("Generate some ideas") == "brainstorm_v1"


def test_summarize_keywords():
    assert select_workflow("Summarize this article") == "summarize_v1"
    assert select_workflow("Give me a tl;dr") == "summarize_v1"
    assert select_workflow("Recap the meeting notes") == "summarize_v1"


def test_default_workflow():
    assert select_workflow("Hello, how are you?") == "research_v1"
    assert select_workflow("") == "research_v1"


def test_case_insensitive():
    assert select_workflow("COMPARE these two things") == "compare_v1"
    assert select_workflow("SUMMARIZE this") == "summarize_v1"


def test_get_builtin_instruction():
    instruction = get_workflow_instruction("research_v1")
    assert "Research" in instruction
    assert len(instruction) > 20


def test_get_unknown_workflow_falls_back():
    instruction = get_workflow_instruction("nonexistent_workflow")
    assert instruction == BUILTIN_WORKFLOWS["research_v1"]


def test_all_builtins_exist():
    expected = {"research_v1", "compare_v1", "brainstorm_v1", "summarize_v1"}
    assert set(BUILTIN_WORKFLOWS.keys()) == expected
