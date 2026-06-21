"""Built-in + plugin tools the agent can call during task execution."""
import json
import logging
import math
import re
from datetime import datetime, timezone
from typing import Optional

import httpx
from sqlalchemy.orm import Session

logger = logging.getLogger("voree.tools")

BUILTIN_TOOL_DEFINITIONS = [
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


TOOL_DEFINITIONS = BUILTIN_TOOL_DEFINITIONS


def get_all_tool_definitions(db: Optional[Session] = None) -> list:
    """Return built-in tools + any active plugins from the database."""
    tools = list(BUILTIN_TOOL_DEFINITIONS)
    if db:
        from models import Plugin
        plugins = db.query(Plugin).filter(Plugin.is_active == True).all()
        for p in plugins:
            try:
                params = json.loads(p.parameters_json)
            except json.JSONDecodeError:
                params = {"type": "object", "properties": {}}
            tools.append({
                "name": p.name,
                "description": p.description,
                "input_schema": params,
            })
    return tools


def execute_tool(name: str, input_data: dict, db: Optional[Session] = None) -> str:
    if name == "calculator":
        return _calculator(input_data.get("expression", ""))
    elif name == "get_current_time":
        return _get_current_time()
    elif name == "knowledge_lookup":
        return _knowledge_lookup(input_data.get("query", ""))

    if db:
        return _execute_plugin(name, input_data, db)

    return f"Unknown tool: {name}"


def _execute_plugin(name: str, input_data: dict, db: Session) -> str:
    from models import Plugin
    plugin = db.query(Plugin).filter(Plugin.name == name, Plugin.is_active == True).first()
    if not plugin:
        return f"Unknown tool: {name}"
    try:
        headers = {"Content-Type": "application/json"}
        if plugin.headers_json:
            extra = json.loads(plugin.headers_json)
            headers.update(extra)

        if plugin.method.upper() == "GET":
            resp = httpx.get(plugin.url, params=input_data, headers=headers, timeout=15)
        else:
            resp = httpx.post(plugin.url, json=input_data, headers=headers, timeout=15)

        logger.info(f"Plugin {name} -> {resp.status_code}")
        return resp.text[:2000]
    except Exception as e:
        logger.error(f"Plugin {name} failed: {e}")
        return f"Plugin error: {e}"


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
