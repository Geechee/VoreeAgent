"""Built-in tools the agent can call during task execution."""
import json
import math
import re
from datetime import datetime, timezone

TOOL_DEFINITIONS = [
    {
        "name": "calculator",
        "description": "Evaluate a mathematical expression. Supports basic arithmetic, exponents, sqrt, and common math functions.",
        "input_schema": {
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "The math expression to evaluate, e.g. '(45 * 12) + sqrt(144)'"
                }
            },
            "required": ["expression"],
        },
    },
    {
        "name": "get_current_time",
        "description": "Get the current date and time in UTC.",
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "knowledge_lookup",
        "description": "Look up factual information from VOREE's knowledge base. Use for definitions, facts, or reference data.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The topic or question to look up"
                }
            },
            "required": ["query"],
        },
    },
]

_SAFE_MATH = {
    "abs": abs, "round": round, "min": min, "max": max,
    "sqrt": math.sqrt, "pow": pow, "log": math.log, "log10": math.log10,
    "sin": math.sin, "cos": math.cos, "tan": math.tan,
    "pi": math.pi, "e": math.e,
}


def execute_tool(name: str, input_data: dict) -> str:
    if name == "calculator":
        return _calculator(input_data.get("expression", ""))
    elif name == "get_current_time":
        return _get_current_time()
    elif name == "knowledge_lookup":
        return _knowledge_lookup(input_data.get("query", ""))
    return f"Unknown tool: {name}"


def _calculator(expression: str) -> str:
    try:
        cleaned = re.sub(r'[^0-9+\-*/().,%^ a-zA-Z_]', '', expression)
        cleaned = cleaned.replace('^', '**')
        result = eval(cleaned, {"__builtins__": {}}, _SAFE_MATH)
        return str(result)
    except Exception as e:
        return f"Error: {e}"


def _get_current_time() -> str:
    now = datetime.now(timezone.utc)
    return json.dumps({
        "utc": now.isoformat(),
        "date": now.strftime("%Y-%m-%d"),
        "time": now.strftime("%H:%M:%S"),
        "day_of_week": now.strftime("%A"),
    })


def _knowledge_lookup(query: str) -> str:
    return f"Knowledge lookup for '{query}': This tool provides access to VOREE's internal knowledge. The agent should synthesize this with its own knowledge to provide a comprehensive answer."
