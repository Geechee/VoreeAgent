"""Tests for the template library."""
from templates import BUILTIN_TEMPLATES, render_template


def test_all_templates_have_required_fields():
    for t in BUILTIN_TEMPLATES:
        assert "name" in t
        assert "category" in t
        assert "description" in t
        assert "prompt" in t
        assert "variables" in t


def test_template_names_unique():
    names = [t["name"] for t in BUILTIN_TEMPLATES]
    assert len(set(names)) == len(names)


def test_template_count():
    assert len(BUILTIN_TEMPLATES) == 8


def test_categories():
    cats = {t["category"] for t in BUILTIN_TEMPLATES}
    assert "writing" in cats
    assert "coding" in cats
    assert "business" in cats
    assert "analysis" in cats
    assert "creative" in cats


def test_render_basic():
    result = render_template("Hello {{name}}", {"name": "World"})
    assert result == "Hello World"


def test_render_multiple_vars():
    result = render_template("{{a}} and {{b}}", {"a": "X", "b": "Y"})
    assert result == "X and Y"


def test_render_missing_var_preserved():
    result = render_template("Hello {{name}}", {})
    assert result == "Hello {{name}}"


def test_render_extra_vars_ignored():
    result = render_template("Hello {{name}}", {"name": "World", "extra": "ignored"})
    assert result == "Hello World"


def test_all_templates_have_placeholders():
    for t in BUILTIN_TEMPLATES:
        assert "{{" in t["prompt"], f"Template {t['name']} has no placeholders"


def test_variables_have_names():
    for t in BUILTIN_TEMPLATES:
        for v in t["variables"]:
            assert "name" in v, f"Variable in {t['name']} missing name"
            assert "description" in v, f"Variable {v.get('name')} in {t['name']} missing description"
