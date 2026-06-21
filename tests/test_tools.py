"""Tests for the built-in tools."""
import json
from tools import execute_tool


def test_calculator_basic():
    assert execute_tool("calculator", {"expression": "2 + 2"}) == "4"


def test_calculator_complex():
    result = float(execute_tool("calculator", {"expression": "10 * 5 + 3"}))
    assert result == 53.0


def test_calculator_sqrt():
    result = float(execute_tool("calculator", {"expression": "sqrt(144)"}))
    assert result == 12.0


def test_calculator_exponent():
    result = float(execute_tool("calculator", {"expression": "2 ^ 10"}))
    assert result == 1024.0


def test_calculator_error():
    result = execute_tool("calculator", {"expression": "invalid"})
    assert "Error" in result


def test_get_current_time():
    result = execute_tool("get_current_time", {})
    data = json.loads(result)
    assert "utc" in data
    assert "date" in data
    assert "time" in data
    assert "day_of_week" in data


def test_knowledge_lookup():
    result = execute_tool("knowledge_lookup", {"query": "test query"})
    assert "test query" in result


def test_unknown_tool():
    result = execute_tool("nonexistent", {})
    assert "Unknown tool" in result
